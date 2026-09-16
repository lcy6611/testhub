"""压测引擎工厂与状态探测。

| 引擎    | 运行期依赖                       | 产物            |
|---------|---------------------------------|-----------------|
| BUILTIN | 无（asyncio + httpx）            | CSV JTL         |
| LOCUST  | pip 包 locust                    | CSV JTL（钩子写）|
| JMETER  | java + JMeter 发行包             | JTL（原有链路）  |

三个引擎的可用性由**环境**决定，`engine_status()` 是唯一真相源：
前端据此置灰下拉项，执行前据此拦截。JMeter 走 executor 原有的子进程链路（不经由引擎类），
其余两个引擎的产物统一是 CSV JTL，下游链路完全复用。
"""
from __future__ import annotations

import os
import shutil
import threading
import time
from typing import Any, Dict, List, Optional

from .base import JTL_COLUMNS, BaseEngine, EngineError
from .builtin import BuiltinEngine, debug_run
from .locust_engine import LocustEngine, get_version as locust_version, is_available as locust_available

#: 引擎名 -> 引擎类（JMETER 为 None：走 executor 原有 JMeter 链路）
ENGINES: Dict[str, Optional[type]] = {
    "BUILTIN": BuiltinEngine,
    "LOCUST": LocustEngine,
    "JMETER": None,
}

ENGINE_CHOICES = [
    ("JMETER", "JMeter"),
    ("BUILTIN", "内置引擎"),
    ("LOCUST", "Locust"),
]

#: engine_status 结果缓存（TTL）。jmeter --version 要拉起 JVM，现场探测耗时数秒，
#: 前端轮询会把页面拖卡；短 TTL 既能保性能，又能让运维临时装好引擎后很快生效。
_STATUS_TTL_SECONDS = 15
_status_cache: Dict[str, Any] = {"ts": 0.0, "data": None}
_status_lock = threading.Lock()


def normalize(name: Optional[str]) -> str:
    """归一化引擎名，未知值回退 JMETER（保持历史行为）。"""
    key = (name or "").strip().upper()
    return key if key in ENGINES else "JMETER"


def get_engine_class(name: str):
    key = normalize(name)
    klass = ENGINES.get(key)
    if klass is None:
        raise EngineError(f"引擎 {key} 不走引擎类（由 executor 原有链路处理）")
    return klass


def jmeter_bin() -> str:
    """JMeter 可执行文件路径（设置优先，其次 PATH）。"""
    try:
        from django.conf import settings

        configured = getattr(settings, "PERFORMANCE_JMETER_PATH", "") or ""
    except Exception:  # noqa: BLE001
        configured = ""
    if configured:
        return configured
    return shutil.which("jmeter") or ""


def jmeter_available() -> bool:
    path = jmeter_bin()
    if not path:
        return False
    if os.path.isabs(path) or os.sep in path:
        return os.path.exists(path)
    return bool(shutil.which(path))


def jmeter_version() -> str:
    if not jmeter_available():
        return ""
    import subprocess

    try:
        out = subprocess.run([jmeter_bin(), "--version"], capture_output=True, text=True, timeout=30)
        text = (out.stdout or "") + "\n" + (out.stderr or "")
        # JMeter --version 先打一堆 WARN 和 ASCII banner，版本号是拼在 banner 末尾的（如 "... \_\ 5.6.3"），
        # 所以先剔除日志行，再全文本抓第一个 x.y[.z] 形态的版本号。
        import re as _re

        cleaned = "\n".join(
            line for line in text.splitlines()
            if not line.strip().startswith(("WARN", "INFO", "ERROR", "DEBUG"))
        )
        match = _re.search(r"\b(\d+\.\d+(?:\.\d+)?)\b", cleaned)
        return match.group(1) if match else ""
    except Exception:  # noqa: BLE001
        return ""


def engine_status(force: bool = False) -> List[Dict[str, Any]]:
    """引擎健康检查（供 /engines/status/ 与自检命令使用），带短 TTL 缓存。"""
    now = time.monotonic()
    with _status_lock:
        if not force and _status_cache["data"] is not None and now - _status_cache["ts"] < _STATUS_TTL_SECONDS:
            return _status_cache["data"]

    data = [
        {
            "name": "JMETER",
            "label": "JMeter",
            "available": jmeter_available(),
            "version": jmeter_version() or "unknown",
            "default": True,
            "description": "需 java + JMeter 发行包；协议覆盖广，可复用既有 .jmx 资产",
        },
        {
            "name": "BUILTIN",
            "label": "内置引擎 (asyncio + httpx)",
            "available": True,
            "version": "built-in",
            "default": False,
            "description": "零依赖，适合中小并发（建议 ≤ 1000 并发）",
        },
        {
            "name": "LOCUST",
            "label": "Locust",
            "available": locust_available(),
            "version": locust_version() or "未安装",
            "default": False,
            "description": "需 pip install locust（镜像默认不带），适合更大并发与后续分布式扩展",
        },
    ]

    with _status_lock:
        _status_cache["ts"] = time.monotonic()
        _status_cache["data"] = data
    return data


def available_engines() -> List[str]:
    return [item["name"] for item in engine_status() if item["available"]]


__all__ = [
    "BaseEngine", "EngineError", "BuiltinEngine", "LocustEngine",
    "ENGINES", "ENGINE_CHOICES", "JTL_COLUMNS",
    "normalize", "get_engine_class", "engine_status", "available_engines",
    "jmeter_available", "jmeter_version", "jmeter_bin",
    "locust_available", "locust_version", "debug_run",
]
