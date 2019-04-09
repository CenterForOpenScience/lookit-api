from django.conf.urls import include, url
from rest_framework_nested import routers

from api import views as api_views

router = routers.DefaultRouter()
router.register(r"users", api_views.UserViewSet)
router.register(r"studies", api_views.StudyViewSet)
router.register(r"demographics", api_views.DemographicDataViewSet)
router.register(r"children", api_views.ChildViewSet)
router.register(r"responses", api_views.ResponseViewSet)
router.register(r"organizations", api_views.OrganizationViewSet)
router.register(r"feedback", api_views.FeedbackViewSet)

user_router = routers.NestedSimpleRouter(router, r"users", lookup="user")
user_router.register(
    r"demographics", api_views.DemographicDataViewSet, basename="user-demographics"
)
user_router.register(r"children", api_views.ChildViewSet, basename="user-children")

study_router = routers.NestedSimpleRouter(router, r"studies", lookup="study")
study_router.register(
    r"responses", api_views.ResponseViewSet, basename="study-responses"
)

child_router = routers.NestedSimpleRouter(router, r"children", lookup="child")

response_router = routers.NestedSimpleRouter(router, r"responses", lookup="response")

feedback_router = routers.NestedSimpleRouter(router, r"feedback", lookup="feedback")

urlpatterns = [
    url(r"^(?P<version>(v1|v2))/", include(user_router.urls)),
    url(r"^(?P<version>(v1|v2))/", include(study_router.urls)),
    url(r"^(?P<version>(v1|v2))/", include(child_router.urls)),
    url(r"^(?P<version>(v1|v2))/", include(response_router.urls)),
    url(r"^(?P<version>(v1|v2))/", include(feedback_router.urls)),
    url(r"^(?P<version>(v1|v2))/", include(router.urls)),
]
