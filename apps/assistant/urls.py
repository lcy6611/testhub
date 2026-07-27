from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssistantSessionViewSet, ChatViewSet, assistant_view
from .views_config import DifyConfigViewSet
from .agent_views import agent_chat
from .views_hermes import HermesConversationViewSet, HermesAgentConfigViewSet, upload_hermes_image

router = DefaultRouter()
router.register(r'sessions', AssistantSessionViewSet, basename='assistant-sessions')
router.register(r'chat', ChatViewSet, basename='chat')
router.register(r'config/dify', DifyConfigViewSet, basename='dify-config')
router.register(r'hermes/conversations', HermesConversationViewSet, basename='hermes-conversations')
router.register(r'hermes/config', HermesAgentConfigViewSet, basename='hermes-config')

urlpatterns = [
    path('', include(router.urls)),
    path('view/', assistant_view, name='assistant-view'),
    path('agent/chat/', agent_chat, name='agent-chat'),
    path('hermes/upload-image/', upload_hermes_image, name='hermes-upload-image'),
]