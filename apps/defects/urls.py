from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DefectViewSet, ReleaseConclusionViewSet,
    RequirementCoverageView, QualityGateView,
)

router = DefaultRouter()
router.register(r'defects', DefectViewSet, basename='defects')
router.register(r'release-conclusions', ReleaseConclusionViewSet, basename='release-conclusions')

urlpatterns = [
    path('', include(router.urls)),
    path('requirement-coverage/', RequirementCoverageView.as_view()),
    path('quality-gate/', QualityGateView.as_view()),
]
