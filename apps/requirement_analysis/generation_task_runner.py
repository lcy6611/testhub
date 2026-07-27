"""测试用例生成任务后台执行（generate 接口与知识库对话一键生成共用）。"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Dict

from asgiref.sync import async_to_sync
from django.db import close_old_connections
from django.utils import timezone

from .models import AIModelService, GenerationConfig, TestCaseGenerationTask

logger = logging.getLogger(__name__)


def _resolve_generation_options() -> tuple[bool, int | None]:
    gen_cfg = GenerationConfig.get_active_config()
    enable_auto_review = True
    if gen_cfg and gen_cfg.enable_auto_review is not None:
        enable_auto_review = bool(gen_cfg.enable_auto_review)
    review_timeout_s = None
    if gen_cfg and getattr(gen_cfg, "review_timeout", None):
        try:
            review_timeout_s = int(gen_cfg.review_timeout)
        except Exception:
            review_timeout_s = None
    return enable_auto_review, review_timeout_s


def run_generation_task(task_pk: int) -> None:
    """同步执行单个生成任务（供后台线程调用）。"""
    enable_auto_review, review_timeout_s = _resolve_generation_options()
    close_old_connections()
    try:
        t = TestCaseGenerationTask.objects.select_related(
            "writer_model_config",
            "reviewer_model_config",
            "writer_prompt_config",
            "reviewer_prompt_config",
            "source_document",
        ).get(pk=task_pk)
        _ = t.writer_model_config
        _ = t.writer_prompt_config
        _ = t.reviewer_model_config
        _ = t.reviewer_prompt_config
        _ = t.source_document
    except Exception as e:
        logger.exception("后台生成线程获取任务失败: %s", e)
        close_old_connections()
        return

    _stream_buf = t.stream_buffer or ""
    _last_flush = 0.0
    _pending_chars = 0

    def _flush(force: bool = False):
        nonlocal _stream_buf, _last_flush, _pending_chars
        now = time.time()
        if not force:
            if (now - _last_flush) < 0.2 and _pending_chars < 4096:
                return
        close_old_connections()
        TestCaseGenerationTask.objects.filter(pk=task_pk).update(
            stream_buffer=_stream_buf,
            last_stream_update=timezone.now(),
        )
        _last_flush = now
        _pending_chars = 0

    def _append_event(payload: Dict[str, Any], *, flush: bool = False):
        nonlocal _stream_buf, _pending_chars
        line = json.dumps(payload, ensure_ascii=False)
        if _stream_buf and not _stream_buf.endswith("\n"):
            _stream_buf += "\n"
            _pending_chars += 1
        _stream_buf += line
        _pending_chars += len(line)
        _flush(force=flush)

    def _record_ai_call_meta(phase: str):
        meta = AIModelService.pop_last_call_meta()
        if not meta:
            return
        entry = json.dumps({"phase": phase, **meta}, ensure_ascii=False)
        close_old_connections()
        task_obj = TestCaseGenerationTask.objects.filter(pk=task_pk).only("generation_log").first()
        if not task_obj:
            return
        prev = (task_obj.generation_log or "").strip()
        new_log = f"{prev}\n{entry}".strip() if prev else entry
        TestCaseGenerationTask.objects.filter(pk=task_pk).update(generation_log=new_log)
        # #261 成本观测：需求生成是最大 AI 消耗，落库 tokens/cost
        try:
            from apps.ai_eval.calllog import record_ai_call
            usage = meta.get("usage") or {}
            record_ai_call(
                module="requirement_analysis",
                feature=f"generate:{phase}",
                model_name=meta.get("model") or "",
                user_id=getattr(t, "created_by_id", None),
                input_tokens=usage.get("prompt_tokens", 0) or 0,
                output_tokens=usage.get("completion_tokens", 0) or 0,
                total_tokens=usage.get("total_tokens", 0) or 0,
                status="success",
            )
        except Exception:
            pass

    try:
        TestCaseGenerationTask.objects.filter(pk=task_pk).update(
            status="generating",
            progress=10,
            last_stream_update=timezone.now(),
        )
        _append_event({"type": "progress", "status": "generating", "progress": 10}, flush=True)

        if t.output_mode == "stream":

            def on_chunk_writer(ch: str):
                _append_event({"type": "content", "content": ch})

            generated = async_to_sync(AIModelService.generate_test_cases_stream)(t, on_chunk_writer)
        else:
            generated = async_to_sync(AIModelService.generate_test_cases)(t)
        _record_ai_call_meta("generate")

        next_status = (
            "reviewing"
            if enable_auto_review and t.reviewer_model_config_id and t.reviewer_prompt_config_id
            else "completed"
        )
        TestCaseGenerationTask.objects.filter(pk=task_pk).update(
            generated_test_cases=(generated or ""),
            progress=60,
            status=next_status,
        )

        if next_status == "reviewing":
            if review_timeout_s is None:
                timeout_s = 3600
            else:
                timeout_s = int(review_timeout_s)
            if timeout_s > 0 and timeout_s < 600:
                timeout_s = 3600

            review = ""
            review_failed = False
            try:
                if t.output_mode == "stream":
                    TestCaseGenerationTask.objects.filter(pk=task_pk).update(progress=70, status="reviewing")
                    _append_event({"type": "progress", "status": "reviewing", "progress": 70}, flush=True)

                    def on_chunk_review(ch: str):
                        _append_event({"type": "review_content", "content": ch})

                    review = async_to_sync(AIModelService.review_test_cases_stream)(
                        t, (generated or ""), on_chunk_review
                    )
                else:
                    TestCaseGenerationTask.objects.filter(pk=task_pk).update(progress=70, status="reviewing")
                    review = async_to_sync(AIModelService.review_test_cases)(t, (generated or ""))
                _record_ai_call_meta("review")
                TestCaseGenerationTask.objects.filter(pk=task_pk).update(review_feedback=(review or ""))
            except Exception as review_exc:
                review_failed = True
                logger.exception("评审阶段失败，回退为初稿: %s", review_exc)
                _append_event(
                    {
                        "type": "warning",
                        "message": f"评审阶段失败，已保留 AI 初稿供下载与继续处理：{review_exc}",
                    },
                    flush=True,
                )

            if review_failed:
                final = generated or ""
                TestCaseGenerationTask.objects.filter(pk=task_pk).update(final_test_cases=final)
            elif t.output_mode == "stream":
                TestCaseGenerationTask.objects.filter(pk=task_pk).update(progress=85, status="revising")
                _append_event({"type": "progress", "status": "revising", "progress": 85}, flush=True)

                def on_chunk_final(ch: str):
                    _append_event({"type": "final_content", "content": ch})

                try:
                    final = async_to_sync(AIModelService.revise_test_cases_stream)(
                        t, (generated or ""), (review or ""), on_chunk_final
                    )
                    _record_ai_call_meta("revise")
                except Exception as revise_exc:
                    logger.exception("最终版用例生成失败，回退为初稿: %s", revise_exc)
                    final = generated or ""
                    _append_event(
                        {"type": "warning", "message": f"最终版生成失败，已保留初稿：{revise_exc}"},
                        flush=True,
                    )
                TestCaseGenerationTask.objects.filter(pk=task_pk).update(final_test_cases=(final or ""))
            else:
                TestCaseGenerationTask.objects.filter(pk=task_pk).update(progress=85, status="revising")
                try:
                    final = async_to_sync(AIModelService.revise_test_cases)(t, (generated or ""), (review or ""))
                    _record_ai_call_meta("revise")
                except Exception as revise_exc:
                    logger.exception("最终版用例生成失败，回退为初稿: %s", revise_exc)
                    final = generated or ""
                    _append_event(
                        {"type": "warning", "message": f"最终版生成失败，已保留初稿：{revise_exc}"},
                        flush=True,
                    )
                TestCaseGenerationTask.objects.filter(pk=task_pk).update(final_test_cases=(final or ""))

        if next_status != "reviewing":
            TestCaseGenerationTask.objects.filter(pk=task_pk).update(final_test_cases=(generated or ""))

        TestCaseGenerationTask.objects.filter(pk=task_pk).update(
            status="completed",
            progress=100,
            completed_at=timezone.now(),
        )
        _append_event({"type": "status", "status": "completed"})
        _append_event({"type": "done"}, flush=True)
    except Exception as e:
        try:
            task_row = TestCaseGenerationTask.objects.filter(pk=task_pk).only(
                "generated_test_cases", "final_test_cases"
            ).first()
            draft = ""
            if task_row:
                draft = (task_row.generated_test_cases or task_row.final_test_cases or "").strip()
            if draft:
                TestCaseGenerationTask.objects.filter(pk=task_pk).update(
                    status="completed",
                    final_test_cases=draft,
                    error_message=f"部分阶段失败：{e}",
                    completed_at=timezone.now(),
                    progress=100,
                )
                _append_event(
                    {
                        "type": "warning",
                        "message": f"部分阶段失败，已保留可用初稿：{e}",
                    },
                    flush=True,
                )
                _append_event({"type": "status", "status": "completed"})
                _append_event({"type": "done"}, flush=True)
            else:
                TestCaseGenerationTask.objects.filter(pk=task_pk).update(
                    status="failed",
                    error_message=str(e),
                    completed_at=timezone.now(),
                )
                _append_event({"type": "status", "status": "failed", "error_message": str(e)})
                _append_event({"type": "done"}, flush=True)
        except Exception:
            pass
        logger.exception("后台生成任务失败: %s", e)
    finally:
        try:
            _flush(force=True)
        except Exception:
            pass
        close_old_connections()


def start_generation_task_background(task_pk: int) -> None:
    threading.Thread(target=run_generation_task, args=(task_pk,), daemon=True).start()


def _reindex_generation_task_graph(task_pk: int) -> None:
    """继续优化/生成完成后刷新任务节点属性与关联边。"""
    try:
        from apps.knowledge_graph.builder import index_generation_task

        task_fresh = (
            TestCaseGenerationTask.objects.select_related("created_by").filter(pk=task_pk).first()
        )
        if task_fresh:
            index_generation_task(task_fresh, created_by=task_fresh.created_by)
    except Exception as exc:
        logger.warning("图谱 re-index 失败: %s", exc, exc_info=True)


def run_refinement_task(task_pk: int, refinement_instructions: str) -> None:
    """在已有用例基础上按用户补充要求迭代修改（默认跳过评审环节）。"""
    close_old_connections()
    try:
        t = TestCaseGenerationTask.objects.select_related(
            "writer_model_config",
            "writer_prompt_config",
            "source_document",
        ).get(pk=task_pk)
        _ = t.writer_model_config
        _ = t.writer_prompt_config
        _ = t.source_document
    except Exception as e:
        logger.exception("迭代优化线程获取任务失败: %s", e)
        close_old_connections()
        return

    existing = (t.final_test_cases or t.generated_test_cases or "").strip()
    if not existing:
        TestCaseGenerationTask.objects.filter(pk=task_pk).update(
            status="failed",
            error_message="当前任务无可用用例，无法继续优化",
            completed_at=timezone.now(),
        )
        close_old_connections()
        return

    _stream_buf = t.stream_buffer or ""
    _last_flush = 0.0
    _pending_chars = 0

    def _flush(force: bool = False):
        nonlocal _stream_buf, _last_flush, _pending_chars
        now = time.time()
        if not force:
            if (now - _last_flush) < 0.2 and _pending_chars < 4096:
                return
        close_old_connections()
        TestCaseGenerationTask.objects.filter(pk=task_pk).update(
            stream_buffer=_stream_buf,
            last_stream_update=timezone.now(),
        )
        _last_flush = now
        _pending_chars = 0

    def _append_event(payload: Dict[str, Any], *, flush: bool = False):
        nonlocal _stream_buf, _pending_chars
        line = json.dumps(payload, ensure_ascii=False)
        if _stream_buf and not _stream_buf.endswith("\n"):
            _stream_buf += "\n"
            _pending_chars += 1
        _stream_buf += line
        _pending_chars += len(line)
        _flush(force=flush)

    def _record_ai_call_meta(phase: str):
        meta = AIModelService.pop_last_call_meta()
        if not meta:
            return
        entry = json.dumps({"phase": phase, **meta}, ensure_ascii=False)
        close_old_connections()
        task_obj = TestCaseGenerationTask.objects.filter(pk=task_pk).only("generation_log").first()
        if not task_obj:
            return
        prev = (task_obj.generation_log or "").strip()
        new_log = f"{prev}\n{entry}".strip() if prev else entry
        TestCaseGenerationTask.objects.filter(pk=task_pk).update(generation_log=new_log)
        # #261 成本观测：需求生成是最大 AI 消耗，落库 tokens/cost
        try:
            from apps.ai_eval.calllog import record_ai_call
            usage = meta.get("usage") or {}
            record_ai_call(
                module="requirement_analysis",
                feature=f"generate:{phase}",
                model_name=meta.get("model") or "",
                user_id=getattr(t, "created_by_id", None),
                input_tokens=usage.get("prompt_tokens", 0) or 0,
                output_tokens=usage.get("completion_tokens", 0) or 0,
                total_tokens=usage.get("total_tokens", 0) or 0,
                status="success",
            )
        except Exception:
            pass

    try:
        TestCaseGenerationTask.objects.filter(pk=task_pk).update(
            status="generating",
            progress=15,
            last_stream_update=timezone.now(),
        )
        _append_event({"type": "progress", "status": "generating", "progress": 15, "message": "继续优化用例"}, flush=True)

        if t.output_mode == "stream":

            def on_chunk(ch: str):
                _append_event({"type": "content", "content": ch})

            refined = async_to_sync(AIModelService.continue_refine_test_cases_stream)(
                t, existing, refinement_instructions, on_chunk
            )
        else:
            refined = async_to_sync(AIModelService.continue_refine_test_cases)(
                t, existing, refinement_instructions
            )
        _record_ai_call_meta("continue_refine")

        refined = (refined or "").strip() or existing
        TestCaseGenerationTask.objects.filter(pk=task_pk).update(
            generated_test_cases=refined,
            final_test_cases=refined,
            review_feedback="",
            progress=100,
            status="completed",
            completed_at=timezone.now(),
            error_message="",
        )
        _append_event({"type": "status", "status": "completed"})
        _append_event({"type": "done"}, flush=True)

        _reindex_generation_task_graph(task_pk)
    except Exception as e:
        try:
            TestCaseGenerationTask.objects.filter(pk=task_pk).update(
                status="failed",
                error_message=str(e),
                completed_at=timezone.now(),
            )
        except Exception:
            pass
        logger.exception("迭代优化任务失败: %s", e)
        try:
            _append_event({"type": "status", "status": "failed", "error_message": str(e)})
            _append_event({"type": "done"}, flush=True)
        except Exception:
            pass
    finally:
        try:
            _flush(force=True)
        except Exception:
            pass
        close_old_connections()


def start_refinement_task_background(task_pk: int, refinement_instructions: str) -> None:
    threading.Thread(
        target=run_refinement_task,
        args=(task_pk, refinement_instructions),
        daemon=True,
    ).start()
