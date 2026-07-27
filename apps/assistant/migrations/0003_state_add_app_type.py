from django.db import migrations, models


class Migration(migrations.Migration):
    """
    State-only migration.

    The production database already contains column `dify_configs.app_type` as NOT NULL.
    Older code didn't declare this field, so INSERT failed with:
      (1364, "Field 'app_type' doesn't have a default value")

    We add the field to Django's model state without touching the database schema.
    """

    dependencies = [
        ("assistant", "0002_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="difyconfig",
                    name="app_type",
                    field=models.CharField(
                        default="workflow",
                        help_text="dify 应用类型（workflow/chat），用于决定调用哪个接口",
                        max_length=20,
                        verbose_name="应用类型",
                    ),
                ),
            ],
        )
    ]

