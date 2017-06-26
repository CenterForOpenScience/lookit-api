import operator
from functools import reduce

from django.http import HttpResponseRedirect
from django.shortcuts import reverse
from django.views import generic
from django.db.models import Q
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from guardian.mixins import LoginRequiredMixin
from guardian.shortcuts import get_objects_for_user, get_perms

from studies.forms import StudyForm
from studies.models import Study


class StudyCreateView(LoginRequiredMixin, generic.CreateView):
    '''
    StudyCreateView allows a user to create a study and then redirects
    them to the detail view for that study.
    '''
    fields = ('name', 'organization', 'blocks', )
    model = Study

    def get_form_class(self):
        return StudyForm

    def get_success_url(self):
        return reverse('exp:study-detail', kwargs=dict(pk=self.object.id))


class StudyListView(LoginRequiredMixin, generic.ListView):
    '''
    StudyListView shows a list of studies that a user has permission to.
    '''
    model = Study
    template_name = 'studies/study_list.html'

    def get_queryset(self, *args, **kwargs):
        request = self.request.GET
        queryset = get_objects_for_user(self.request.user, 'studies.can_view')

        state = request.get('state')
        if state and state != 'all':
            if state == 'myStudies':
                queryset = queryset.filter(creator=self.request.user)
            else:
                queryset = queryset.filter(state=state)

        match = request.get('match')
        if match:
            queryset = queryset.filter(reduce(operator.or_,
              (Q(name__icontains=term) | Q(short_description__icontains=term) for term in match.split())))

        sort = request.get('sort')
        if sort:
            if 'name' in sort:
                queryset = queryset.order_by(sort)
            elif 'beginDate' in sort:
                # TODO optimize using subquery
                queryset = sorted(queryset, key=lambda t: t.begin_date or timezone.now(), reverse=True if '-' in sort else False)
            elif 'endDate' in sort:
                # TODO optimize using subquery
                queryset = sorted(queryset, key=lambda t: t.end_date or timezone.now(), reverse=True if '-' in sort else False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['state'] = self.request.GET.get('state', 'all')
        context['match'] = self.request.GET.get('match') or ''
        context['sort'] = self.request.GET.get('sort') or ''
        return context


class StudyDetailView(LoginRequiredMixin, generic.DetailView):
    '''
    StudyDetailView shows information about a study.
    '''
    template_name = 'studies/study_detail.html'
    model = Study

    def get_permitted_triggers(self, triggers):
        permitted_triggers = []
        organization_permissions = get_perms(self.request.user, self.object.organization)

        admin_triggers = ['reject', 'approve']

        for trigger in triggers:
            # remove autogenerated triggers
            if trigger.startswith('to_'):
                continue
            # remove triggers that people don't have permission to
            if not self.request.user.is_superuser or (trigger in admin_triggers and 'is_admin' not in organization_permissions):
                continue

            permitted_triggers.append(trigger)

        return permitted_triggers

    def post(self, *args, **kwargs):
        trigger = self.request.POST.get('trigger')
        object = self.get_object()
        if trigger:
            if hasattr(object, trigger):
                # transition through workflow state
                getattr(object, trigger)(user=self.request.user)
        if 'comments-text' in self.request.POST.keys():
            object.comments = self.request.POST['comments-text']
            object.save()
        return HttpResponseRedirect(reverse('exp:study-detail', kwargs=dict(pk=object.pk)))

    def study_logs(self):
        ''' Returns a page object with 10 study logs'''
        logs_list = self.object.logs.all()
        paginator = Paginator(logs_list, 10)
        page = self.request.GET.get('logs_page')
        try:
            logs = paginator.page(page)
        except PageNotAnInteger:
            logs = paginator.page(1)
        except EmptyPage:
            logs = paginator.page(paginator.num_pages)
        return logs

    def get_context_data(self, **kwargs):
        context = super(StudyDetailView, self).get_context_data(**kwargs)
        context['triggers'] = self.get_permitted_triggers(
            self.object.machine.get_triggers(self.object.state))
        context['logs'] = self.study_logs()
        return context
