from django.conf import settings

from storages.backends.gcloud import GoogleCloudStorage
from storages.utils import safe_join, clean_name


class LocationPrefixedPublicGoogleCloudStorage(GoogleCloudStorage):
    location = None

    def _normalize_name(self, name):
        if self.location:
            return super()._normalize_name(safe_join(self.location, name))
        return super()._normalize_name(name.lower())

    def url(self, name):
        """
        The parent implementation calls GoogleCloudStorage on every request
        once for oauth and again to get the file. Since we're proxying requests
        through nginx's proxy_pass to GoogleCloudStorage we don't need their url
        nonsense or to use the actual domain or bucket name.
        """
        name = self._normalize_name(clean_name(name))
        return f"/{name.lstrip('/')}"


class LowercaseNameMixin(GoogleCloudStorage):
    def _normalize_name(self, name):
        return super()._normalize_name(name.lower())


class LookitStaticStorage(LowercaseNameMixin, LocationPrefixedPublicGoogleCloudStorage):
    location = settings.STATICFILES_LOCATION


class LookitMediaStorage(LowercaseNameMixin, LocationPrefixedPublicGoogleCloudStorage):
    location = settings.MEDIAFILES_LOCATION


class LookitExperimentStorage(LocationPrefixedPublicGoogleCloudStorage):
    location = settings.EXPERIMENT_LOCATION


class LookitPreviewExperimentStorage(LocationPrefixedPublicGoogleCloudStorage):
    location = settings.PREVIEW_EXPERIMENT_LOCATION
