from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assistant", "0004_difyconfig_dataset_api_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="difyconfig",
            name="invoke_mode",
            field=models.CharField(
                choices=[("chat", "对话应用"), ("workflow", "工作流应用")],
                default="workflow",
                help_text="AI 评测师调用 Dify 时使用的 API：chat-messages 或 workflows/run",
                max_length=20,
                verbose_name="Dify 调用模式",
            ),
        ),
    ]
