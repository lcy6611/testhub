# -*- coding: utf-8 -*-
"""知识中枢模块：KnowledgeHubConfig + Native 知识库三件套。"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assistant", "0001_initial"),
        ("projects", "0003_projectmapping"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("requirement_analysis", "0016_skill_system_redesign"),
    ]

    operations = [
        migrations.CreateModel(
            name="KnowledgeHubConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("engine", models.CharField(
                    choices=[("dify", "Dify 知识库"), ("native", "知识中枢（自建）")],
                    default="dify", max_length=16, verbose_name="知识中枢引擎")),
                ("parser_type", models.CharField(
                    choices=[("tika", "Apache Tika（内置兜底）"), ("mineru", "MinerU（私有）"), ("textin", "TextIn（云端）")],
                    default="tika", max_length=16, verbose_name="文档解析器")),
                ("parser_api_url", models.URLField(blank=True, default="", verbose_name="解析服务地址")),
                ("parser_api_key", models.CharField(blank=True, default="", max_length=256, verbose_name="解析服务密钥")),
                ("embedding_api_url", models.URLField(blank=True, default="", verbose_name="Embedding API 地址")),
                ("embedding_api_key", models.CharField(blank=True, default="", max_length=256, verbose_name="Embedding API Key")),
                ("embedding_model_name", models.CharField(blank=True, default="Qwen/Qwen3-Embedding-8B", max_length=128, verbose_name="Embedding 模型")),
                ("rerank_api_url", models.URLField(blank=True, default="", verbose_name="Rerank API 地址")),
                ("rerank_api_key", models.CharField(blank=True, default="", max_length=256, verbose_name="Rerank API Key")),
                ("rerank_model_name", models.CharField(blank=True, default="Qwen/Qwen3-Reranker-8B", max_length=128, verbose_name="Rerank 模型")),
                ("extraction_api_url", models.URLField(blank=True, default="", verbose_name="抽取模型 API 地址")),
                ("extraction_api_key", models.CharField(blank=True, default="", max_length=256, verbose_name="抽取模型 API Key")),
                ("extraction_model_name", models.CharField(blank=True, default="", max_length=128, verbose_name="抽取模型名称")),
                ("vision_api_url", models.URLField(blank=True, default="", verbose_name="视觉模型 API 地址")),
                ("vision_api_key", models.CharField(blank=True, default="", max_length=256, verbose_name="视觉模型 API Key")),
                ("vision_model_name", models.CharField(blank=True, default="", max_length=128, verbose_name="视觉模型名称")),
                ("top_k", models.PositiveSmallIntegerField(default=5, verbose_name="检索条数 Top-K")),
                ("chunk_size", models.PositiveIntegerField(default=500, verbose_name="分块大小（字符）")),
                ("chunk_overlap", models.PositiveIntegerField(default=80, verbose_name="分块重叠（字符）")),
                ("min_score", models.FloatField(default=0.3, verbose_name="最低相关度阈值")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("dify_config", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="kb_hub_configs", to="assistant.difyconfig", verbose_name="Dify 配置")),
            ],
            options={
                "db_table": "kb_hub_config",
                "verbose_name": "知识中枢配置",
                "verbose_name_plural": "知识中枢配置",
            },
        ),
        migrations.CreateModel(
            name="NativeKb",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="知识库名称")),
                ("description", models.TextField(blank=True, default="", verbose_name="描述")),
                ("status", models.CharField(
                    choices=[("draft", "草稿"), ("published", "已发布"), ("archived", "已归档")],
                    default="draft", max_length=16, verbose_name="状态")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("project", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="native_kbs", to="projects.project", verbose_name="关联项目")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL, verbose_name="创建者")),
            ],
            options={
                "db_table": "kb_hub_native_kb",
                "verbose_name": "自建知识库",
                "verbose_name_plural": "自建知识库",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="NativeKbDocument",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=300, verbose_name="文档标题")),
                ("source_type", models.CharField(
                    choices=[("file", "文件上传"), ("text", "文本录入"), ("url", "URL 抓取")],
                    default="file", max_length=16, verbose_name="来源类型")),
                ("file", models.FileField(blank=True, null=True, upload_to="kb_hub/docs/", verbose_name="源文件")),
                ("content_text", models.TextField(blank=True, default="", verbose_name="原始文本")),
                ("content_md", models.TextField(blank=True, default="", verbose_name="解析后 Markdown")),
                ("status", models.CharField(
                    choices=[("pending", "待解析"), ("parsed", "已解析"), ("failed", "解析失败")],
                    default="pending", max_length=16, verbose_name="解析状态")),
                ("word_count", models.PositiveIntegerField(default=0, verbose_name="字数")),
                ("doc_meta", models.JSONField(blank=True, default=dict, verbose_name="元信息")),
                ("error_message", models.TextField(blank=True, default="", verbose_name="错误信息")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("kb", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="documents",
                    to="requirement_analysis.nativekb", verbose_name="所属知识库")),
            ],
            options={
                "db_table": "kb_hub_native_doc",
                "verbose_name": "知识库文档",
                "verbose_name_plural": "知识库文档",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="NativeKbChunk",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_index", models.PositiveIntegerField(default=0, verbose_name="分块序号")),
                ("content", models.TextField(verbose_name="分块内容")),
                ("embedding", models.JSONField(blank=True, default=list, verbose_name="向量")),
                ("token_count", models.PositiveIntegerField(default=0, verbose_name="Token 数")),
                ("enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("document", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="chunks",
                    to="requirement_analysis.nativekbdocument", verbose_name="所属文档")),
            ],
            options={
                "db_table": "kb_hub_native_chunk",
                "verbose_name": "知识库分块",
                "verbose_name_plural": "知识库分块",
            },
        ),
        migrations.AddIndex(
            model_name="nativekbchunk",
            index=models.Index(fields=["document"], name="kb_hub_chunk_doc_idx"),
        ),
    ]
