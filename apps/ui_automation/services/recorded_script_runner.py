"""录制脚本执行服务（Playwright codegen 回放）。

7.0 最大亮点「Playwright 录制回放」的本质链路：
   playwright codegen 录制 -> 回传 .py 脚本 -> 脚本编辑器 -> 回放执行。
录制得到的 playwright_code 是一段**独立可运行的 Python**（自带 sync_playwright 上下文），
因此最贴近原意的执行方式就是把它写到临时文件后用解释器跑，而非塞进结构化步骤引擎。

本模块同时服务于：
  - UiScriptGeneration 的「执行录制脚本」端点（#329）
  - UiScheduledTask 定时任务「录制脚本执行」类型（#328）
"""
import os
import re
import subprocess
import sys
import tempfile
import time

from django.utils import timezone


def run_recorded_script(script_generation, headless=None, browser="chromium", timeout=300):
    """执行一条 UiScriptGeneration 的录制脚本（playwright_code 字段）。

    Args:
        script_generation: UiScriptGeneration 实例（含 playwright_code）
        headless: None=沿用脚本原设置；True/False=把无参 launch() 改为对应 headless
        browser: 仅作记录，codegen 脚本已自带浏览器选择
        timeout: 单脚本执行超时（秒）

    Returns:
        dict: {status, exit_code, output, duration}
    """
    code = (getattr(script_generation, "playwright_code", "") or "").strip()
    if not code:
        return {"status": "failed", "error": "录制脚本为空，无法执行", "exit_code": None, "output": ""}

    # 仅在脚本用无参 launch() 时注入 headless 设置，避免污染已显式指定参数的 launch
    if headless is True:
        code = code.replace("launch()", "launch(headless=True)")
    elif headless is False:
        code = code.replace("launch()", "launch(headless=False)")

    tmp_dir = tempfile.gettempdir()
    safe_id = getattr(script_generation, "id", None) or "x"
    py_path = os.path.join(tmp_dir, "recorded_%s.py" % safe_id)
    with open(py_path, "w", encoding="utf-8") as f:
        f.write(code)

    start = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, py_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = round(time.time() - start, 2)
        ok = proc.returncode == 0
        output = (proc.stdout or "") + (proc.stderr or "")
        _update_gen_status(script_generation, "passed" if ok else "failed",
                           "" if ok else (proc.stderr or "")[:1000])
        return {
            "status": "passed" if ok else "failed",
            "exit_code": proc.returncode,
            "output": output[-4000:],
            "duration": elapsed,
        }
    except subprocess.TimeoutExpired:
        _update_gen_status(script_generation, "failed", "执行超时（>%ss）" % timeout)
        return {"status": "failed", "error": "执行超时（>%ss）" % timeout, "exit_code": None, "output": ""}
    except Exception as e:  # noqa: BLE001
        _update_gen_status(script_generation, "failed", str(e)[:1000])
        return {"status": "failed", "error": str(e), "exit_code": None, "output": ""}
    finally:
        try:
            os.remove(py_path)
        except OSError:
            pass


def _update_gen_status(gen, status, error):
    try:
        gen.status = status
        gen.error_message = error or ""
        gen.save(update_fields=["status", "error_message", "updated_at"])
    except Exception:  # noqa: BLE001
        pass


def build_codegen_command(base_url, output_file=None):
    """生成 playwright codegen 录制命令，供前端展示让用户复制到本机执行。

    codegen 在用户本机运行（需能访问被测站点），录制完成回传 .py 到平台保存。
    """
    if not output_file:
        safe = re.sub(r"[^0-9A-Za-z]", "_", base_url or "site")[:40]
        output_file = "recorded_%s.py" % safe
    # --target python 生成 Python；-o 指定输出文件；--browser chromium 默认 chromium
    return (
        'playwright codegen --target python --browser chromium '
        '-o %s "%s"' % (output_file, base_url)
    )
