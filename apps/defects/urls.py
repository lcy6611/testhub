from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DefectViewSet, DefectAttachmentViewSet, ReleaseConclusionViewSet,
    DefectCommentViewSet, DefectTransitionLogViewSet,
    RequirementCoverageView, QualityGateView,
)

router = DefaultRouter()
router.register(r'defects', DefectViewSet, basename='defects')
router.register(r'defect-attachments', DefectAttachmentViewSet, basename='defect-attachments')
router.register(r'defect-comments', DefectCommentViewSet, basename='defect-comments')
router.register(r'defect-transitions', DefectTransitionLogViewSet, basename='defect-transitions')
router.register(r'release-conclusions', ReleaseConclusionViewSet, basename='release-conclusions')

urlpatterns = [
    path('', include(router.urls)),
    path('requirement-coverage/', RequirementCoverageView.as_view()),
    path('quality-gate/', QualityGateView.as_view()),
]
