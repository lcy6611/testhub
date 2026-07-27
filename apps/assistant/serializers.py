from rest_framework import serializers
from .models import (
    AssistantSession, AssistantMessage, DifyConfig, ChatMessage,
    HermesAgentConfig, HermesConversation, HermesMessage, HermesImage,
)


class DifyConfigSerializer(serializers.ModelSerializer):
    dataset_api_key_masked = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DifyConfig
        fields = [
            'id', 'api_url', 'api_key', 'dataset_api_key', 'dataset_api_key_masked',
            'app_type', 'invoke_mode', 'is_active', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'api_key': {'write_only': True},
            'dataset_api_key': {'write_only': True},
        }

    def get_dataset_api_key_masked(self, obj):
        key = getattr(obj, 'dataset_api_key', '') or ''
        if not key:
            return ''
        if len(key) > 7:
            return f"{key[:3]}{'*' * (len(key) - 7)}{key[-4:]}"
        return '*' * len(key)


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'conversation_id', 'message_id', 'created_at']
        read_only_fields = ['conversation_id', 'message_id', 'created_at']


class AssistantMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantMessage
        fields = ['id', 'message_type', 'content', 'created_at']


class AssistantSessionSerializer(serializers.ModelSerializer):
    messages = AssistantMessageSerializer(many=True, read_only=True)
    chat_messages = ChatMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = AssistantSession
        fields = ['id', 'session_id', 'conversation_id', 'title', 'created_at', 'updated_at', 'messages', 'chat_messages']


class AssistantSessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantSession
        fields = ['session_id', 'title']
    
class AssistantSessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantSession
        fields = ['session_id', 'title']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class HermesAgentConfigSerializer(serializers.ModelSerializer):
    model_config_name = serializers.CharField(source='model_config.name', read_only=True, default='')

    class Meta:
        model = HermesAgentConfig
        fields = [
            'id', 'name', 'system_prompt', 'model_config', 'model_config_name',
            'avatar_url', 'tts_enabled', 'active_skills', 'is_active',
            'created_at', 'updated_at',
        ]


class HermesImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = HermesImage
        fields = ['id', 'name', 'url', 'created_at']

    def get_url(self, obj):
        request = self.context.get('request')
        if obj.image:
            url = obj.image.url
            if request:
                return request.build_absolute_uri(url)
            return url
        return ''


class HermesImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)
    name = serializers.CharField(required=False, allow_blank=True, default='')


class HermesMessageSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = HermesMessage
        fields = ['id', 'role', 'content', 'images', 'tool_calls', 'thought_text', 'created_at']

    def get_images(self, obj):
        if not obj.images:
            return []
        image_ids = [i for i in obj.images if i]
        if not image_ids:
            return []
        request = self.context.get('request')
        qs = HermesImage.objects.filter(pk__in=image_ids)
        return HermesImageSerializer(qs, many=True, context={'request': request}).data



class HermesConversationSerializer(serializers.ModelSerializer):
    messages = HermesMessageSerializer(many=True, read_only=True)

    class Meta:
        model = HermesConversation
        fields = ['id', 'title', 'messages', 'created_at', 'updated_at']


class HermesConversationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = HermesConversation
        fields = ['id', 'title', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
