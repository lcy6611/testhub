"""内置压测引擎（asyncio + httpx，零外部依赖）。

设计要点：**产物写成与 JMeter 同构的 CSV JTL**，因此 `result_parser.parse_jtl`
→ 汇总/指标 → HTML 报告 → SLA/验收判定 → 基线/对照 → WebSocket 推送
整条下游链路完全复用，无需为引擎做任何分支。

适用中低并发；高并发/协议复杂场景仍建议用 JMeter。
"""
from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx

from .base import JTL_COLUMNS, BaseEngine, EngineError

logger = logging.getLogger(__name__)

#: 支持 {{var}} 与 ${var} 两种占位符（与脚本编辑页/接口测试模块一致）
PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}|\$\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}")


class BuiltinEngine(BaseEngine):
    """内置 HTTP 压测引擎。"""

    name = "BUILTIN"

    #: 单机安全上限（超过建议改用 JMeter/Locust）
    MAX_USERS = 1000
    MAX_DURATION = 3600

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event: Optional[asyncio.Event] = None
        self._lock: Optional[asyncio.Lock] = None
        self._stats = {"sent": 0, "errors": 0, "iterations": 0}

    # ------------------------------------------------------------------ #
    def prepare(self) -> None:
        steps = self._steps()
        if not steps:
            raise EngineError("内置引擎需要在脚本中至少配置一个 HTTP 请求")
        bad = [s.get("url") or "" for s in steps if not (s.get("url") or "").strip()]
        if bad:
            raise EngineError("存在未填写 URL 的请求，无法用内置引擎执行")
        users = int(self.run_opts.get("thread_count") or 1)
        if users > self.MAX_USERS:
            raise EngineError(f"内置引擎单机建议 ≤ {self.MAX_USERS} 并发，请改用 JMeter/Locust")

    def run(self) -> Dict[str, Any]:
        self.prepare()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._run_async())
        # 已在事件循环中（例如被异步上下文调用）：换到独立线程跑
        import threading

        box: Dict[str, Any] = {}

        def _worker():
            box["result"] = asyncio.run(self._run_async())

        t = threading.Thread(target=_worker, name="BuiltinEngineRun", daemon=True)
        t.start()
        t.join()
        return box.get("result") or {}

    def stop(self, graceful: bool = True) -> None:
        ev = self._stop_event
        if ev is not None:
            try:
                loop = asyncio.get_event_loop_policy().get_event_loop()
                loop.call_soon_threadsafe(ev.set)
            except Exception:  # noqa: BLE001
                pass

    def collect(self) -> Dict[str, Any]:
        info = super().collect()
        info.update(self._stats)
        return info

    # ------------------------------------------------------------------ #
    def _steps(self) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        for tg in self.config.get("thread_groups") or []:
            if not isinstance(tg, dict):
                continue
            for s in tg.get("samplers") or []:
                if isinstance(s, dict):
                    steps.append(s)
        return steps

    def _variables(self) -> Dict[str, str]:
        values: Dict[str, str] = {}
        for item in self.config.get("variables") or []:
            if isinstance(item, dict) and (item.get("name") or "").strip():
                values[item["name"].strip()] = str(item.get("value", ""))
        for tg in self.config.get("thread_groups") or []:
            for item in (tg.get("variables") or []) if isinstance(tg, dict) else []:
                if isinstance(item, dict) and (item.get("name") or "").strip():
                    values[item["name"].strip()] = str(item.get("value", ""))
        return values

    def _substitute(self, text: str, variables: Dict[str, str]) -> str:
        if not text:
            return text

        def _repl(m: re.Match) -> str:
            name = m.group(1) or m.group(2)
            return variables.get(name, m.group(0))

        return PLACEHOLDER_RE.sub(_repl, text)

    def _build_url(self, url: str, params: List[Dict[str, Any]], variables: Dict[str, str]) -> str:
        url = self._substitute(url or "", variables)
        pairs = []
        for p in params or []:
            if not isinstance(p, dict):
                continue
            name = self._substitute(str(p.get("name", "")), variables)
            if not name:
                continue
            pairs.append((name, self._substitute(str(p.get("value", "")), variables)))
        if not pairs:
            return url
        parts = urlsplit(url)
        extra = urlencode(pairs)
        query = f"{parts.query}&{extra}" if parts.query else extra
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))

    # ------------------------------------------------------------------ #
    async def _run_async(self) -> Dict[str, Any]:
        users = max(1, int(self.run_opts.get("thread_count") or 1))
        ramp_up = max(0, int(self.run_opts.get("ramp_up") or 0))
        duration = max(1, int(self.run_opts.get("duration") or 60))
        if duration > self.MAX_DURATION:
            duration = self.MAX_DURATION
        loops = self.iterations()
        steps = self._steps()
        variables = self._variables()

        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()
        started = time.time()

        os.makedirs(self.work_dir, exist_ok=True)
        jtl_path = self.jtl_path
        jtl_file = open(jtl_path, "w", encoding="utf-8", newline="")
        writer = csv.writer(jtl_file)
        writer.writerow(JTL_COLUMNS)
        jtl_file.flush()

        timeout = httpx.Timeout(60.0, connect=15.0)
        limits = httpx.Limits(max_connections=max(users * 2, 10), max_keepalive_connections=users)
        async with httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=True) as client:
            deadline = started + duration
            tasks = []
            for idx in range(users):
                delay = (ramp_up * idx / users) if ramp_up > 0 else 0
                tasks.append(asyncio.create_task(
                    self._virtual_user(client, idx, steps, variables, writer, jtl_file, deadline, loops, delay)
                ))

            async def _watch():
                """到点或收到停止信号就结束。"""
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=duration)
                except asyncio.TimeoutError:
                    pass

            watcher = asyncio.create_task(_watch())
            await asyncio.gather(*tasks, return_exceptions=True)
            watcher.cancel()

        jtl_file.flush()
        jtl_file.close()
        elapsed = round(time.time() - started, 2)
        msg = (f"内置引擎完成：{self._stats['iterations']} 轮迭代 / "
               f"{self._stats['sent']} 次请求 / {self._stats['errors']} 次失败 / 用时 {elapsed}s")
        self.log(msg)
        return {
            "returncode": 0,
            "jtl_path": jtl_path,
            "log": msg,
            "stats": dict(self._stats),
        }

    async def _virtual_user(self, client: httpx.AsyncClient, idx: int, steps: List[Dict[str, Any]],
                            variables: Dict[str, str], writer, jtl_file, deadline: float, loops: int,
                            delay: float) -> None:
        if delay:
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                return  # 等待期间已被要求停止
            except asyncio.TimeoutError:
                pass

        finished = 0
        while not self._stop_event.is_set():
            for step in steps:
                if self._stop_event.is_set():
                    break
                await self._execute_step(client, step, variables, writer, jtl_file)
            finished += 1
            async with self._lock:
                self._stats["iterations"] += 1
            if loops > 0 and finished >= loops:
                return
            if time.time() >= deadline:
                return

    async def _execute_step(self, client: httpx.AsyncClient, step: Dict[str, Any],
                            variables: Dict[str, str], writer, jtl_file) -> None:
        label = (step.get("name") or "HTTP Request")[:200]
        method = (step.get("method") or "GET").upper()
        url = self._build_url(step.get("url") or "", step.get("params") or [], variables)
        headers = {}
        for h in step.get("headers") or []:
            if isinstance(h, dict) and (h.get("name") or "").strip():
                headers[self._substitute(str(h["name"]), variables)] = self._substitute(str(h.get("value", "")), variables)
        body = self._substitute(str(step.get("body") or ""), variables)

        start = time.time()
        code = ""
        success = False
        recv = 0
        sent = len(body.encode("utf-8")) if body else 0
        try:
            resp = await client.request(method, url, headers=headers, content=body or None)
            elapsed = (time.time() - start) * 1000
            recv = len(resp.content or b"")
            sent += len(str(resp.request.headers).encode("utf-8"))
            code = str(resp.status_code)
            # 与 JMeter/Locust 对齐：HTTP 4xx/5xx 默认记为失败样本（JMeter 也是按状态码判失败），
            # 断言只能在此基础上再判失败，不能把错误码「洗白」成成功。
            status_ok = resp.status_code < 400
            success = status_ok and self._run_assertions(step.get("assertions") or [], resp)
        except Exception as exc:  # noqa: BLE001  网络异常记为失败样本
            elapsed = (time.time() - start) * 1000
            code = "0"
            success = False
            self.log(f"请求失败 {label}: {exc}")
        finally:
            self._stats["sent"] += 1
            if not success:
                self._stats["errors"] += 1
            row = [int(time.time() * 1000), int(elapsed), label, code,
                   "true" if success else "false", int(recv), int(sent)]
            async with self._lock:
                writer.writerow(row)
                jtl_file.flush()
            if self.on_sample:
                try:
                    self.on_sample({"label": label, "elapsed": elapsed, "success": success,
                                    "responseCode": code, "bytes": recv})
                except Exception:  # noqa: BLE001
                    pass

    def _run_assertions(self, assertions: List[Dict[str, Any]], resp) -> bool:
        for a in assertions or []:
            if not isinstance(a, dict):
                continue
            atype = (a.get("type") or "response_code").lower()
            expected = str(a.get("value", "")).strip()
            if atype == "response_code":
                if not expected:
                    continue
                if str(resp.status_code) != expected:
                    return False
            elif atype == "contains":
                if expected and expected not in (resp.text or ""):
                    return False
            elif atype in ("json", "json_path"):
                path = (a.get("path") or "").strip()
                if not path:
                    continue
                try:
                    data = resp.json()
                except Exception:  # noqa: BLE001
                    return False
                actual = _json_path_get(data, path)
                if actual is None or (expected and str(actual) != expected):
                    return False
        return True


def _json_path_get(data: Any, path: str) -> Any:
    """极简 JSONPath：支持 ``$.a.b[0].c`` 这类取值。"""
    expr = path.strip()
    if expr.startswith("$"):
        expr = expr[1:]
    cur = data
    for token in re.findall(r"\.([^.\[\]]+)|\[(\d+)\]", expr):
        key, index = token
        try:
            if key:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(key)
            else:
                if not isinstance(cur, list):
                    return None
                cur = cur[int(index)]
        except (KeyError, IndexError, TypeError):
            return None
    return cur


def debug_run(config: Dict[str, Any], run_opts: Dict[str, Any], work_dir: str) -> Dict[str, Any]:
    """调试入口：同步跑一次内置引擎（自检命令用）。"""
    return BuiltinEngine(config, run_opts, work_dir).run()
