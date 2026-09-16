"""Locust 压测引擎（需要 ``pip install locust``）。

实现方式：按脚本配置**动态生成 locustfile**，用 ``locust --headless`` 跑，
并通过 ``events.request`` 钩子把每个请求写成与 JMeter 同构的 CSV JTL，
因此下游解析/报告/判定链路与内置引擎完全一致。

⚠️ 本镜像默认**未安装 locust**（与开源版一致，未写入依赖清单）。
未安装时 ``is_available()`` 返回 False，前端会置灰该选项、执行前会被拦截。
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

from .base import BaseEngine, EngineError

LOCUSTFILE_NAME = "locustfile_generated.py"

#: locustfile 模板：任务与 JTL 记录钩子都由脚本配置驱动
_LOCUSTFILE_TEMPLATE = '''# -*- coding: utf-8 -*-
"""由 TestHub 性能模块自动生成，请勿手工修改。"""
import csv
import os
import time

from locust import HttpUser, task, events

JTL_PATH = {jtl_path!r}
STEPS = {steps!r}
#: >0 表示「按循环次数跑」：达到该请求数即主动停止（users × loops × 每轮请求数）
TARGET_REQUESTS = {target_requests!r}

_fh = None
_writer = None
_env = None
_count = 0


@events.init.add_listener
def _open_jtl(environment, **kwargs):
    global _fh, _writer, _env
    _env = environment
    os.makedirs(os.path.dirname(JTL_PATH), exist_ok=True)
    _fh = open(JTL_PATH, "w", encoding="utf-8", newline="")
    _writer = csv.writer(_fh)
    _writer.writerow(["timeStamp", "elapsed", "label", "responseCode", "success", "bytes", "sentBytes"])
    _fh.flush()


@events.quit.add_listener
def _close_jtl(exit_code, **kwargs):
    if _fh:
        _fh.flush()
        _fh.close()


@events.request.add_listener
def _record(request_type, name, response_time, response_length, exception, **kwargs):
    global _count
    if _writer is None:
        return
    code = ""
    if getattr(exception, "response", None) is not None:
        code = str(getattr(exception.response, "status_code", ""))
    ok = exception is None
    if ok:
        code = "200"
    _writer.writerow([int(time.time() * 1000), int(response_time or 0), name,
                      code, "true" if ok else "false", int(response_length or 0), 0])
    _fh.flush()

    _count += 1
    if TARGET_REQUESTS and _count >= TARGET_REQUESTS:
        runner = getattr(_env, "runner", None)
        if runner is not None:
            runner.quit()


class TestHubUser(HttpUser):
    @task
    def run_all_steps(self):
        for step in STEPS:
            with self.client.request(
                step["method"], step["url"], headers=step.get("headers") or None,
                data=step.get("body") or None, name=step["name"],
                catch_response=True,
            ) as resp:
                if not _assert_ok(step.get("assertions") or [], resp):
                    resp.failure("断言未通过")


def _assert_ok(assertions, resp):
    for a in assertions:
        atype = (a.get("type") or "response_code").lower()
        expected = str(a.get("value", "")).strip()
        if atype == "response_code" and expected and str(resp.status_code) != expected:
            return False
        if atype == "contains" and expected and expected not in (resp.text or ""):
            return False
    return True
'''


def is_available() -> bool:
    """locust 是否已安装（供引擎状态接口与自检命令使用）。"""
    import importlib.util

    return importlib.util.find_spec("locust") is not None


def get_version() -> str:
    """取 locust 版本。

    ⚠️ 这里**必须避免 import locust**：locust 导入时会做 gevent monkey-patching
    （会警告 "Monkey-patching ssl after ssl has already been imported"），
    而本函数会被引擎状态接口在 Web 服务进程（daphne）与测试进程里调用，
    一旦污染主进程会破坏 Django 的线程内数据库连接管理
    （表现为 DatabaseWrapper objects created in a thread can only be used in that same thread）。
    改用 importlib.metadata 只读包元数据，不触发任何导入。
    """
    if not is_available():
        return ""
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("locust")
    except PackageNotFoundError:
        return "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


class LocustEngine(BaseEngine):
    """Locust 引擎。"""

    name = "LOCUST"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._proc: Optional[subprocess.Popen] = None

    def prepare(self) -> None:
        if not is_available():
            raise EngineError("未安装 locust，请先 pip install locust 或改用内置/JMeter 引擎")
        if not self._steps():
            raise EngineError("Locust 引擎需要在脚本中至少配置一个 HTTP 请求")

    def run(self) -> Dict[str, Any]:
        self.prepare()
        steps = self._steps()

        users = max(1, int(self.run_opts.get("thread_count") or 1))
        ramp_up = max(1, int(self.run_opts.get("ramp_up") or 1))
        duration = max(1, int(self.run_opts.get("duration") or 60))
        host = self._host(steps[0].get("url") or "")
        loops = self.iterations()
        # 按循环次数跑：达到 users × loops × 每轮请求数 就由 locustfile 主动 quit；
        # 此时 -t 仅作为兜底上限（避免异常情况下永不退出）。
        target_requests = users * loops * len(steps) if loops > 0 else 0

        locustfile = os.path.join(self.work_dir, LOCUSTFILE_NAME)
        os.makedirs(self.work_dir, exist_ok=True)
        with open(locustfile, "w", encoding="utf-8") as f:
            f.write(_LOCUSTFILE_TEMPLATE.format(
                jtl_path=self.jtl_path, steps=steps, target_requests=target_requests))

        cmd = [
            sys.executable, "-m", "locust", "-f", locustfile,
            "--headless", "-u", str(users), "-r", str(ramp_up),
            "-t", f"{duration}s", "--host", host, "--only-summary",
        ]
        self.log("执行 Locust: " + " ".join(cmd))
        out, returncode = "", -1
        try:
            self._proc = subprocess.Popen(cmd, cwd=self.work_dir, stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, text=True)
            out, _ = self._proc.communicate(timeout=duration + 300)
            returncode = self._proc.returncode
        except subprocess.TimeoutExpired:
            self.stop()
            return {"returncode": -1, "jtl_path": self.jtl_path, "log": "Locust 执行超时"}
        except Exception as exc:  # noqa: BLE001
            return {"returncode": -1, "jtl_path": self.jtl_path, "log": f"Locust 执行异常：{exc}"}
        finally:
            self._proc = None
        return {"returncode": returncode, "jtl_path": self.jtl_path,
                "log": (out or "")[-2000:]}

    def stop(self, graceful: bool = True) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ #
    def _steps(self) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        for tg in self.config.get("thread_groups") or []:
            if not isinstance(tg, dict):
                continue
            for s in tg.get("samplers") or []:
                if not isinstance(s, dict):
                    continue
                url = (s.get("url") or "").strip()
                if not url:
                    continue
                headers = {}
                for h in s.get("headers") or []:
                    if isinstance(h, dict) and (h.get("name") or "").strip():
                        headers[str(h["name"])] = str(h.get("value", ""))
                steps.append({
                    "name": (s.get("name") or "HTTP Request")[:200],
                    "method": (s.get("method") or "GET").upper(),
                    "url": url,
                    "headers": headers,
                    "body": str(s.get("body") or ""),
                    "assertions": s.get("assertions") or [],
                })
        return steps

    @staticmethod
    def _host(url: str) -> str:
        from urllib.parse import urlsplit

        parts = urlsplit(url)
        if parts.scheme and parts.netloc:
            return f"{parts.scheme}://{parts.netloc}"
        return "http://127.0.0.1"


def debug_run(config: Dict[str, Any], run_opts: Dict[str, Any], work_dir: str) -> Dict[str, Any]:
    return LocustEngine(config, run_opts, work_dir).run()


def locust_available() -> bool:
    return is_available()


__all__ = ["LocustEngine", "is_available", "get_version", "debug_run", "locust_available"]
