from django.db import migrations


def sync_old_recorded_to_testscript(apps, schema_editor):
    """把旧的录制脚本（UiScriptGeneration.playwright_code）同步进统一脚本库（TestScript）。

    7.0 录制回放重构后，统一数据源改为 TestScript；之前通过旧「保存到平台」入口
    落库的 UiScriptGeneration 不会自动出现在脚本库 / 回放列表中。本迁移一次性补齐：
      - 仅处理有 playwright_code 且尚未关联 TestScript 的记录
      - 取 ui_project；若无则退化为库中第一个 UI 项目（保证 TestScript.project 非空）
    """
    UiScriptGeneration = apps.get_model('ui_automation', 'UiScriptGeneration')
    TestScript = apps.get_model('ui_automation', 'TestScript')
    UiProject = apps.get_model('ui_automation', 'UiProject')

    fallback = UiProject.objects.first()
    synced = 0
    for gen in UiScriptGeneration.objects.exclude(
        playwright_code__isnull=True
    ).exclude(playwright_code=''):
        if gen.generated_script_id:
            continue
        project = gen.ui_project or fallback
        if not project:
            continue
        ts = TestScript.objects.create(
            project=project,
            name=(gen.source_testcase_title or '录制脚本')[:200],
            description='由旧录制数据同步（UiScriptGeneration）',
            script_type='CODE',
            content=gen.playwright_code,
            language='python',
            framework='playwright',
        )
        gen.generated_script = ts
        gen.save(update_fields=['generated_script', 'updated_at'])
        synced += 1
    print('[migration 0026] 已同步 %d 条旧录制脚本到脚本库' % synced)


class Migration(migrations.Migration):
    dependencies = [
        ('ui_automation', '0025_uiscriptgeneration_nullable_ui_project'),
    ]

    operations = [
        migrations.RunPython(sync_old_recorded_to_testscript, migrations.RunPython.noop),
    ]
