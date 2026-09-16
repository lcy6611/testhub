"""压测引擎抽象层。

三个引擎的运行期依赖不同，可用性由环境决定而非代码：

| 引擎    | 运行期依赖                      |
|---------|--------------------------------|
| BUILTIN | 无（asyncio + httpx，随项目安装）|
| LOCUST  | pip 包 locust                  |
| JMETER  | java + JMeter 发行包            |

**约定**：所有引擎都必须把采样结果写成与 JMeter 同构的 CSV JTL
（列：``timeStamp,elapsed,label,responseCode,success,bytes,sentBytes``），
这样 ``result_parser.parse_jtl`` → 汇总/指标 → 报告 → SLA/验收判定 → 基线/对照
整条下游链路无需为引擎做任何分支。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

#: 所有引擎统一的 JTL CSV 表头（顺序即列顺序）
JTL_COLUMNS = ["timeStamp", "elapsed", "label", "responseCode", "success", "bytes", "sentBytes"]


class EngineError(Exception):
    """引擎不可用或执行失败。"""


class BaseEngine(ABC):
    """压测引擎基类。

    :param config: 生效配置（``jmx_config``，可能已被执行环境叠加）
    :param run_opts: 运行参数 ``{thread_count, ramp_up, duration, loops}``
    :param work_dir: 工作目录（引擎产物如 JTL 写在这里）
    :param on_sample: 采样回调（可选，用于实时指标落库）
    :param on_log: 日志回调（可选）
    """

    name = "BASE"

    def __init__(self, config: Dict[str, Any], run_opts: Dict[str, Any], work_dir: str,
                 on_sample: Optional[Callable[[Dict[str, Any]], None]] = None,
                 on_log: Optional[Callable[[str], None]] = None):
        self.config = config or {}
        self.run_opts = run_opts or {}
        self.work_dir = work_dir
        self.on_sample = on_sample
        self.on_log = on_log

    def log(self, message: str) -> None:
        if self.on_log:
            try:
                self.on_log(message)
            except Exception:  # noqa: BLE001  日志回调不能影响压测
                pass

    @property
    def jtl_path(self) -> str:
        import os

        return os.path.join(self.work_dir, "result.jtl")

    def iterations(self) -> int:
        """循环次数（-1/0 表示按 duration 跑满）。"""
        try:
            loops = int(self.run_opts.get("loops") or 0)
        except (TypeError, ValueError):
            loops = 0
        return loops

    @abstractmethod
    def prepare(self) -> None:
        """执行前校验与准备（依赖缺失时抛 EngineError）。"""

    @abstractmethod
    def run(self) -> Dict[str, Any]:
        """同步执行一次压测，返回 ``{returncode, jtl_path, log}``。"""

    def stop(self, graceful: bool = True) -> None:
        """请求停止（默认空实现，仅长驻引擎需要）。"""

    def collect(self) -> Dict[str, Any]:
        """收集产物信息（默认返回 JTL 路径）。"""
        import os

        return {"jtl_path": self.jtl_path, "exists": os.path.exists(self.jtl_path)}
