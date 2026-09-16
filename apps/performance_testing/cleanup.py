"""执行数据与产物清理：供管理命令与视图删除共用，保证路径约定只有一处。

产物目录约定：``media/performance/<execution_id>/``（内含 result.jtl、plan.jmx、
report/、jmeter.log 等）。清理是幂等的，且**只删目录名包含 execution_id 的目录**，
避免误删。
"""
from __future__ import annotations

import logging
import os
import shutil

logger = logging.getLogger(__name__)


def artifact_dir(execution) -> str:
    """推断执行产物目录；推断不出返回空串。"""
    for path in (execution.jtl_path, execution.jmx_path, execution.report_path, execution.jmeter_log):
        if path and os.path.exists(path):
            return os.path.dirname(path) if os.path.isfile(path) else path
    return ""


def cleanup_execution_artifacts(execution) -> bool:
    """删除该执行的产物目录。返回是否真的删除了目录。"""
    base = artifact_dir(execution)
    if not base or not execution.execution_id or execution.execution_id not in base:
        return False
    if not os.path.isdir(base):
        return False
    try:
        shutil.rmtree(base)
        return True
    except Exception:  # noqa: BLE001  清理失败不能影响主流程
        logger.exception("删除执行介质目录失败 %s", base)
        return False
