from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RequirementDocumentViewSet,
    RequirementAnalysisViewSet,
    BusinessRequirementViewSet,
    GeneratedTestCaseViewSet,
    AnalysisTaskViewSet,
    AIModelConfigViewSet,
    PromptConfigViewSet,
    GenerationConfigViewSet,
    TestCaseGenerationTaskViewSet,
    DifyKnowledgeBaseViewSet,
    ConfigStatusViewSet,
    TestCaseSkillViewSet,
    upload_and_analyze,
    analyze_text
)
from .kb_views import KbFunctionViewSet
from .kb_chat_views import KbChatSessionViewSet, KbChatViewSet

# 创建DRF路由器（与上游一致：直接挂到 requirement-analysis 下，无中间 api/）
router = DefaultRouter()
router.register(r'documents', RequirementDocumentViewSet, basename='requirementdocument')
router.register(r'analyses', RequirementAnalysisViewSet, basename='requirementanalysis')
router.register(r'requirements', BusinessRequirementViewSet, basename='businessrequirement')
router.register(r'test-cases', GeneratedTestCaseViewSet, basename='generatedtestcase')
router.register(r'tasks', AnalysisTaskViewSet, basename='analysistask')
router.register(r'ai-models', AIModelConfigViewSet, basename='aimodelconfig')
router.register(r'prompts', PromptConfigViewSet, basename='promptconfig')
router.register(r'generation-config', GenerationConfigViewSet, basename='generationconfig')
router.register(r'testcase-generation', TestCaseGenerationTaskViewSet, basename='testcasegenerationtask')
router.register(r'dify-knowledge-bases', DifyKnowledgeBaseViewSet, basename='difyknowledgebase')
router.register(r'kb-functions', KbFunctionViewSet, basename='kbfunction')
router.register(r'kb-chat/sessions', KbChatSessionViewSet, basename='kbchatsession')
router.register(r'kb-chat', KbChatViewSet, basename='kbchat')
router.register(r'config', ConfigStatusViewSet, basename='configstatus')
router.register(r'skills', TestCaseSkillViewSet, basename='testcaseskill')

app_name = 'requirement_analysis'

urlpatterns = [
    path('', include(router.urls)),
    path('upload-and-analyze/', upload_and_analyze, name='upload-and-analyze'),
    path('analyze-text/', analyze_text, name='analyze-text'),
    path('kb-hub/', include('apps.requirement_analysis.kb_hub.urls')),
]