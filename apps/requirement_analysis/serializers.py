from rest_framework import serializers
from .models import (
    RequirementDocument, RequirementAnalysis, BusinessRequirement,
    GeneratedTestCase, AnalysisTask, AIModelConfig, PromptConfig,
    GenerationConfig, TestCaseGenerationTask, TestCaseSkill, SkillArtifact
)


class RequirementDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = RequirementDocument
        fields = ['id', 'title', 'file', 'file_url', 'document_type', 'document_type_display', 
                 'status', 'status_display', 'uploaded_by', 'uploaded_by_name', 'project', 
                 'project_name', 'created_at', 'updated_at', 'file_size', 'extracted_text']
        read_only_fields = ['uploaded_by', 'file_size', 'extracted_text']
    
    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None


class BusinessRequirementSerializer(serializers.ModelSerializer):
    requirement_type_display = serializers.CharField(source='get_requirement_type_display', read_only=True)
    requirement_level_display = serializers.CharField(source='get_requirement_level_display', read_only=True)
    parent_requirement_name = serializers.CharField(source='parent_requirement.requirement_name', read_only=True)
    
    class Meta:
        model = BusinessRequirement
        fields = ['id', 'requirement_id', 'requirement_name', 'requirement_type', 
                 'requirement_type_display', 'parent_requirement', 'parent_requirement_name',
                 'module', 'requirement_level', 'requirement_level_display', 'reviewer', 
                 'estimated_hours', 'description', 'acceptance_criteria', 'created_at', 'updated_at']


class RequirementAnalysisSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source='document.title', read_only=True)
    document_id = serializers.IntegerField(source='document.id', read_only=True)
    requirements = BusinessRequirementSerializer(many=True, read_only=True)
    
    class Meta:
        model = RequirementAnalysis
        fields = ['id', 'document_id', 'document_title', 'analysis_report', 
                 'requirements_count', 'analysis_time', 'created_at', 'updated_at', 'requirements']


class GeneratedTestCaseSerializer(serializers.ModelSerializer):
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    requirement_name = serializers.CharField(source='requirement.requirement_name', read_only=True)
    requirement_id_display = serializers.CharField(source='requirement.requirement_id', read_only=True)
    
    class Meta:
        model = GeneratedTestCase
        fields = ['id', 'case_id', 'title', 'priority', 'priority_display', 'precondition',
                 'test_steps', 'expected_result', 'status', 'status_display', 'generated_by_ai',
                 'reviewed_by_ai', 'review_comments', 'requirement', 'requirement_name', 
                 'requirement_id_display', 'created_at', 'updated_at']


class AnalysisTaskSerializer(serializers.ModelSerializer):
    task_type_display = serializers.CharField(source='get_task_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    document_title = serializers.CharField(source='document.title', read_only=True)
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = AnalysisTask
        fields = ['id', 'task_id', 'task_type', 'task_type_display', 'document', 'document_title',
                 'status', 'status_display', 'progress', 'result', 'error_message', 
                 'started_at', 'completed_at', 'created_at', 'duration']
        read_only_fields = ['task_id', 'result', 'error_message', 'started_at', 'completed_at']
    
    def get_duration(self, obj):
        if obj.started_at and obj.completed_at:
            return (obj.completed_at - obj.started_at).total_seconds()
        return None


class DocumentUploadSerializer(serializers.ModelSerializer):
    """文档上传专用序列化器"""
    class Meta:
        model = RequirementDocument
        fields = ['id', 'title', 'file', 'project']
    
    def create(self, validated_data):
        # 自动设置上传者（如果用户已登录）
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['uploaded_by'] = user
        else:
            # 如果是匿名用户，使用第一个超级用户作为默认用户
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first()
            if not default_user:
                default_user = User.objects.first()
            validated_data['uploaded_by'] = default_user
        
        # 根据文件扩展名设置文档类型
        file = validated_data['file']
        if file.name.lower().endswith('.pdf'):
            validated_data['document_type'] = 'pdf'
        elif file.name.lower().endswith(('.doc', '.docx')):
            validated_data['document_type'] = 'docx'
        elif file.name.lower().endswith('.txt'):
            validated_data['document_type'] = 'txt'
        
        # 设置文件大小
        validated_data['file_size'] = file.size
        
        return super().create(validated_data)


class TestCaseGenerationRequestSerializer(serializers.Serializer):
    """测试用例生成请求序列化器"""
    requirement_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="需求ID列表"
    )
    test_level = serializers.ChoiceField(
        choices=[('unit', '单元测试'), ('integration', '集成测试'), ('system', '系统测试'), ('acceptance', '验收测试')],
        default='system',
        help_text="测试级别"
    )
    test_priority = serializers.ChoiceField(
        choices=[('P0', '最高优先级'), ('P1', '高优先级'), ('P2', '中优先级'), ('P3', '低优先级')],
        default='P1',
        help_text="测试优先级"
    )
    test_case_count = serializers.IntegerField(
        min_value=1,
        max_value=50,
        default=10,
        help_text="生成测试用例数量"
    )


class TestCaseGenerationCreateFromTextSerializer(serializers.Serializer):
    """
    从纯文本创建“用例生成任务”的请求序列化器（给旧前端/简化入口使用）。
    """

    title = serializers.CharField(max_length=200)
    requirement_text = serializers.CharField()
    output_mode = serializers.ChoiceField(choices=[("stream", "stream"), ("json", "json")], required=False, default="stream")
    project = serializers.IntegerField(required=False, allow_null=True)
    source_document = serializers.IntegerField(required=False, allow_null=True)


class TestCaseReviewRequestSerializer(serializers.Serializer):
    """测试用例评审请求序列化器"""
    test_case_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="测试用例ID列表"
    )
    review_criteria = serializers.CharField(
        max_length=500,
        default="检查测试用例的完整性、准确性和可执行性",
        help_text="评审标准"
    )


class AIModelConfigSerializer(serializers.ModelSerializer):
    """AI模型配置序列化器"""
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    api_key_masked = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = AIModelConfig
        fields = ['id', 'name', 'model_type', 'model_type_display', 'role', 'role_display',
                 'api_key', 'api_key_masked', 'base_url', 'model_name', 'max_tokens', 'temperature', 'top_p', 
                 'is_active', 'created_by', 'created_by_name', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'created_by_name']
        extra_kwargs = {
            'api_key': {'write_only': True}  # API Key只用于写入，不在响应中返回
        }
    
    def get_api_key_masked(self, obj):
        """返回掩码版本的API Key"""
        if obj.api_key:
            # 显示前3个字符和后4个字符，中间用*替代
            if len(obj.api_key) > 7:
                return f"{obj.api_key[:3]}{'*' * (len(obj.api_key) - 7)}{obj.api_key[-4:]}"
            else:
                return '*' * len(obj.api_key)
        return ''
    
    def create(self, validated_data):
        # 自动设置创建者
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        else:
            # 如果是匿名用户，使用第一个超级用户作为默认用户
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first()
            if not default_user:
                default_user = User.objects.first()
            validated_data['created_by'] = default_user
        
        return super().create(validated_data)


class PromptConfigSerializer(serializers.ModelSerializer):
    """提示词配置序列化器"""
    prompt_type_display = serializers.CharField(source='get_prompt_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = PromptConfig
        fields = ['id', 'name', 'prompt_type', 'prompt_type_display', 'content', 'is_active',
                 'created_by', 'created_by_name', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'created_by_name']
    
    def create(self, validated_data):
        # 自动设置创建者
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        else:
            # 如果是匿名用户，使用第一个超级用户作为默认用户
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first()
            if not default_user:
                default_user = User.objects.first()
            validated_data['created_by'] = default_user
        
        return super().create(validated_data)


class TestCaseGenerationTaskSerializer(serializers.ModelSerializer):
    """测试用例生成任务序列化器"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    writer_model_name = serializers.CharField(source='writer_model_config.name', read_only=True)
    reviewer_model_name = serializers.CharField(source='reviewer_model_config.name', read_only=True)
    writer_prompt_name = serializers.CharField(source='writer_prompt_config.name', read_only=True)
    reviewer_prompt_name = serializers.CharField(source='reviewer_prompt_config.name', read_only=True)
    
    class Meta:
        model = TestCaseGenerationTask
        fields = ['id', 'task_id', 'title', 'requirement_text', 'status', 'status_display',
                 'progress', 'output_mode', 'stream_buffer', 'stream_position', 'last_stream_update',
                 'project', 'project_name', 'source_document',
                 'dify_config', 'dify_dataset_id', 'dify_dataset_name', 'kb_context', 'kb_context_meta',
                 'kb_top_k', 'kb_reference_mode', 'kb_document_ids', 'kb_function_ids',
                 'writer_model_config', 'writer_model_name', 
                 'reviewer_model_config', 'reviewer_model_name', 'writer_prompt_config', 'writer_prompt_name',
                 'reviewer_prompt_config', 'reviewer_prompt_name', 'generated_test_cases',
                 'review_feedback', 'final_test_cases', 'generation_log', 'error_message',
                 'created_by', 'created_by_name', 'created_at', 'updated_at', 'completed_at']
        read_only_fields = ['task_id', 'status', 'progress', 'generated_test_cases', 
                          'review_feedback', 'final_test_cases', 'generation_log', 
                          'error_message', 'created_by', 'completed_at']
    
    def create(self, validated_data):
        # 自动设置创建者和任务ID
        import uuid
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        else:
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first()
            if not default_user:
                default_user = User.objects.first()
            validated_data['created_by'] = default_user
        
        validated_data['task_id'] = f"TASK_{uuid.uuid4().hex[:8].upper()}"
        
        return super().create(validated_data)


class TestCaseGenerationRequestSerializer(serializers.Serializer):
    """新的测试用例生成请求序列化器"""
    title = serializers.CharField(max_length=200, help_text="任务标题")
    requirement_text = serializers.CharField(help_text="需求描述")
    use_writer_model = serializers.BooleanField(default=True, help_text="是否使用编写模型")
    use_reviewer_model = serializers.BooleanField(default=True, help_text="是否使用评审模型")
    project = serializers.IntegerField(required=False, allow_null=True, help_text="关联项目ID")
    source_document = serializers.IntegerField(required=False, allow_null=True, help_text="来源需求文档ID（可选，用于多模态图文生成）")
    output_mode = serializers.ChoiceField(
        choices=[('stream', '实时流式输出'), ('complete', '完整输出')],
        required=False, default='stream', help_text="输出模式"
    )
    dify_config_id = serializers.IntegerField(required=False, allow_null=True, help_text="Dify 配置 ID")
    dify_dataset_id = serializers.CharField(required=False, allow_blank=True, default='', help_text="Dify 知识库 ID")
    dify_dataset_name = serializers.CharField(required=False, allow_blank=True, default='', help_text="Dify 知识库名称")
    kb_top_k = serializers.IntegerField(required=False, default=5, min_value=1, max_value=10, help_text="知识库检索条数")
    kb_reference_mode = serializers.ChoiceField(
        choices=[('documents', '指定文档'), ('retrieval', '语义检索'), ('hybrid', '混合')],
        required=False,
        default='hybrid',
        help_text="知识库参考模式",
    )
    kb_document_ids = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True, default=list,
        help_text="指定参考的 Dify 文档 ID 列表",
    )
    kb_function_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True, default=list,
        help_text="关联功能模块 ID 列表",
    )
    document_names = serializers.DictField(
        child=serializers.CharField(), required=False, allow_empty=True, default=dict,
        help_text="文档 ID -> 名称映射",
    )
    image_data_urls = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        default=list,
        help_text="界面截图 data URL 列表（多模态生成，兼容旧版）",
    )
    image_attachments = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        default=list,
        help_text="带角色的图片附件 [{url, role: ui_layout|operation_step, caption?, step_index?}]",
    )


class GenerationConfigSerializer(serializers.ModelSerializer):
    """生成行为配置序列化器"""
    default_output_mode_display = serializers.CharField(source='get_default_output_mode_display', read_only=True)

    class Meta:
        model = GenerationConfig
        fields = [
            'id', 'name', 'default_output_mode', 'default_output_mode_display',
            'enable_auto_review', 'review_timeout',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SkillArtifactSerializer(serializers.ModelSerializer):
    """Skill 包内文件序列化器"""
    artifact_type_display = serializers.CharField(source='get_artifact_type_display', read_only=True)
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = SkillArtifact
        fields = [
            'id', 'skill', 'artifact_type', 'artifact_type_display',
            'path', 'file', 'file_url', 'file_name', 'text_content',
            'is_binary', 'created_at', 'updated_at',
        ]
        read_only_fields = ['skill']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file:
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_file_name(self, obj):
        import os
        if obj.file:
            return os.path.basename(obj.file.name)
        return obj.path.split('/')[-1] if obj.path else ''


class TestCaseSkillSerializer(serializers.ModelSerializer):
    """Skill 技能包序列化器"""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    skill_type_display = serializers.CharField(source='get_skill_type_display', read_only=True)
    output_format_display = serializers.CharField(source='get_output_format_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    writer_model_name = serializers.CharField(source='writer_model_config.name', read_only=True)
    reviewer_model_name = serializers.CharField(source='reviewer_model_config.name', read_only=True)
    writer_prompt_name = serializers.CharField(source='writer_prompt_config.name', read_only=True)
    reviewer_prompt_name = serializers.CharField(source='reviewer_prompt_config.name', read_only=True)
    generation_config_name = serializers.CharField(source='generation_config.name', read_only=True)
    config_complete = serializers.SerializerMethodField()
    full_system_prompt = serializers.SerializerMethodField()
    template_filename = serializers.SerializerMethodField()
    template_url = serializers.SerializerMethodField()
    artifacts = SkillArtifactSerializer(many=True, read_only=True)
    file_count = serializers.SerializerMethodField()

    class Meta:
        model = TestCaseSkill
        fields = [
            'id', 'name', 'description', 'icon', 'category', 'category_display',
            # 技能包核心字段
            'skill_type', 'skill_type_display',
            'system_prompt', 'constraint_rules', 'output_format', 'output_format_display',
            'is_builtin', 'version', 'full_system_prompt',
            # 结构化技能包字段
            'author', 'tags', 'input_spec', 'output_spec', 'tools',
            # 技能包文件结构
            'readme', 'trigger_keywords', 'package_files', 'artifacts', 'file_count',
            # 团队模板
            'template_file', 'template_columns', 'template_filename', 'template_url',
            # 高级配置 FK
            'writer_model_config', 'writer_model_name',
            'reviewer_model_config', 'reviewer_model_name',
            'writer_prompt_config', 'writer_prompt_name',
            'reviewer_prompt_config', 'reviewer_prompt_name',
            'generation_config', 'generation_config_name',
            'config_complete',
            # 管理
            'is_active', 'sort_order',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_by_name', 'is_builtin']

    def get_config_complete(self, obj):
        """Skill 可用性检查：有 system_prompt 或有 writer_prompt_config"""
        return bool(obj.system_prompt.strip() or obj.writer_prompt_config_id)

    def get_full_system_prompt(self, obj):
        """返回组装后的完整系统提示词（只读）"""
        return obj.get_full_system_prompt()

    def get_template_filename(self, obj):
        import os
        if obj.template_file:
            return os.path.basename(obj.template_file.name)
        return None

    def get_template_url(self, obj):
        request = self.context.get('request')
        if obj.template_file:
            if request:
                return request.build_absolute_uri(obj.template_file.url)
            return obj.template_file.url
        return None

    def get_file_count(self, obj):
        return obj.artifacts.count()

    def create(self, validated_data):
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        else:
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first()
            if not default_user:
                default_user = User.objects.first()
            validated_data['created_by'] = default_user
        return super().create(validated_data)