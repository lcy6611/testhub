# -*- coding: utf-8 -*-
"""AI 评测与反馈闭环 — 业务逻辑。"""
import json
import time
import asyncio
import threading
import logging

from django.db.models import Sum, Count, Avg
from django.utils import timezone
import datetime

from .calllog import estimate_cost

logger = logging.getLogger(__name__)


def aggregate_stats(project_id=None, days=30):
    """聚合 AI 调用观测 + 评测汇总，供效果看板使用。"""
    from .models import AICallLog, EvalRun

    since = timezone.now() - datetime.timedelta(days=days)
    qs = AICallLog.objects.filter(created_at__gte=since)
    if project_id:
        qs = qs.filter(project_id=project_id)

    totals = qs.aggregate(
        calls=Count("id"),
        in_tok=Sum("input_tokens"),
        out_tok=Sum("output_tokens"),
        total_tok=Sum("total_tokens"),
        cost=Sum("cost"),
        avg_latency=Avg("latency_ms"),
    )
    calls = totals["calls"] or 0
    success = qs.filter(status="success").count()

    by_module = list(
        qs.values("module").annotate(
            calls=Count("id"), tokens=Sum("total_tokens"), cost=Sum("cost")
        ).order_by("-calls")
    )
    # 用 DATE(created_at) 避免 MySQL CONVERT_TZ 对时区表的依赖
    by_day = list(
        qs.extra(select={"day": "DATE(created_at)"})
        .values("day")
        .annotate(calls=Count("id"), tokens=Sum("total_tokens"), cost=Sum("cost"))
        .order_by("day")
    )
    for d in by_day:
        d["day"] = str(d["day"]) if d["day"] is not None else None

    runs = EvalRun.objects.filter(created_at__gte=since)
    if project_id:
        runs = runs.filter(dataset__project_id=project_id)
    eval_summary = list(runs.values("status").annotate(cnt=Count("id")))
    last_run = runs.exclude(summary="").order_by("-finished_at").first()
    latest_eval = last_run.get_summary() if last_run else {}

    return {
        "totals": {
            "calls": calls,
            "input_tokens": totals["in_tok"] or 0,
            "output_tokens": totals["out_tok"] or 0,
            "total_tokens": totals["total_tok"] or 0,
            "cost": round(float(totals["cost"] or 0.0), 4),
            "avg_latency_ms": int(totals["avg_latency"] or 0),
            "success_rate": round(success / calls, 4) if calls else 1.0,
        },
        "by_module": by_module,
        "by_day": by_day,
        "eval_summary": eval_summary,
        "latest_eval": latest_eval,
    }


async def _judge_case(config, case, output):
    """用 LLM 当裁判，对输出按期望/标准判分。返回 dict。"""
    from apps.requirement_analysis.models import AIModelService

    rubric = []
    if case.expected_output:
        rubric.append(f"期望输出参考：\n{case.expected_output}")
    if case.criteria:
        rubric.append(f"判分标准：\n{case.criteria}")
    rubric_text = "\n".join(rubric) if rubric else "请从准确性、完整性、可用性角度评价该输出。"

    judge_prompt = (
        "你是严格的测试 AI 质量评审。请基于判分依据对【模型输出】打分。\n"
        "只返回一个 JSON 对象，不要有其他文字，格式：\n"
        '{"score": <0-100整数>, "passed": <true/false>, "reason": "<简短理由>"}\n\n'
        f"判分依据：\n{rubric_text}\n\n"
        f"原始输入：\n{case.input_text}\n\n"
        f"模型输出：\n{output}"
    )
    messages = [{"role": "user", "content": judge_prompt}]
    resp = await AIModelService.call_openai_compatible_api(config, messages)
    text = resp.get("choices", [{}])[0].get("message", {}).get("content", "") if isinstance(resp, dict) else ""
    return _parse_judge(text)


def _parse_judge(text):
    """从模型文本中解析 JSON 判分结果。"""
    if not text:
        return {"score": None, "passed": None, "reason": "无判分输出"}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"score": None, "passed": None, "reason": text[:200]}
    try:
        obj = json.loads(text[start:end + 1])
        score = obj.get("score")
        passed = obj.get("passed")
        if isinstance(passed, str):
            passed = passed.strip().lower() in ("true", "1", "yes", "通过")
        return {
            "score": float(score) if score is not None else None,
            "passed": bool(passed) if passed is not None else None,
            "reason": str(obj.get("reason", ""))[:500],
        }
    except Exception:
        return {"score": None, "passed": None, "reason": text[:200]}


def run_eval_sync(run_id):
    """评测运行 worker（在独立线程中执行，避免阻塞请求）。"""
    from .models import EvalRun, EvalResult
    from apps.requirement_analysis.models import AIModelService

    run = EvalRun.objects.get(id=run_id)
    run.status = "running"
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])

    total_score = 0.0
    scored = 0
    passed_cnt = 0
    tok_total = 0
    cost_total = 0.0

    try:
        cfg = run.model_config
        prompt = run.prompt_version.content if run.prompt_version else ""
        cases = list(run.dataset.cases.all())
        run.total = len(cases)
        run.save(update_fields=["total"])

        for case in cases:
            t0 = time.monotonic()
            messages = [
                {"role": "system", "content": prompt or "你是一个专业的测试助手。"},
                {"role": "user", "content": case.input_text},
            ]
            resp = asyncio.run(
                AIModelService.call_openai_compatible_api(
                    cfg,
                    messages,
                    meta={
                        "module": "ai_eval",
                        "feature": "eval_run",
                        "project_id": run.dataset.project_id,
                    },
                )
            )
            usage = resp.get("usage") or {} if isinstance(resp, dict) else {}
            content = ""
            if isinstance(resp, dict):
                content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
            latency = int((time.monotonic() - t0) * 1000)
            in_tok = usage.get("prompt_tokens", 0) or 0
            out_tok = usage.get("completion_tokens", 0) or 0
            tt = usage.get("total_tokens", 0) or (in_tok + out_tok)
            cost = estimate_cost(cfg.model_name, in_tok, out_tok)

            score = None
            passed = None
            note = ""
            scored_by = ""
            if case.expected_output or case.criteria:
                try:
                    jr = asyncio.run(_judge_case(cfg, case, content))
                    score = jr.get("score")
                    passed = jr.get("passed")
                    note = jr.get("reason", "")
                    scored_by = "auto"
                except Exception as e:  # pragma: no cover
                    note = f"自动判分失败: {e}"

            if score is not None:
                total_score += score
                scored += 1
            if passed:
                passed_cnt += 1
            tok_total += tt
            cost_total += cost

            EvalResult.objects.update_or_create(
                run=run,
                case=case,
                defaults={
                    "output": content,
                    "score": score,
                    "passed": passed,
                    "judge_note": note,
                    "scored_by": scored_by,
                    "latency_ms": latency,
                    "tokens": tt,
                    "cost": cost,
                },
            )

        pass_rate = round(passed_cnt / len(cases), 4) if cases else 0.0
        avg_score = round(total_score / scored, 2) if scored else 0.0
        summary = {
            "total": len(cases),
            "scored": scored,
            "passed": passed_cnt,
            "pass_rate": pass_rate,
            "avg_score": avg_score,
            "total_tokens": tok_total,
            "total_cost": round(cost_total, 4),
        }
        run.summary = json.dumps(summary, ensure_ascii=False)
        run.status = "completed"
        run.finished_at = timezone.now()
        run.save(update_fields=["summary", "status", "finished_at"])
    except Exception as e:  # pragma: no cover
        logger.exception("eval run %s failed", run_id)
        run.status = "failed"
        run.error = str(e)[:1000]
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "finished_at"])


def start_eval_thread(run_id):
    """在后台线程启动评测，立即返回。"""
    t = threading.Thread(target=run_eval_sync, args=(run_id,), daemon=True)
    t.start()
