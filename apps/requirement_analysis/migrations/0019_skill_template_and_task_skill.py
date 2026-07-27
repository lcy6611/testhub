from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('requirement_analysis', '0018_add_vision_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='testcaseskill',
            name='template_columns',
            field=models.JSONField(blank=True, default=list, help_text='上传 Excel/CSV 后自动解析首行得到的列名列表', verbose_name='模板列名'),
        ),
        migrations.AddField(
            model_name='testcaseskill',
            name='template_file',
            field=models.FileField(blank=True, null=True, upload_to='skill_templates/', verbose_name='团队模板文件'),
        ),
        migrations.AddField(
            model_name='testcasegenerationtask',
            name='skill',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='requirement_analysis.testcaseskill', verbose_name='关联技能'),
        ),
        migrations.AddField(
            model_name='testcasegenerationtask',
            name='skill_system_prompt',
            field=models.TextField(blank=True, default='', verbose_name='技能系统提示词(快照)'),
        ),
        migrations.AddField(
            model_name='testcasegenerationtask',
            name='skill_template_columns',
            field=models.JSONField(blank=True, default=list, verbose_name='技能模板列名(快照)'),
        ),
    ]
