from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.scheduler.views import ScheduleOverviewViewSet

router = DefaultRouter()
router.register(r'overview', ScheduleOverviewViewSet, basename='scheduler-overview')

urlpatterns = [
    path('', include(router.urls)),
]
