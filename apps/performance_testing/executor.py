# -*- coding: utf-8 -*-
"""
性能测试执行引擎（核心枢纽）。

完整生命周期：
  校验负载上限 → 生成/准备 JMX → JMeter non-GUI 执行 → BackendListener 实时上报
  → HTML 报告生成 → JTL 解析 → summary + metrics 落库 → 更新执行状态
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import uuid
from typing import Any, Dict, List, Optional, Set

from django.conf import settings
from django.utils import timezone

from .models import (
    PerformanceExecution, PerformanceMetric, PerformanceSummary, PerformanceConfig,
)
from .jmx_builder import JMeterPlanBuilder, UploadedJMXPlanBuilder
from .result_parser import parse_jtl
from .influxdb_client import query_realtime, is_enabled as realtime_enabled

logger = logging.getLogger(__name__)

DEFAULT_MAX_THREADS = 1000
DEFAULT_MAX_DURATION = 7200


def _config() -> PerformanceConfig:
    return PerformanceConfig.get_singleton()


def _jmeter_command() -> str:
    """获取 JMeter 可执行命令，优先使用数据库配置。"""
    cmd = ""
    try:
        cmd = _config().jmeter_path or ""
    except Exception:
        pass
    if not cmd:
        cmd = getattr(settings, "PERFORMANCE_JMETER_PATH", "") or os.environ.get("JMETER_PATH", "")
    if not cmd:
        cmd = "jmeter"
    if os.name == "nt" and cmd and not cmd.lower().endswith((".bat", ".cmd", ".exe")):
        candidate = cmd + ".bat"
        if os.path.exists(candidate) or " " not in candidate:
            cmd = candidate
    return cmd


def _max_threads() -> int:
    try:
        return _config().max_threads or DEFAULT_MAX_THREADS
    except Exception:
        return DEFAULT_MAX_THREADS


def _max_duration() -> int:
    try:
        return _config().max_duration or DEFAULT_MAX_DURATION
    except Exception:
        return DEFAULT_MAX_DURATION


def validate_load(thread_count: int, duration: int) -> Optional[str]:
    """校验负载上限。返回错误信息或 None。"""
    max_threads = _max_threads()
    max_duration = _max_duration()
    if thread_count <= 0:
        return "线程数必须大于 0"
    if thread_count > max_threads:
        return f"线程数不能超过 {max_threads}"
    if duration <= 0:
        return "持续时间必须大于 0"
    if duration > max_duration:
        return f"持续时间不能超过 {max_duration} 秒"
    return None


def _work_dir(execution_id: str) -> str:
    base = os.path.join(settings.MEDIA_ROOT, "performance", execution_id)
    os.makedirs(base, exist_ok=True)
    return base


def _collect_csv_filenames(config: Dict[str, Any]) -> Set[str]:
    """从 jmx_config 中收集所有 CSV 文件名。"""
    names: Set[str] = set()
    for csv in config.get("csv_datasets") or []:
        fname = csv.get("file") or csv.get("filename")
        if fname:
            names.add(os.path.basename(fname))
    for tg in config.get("thread_groups") or []:
        for csv in tg.get("csv_datasets") or []:
            fname = csv.get("file") or csv.get("filename")
            if fname:
                names.add(os.path.basename(fname))
    return names


def _copy_csv_files_to_work_dir(script, work_dir: str) -> List[str]:
    """将脚本关联的 CSV 文件复制到工作目录，返回实际文件名列表。"""
    copied: List[str] = []
    for csv_obj in script.csv_files.all():
        src = csv_obj.file.path
        if not os.path.exists(src):
            continue
        filename = csv_obj.original_name or os.path.basename(csv_obj.file.name)
        dst = os.path.join(work_dir, filename)
        shutil.copy2(src, dst)
        copied.append(filename)
    return copied


def _backend_listener_config() -> Optional[Dict[str, Any]]:
    """从 PerformanceConfig 读取 InfluxDB 配置，动态注入 JMeter Backend Listener。"""
    try:
        cfg = PerformanceConfig.get_singleton()
    except Exception:
        return None
    if not cfg.realtime_report_enabled:
        return None
    if not cfg.influxdb_url:
        return None
    return {
        "url": cfg.influxdb_url,
        "org": cfg.influxdb_org or "testhub",
        "bucket": cfg.influxdb_bucket or "jmeter",
        "token": cfg.influxdb_token or "",
        "measurement": cfg.influxdb_measurement or "jmeter",
    }


def execute(execution_id: str) -> None:
    """执行一次性能测试（同步，供后台线程调用）。"""
    from django.db import close_old_connections

    close_old_connections()
    try:
        execution = PerformanceExecution.objects.get(execution_id=execution_id)
    except PerformanceExecution.DoesNotExist:
        logger.error("性能执行记录不存在: %s", execution_id)
        return

    script = execution.script
    work_dir = _work_dir(execution_id)

    # ---- 监控采集后台线程（执行中实时落库，详情/看板/报告都能看到） ----
    _monitor_stop = threading.Event()
    _monitor_thread: Optional[threading.Thread] = None

    def _collect_monitoring(*, running: bool = False) -> int:
        from django.db import close_old_connections
        from .prometheus_client import collect_execution_monitoring
        try:
            close_old_connections()
            # 每次落库前 refresh，确保 started_at / completed_at 最新
            execution.refresh_from_db()
            collected = collect_execution_monitoring(execution, running=running)
            _push_progress()
            return collected
        except Exception as exc:
            logger.warning("监控采集异常（不阻塞）: %s", exc)
            return 0

    def _monitor_loop():
        try:
            step = max(5, (_config().prometheus_step or 15))
        except Exception:
            step = 15
        # 先立即采一次，让详情 Tab 在 started_at 后立刻有数据
        _collect_monitoring(running=True)
        while not _monitor_stop.is_set():
            if _monitor_stop.wait(step):
                break
            _collect_monitoring(running=True)

    def _start_monitor_thread():
        nonlocal _monitor_thread
        if _monitor_thread and _monitor_thread.is_alive():
            return
        _monitor_stop.clear()
        _monitor_thread = threading.Thread(
            target=_monitor_loop, name=f"PerfMonitor-{execution_id}", daemon=True
        )
        _monitor_thread.start()
        logger.info("性能执行监控线程已启动 %s", execution_id)

    def _stop_monitor_thread():
        _monitor_stop.set()
        if _monitor_thread:
            _monitor_thread.join(timeout=max(5, (_config().prometheus_step or 15) + 5))

    def _push_progress() -> None:
        """把当前执行状态（含实时指标）推给订阅方；任何异常都不影响压测。"""
        try:
            execution.refresh_from_db()
            payload: Dict[str, Any] = {
                "execution_id": execution.pk,
                "execution_no": execution.execution_id,
                "status": execution.status,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "duration": execution.duration,
                "sla_result": execution.sla_result,
                "verdict": execution.verdict,
            }
            if realtime_enabled():
                payload["realtime"] = query_realtime(execution.execution_id, window_s=60)
            push_update(execution.pk, payload)
        except Exception as exc:  # noqa: BLE001
            logger.debug("推送执行进度失败（忽略）: %s", exc)

    def _fail(msg: str):
        PerformanceExecution.objects.filter(pk=execution.pk).update(
            status="FAILED", error_message=msg, completed_at=timezone.now(),
        )
        _push_progress()
        logger.error("性能执行失败 %s: %s", execution_id, msg)
        # 失败也要把已采集到的监控数据落库，便于详情/报告展示
        _collect_monitoring(running=True)

    # 1. 校验负载上限
    err = validate_load(execution.thread_count, execution.duration)
    if err:
        _fail(err)
        return

    try:
        PerformanceExecution.objects.filter(pk=execution.pk).update(
            status="RUNNING", started_at=timezone.now(),
        )

        # 启动服务器/DB 监控后台采集线程（执行中实时刷新数据）
        _start_monitor_thread()

        # 1.5 复制 CSV 附件到工作目录，并检查是否齐全
        _copy_csv_files_to_work_dir(script, work_dir)
        # 生效配置：有环境快照用快照，否则用脚本自身配置
        effective_config = execution.config_snapshot or script.jmx_config or {}
        required_csv = _collect_csv_filenames(effective_config)
        missing = []
        for fname in required_csv:
            if not os.path.exists(os.path.join(work_dir, fname)):
                missing.append(fname)
        if missing:
            _fail(f"缺少 CSV 数据文件：{', '.join(missing)}，请先在脚本编辑页上传")
            return

        # 2. 生成/准备 JMX
        jmx_path = ""
        warnings: list = []
        backend_listener = _backend_listener_config() if execution.realtime_enabled else None
        if script.script_type == "JMX_UPLOAD":
            if not script.jmx_file:
                _fail("JMX 脚本文件缺失")
                return
            result = UploadedJMXPlanBuilder.prepare(
                script.jmx_file.path,
                thread_count=execution.thread_count,
                ramp_up=execution.ramp_up,
                duration=execution.duration,
                backend_listener=backend_listener,
                output_dir=work_dir,
            )
            if not result.get("ok"):
                _fail(result.get("error") or "JMX 准备失败")
                return
            jmx_path = result["jmx_path"]
            warnings = result.get("warnings") or []
        elif script.script_type == "JMX_RAW":
            if not script.jmx_content:
                _fail("纯 JMX 模式内容为空")
                return
            jmx_path = os.path.join(work_dir, "plan.jmx")
            with open(jmx_path, "w", encoding="utf-8") as f:
                f.write(script.jmx_content)
            # 尝试覆盖线程数等参数，并注入 Backend Listener
            try:
                UploadedJMXPlanBuilder.prepare(
                    jmx_path,
                    thread_count=execution.thread_count,
                    ramp_up=execution.ramp_up,
                    duration=execution.duration,
                    backend_listener=backend_listener,
                    output_dir=work_dir,
                )
            except Exception:
                pass
        else:
            jmx_path = JMeterPlanBuilder.build(
                effective_config,
                thread_count=execution.thread_count,
                ramp_up=execution.ramp_up,
                duration=execution.duration,
                backend_listener=backend_listener,
                output_dir=work_dir,
            )

        jtl_path = os.path.join(work_dir, "result.jtl")
        log_path = os.path.join(work_dir, "jmeter.log")
        report_dir = os.path.join(work_dir, "report")

        PerformanceExecution.objects.filter(pk=execution.pk).update(jmx_path=jmx_path, jtl_path=jtl_path)

        # 3. JMeter non-GUI 执行
        jm_cmd = _jmeter_command()
        run_cmd = [jm_cmd, "-n", "-t", jmx_path, "-l", jtl_path, "-j", log_path]
        logger.info("执行 JMeter: %s", " ".join(run_cmd))
        timeout = execution.duration + execution.ramp_up + 300
        proc = subprocess.run(
            run_cmd, capture_output=True, text=True, timeout=timeout,
            cwd=work_dir,
        )
        jmeter_log = ""
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                jmeter_log = f.read()[-20000:]
        except Exception:
            pass

        if proc.returncode != 0 and not os.path.exists(jtl_path):
            PerformanceExecution.objects.filter(pk=execution.pk).update(
                jmeter_log=jmeter_log, error_message=f"JMeter 执行失败(returncode={proc.returncode}): {proc.stderr[:1000]}",
            )
            _fail(f"JMeter 执行失败 (returncode={proc.returncode})")
            return

        PerformanceExecution.objects.filter(pk=execution.pk).update(jmeter_log=jmeter_log)

        # 4. 停止监控线程 + 最终采集（拿停止那一刻的快照，作为执行中最后一次写库）
        _stop_monitor_thread()
        _collect_monitoring(running=False)

        # 5. JTL 解析 → summary + metrics
        parsed = parse_jtl(jtl_path)
        if parsed.get("error"):
            logger.warning("JTL 解析告警: %s", parsed["error"])

        summary_data = parsed.get("summary") or {}
        if summary_data:
            PerformanceSummary.objects.update_or_create(
                execution=execution,
                defaults={
                    "total_samples": summary_data.get("total_samples", 0),
                    "error_count": summary_data.get("error_count", 0),
                    "error_rate": summary_data.get("error_rate", 0.0),
                    "avg_response_time": summary_data.get("avg", 0.0),
                    "min_response_time": summary_data.get("min", 0.0),
                    "max_response_time": summary_data.get("max", 0.0),
                    "p90": summary_data.get("p90", 0.0),
                    "p95": summary_data.get("p95", 0.0),
                    "p99": summary_data.get("p99", 0.0),
                    "throughput": summary_data.get("throughput", 0.0),
                    "data_received": summary_data.get("data_received", 0),
                    "data_sent": summary_data.get("data_sent", 0),
                },
            )

        # 清理旧 metrics
        PerformanceMetric.objects.filter(execution=execution).delete()
        metric_objs = []
        for m in parsed.get("metrics") or []:
            metric_objs.append(PerformanceMetric(
                execution=execution,
                sample_label=m.get("sample_label", "")[:500],
                sample_count=m.get("sample_count", 0),
                error_count=m.get("error_count", 0),
                error_rate=m.get("error_rate", 0.0),
                avg=m.get("avg", 0.0),
                min=m.get("min", 0.0),
                max=m.get("max", 0.0),
                p90=m.get("p90", 0.0),
                p95=m.get("p95", 0.0),
                p99=m.get("p99", 0.0),
                throughput=m.get("throughput", 0.0),
                timeline=m.get("timeline") or [],
                top_errors=m.get("top_errors") or [],
            ))
        if metric_objs:
            PerformanceMetric.objects.bulk_create(metric_objs)

        # 5.5 验收判定（SLA 阈值 + 验收目标）：脚本未配置时统一为 NOT_EVALUATED，不影响既有流程
        verdict_fields: Dict[str, Any] = {}
        try:
            from .acceptance import evaluate_acceptance

            summary_for_eval = {
                "avg_response_time": summary_data.get("avg", 0.0),
                "p90": summary_data.get("p90", 0.0),
                "p95": summary_data.get("p95", 0.0),
                "p99": summary_data.get("p99", 0.0),
                "error_rate": summary_data.get("error_rate", 0.0),
                "throughput": summary_data.get("throughput", 0.0),
            }
            verdict_fields = evaluate_acceptance(
                getattr(execution.script, "perf_targets", None),
                getattr(execution.script, "sla_config", None),
                summary_for_eval,
                parsed.get("metrics") or [],
            )
        except Exception as exc:  # 判定失败不能影响执行本身的终态
            logger.warning("验收判定失败（不阻塞）: %s", exc)

        warn_msg = "; ".join(warnings) if warnings else ""
        # 6. 终态先在内存实例上生效：报告里的「状态 / 结束时间」取的就是这个实例，
        #    若不同步，报告会在 JMeter 结束后立刻生成却拿到仍为 RUNNING 的实例，
        #    表现为「报告里状态还是执行中、结束时间缺失（回退成 JTL 推算时间）」，必须手动重新生成才正常。
        finish_at = timezone.now()
        execution.status = "COMPLETED"
        execution.completed_at = finish_at
        execution.error_message = warn_msg
        for _k, _v in verdict_fields.items():
            setattr(execution, _k, _v)

        # 7. HTML 报告（执行结束即自动生成，无需进详情页手动「重新生成报告」）
        try:
            os.makedirs(report_dir, exist_ok=True)
            # 7.1 JMeter 原生报告
            subprocess.run(
                [jm_cmd, "-g", jtl_path, "-o", report_dir],
                capture_output=True, text=True, timeout=180, cwd=work_dir,
            )
            # 7.2 自定义 TestHub 报告（独立 HTML，内置 CDN 资源，避免 iframe 路径问题）
            from .report_generator import generate_html_report
            jmeter_index = os.path.join(report_dir, "index.html")
            if os.path.exists(jmeter_index):
                # 保留 JMeter 原生报告
                os.rename(jmeter_index, os.path.join(report_dir, "index_jmeter.html"))
            custom_index = os.path.join(report_dir, "index.html")
            generate_html_report(execution, custom_index, jtl_path=jtl_path)
            if os.path.exists(custom_index):
                PerformanceExecution.objects.filter(pk=execution.pk).update(report_path=report_dir)
        except Exception as exc:
            logger.warning("HTML 报告生成失败（不阻塞）: %s", exc)

        # 8. 终态落库（报告已生成，前端刷新时状态与报告同步可见）
        PerformanceExecution.objects.filter(pk=execution.pk).update(
            status="COMPLETED", completed_at=finish_at,
            error_message=warn_msg,
            **verdict_fields,
        )
        _push_progress()
        logger.info("性能执行完成 %s", execution_id)

    except subprocess.TimeoutExpired:
        _fail("JMeter 执行超时")
    except FileNotFoundError:
        _fail(f"未找到 JMeter 命令：{ _jmeter_command() }，请在设置中配置 PERFORMANCE_JMETER_PATH")
    except Exception as exc:
        logger.exception("性能执行异常 %s", execution_id)
        _fail(str(exc)[:1000])
    finally:
        # 任何分支退出都要保证停掉监控线程
        _stop_monitor_thread()
        close_old_connections()


def push_update(execution_id: int, payload: Dict[str, Any]) -> None:
    """向 WebSocket 组推送执行更新（非阻塞）。

    channels / Redis 不可用时静默返回，前端会自动降级为轮询 /realtime/。
    注意 ``type`` 必须是 ``execution.update``（channels 会转成 consumer 的
    ``execution_update`` 方法）。
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        async_to_sync(channel_layer.group_send)(
            f"perf_execution_{execution_id}",
            {"type": "execution.update", **payload},
        )
    except Exception as exc:  # noqa: BLE001  推送失败不能影响压测本身
        logger.debug("压测 WS 推送失败（忽略）: %s", exc)


def start_execution_background(execution_id: str) -> None:
    threading.Thread(target=execute, args=(execution_id,), daemon=True).start()


def create_execution(script, *, created_by, thread_count=None, ramp_up=None, duration=None,
                     realtime_enabled=None, environment=None) -> PerformanceExecution:
    """创建执行记录并后台启动。

    指定 ``environment`` 时，会先把环境叠加到脚本配置上并存入 ``config_snapshot``，
    执行阶段优先使用该快照（未指定环境则快照为空、照旧直接用脚本配置）。
    """
    err = validate_load(thread_count or script.thread_count, duration or script.duration)
    if err:
        raise ValueError(err)

    # 仅「显式指定环境」才做叠加：避免用户建了个激活环境就悄悄改写所有人的执行目标
    snapshot = {}
    if environment is not None:
        from .environment import build_effective_config
        snapshot = build_effective_config(script.jmx_config or {}, environment)

    execution = PerformanceExecution.objects.create(
        execution_id=f"PERF_{uuid.uuid4().hex[:12].upper()}",
        script=script,
        status="QUEUED",
        thread_count=thread_count or script.thread_count,
        ramp_up=ramp_up or script.ramp_up,
        duration=duration or script.duration,
        realtime_enabled=realtime_enabled if realtime_enabled is not None else script.realtime_enabled,
        environment=environment,
        config_snapshot=snapshot,
        created_by=created_by,
    )
    start_execution_background(execution.execution_id)
    return execution


# ==================== 批量执行 ====================

def create_batch_execution(scripts, *, created_by, project=None, name="",
                           thread_count=None, ramp_up=None, duration=None, realtime_enabled=None):
    """创建批量执行记录并后台启动。"""
    from .models import PerformanceBatchExecution

    if not scripts:
        raise ValueError("至少选择一个脚本")

    batch = PerformanceBatchExecution.objects.create(
        batch_id=f"BATCH_{uuid.uuid4().hex[:12].upper()}",
        project=project,
        name=name or f"批量执行-{timezone.now().strftime('%Y%m%d_%H%M%S')}",
        status="QUEUED",
        total_scripts=len(scripts),
        thread_count=thread_count or 10,
        ramp_up=ramp_up or 5,
        duration=duration or 60,
        realtime_enabled=realtime_enabled if realtime_enabled is not None else False,
        created_by=created_by,
    )

    # 创建各脚本的执行记录
    for script in scripts:
        tc = thread_count or script.thread_count
        rp = ramp_up or script.ramp_up
        du = duration or script.duration
        err = validate_load(tc, du)
        if err:
            raise ValueError(err)
        PerformanceExecution.objects.create(
            execution_id=f"PERF_{uuid.uuid4().hex[:12].upper()}",
            script=script,
            batch=batch,
            status="QUEUED",
            thread_count=tc,
            ramp_up=rp,
            duration=du,
            realtime_enabled=realtime_enabled if realtime_enabled is not None else script.realtime_enabled,
            created_by=created_by,
        )

    # 后台执行
    threading.Thread(target=execute_batch, args=(batch.batch_id,), daemon=True).start()
    return batch


def execute_batch(batch_id: str) -> None:
    """顺序执行批次内所有脚本。"""
    from django.db import close_old_connections
    from .models import PerformanceBatchExecution

    close_old_connections()
    try:
        batch = PerformanceBatchExecution.objects.get(batch_id=batch_id)
    except PerformanceBatchExecution.DoesNotExist:
        logger.error("批量执行记录不存在: %s", batch_id)
        return

    PerformanceBatchExecution.objects.filter(pk=batch.pk).update(
        status="RUNNING",
    )

    executions = batch.executions.order_by("id").all()
    completed = 0
    failed = 0
    errors = []

    for execution in executions:
        # 逐个执行
        execute(execution.execution_id)

        # 刷新状态
        execution.refresh_from_db()
        if execution.status == "COMPLETED":
            completed += 1
        else:
            failed += 1
            errors.append(f"{execution.execution_id}: {execution.error_message[:200]}")

        # 更新批次进度
        PerformanceBatchExecution.objects.filter(pk=batch.pk).update(
            completed_scripts=completed,
            failed_scripts=failed,
        )

    # 最终状态
    if failed == 0:
        final_status = "COMPLETED"
    elif completed > 0:
        final_status = "PARTIAL"
    else:
        final_status = "FAILED"

    PerformanceBatchExecution.objects.filter(pk=batch.pk).update(
        status=final_status,
        completed_at=timezone.now(),
        error_message="; ".join(errors)[:2000] if errors else "",
    )

    # 生成项目级 HTML 报告
    try:
        from .batch_report_generator import generate_batch_report
        batch_report_dir = os.path.join(settings.MEDIA_ROOT, "performance", batch.batch_id, "report")
        os.makedirs(batch_report_dir, exist_ok=True)
        batch_report_index = os.path.join(batch_report_dir, "index.html")
        generate_batch_report(batch, batch_report_index)
        PerformanceBatchExecution.objects.filter(pk=batch.pk).update(report_path=batch_report_dir)
    except Exception as exc:
        logger.warning("批量执行项目级报告生成失败: %s", exc)

    logger.info("批量执行完成 %s: %d 成功, %d 失败", batch_id, completed, failed)
    close_old_connections()
