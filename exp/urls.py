"""project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Import the include() function: from django.conf.urls import url, include
    3. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import url
from django.views.decorators.csrf import csrf_exempt

from exp.views import (
    ExperimenterDashboardView,
    ParticipantDetailView,
    ParticipantListView,
    PreviewProxyView,
    RenameVideoView,
    ResearcherDetailView,
    ResearcherListView,
    StudyAttachments,
    StudyBuildView,
    StudyChildrenSummaryCSV,
    StudyChildrenSummaryDictCSV,
    StudyCollisionCheck,
    StudyCreateView,
    StudyDemographics,
    StudyDemographicsDownloadCSV,
    StudyDemographicsDownloadDictCSV,
    StudyDemographicsDownloadJSON,
    StudyDetailView,
    StudyListView,
    StudyParticipantAnalyticsView,
    StudyParticipantContactView,
    StudyPreviewDetailView,
    StudyResponsesAll,
    StudyResponsesAllDownloadJSON,
    StudyResponsesConsentManager,
    StudyResponsesFrameDataCSV,
    StudyResponsesFrameDataDictCSV,
    StudyResponsesFrameDataIndividualCSV,
    StudyResponsesList,
    StudyResponsesSummaryDictCSV,
    StudyResponsesSummaryDownloadCSV,
    StudyUpdateView,
)

app_name = "exp"

urlpatterns = [
    url(r"researchers/$", ResearcherListView.as_view(), name="researcher-list"),
    url(
        r"researchers/(?P<pk>\d+)/$",
        ResearcherDetailView.as_view(),
        name="researcher-detail",
    ),
    url(r"participants/$", ParticipantListView.as_view(), name="participant-list"),
    url(
        r"participants/(?P<pk>\d+)/$",
        ParticipantDetailView.as_view(),
        name="participant-detail",
    ),
    url(r"renamevideo/$", csrf_exempt(RenameVideoView.as_view()), name="rename-video"),
    url(r"studies/$", StudyListView.as_view(), name="study-list"),
    url(
        r"studies/analytics/$",
        StudyParticipantAnalyticsView.as_view(),
        name="study-participant-analytics",
    ),
    url(r"studies/create/$", StudyCreateView.as_view(), name="study-create"),
    url(r"studies/(?P<pk>\d+)/$", StudyDetailView.as_view(), name="study-detail"),
    url(
        r"studies/(?P<pk>\d+)/contact/$",
        StudyParticipantContactView.as_view(),
        name="study-participant-contact",
    ),
    url(r"studies/(?P<pk>\d+)/edit/$", StudyUpdateView.as_view(), name="study-edit"),
    url(
        r"studies/(?P<pk>\d+)/responses/$",
        StudyResponsesList.as_view(),
        name="study-responses-list",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/all/$",
        StudyResponsesAll.as_view(),
        name="study-responses-all",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/consent_videos/$",
        StudyResponsesConsentManager.as_view(),
        name="study-responses-consent-manager",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/all/download_json/$",
        StudyResponsesAllDownloadJSON.as_view(),
        name="study-responses-download-json",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/all/download_summary_csv/$",
        StudyResponsesSummaryDownloadCSV.as_view(),
        name="study-responses-download-csv",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/all/download_summary_dict_csv/$",
        StudyResponsesSummaryDictCSV.as_view(),
        name="study-responses-download-summary-dict-csv",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/all/download_summary_children_csv/$",
        StudyChildrenSummaryCSV.as_view(),
        name="study-responses-children-summary-csv",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/all/download_summary_children_dict_csv/$",
        StudyChildrenSummaryDictCSV.as_view(),
        name="study-responses-children-summary-dict-csv",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/all/collision_check/$",
        StudyCollisionCheck.as_view(),
        name="study-hashed-id-collision-check",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/all/download_frame_csv/$",
        StudyResponsesFrameDataCSV.as_view(),
        name="study-responses-download-frame-data-csv",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/all/download_frame_zip_csv/$",
        StudyResponsesFrameDataIndividualCSV.as_view(),
        name="study-responses-download-frame-data-zip-csv",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/all/download_frame_dict_csv/$",
        StudyResponsesFrameDataDictCSV.as_view(),
        name="study-responses-download-frame-data-dict-csv",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/demographics/$",
        StudyDemographics.as_view(),
        name="study-demographics",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/demographics/download_json/$",
        StudyDemographicsDownloadJSON.as_view(),
        name="study-demographics-download-json",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/demographics/download_csv/$",
        StudyDemographicsDownloadCSV.as_view(),
        name="study-demographics-download-csv",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/demographics/download_csv_dict/$",
        StudyDemographicsDownloadDictCSV.as_view(),
        name="study-demographics-download-dict-csv",
    ),
    url(
        r"studies/(?P<pk>\d+)/responses/attachments/$",
        StudyAttachments.as_view(),
        name="study-attachments",
    ),
    url(
        r"studies/(?P<uuid>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89ab][0-9a-fA-F]{3}-[0-9a-fA-F]{12})/build/$",
        StudyBuildView.as_view(),
        name="study-build",
    ),
    url(
        r"studies/(?P<uuid>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89ab][0-9a-fA-F]{3}-[0-9a-fA-F]{12})/preview-detail/$",
        StudyPreviewDetailView.as_view(),
        name="preview-detail",
    ),
    url(
        r"studies/(?P<uuid>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89ab][0-9a-fA-F]{3}-[0-9a-fA-F]{12})/(?P<child_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89ab][0-9a-fA-F]{3}-[0-9a-fA-F]{12})/preview/$",
        PreviewProxyView.as_view(),
        name="preview-proxy",
    ),
    url(r"", ExperimenterDashboardView.as_view(), name="dashboard"),
]
