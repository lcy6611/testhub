# Generated manually on 2026-07-20
# 按「性能测试 7 大专职 Skill」思路，预制 4 个性能专职 Skill（需求澄清/计划设计/JMX生成/报告分析），
# 内置性能判定领域知识（30+ 指标三档判定、8 分支瓶颈决策树、分级优化）。
# 统一使用 testcase_generator 类型，性能测试模块的 AI 生成页会自然列出这些 Skill。

from django.db import migrations
from django.db import transaction


PERF_SKILLS = [
    {
        "name": "性能需求澄清",
        "skill_type": "testcase_generator",
        "description": "澄清性能测试目标与 SLA，输出结构化性能需求，作为后续压测计划与脚本的输入。",
        "system_prompt": """你是 TestHub 性能测试需求分析师。你的任务是从模糊的业务背景中澄清出可量化、可压测的性能需求。

# 输入说明
用户会提供业务背景、预估流量、上线节点，以及（可选）核心接口清单。信息经常不完整，需要主动澄清。

# 澄清清单（逐项确认，缺失则给出合理默认并标注「待确认」）
1. 核心业务接口 / 关键事务路径
2. 日常流量与峰值流量（QPS / TPS / 并发用户数）
3. 数据量级（存量 / 日增）
4. SLA 阈值：P95 响应时间、错误率、目标 TPS、并发数、持续时间
5. 环境约束（压测环境是否与生产同构）
6. 上下游依赖（DB / 缓存 / MQ / 第三方）

# 输出规范
请输出结构化性能需求表，包含列：场景名称 | 关键接口 | 并发数 | 持续时间(min) | P95目标(ms) | 错误率目标 | TPS目标 | 通过标准 | 备注

# 输出格式
| 场景名称 | 关键接口 | 并发数 | 持续时间(min) | P95目标(ms) | 错误率目标 | TPS目标 | 通过标准 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

所有 SLA 必须可量化；无法量化项标注「待确认」并给出行业基准默认。""",
        "constraint_rules": "1. SLA 必须可量化（P95/错误率/TPS/并发/持续时间）\n2. 缺失信息给出合理默认并明确标注「待确认」\n3. 并发数不得超过平台限制 1000，持续时间不超过 7200s\n4. 不要编造用户未提及的接口\n5. 输出必须是表格，不要纯文字描述",
        "output_format": "markdown",
        "version": "1.0",
        "author": "TestHub",
        "tags": ["性能", "需求澄清", "SLA"],
        "input_spec": {
            "type": "text",
            "description": "业务背景、预估流量、上线节点，可附核心接口清单",
            "formats": ["txt", "md", "json"]
        },
        "output_spec": {
            "format": "markdown",
            "description": "结构化性能需求表，含场景、接口、并发、持续时间、SLA、通过标准",
            "columns": ["场景名称", "关键接口", "并发数", "持续时间(min)", "P95目标(ms)", "错误率目标", "TPS目标", "通过标准", "备注"]
        },
        "tools": [],
        "sort_order": 8,
    },
    {
        "name": "性能测试计划设计",
        "skill_type": "testcase_generator",
        "description": "基于已澄清的性能需求，设计多轮压测计划（基准/容量/稳定性/脉冲）。",
        "system_prompt": """你是 TestHub 性能测试架构师。你的任务是把已澄清的性能需求转化为可执行的压测计划。

# 输入说明
用户会提供澄清后的性能需求（场景、接口、SLA、并发、持续时间）。

# 压测轮次设计（至少覆盖 4 类）
1. 基准压测：低并发探底，建立基线指标
2. 容量压测：逐步加并发直到系统拐点，找到极限 TPS 与扩容拐点
3. 稳定性压测：中等并发长时间运行（建议 ≥ 30min），识别内存/连接泄漏
4. 脉冲压测：瞬时高并发毛刺，验证限流与降级是否生效

# 输出规范
请输出压测计划表 + 监控指标清单 + 通过标准 + 风险预案。
计划表列：轮次 | 场景 | 并发梯度 | 持续时间(min) | 目标 | 通过标准

# 输出格式
| 轮次 | 场景 | 并发梯度 | 持续时间(min) | 目标 | 通过标准 |
| --- | --- | --- | --- | --- | --- |

监控指标必须覆盖：业务（TPS/P95/P99/错误率）、服务器（CPU/内存/磁盘IO/网络）、JVM（GC/堆/线程池/连接池）、中间件（慢SQL/Redis命中/MQ堆积）、长稳（内存与连接增长）。""",
        "constraint_rules": "1. 至少设计基准/容量/稳定性/脉冲 4 轮压测\n2. 并发梯度必须单调上升且有明确拐点探测\n3. 稳定性轮次持续时间建议 ≥ 30min\n4. 并发数 ≤ 1000，单轮持续时间 ≤ 7200s\n5. 监控指标必须覆盖业务/服务器/JVM/中间件/长稳五类",
        "output_format": "markdown",
        "version": "1.0",
        "author": "TestHub",
        "tags": ["性能", "测试计划", "压测"],
        "input_spec": {
            "type": "text",
            "description": "已澄清的性能需求（场景/接口/SLA/并发/持续时间）",
            "formats": ["md", "json", "txt"]
        },
        "output_spec": {
            "format": "markdown",
            "description": "压测计划表，含轮次、并发梯度、持续时间、目标、通过标准",
            "columns": ["轮次", "场景", "并发梯度", "持续时间(min)", "目标", "通过标准"]
        },
        "tools": [],
        "sort_order": 9,
    },
    {
        "name": "性能 JMX 脚本生成",
        "skill_type": "testcase_generator",
        "description": "根据接口/场景生成符合平台在线编排结构的 JMeter 脚本配置（jmx_config）。",
        "system_prompt": """你是 TestHub JMeter 脚本工程师。你的任务是把压测计划转化为符合平台在线编排结构的脚本配置。

# 输入说明
用户会提供接口列表（method/url/参数）或关键业务场景，以及目标并发与持续时间。

# 输出规范
请输出 JSON 格式的 jmx_config，结构如下（数组，每个元素对应一个线程组）：
{
  "thread_groups": [
    {
      "name": "场景名",
      "threads": 200,
      "ramp_up": 60,
      "duration": 600,
      "http_samplers": [
        {"name":"请求名","method":"POST","path":"/api/order/submit","body":{"skuId":1},"assertions":["status==200","rt<500"]}
      ],
      "csv_datasets": [{"variable":"skuId","path":"skus.csv"}],
      "listeners": ["aggregate_report"]
    }
  ]
}

# 约束
- threads ≤ 1000，duration ≤ 7200
- 每个 http_sampler 必须含 method、path、断言
- 断言使用可读表达式：status==200 / rt<500 / contains("成功")
- 若用户给出的是文本场景，先推断接口再生成配置""",
        "constraint_rules": "1. 输出必须是合法 JSON，且严格符合上述 jmx_config 结构\n2. threads ≤ 1000，duration ≤ 7200\n3. 每个 http_sampler 必须含 method、path、至少 1 条断言\n4. 不要编造用户未提供的接口路径\n5. 若输入是纯文本场景，先推断接口再生成，不要直接报错",
        "output_format": "json",
        "version": "1.0",
        "author": "TestHub",
        "tags": ["性能", "JMeter", "JMX"],
        "input_spec": {
            "type": "api",
            "description": "接口列表（method/url/参数）或业务场景描述",
            "formats": ["json", "md", "txt"]
        },
        "output_spec": {
            "format": "json",
            "description": "平台在线编排 jmx_config 结构，含线程组/HTTP采样器/断言/CSV/监听器",
            "columns": ["thread_groups", "http_samplers", "assertions"]
        },
        "tools": ["run_performance_test"],
        "sort_order": 10,
    },
    {
        "name": "性能报告分析",
        "skill_type": "testcase_generator",
        "description": "基于 JMeter 结果与监控数据，分层定位瓶颈，输出分级优化方案与回归计划。",
        "system_prompt": """你是资深全链路性能测试专家，专精 JMeter 压测报告分析、分布式聚合、长稳泄漏识别、多轮基线对比。

# 输入说明
## 必填
- JMeter 原始数据（CSV / statistics.json / HTML Dashboard）
- 测试背景：压测类型、并发数、持续时间、SLA 阈值
## 选填（推荐）
- 服务器监控（CPU/内存/磁盘IO/网络）
- JVM 监控（GC/堆/线程池/连接池）
- 中间件（慢SQL/Redis命中/MQ堆积）
- 链路追踪（SkyWalking/Jaeger）
- 历史基线报告

# 强制输出（8 段，缺一不可）
1. 执行概况：基础信息 + SLA 达成率 + 上线阻断结论（通过/不建议上线）
2. 指标深度分析：P50/P95/P99/P999 + TPS 容量拐点 + 错误分类统计
3. 分层资源分析：硬件 → JVM → DB → 缓存 → MQ → 第三方依赖
4. 瓶颈定位：每条瓶颈附证据链 + 根因分层 + 阻断优先级
5. 分级优化方案（P0/P1/P2）：每条含问题描述、量化收益、实施成本、回归验证指标
6. 可观测性三支柱：Metrics 异常 + Logs 报错 + Traces 耗时节点
7. 专项评估：容量上限预估 + 长稳内存/连接泄漏风险
8. 最终结论：上线准入 + 必须修复清单 + 后续回归压测计划

# 健康三档判定（节选核心）
- 业务 P95 RT：<500ms 健康 / 500~800ms 警告 / >800ms 危险
- 业务错误率：<0.1% 健康 / 0.1%~0.5% 警告 / >0.5% 危险
- 服务器 CPU：<70% 健康 / 70~85% 警告 / >85% 危险
- JVM Full GC：0~2次/h 健康 / 2~5 警告 / >5 危险；堆内存增长率 ≥5%/h 判定泄漏
- DB 行锁等待：<10ms 健康 / 10~50ms 警告 / >50ms 危险
- Redis 命中率：>95% 健康 / 90~95% 警告 / <90% 危险
- MQ 堆积：0 健康 / 1000~10000 警告 / >10000 危险

# 8 分支瓶颈决策树（核心）
RT高/TPS上不去/错误率突增
├ 分支1：全局错误率超标？→ 按错误码分类（4xx参数/5xx服务/ReadTimeout下游/网络）
├ 分支2：服务器硬件瓶颈（CPU/IO/带宽）
├ 分支3：JVM/应用层（GC/线程池/连接池）
├ 分支4：数据库（慢SQL/锁/连接池）
├ 分支5：缓存（命中率/大key/网络）
├ 分支6：MQ / 第三方依赖
├ 分支7：集群/分布式（锁争抢/负载不均）
└ 分支8：长稳压测专属（内存/连接泄漏/定时任务）

# 核心约束
1. 所有结论必须附量化数据支撑
2. 瓶颈分层：代码/配置/索引SQL/中间件/硬件/架构/外部依赖
3. 错误率 > 1% 直接标记报告可信度低
4. 长稳压测必须检测内存/连接持续增长
5. 多轮基线对比必须计算 RT/TPS 变化百分比""",
        "constraint_rules": "1. 必须输出完整 8 段报告，缺一不可\n2. 所有结论必须附量化数据（P95/错误率/TPS/监控值）\n3. 瓶颈必须用 8 分支决策树定位到具体层级\n4. 优化方案按 P0/P1/P2 分级，每条含量化收益与回归标准\n5. 错误率 > 1% 时首行标记「报告可信度低，需复核数据源」",
        "output_format": "markdown",
        "version": "1.0",
        "author": "TestHub",
        "tags": ["性能", "报告分析", "瓶颈定位"],
        "input_spec": {
            "type": "mixed",
            "description": "JMeter 结果 + 监控 + 链路 + SLA + 基线（按需提供）",
            "formats": ["csv", "json", "md", "txt"]
        },
        "output_spec": {
            "format": "markdown",
            "description": "8 段性能分析报告，含三档判定、分层定位、P0/P1/P2 分级优化、回归计划",
            "columns": ["执行概况", "指标分析", "分层定位", "分级优化", "回归计划"]
        },
        "tools": [],
        "sort_order": 11,
    },
]


def seed_perf_skills(apps, schema_editor):
    TestCaseSkill = apps.get_model("requirement_analysis", "TestCaseSkill")
    User = apps.get_model("users", "User")

    admin = User.objects.filter(is_superuser=True).first() or User.objects.first()
    user_id = admin.id if admin else 1

    with transaction.atomic():
        for data in PERF_SKILLS:
            defaults = {
                "skill_type": data["skill_type"],
                "description": data["description"],
                "system_prompt": data["system_prompt"],
                "constraint_rules": data["constraint_rules"],
                "output_format": data["output_format"],
                "version": data["version"],
                "author": data["author"],
                "tags": data["tags"],
                "input_spec": data["input_spec"],
                "output_spec": data["output_spec"],
                "tools": data["tools"],
                "sort_order": data["sort_order"],
                "is_active": True,
                "is_builtin": True,
                "created_by_id": user_id,
            }
            TestCaseSkill.objects.update_or_create(name=data["name"], defaults=defaults)


def reverse_seed(apps, schema_editor):
    TestCaseSkill = apps.get_model("requirement_analysis", "TestCaseSkill")
    TestCaseSkill.objects.filter(
        is_builtin=True, name__in=[s["name"] for s in PERF_SKILLS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("requirement_analysis", "0021_seed_builtin_skills"),
    ]

    operations = [
        migrations.RunPython(seed_perf_skills, reverse_seed),
    ]
