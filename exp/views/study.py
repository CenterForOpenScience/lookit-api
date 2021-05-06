import json
import operator
from functools import reduce
from typing import NamedTuple

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, reverse
from django.views import generic
from django.views.generic.detail import SingleObjectMixin
from revproxy.views import ProxyView

from accounts.models import Child, User
from exp.mixins.paginator_mixin import PaginatorMixin
from exp.views.mixins import (
    ExperimenterLoginRequiredMixin,
    SingleObjectFetchProtocol,
    StudyTypeMixin,
)
from project import settings
from studies.forms import StudyCreateForm, StudyEditForm
from studies.helpers import send_mail
from studies.models import Study, StudyType, Lab
from studies.permissions import LabPermission, StudyPermission
from studies.queries import get_study_list_qs
from studies.tasks import ember_build_and_gcp_deploy
from studies.workflow import (
    COMMENTS_HELP_TEXT,
    STATE_UI_SIGNALS,
    STATUS_HELP_TEXT,
    TRANSITION_HELP_TEXT,
    TRANSITION_LABELS,
)


class DiscoverabilityKey(NamedTuple):
    """Key to a small truth table for help text."""

    active: bool
    public: bool


STUDY_LISTING_A_TAG = (
    f'<a href="{settings.BASE_URL}/studies/">the study listing page</a>'
)

DISCOVERABILITY_HELP_TEXT = {
    (
        True,
        True,
    ): "Public. Your study is active and public. Participants can access it at your study link, "
    f"and it can be found listed in {STUDY_LISTING_A_TAG}.",
    (
        True,
        False,
    ): "Private. Your study is active, but not public. Participants may access it at your study link, "
    f"however will not be listed in {STUDY_LISTING_A_TAG}.",
    (
        False,
        True,
    ): "Public. Your study is not currently active, but it is public. When it is active, participants will be able to access it at your study link, "
    f"and it will be found listed in {STUDY_LISTING_A_TAG}. ",
    (
        False,
        False,
    ): "Private. Your study is not currently active, and is not public. When it is active, participants will be able to access it at your study link, "
    f"but it will not be listed in {STUDY_LISTING_A_TAG}. ",
}


def get_discoverability_text(study):
    """Helper function for getting discoverability text."""
    discoverability_key = DiscoverabilityKey(
        active=study.state == "active", public=study.public
    )
    return DISCOVERABILITY_HELP_TEXT.get(discoverability_key)


KEY_DISPLAY_NAMES = {
    "player_repo_url": "Experiment runner code URL",
    "last_known_player_sha": "Experiment runner version (commit SHA)",
}


class StudyCreateView(
    ExperimenterLoginRequiredMixin,
    UserPassesTestMixin,
    StudyTypeMixin,
    generic.CreateView,
):
    """
    StudyCreateView allows a user to create a study and then redirects
    them to the detail view for that study.
    """

    model = Study
    raise_exception = True
    form_class = StudyCreateForm

    def user_can_make_study(self):
        # If returning False,
        # should effectively delegate to the correct handler by way of
        # View.dispatch()
        return self.request.user.is_researcher and self.request.user.can_create_study()

    # Make PyCharm happy - otherwise we'd just override get_test_func()
    test_func = user_can_make_study

    def form_valid(self, form):
        """
        Add the logged-in user as the study creator. If the form is valid,
        save the associated study and redirect to the supplied URL
        """
        user = self.request.user
        target_study_type_id = self.request.POST["study_type"]
        target_study_type = StudyType.objects.get(id=target_study_type_id)
        form.instance.metadata = self.extract_type_metadata(target_study_type)
        form.instance.creator = user
        # Add user to admin group for study.
        new_study = self.object = form.save()
        new_study.admin_group.user_set.add(user)
        new_study.save()
        # Adds success message that study has been created.
        messages.success(self.request, f"{self.object.name} created.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("exp:study-detail", kwargs=dict(pk=self.object.id))

    def get_context_data(self, **kwargs):
        """
        Adds study types to get_context_data
        """
        context = super().get_context_data(**kwargs)
        context["types"] = [
            study_type["metadata"]["fields"]
            for study_type in StudyType.objects.all().values_list(
                "configuration", flat=True
            )
        ]
        context["key_display_names"] = KEY_DISPLAY_NAMES
        return context

    def get_initial(self):
        """
        Returns initial data to use for the create study form - make default
        structure field data an empty dict
        """
        initial = super().get_initial()
        initial["structure"] = json.dumps(Study._meta.get_field("structure").default())
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


class StudyUpdateView(
    ExperimenterLoginRequiredMixin,
    UserPassesTestMixin,
    StudyTypeMixin,
    SingleObjectFetchProtocol[Study],
    generic.UpdateView,
):
    """
    StudyUpdateView allows user to edit study metadata, add researchers to study, update researcher permissions, and delete researchers from study.
    Also allows you to update the study status.
    """

    model = Study
    template_name = "studies/study_edit.html"
    form_class = StudyEditForm
    raise_exception = True

    def user_can_edit_study(self):
        """Test predicate for the study editing view.

        Returns:
            True if this user can edit this Study, False otherwise

        """
        user: User = self.request.user  # Weird that PyCharm can't figure out the type?
        study = self.get_object()

        return user.is_researcher and user.has_study_perms(
            StudyPermission.WRITE_STUDY_DETAILS, study
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    # Make PyCharm happy - otherwise we'd just override
    # UserPassesTestMixin.get_test_func()
    test_func = user_can_edit_study

    def get_initial(self):
        """Get initial data for the study update form.

        Provides the exact_text stored in the structure field as the initial
        value to edit, to preserve ordering and formatting from user's standpoint.

        Provides the initial value of the generator function if current value is empty.

        Returns:
            A dictionary containing initial data for the form

        """
        initial = super().get_initial()
        # For editing, display the exact text that was used to generate the structure,
        # if available. We rely on form validation to make sure structure["exact_text"]
        # is valid JSON.
        structure = self.object.structure
        if structure:
            if "exact_text" in structure:
                initial["structure"] = structure["exact_text"]
            else:
                initial["structure"] = json.dumps(structure)
        if not self.object.generator.strip():
            initial["generator"] = StudyEditForm.base_fields["generator"].initial
        return initial

    def post(self, request, *args, **kwargs):
        """
        Handles updating study metadata like name, short_description, etc.
        """
        study = self.get_object()

        # TODO: why is this not in the form's clean function?
        target_study_type_id = int(self.request.POST["study_type"])
        target_study_type = StudyType.objects.get(id=target_study_type_id)

        metadata, meta_errors = self.validate_and_fetch_metadata(
            study_type=target_study_type
        )

        if meta_errors:
            messages.error(
                self.request,
                f"WARNING: Experiment runner version not saved: {meta_errors}",
            )
        else:
            # Check that study type hasn't changed.
            if not (
                study.study_type_id == target_study_type_id
                and metadata == study.metadata
            ):
                # Invalidate the previous build
                study.built = False
                # May still be building, but we're now good to allow another build
                study.is_building = False
            study.metadata = metadata
            study.study_type_id = target_study_type_id
            study.save()

            return super().post(request, *args, **kwargs)

        return HttpResponseRedirect(reverse("exp:study-edit", kwargs=dict(pk=study.pk)))

    def form_valid(self, form):
        """
        Add success message that edits to study have been saved.
        """
        ret = super().form_valid(form)
        messages.success(self.request, f"{self.get_object().name} study details saved.")
        return ret

    def get_context_data(self, **kwargs):
        """
        In addition to the study, adds several items to the context dictionary.
        """
        context = super().get_context_data(**kwargs)

        context["study_types"] = StudyType.objects.all()
        context["study_metadata"] = self.object.metadata
        context["key_display_names"] = KEY_DISPLAY_NAMES
        context["types"] = [
            exp_type.configuration["metadata"]["fields"]
            for exp_type in context["study_types"]
        ]
        context["save_confirmation"] = self.object.state in [
            "approved",
            "active",
            "paused",
            "deactivated",
        ]
        return context

    def get_success_url(self):
        return reverse("exp:study-edit", kwargs={"pk": self.object.id})


class StudyListView(
    ExperimenterLoginRequiredMixin, UserPassesTestMixin, generic.ListView
):
    """
    StudyListView shows a list of studies that a user has permission to.
    """

    model = Study
    raise_exception = True
    template_name = "studies/study_list.html"
    paginate_by = 10
    ordering = ("name",)

    def can_see_study_list(self):
        return self.request.user.is_researcher

    test_func = can_see_study_list

    def get_queryset(self, *args, **kwargs):
        """
        Returns paginated list of items for the StudyListView - handles filtering on state, match,
        and sort.
        """
        user = self.request.user
        query_dict = self.request.GET
        
        queryset = get_study_list_qs(user, query_dict)  # READ_STUDY_DETAILS permission

        return queryset

    def get_context_data(self, **kwargs):
        """
        Gets the context for the StudyListView and supplements with the state, match, and sort query params.
        """
        context = super().get_context_data(**kwargs)
        context["state"] = self.request.GET.get("state", "all")
        context["lab"] = self.request.GET.get("lab", "all")
        context["match"] = self.request.GET.get("match", "")
        context["sort"] = self.request.GET.get("sort", "name")
        context["page"] = self.request.GET.get("page", "1")
        context["can_create_study"] = self.request.user.can_create_study()
        context["user_labs"] = Lab.objects.filter(Q(id__in=self.request.user.labs.all()))
        return context


class StudyDetailView(
    ExperimenterLoginRequiredMixin,
    UserPassesTestMixin,
    PaginatorMixin,
    SingleObjectFetchProtocol[Study],
    generic.DetailView,
):
    """
    StudyDetailView shows information about a study. Can view basic metadata about a study,
    view study logs, manage study researchers, and change a study's state.
    """

    model = Study
    template_name = "studies/study_detail.html"
    raise_exception = True

    def user_can_see_or_edit_study_details(self):
        """Checks based on method, with fallback to umbrella lab perms.

        Returns:
            A boolean indicating whether or not the user should be able to see
            this view.
        """
        user = self.request.user
        method = self.request.method
        study = self.get_object()

        if not user.is_researcher:
            return False

        if method == "GET":
            return user.has_study_perms(StudyPermission.READ_STUDY_DETAILS, study)
        # TODO: this is very goofy, will make more sense in separate views
        elif method == "POST":
            if (
                "add_user" in self.request.POST
                or "remove_user" in self.request.POST
                or self.request.POST.get("name") == "update_user"
            ):
                return user.has_study_perms(
                    StudyPermission.MANAGE_STUDY_RESEARCHERS, study
                )
            if "trigger" in self.request.POST:
                return user.has_study_perms(StudyPermission.CHANGE_STUDY_STATUS, study)
            if "clone_study" in self.request.POST:
                return user.can_create_study()
        else:
            # If we're not one of the two allowed methods this should be caught
            # earlier
            return False

    # Make PyCharm happy - otherwise we'd just override
    # UserPassesTestMixin.get_test_func()
    test_func = user_can_see_or_edit_study_details

    def post(self, *args, **kwargs):
        """
        Post method can:
         - update the trigger if the state of the study has changed
         - clone study and redirect to the clone
         - add, remove, or update permissions for a researcher
        TODO: these should be broken out into three separate views!
        """
        # Manage researchers case
        if (
            "add_user" in self.request.POST
            or "remove_user" in self.request.POST
            or self.request.POST.get("name") == "update_user"
        ):

            try:
                self.manage_researcher_permissions()
                HttpResponseRedirect(
                    reverse("exp:study-detail", kwargs=dict(pk=self.get_object().pk))
                )
            except AssertionError:
                return HttpResponseForbidden()
        # Change study status case
        if "trigger" in self.request.POST:
            try:
                update_trigger(self)
            except Exception as e:
                messages.error(self.request, f"TRANSITION ERROR: {e}")
                return HttpResponseRedirect(
                    reverse("exp:study-detail", kwargs=dict(pk=self.get_object().pk))
                )
        # Clone study case
        if self.request.POST.get("clone_study"):
            orig_study = self.get_object()
            clone = orig_study.clone()
            clone.creator = self.request.user
            # Clone within the current lab if user is allowed to. Otherwise, choose the first possible
            if self.request.user.has_perm(
                LabPermission.CREATE_LAB_ASSOCIATED_STUDY.codename, obj=orig_study.lab
            ):
                clone.lab = orig_study.lab
            else:
                for lab in self.request.user.labs.only("id"):
                    if clone.creator.has_perm(
                        LabPermission.CREATE_LAB_ASSOCIATED_STUDY.codename, obj=lab
                    ):
                        clone.lab = lab
                        break
                else:
                    # Shouldn't end up here because we checked can_create_study, but just in case
                    return HttpResponseForbidden()
            clone.study_type = orig_study.study_type
            clone.built = False
            clone.is_building = False
            clone.save()
            # Adds success message when study is cloned
            messages.success(self.request, f"{orig_study.name} copied.")
            self.add_creator_to_study_admin_group(clone)
            return HttpResponseRedirect(
                reverse("exp:study-edit", kwargs=dict(pk=clone.pk))
            )

        return HttpResponseRedirect(
            reverse("exp:study-detail", kwargs=dict(pk=self.get_object().pk))
        )

    def manage_researcher_permissions(self):
        """
        Handles adding, updating, and deleting researcher from study. Users are
        added to study read group by default.
        """
        change_requester = self.request.user
        study = self.get_object()
        study_admin_group = study.admin_group
        id_of_user_to_add = self.request.POST.get("add_user")
        id_of_user_to_remove = self.request.POST.get("remove_user")

        roles_to_groups = {
            "study_preview": study.preview_group,
            "study_design": study.design_group,
            "study_analysis": study.analysis_group,
            "study_submission_processor": study.submission_processor_group,
            "study_researcher": study.researcher_group,
            "study_manager": study.manager_group,
            "study_admin": study.admin_group,
        }

        if self.request.POST.get("name") == "update_user":
            id_of_user_to_update = self.request.POST.get("pk")
            name_of_role_to_enable = self.request.POST.get("value")

            if id_of_user_to_update:
                user_to_update = User.objects.get(pk=id_of_user_to_update)
                if name_of_role_to_enable in roles_to_groups:
                    # Enforce not changing a current admin unless there's another admin
                    if study_admin_group in user_to_update.groups.all():
                        if study_admin_group.user_set.count() <= 1:
                            messages.error(
                                self.request,
                                "Could not change permissions for this researcher. There must be at least one study admin.",
                                extra_tags="user_removed",
                            )
                        assert study_admin_group.user_set.count() > 1
                    for gr in study.all_study_groups():
                        gr.user_set.remove(user_to_update)
                    user_to_update.groups.add(roles_to_groups[name_of_role_to_enable])
                    self.send_study_email(
                        user_to_update, name_of_role_to_enable
                    )  # TODO: format role name for email
        if id_of_user_to_add:
            # Adds user to study read by default
            user_to_add = User.objects.get(pk=id_of_user_to_add)
            user_to_add.groups.add(study.preview_group)
            messages.success(
                self.request,
                f"{user_to_add.get_short_name()} given {study.name} Preview Permissions.",
                extra_tags="user_added",
            )
            self.send_study_email(user_to_add, "study_preview")
        if id_of_user_to_remove:
            # Removes user from both study read and study admin groups
            user_to_remove = User.objects.get(pk=id_of_user_to_remove)
            if (
                study_admin_group in user_to_remove.groups.all()
                and study_admin_group.user_set.count() <= 1
            ):
                messages.error(
                    self.request,
                    "Could not delete this researcher. There must be at least one study admin.",
                    extra_tags="user_removed",
                )
                return
            for gr in study.all_study_groups():
                gr.user_set.remove(user_to_remove)
            messages.success(
                self.request,
                f"{user_to_remove.get_short_name()} removed from {study.name}.",
                extra_tags="user_removed",
            )

    def send_study_email(self, user, permission):
        study = self.get_object()
        context = {
            "permission": permission,
            "study_name": study.name,
            "study_id": study.id,
            "lab_name": study.lab.name,
            "researcher_name": user.get_short_name(),
        }
        send_mail.delay(
            "notify_researcher_of_study_permissions",
            f"New access granted for study {self.get_object().name}",
            user.username,
            from_email=study.lab.contact_email,
            **context,
        )

    def add_creator_to_study_admin_group(self, clone):
        """
        Add the study's creator to the clone's study admin group.
        """
        user = self.request.user
        study_admin_group = clone.admin_group
        user.groups.add(study_admin_group)
        return study_admin_group

    @property
    def study_logs(self):
        """ Returns a page object with 10 study logs"""
        logs_list = self.object.logs.select_related("user").order_by("-created_at")
        page = self.request.GET.get("page")
        return self.paginated_queryset(logs_list, page, 10)

    def get_context_data(self, **kwargs):
        """
        Adds several items to the context dictionary - the study, applicable triggers for the study,
        paginated study logs, and a tooltip that is dependent on the study's current state
        """
        context = super(StudyDetailView, self).get_context_data(**kwargs)

        study = context["study"]
        admin_group = study.admin_group

        context["triggers"] = get_permitted_triggers(
            self, self.object.machine.get_triggers(self.object.state)
        )
        context["logs"] = self.study_logs
        state = context["state"] = self.object.state
        context["status_tooltip"] = STATUS_HELP_TEXT.get(state, state)
        context["current_researchers"] = self.get_annotated_study_researchers()
        context["users_result"] = self.search_researchers()
        context["build_ui_tag"] = "success" if study.built else "warning"
        context["state_ui_tag"] = STATE_UI_SIGNALS.get(study.state, "info")
        context["search_query"] = self.request.GET.get("match")
        context["name"] = self.request.GET.get("match", None)
        context["multiple_admins"] = (
            len(User.objects.filter(groups__name=admin_group.name)) > 1
        )
        context["study_admins"] = User.objects.filter(
            groups__name=admin_group.name
        ).values_list("id", flat=True)
        context["discoverability_text"] = get_discoverability_text(study)
        context["comments_help"] = json.dumps(COMMENTS_HELP_TEXT)
        context["transition_help"] = json.dumps(TRANSITION_HELP_TEXT)
        context["triggers_with_labels"] = [
            {"name": trigger, "label": TRANSITION_LABELS[trigger]}
            for trigger in context["triggers"]
        ]
        context["can_change_status"] = self.request.user.has_study_perms(
            StudyPermission.CHANGE_STUDY_STATUS, study
        )
        context["can_manage_researchers"] = self.request.user.has_study_perms(
            StudyPermission.MANAGE_STUDY_RESEARCHERS, study
        )
        context["can_create_study"] = self.request.user.can_create_study()
        # Since get_obj_perms template tag doesn't collect study + lab perms
        context["study_perms"] = self.request.user.perms_for_study(study)
        return context

    def get_study_researchers(self):
        """Pulls researchers that belong to any study access groups for displaying/managing that access

        Not showing Lab admin & Lab read in this list (even though they technically can view the project)
        """
        study = self.get_object()
        all_study_users = reduce(
            lambda x, y: (x | y),
            [group.user_set.all() for group in study.all_study_groups()],
            User.objects.none(),
        )
        return all_study_users

    def get_annotated_study_researchers(self):
        """Gets current study researchers and their highest-level study-specific perm descriptions"""
        study = self.get_object()
        study_researchers = self.get_study_researchers()
        return [
            {"current_group": study.get_group_of_researcher(user), "user": user}
            for user in study_researchers
        ]

    def search_researchers(self):
        """Searches user first, last, and middle names for search query.
        Does not display researchers that are already on project.
        """
        current_researcher_ids = self.get_study_researchers().values_list(
            "id", flat=True
        )
        user_queryset = User.objects.filter(lab=self.get_object().lab, is_active=True)
        search_query = self.request.GET.get("match", None)
        if search_query:
            user_queryset = user_queryset.filter(
                reduce(
                    operator.or_,
                    (
                        Q(family_name__icontains=term)
                        | Q(given_name__icontains=term)
                        | Q(middle_name__icontains=term)
                        for term in search_query.split()
                    ),
                )
            )
        researchers_result = (
            user_queryset.exclude(id__in=current_researcher_ids)
            .distinct()
            .order_by(Lower("family_name").asc())
        )

        return self.build_researchers_paginator(researchers_result)

    def build_researchers_paginator(self, researchers_result):
        """Builds paginated search results for researchers."""
        page = self.request.GET.get("page")
        return self.paginated_queryset(researchers_result, page, 10)


class StudyBuildView(
    ExperimenterLoginRequiredMixin,
    UserPassesTestMixin,
    SingleObjectFetchProtocol[Study],
    SingleObjectMixin,
    generic.RedirectView,
):
    """
    Checks to make sure an existing build isn't running, that the user has permissions
    to build, and then triggers a build.
    """

    model = Study
    http_method_names = ["post"]
    slug_url_kwarg = "uuid"
    slug_field = "uuid"

    def get_redirect_url(self, *args, **kwargs):
        return reverse("exp:study-detail", kwargs={"pk": str(self.get_object().pk)})

    def user_can_build_study(self):
        user = self.request.user
        study = self.get_object()
        if study.built or study.is_building:
            messages.warning(
                self.request,
                f"Experiment runner for {study.name} is already built or in progress. This may take up to 30 minutes. You will be emailed when it's completed.",
            )
            return False
        return user.is_researcher and user.has_study_perms(
            StudyPermission.WRITE_STUDY_DETAILS, study
        )

    test_func = user_can_build_study

    def post(self, request, *args, **kwargs):
        study = self.get_object()
        study.is_building = True
        study.save(update_fields=["is_building"])
        ember_build_and_gcp_deploy.delay(study.uuid, self.request.user.uuid)
        messages.success(
            request,
            f"Scheduled experiment runner build for {study.name}. You will be emailed when it's completed. This may take up to 30 minutes.",
        )
        return super().post(request, *args, **kwargs)


class StudyPreviewDetailView(
    ExperimenterLoginRequiredMixin,
    UserPassesTestMixin,
    SingleObjectFetchProtocol[Study],
    generic.DetailView,
):

    queryset = Study.objects.all()
    http_method_names = ["get", "post"]
    raise_exception = True
    template_name = "../../web/templates/web/study-detail.html"

    def can_preview(self):
        user = self.request.user
        study = self.get_object()
        # Relevant permission in order to preview is READ_STUDY_DETAILS (previewing is essentially
        # examining the study protocol configuration), rather than READY_STUDY_PREVIEW_DATA
        # (which has to do with accessing data from other preview sessions)
        return user.is_researcher and (
            user.has_study_perms(StudyPermission.READ_STUDY_DETAILS, study)
            or (study.shared_preview and user.is_researcher)
        )

    test_func = can_preview

    def get_object(self, queryset=None):
        """
        Needed because view expecting pk or slug, but url has UUID. Looks up
        study by uuid.
        """
        uuid = self.kwargs.get("uuid")
        return get_object_or_404(Study, uuid=uuid)

    def get_context_data(self, **kwargs):
        """If user is authenticated, add demographic, children, and response data.

        Note: mostly copied from StudyDetailView in web/ until we can find the right
            abstraction for all this.
        """
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context["has_demographic"] = self.request.user.latest_demographics
            context["children"] = self.request.user.children.filter(deleted=False)
            context["preview_mode"] = True

        return context

    def post(self, request, *args, **kwargs):
        """POST override to act as GET would in RedirectView.

        TODO: No more POST masquerading as GET, rewrite the template and both the
            web and experimenter views to be more reasonably sane.
        """
        child_id = self.request.POST.get("child_id")
        kwargs["child_id"] = child_id
        return HttpResponseRedirect(reverse("exp:preview-proxy", kwargs=kwargs))


class PreviewProxyView(ExperimenterLoginRequiredMixin, UserPassesTestMixin, ProxyView):
    """
    Proxy view to forward researcher to preview page in the Ember app
    """

    # So we are definitely not doing PREVIEW_EXPERIMENT_BASE_URL anymore
    upstream = settings.EXPERIMENT_BASE_URL

    def user_can_view_previews(self):
        request = self.request
        kwargs = self.kwargs
        user = request.user

        if not user.is_researcher:
            return False

        try:
            child = Child.objects.get(uuid=kwargs.get("child_id", None))
        except Child.DoesNotExist:
            return False

        try:
            study = Study.objects.get(uuid=kwargs.get("uuid", None))
        except Study.DoesNotExist:
            return False

        if child.user != request.user:
            # requesting user doesn't belong to that child
            return False

        # Relevant permission in order to preview is READ_STUDY_DETAILS (previewing is essentially
        # examining the study protocol configuration), rather than READY_STUDY_PREVIEW_DATA
        # (which has to do with accessing data from other preview sessions)
        return (study.shared_preview and user.is_researcher) or user.has_study_perms(
            StudyPermission.READ_STUDY_DETAILS, study
        )

    test_func = user_can_view_previews

    def dispatch(self, request, *args, **kwargs):
        """Override to fix argument signature mismatch w.r.t. ProxyView.

        Also, the redirect functionality in revproxy is broken so we have to patch
        path replacement manually. Great! Just wonderful.
        """

        _, _, _, study_uuid, _, _, _, *rest = request.path.split("/")
        path = f"{study_uuid}/{'/'.join(rest)}"
        if not rest:
            path += "index.html"
        path = f"{kwargs['uuid']}/index.html"

        return super().dispatch(request, path)


# UTILITY FUNCTIONS
def get_permitted_triggers(view_instance, triggers):
    """Takes in the available triggers (next possible states) for a study and restricts that list
    based on the current user's permissions and whether the lab has been approved.
    The view_instance is the StudyDetailView or the StudyUpdateView.
    """
    permitted_triggers = []
    user = view_instance.request.user
    study = view_instance.object
    lab_approved = study.lab.approved_to_test
    can_change_status = user.has_study_perms(StudyPermission.CHANGE_STUDY_STATUS, study)

    admin_triggers = ["approve", "reject"]

    only_for_approved_labs_triggers = ["activate", "approve", "submit", "resubmit"]

    for trigger in triggers:
        # remove autogenerated triggers
        if trigger.startswith("to_"):
            continue

        if trigger in only_for_approved_labs_triggers and not lab_approved:
            continue

        if (
            not user.has_perm(StudyPermission.APPROVE_REJECT_STUDY.prefixed_codename)
        ) and (not can_change_status or (trigger in admin_triggers)):
            continue

        permitted_triggers.append(trigger)

    return permitted_triggers


def update_trigger(view_instance):
    """Transition to next state in study workflow.

    TODO: Comments text is a bit silly to have here - let's move it to the proper Edit
    View to be in the appropriate functional location once we do a refactor.

    :param view_instance: An instance of the django view.
    :type view_instance: StudyDetailView or StudyUpdateView
    """
    trigger = view_instance.request.POST.get("trigger")
    object = view_instance.get_object()
    if trigger:
        if hasattr(object, trigger):
            if "comments-text" in view_instance.request.POST.keys():
                object.comments = view_instance.request.POST["comments-text"]
                object.save()
            # transition through workflow state
            getattr(object, trigger)(user=view_instance.request.user)
    displayed_state = object.state if object.state != "active" else "activated"
    messages.success(view_instance.request, f"Study {object.name} {displayed_state}.")
    return object
