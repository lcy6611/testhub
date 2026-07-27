# -*- coding: utf-8 -*-
"""
Hermes 数字人会话与配置 API。
"""
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Q
from .models import HermesConversation, HermesMessage, HermesAgentConfig, HermesImage
from .serializers import (
    HermesConversationSerializer,
    HermesConversationCreateSerializer,
    HermesAgentConfigSerializer,
    HermesImageUploadSerializer,
    HermesImageSerializer,
)


class HermesConversationViewSet(viewsets.ModelViewSet):
    """Hermes 会话管理：列表、创建、删除、获取消息"""
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # 会话列表数量可控，关闭全局分页，直接返回数组

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return HermesConversationCreateSerializer
        return HermesConversationSerializer

    def get_queryset(self):
        user = self.request.user
        # 超级用户可查看所有会话；普通用户仅看自己
        if user.is_superuser:
            return HermesConversation.objects.all()
        return HermesConversation.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['delete'])
    def clear_messages(self, request, pk=None):
        """清空某会话的全部消息"""
        conversation = self.get_object()
        conversation.messages.all().delete()
        return Response({'detail': '会话已清空'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def update_title(self, request, pk=None):
        """更新会话标题"""
        conversation = self.get_object()
        title = (request.data.get('title') or '').strip()
        if title:
            conversation.title = title[:500]
            conversation.save(update_fields=['title', 'updated_at'])
        return Response(HermesConversationSerializer(conversation).data)


class HermesAgentConfigViewSet(viewsets.ModelViewSet):
    """Hermes 数字人全局配置"""
    serializer_class = HermesAgentConfigSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return HermesAgentConfig.objects.all()

    @action(detail=False, methods=['get'])
    def active(self, request):
        """返回当前启用的数字人配置"""
        config = HermesAgentConfig.get_active_config()
        if not config:
            return Response({'detail': '未配置'}, status=status.HTTP_404_NOT_FOUND)
        return Response(HermesAgentConfigSerializer(config).data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upload_hermes_image(request):
    """上传 Hermes 会话图片。需 conversation_id 参数。"""
    conversation_id = request.data.get('conversation_id') or request.query_params.get('conversation_id')
    conversation = None
    if conversation_id:
        conversation = HermesConversation.objects.filter(pk=conversation_id).first()
        if conversation and not request.user.is_superuser and conversation.user_id != request.user.id:
            conversation = None
    if not conversation:
        return Response({'detail': '未提供有效的会话 ID'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = HermesImageUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    image = serializer.validated_data['image']
    name = serializer.validated_data.get('name') or image.name

    hermes_image = HermesImage.objects.create(
        conversation=conversation,
        image=image,
        name=name,
    )
    return Response(
        HermesImageSerializer(hermes_image, context={'request': request}).data,
        status=status.HTTP_201_CREATED
    )
