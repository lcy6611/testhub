"""
0016: Skill 系统重构 — 新增技能包核心字段 + 内置 4 个 Skill 数据
"""
from django.db import migrations, models
import django.db.models.deletion


def create_builtin_skills(apps, schema_editor):
    """创建 4 个内置 Skill"""
    TestCaseSkill = apps.get_model('requirement_analysis', 'TestCaseSkill')
    User = apps.get_model('users', 'User')
    AIModelConfig = apps.get_model('requirement_analysis', 'AIModelConfig')
    PromptConfig = apps.get_model('requirement_analysis', 'PromptConfig')

    # 获取默认用户
    user = User.objects.filter(is_superuser=True).first() or User.objects.first()
    if not user:
        return

    # 获取默认活跃模型和提示词
    writer_model = AIModelConfig.objects.filter(role='writer', is_active=True).order_by('-updated_at').first()
    reviewer_model = AIModelConfig.objects.filter(role='reviewer', is_active=True).order_by('-updated_at').first()
    writer_prompt = PromptConfig.objects.filter(prompt_type='writer', is_active=True).order_by('-updated_at').first()
    reviewer_prompt = PromptConfig.objects.filter(prompt_type='reviewer', is_active=True).order_by('-updated_at').first()

    # 如果已有内置 Skill 则跳过
    if TestCaseSkill.objects.filter(is_builtin=True).exists():
        return

    builtin_skills = [
        {
            'name': '需求分析',
            'icon': '📋',
            'skill_type': 'requirements_analysis',
            'description': '分析需求文档，提取功能/性能/安全/接口需求，输出结构化需求列表',
            'system_prompt': """你是 TestHub 需求分析专家。你的任务是分析用户提供的需求文档或需求描述，提取结构化的需求信息。

# 输入说明
用户会提供需求文档（PDF/Word/TXT）的文本内容，或直接输入需求描述。

# 输出规范
输出 Markdown 表格，包含以下列：
| 需求编号 | 需求名称 | 需求类型 | 所属模块 | 优先级 | 需求描述 | 验收标准 |

需求类型包括：功能需求、性能需求、安全需求、可用性需求、接口需求、其他需求。
优先级分为：高、中、低。

# 分析要求
1. 逐条提取需求，不要遗漏
2. 为每条需求编号（REQ-001, REQ-002...）
3. 需求描述要精确、可测试
4. 验收标准要具体、可量化
5. 如果需求描述模糊，在验收标准中注明"需澄清\"""",
            'constraint_rules': """1. 必须覆盖需求文档中的所有功能点
2. 不要编造文档中不存在的内容
3. 需求编号必须连续
4. 优先级判断标准：核心功能=高，辅助功能=中，优化项=低""",
            'output_format': 'markdown',
            'sort_order': 10,
        },
        {
            'name': '需求评审',
            'icon': '🔍',
            'skill_type': 'requirement_reviewer',
            'description': '对需求文档进行评审，输出评审报告+综合评分+改进方向',
            'system_prompt': """你是 TestHub 需求评审专家。你的任务是对用户提供的需求文档进行评审，输出结构化的评审报告。

# 输入说明
用户会提供需求文档的文本内容。

# 输出规范
输出以下三个部分：

## 一、评审结果
Markdown 表格，列出每条需求的评审意见：
| 需求编号 | 需求名称 | 评审意见 | 问题类型 | 严重程度 |

问题类型：描述模糊、缺失边界条件、不可测试、逻辑矛盾、安全风险、性能风险、其他
严重程度：严重、一般、建议

## 二、综合评分
从以下维度评分（1-10分）：
- 完整性：需求是否覆盖所有场景
- 清晰度：需求描述是否明确无歧义
- 可测试性：需求是否可验证
- 一致性：需求之间是否有矛盾
- 总分和综合评价

## 三、改进方向
列出 3-5 条具体的改进建议，按优先级排序。

# 评审要求
1. 客观、专业，基于测试视角
2. 指出具体问题，不要泛泛而谈
3. 改进建议要可执行""",
            'constraint_rules': """1. 评审意见必须针对具体需求条目
2. 不要遗漏任何需求
3. 评分要有依据，不要随意打分
4. 改进方向最多 5 条，聚焦最重要的""",
            'output_format': 'markdown',
            'sort_order': 20,
        },
        {
            'name': '用例评审',
            'icon': '✅',
            'skill_type': 'testcase_reviewer',
            'description': '对已生成的测试用例进行评审，检查完整性/准确性/可执行性',
            'system_prompt': """你是 TestHub 用例评审专家。你的任务是对用户提供的测试用例进行评审，输出评审报告。

# 输入说明
用户会提供需求描述和已生成的测试用例（Markdown 表格或 JSON）。

# 输出规范
输出以下三个部分：

## 一、用例评审明细
Markdown 表格：
| 用例编号 | 用例标题 | 评审意见 | 问题类型 | 严重程度 |

问题类型：步骤缺失、预期结果不明确、前置条件不全、优先级不当、场景遗漏、重复用例、其他
严重程度：严重、一般、建议

## 二、覆盖度分析
- 需求覆盖：列出未覆盖的需求点
- 场景覆盖：列出遗漏的测试场景（正向/反向/边界/异常）
- 评分：覆盖度评分（1-10分）

## 三、改进建议
列出具体改进措施，按优先级排序。

# 评审要求
1. 逐条评审，不要跳过
2. 关注用例的可执行性（步骤是否足够详细）
3. 关注边界值和异常场景的覆盖
4. 改进建议要具体、可落地""",
            'constraint_rules': """1. 必须逐条评审每个用例
2. 覆盖度分析必须对照需求
3. 不要编造不存在的用例问题
4. 改进建议最多 5 条""",
            'output_format': 'markdown',
            'sort_order': 30,
        },
        {
            'name': '全能用例生成',
            'icon': '🎯',
            'skill_type': 'testcase_generator',
            'description': '根据需求生成结构化测试用例，覆盖正向/反向/边界/异常场景',
            'system_prompt': """你是 TestHub 测试用例编写专家。你的任务是根据用户提供的需求描述，生成高质量的测试用例。

# 输入说明
用户会提供需求描述文本，可能附带界面截图。

# 输出规范
输出 Markdown 表格，包含以下列：
| 用例编号 | 用例标题 | 优先级 | 前置条件 | 测试步骤 | 预期结果 |

优先级：P0（最高）、P1（高）、P2（中）、P3（低）

# 生成要求
1. **场景覆盖**：每个功能点必须覆盖以下场景：
   - 正向测试（正常操作流程）
   - 反向测试（错误输入、异常操作）
   - 边界值测试（最大/最小/临界值）
   - 异常场景（网络中断、并发、超时等）

2. **用例质量**：
   - 测试步骤必须详细、可执行（不要写"输入数据"，要写"输入手机号13800138000"）
   - 预期结果必须具体、可验证
   - 前置条件必须完整（环境/数据/权限）
   - 用例编号连续（TC-001, TC-002...）

3. **优先级分配**：
   - P0：核心功能主流程
   - P1：重要功能、常见异常
   - P2：边界值、少见场景
   - P3：兼容性、体验优化

4. **最后总结**：
   在表格后附上总结：总用例数、各优先级分布、覆盖的场景列表""",
            'constraint_rules': """1. 必须覆盖需求中的所有功能点
2. 每个功能点至少 1 个正向 + 2 个反向 + 1 个边界值用例
3. 测试步骤必须具体到可执行
4. 不要生成与需求无关的用例
5. 用例编号必须连续
6. 保持 Markdown 表格格式，不要用其他格式""",
            'output_format': 'markdown',
            'sort_order': 40,
        },
    ]

    for skill_data in builtin_skills:
        TestCaseSkill.objects.create(
            is_builtin=True,
            version='1.0',
            created_by=user,
            writer_model_config=writer_model,
            reviewer_model_config=reviewer_model,
            writer_prompt_config=writer_prompt,
            reviewer_prompt_config=reviewer_prompt,
            **skill_data,
        )


def remove_builtin_skills(apps, schema_editor):
    """回滚：删除内置 Skill"""
    TestCaseSkill = apps.get_model('requirement_analysis', 'TestCaseSkill')
    TestCaseSkill.objects.filter(is_builtin=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('requirement_analysis', '0015_skill'),
    ]

    operations = [
        # 新增技能包核心字段
        migrations.AddField(
            model_name='testcaseskill',
            name='skill_type',
            field=models.CharField(
                choices=[
                    ('requirements_analysis', '需求分析'),
                    ('requirement_reviewer', '需求评审'),
                    ('testcase_reviewer', '用例评审'),
                    ('testcase_generator', '用例生成'),
                    ('custom', '自定义'),
                ],
                default='testcase_generator',
                max_length=30,
                verbose_name='技能类型',
            ),
        ),
        migrations.AddField(
            model_name='testcaseskill',
            name='system_prompt',
            field=models.TextField(
                blank=True, default='',
                help_text='技能的核心系统提示词，定义角色、输入说明、输出规范',
                verbose_name='系统提示词',
            ),
        ),
        migrations.AddField(
            model_name='testcaseskill',
            name='constraint_rules',
            field=models.TextField(
                blank=True, default='',
                help_text='约束规则（自然语言描述），会注入到系统提示词中',
                verbose_name='约束规则',
            ),
        ),
        migrations.AddField(
            model_name='testcaseskill',
            name='output_format',
            field=models.CharField(
                choices=[
                    ('markdown', 'Markdown 表格'),
                    ('json', 'JSON 结构化'),
                    ('excel', 'Excel 表格'),
                    ('xmind', '飞书思维导图'),
                ],
                default='markdown',
                max_length=20,
                verbose_name='输出格式',
            ),
        ),
        migrations.AddField(
            model_name='testcaseskill',
            name='is_builtin',
            field=models.BooleanField(default=False, verbose_name='是否内置'),
        ),
        migrations.AddField(
            model_name='testcaseskill',
            name='version',
            field=models.CharField(default='1.0', max_length=20, verbose_name='版本号'),
        ),
        # 数据迁移：创建内置 4 个 Skill
        migrations.RunPython(create_builtin_skills, remove_builtin_skills),
    ]
