from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OpsEnvironmentViewSet,
    Text2SQLViewSet,
    LogQueryViewSet,
    FileTransferViewSet,
)

router = DefaultRouter()
router.register(r'environments', OpsEnvironmentViewSet, basename='opsenvironment')
router.register(r'text2sql', Text2SQLViewSet, basename='text2sqlrecord')
router.register(r'logs', LogQueryViewSet, basename='logquerysession')
router.register(r'files', FileTransferViewSet, basename='filetransfertask')

app_name = 'ops_tools'

urlpatterns = [
    path('', include(router.urls)),
]
