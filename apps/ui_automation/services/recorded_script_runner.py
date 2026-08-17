"""录制脚本执行服务（Playwright codegen 回放）。

7.0 最大亮点「Playwright 录制回放」的本质链路：
   playwright codegen 录制 -> 回传脚本 -> 脚本库（TestScript）-> 回放执行。
录制得到的代码是一段**独立可运行的**（自带 sync_playwright 上下文），
因此最贴近原意的执行方式就是把它写到临时文件后用解释器跑。

本模块同时服务于：
  - TestScript 的「执行」端点（脚本库统一回放入口）
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


def run_playwright_code(code, headless=None, browser="chromium", timeout=300,
                        language="python"):
    """直接执行一段 Playwright 代码（不依赖 ORM 实例），返回执行结果。

    Args:
        code: 待执行的脚本文本（Python 或 JavaScript）
        headless: None=沿用脚本原设置；True/False=把无参 launch() 改为对应 headless
        browser: 仅作记录，codegen 脚本已自带浏览器选择
        timeout: 单脚本执行超时（秒）
        language: python | javascript（决定解释器与扩展名）

    Returns:
        dict: {status, exit_code, output, duration}
    """
    code = (code or "").strip()
    if not code:
        return {"status": "failed", "error": "脚本为空，无法执行", "exit_code": None, "output": ""}

    # 仅在脚本用无参 launch() 时注入 headless 设置，避免污染已显式指定参数的 launch
    if headless is True:
        code = code.replace("launch()", "launch(headless=True)")
    elif headless is False:
        code = code.replace("launch()", "launch(headless=False)")

    ext = "js" if language == "javascript" else "py"
    exe = "node" if ext == "js" else sys.executable
    fd, tmp_path = tempfile.mkstemp(suffix="." + ext, prefix="recorded_run_")
    os.close(fd)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(code)

    start = time.time()
    try:
        proc = subprocess.run(
            [exe, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = round(time.time() - start, 2)
        ok = proc.returncode == 0
        output = (proc.stdout or "") + (proc.stderr or "")
        return {
            "status": "passed" if ok else "failed",
            "exit_code": proc.returncode,
            "output": output[-4000:],
            "duration": elapsed,
        }
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "执行超时（>%ss）" % timeout, "exit_code": None, "output": ""}
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "error": str(e), "exit_code": None, "output": ""}
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def run_recorded_script(script_generation, headless=None, browser="chromium", timeout=300,
                        code_override=None):
    """执行一条 UiScriptGeneration 的录制脚本（playwright_code 字段）。

    兼容旧的录制任务链路；新链路推荐直接用 TestScript 的「执行」端点。

    Returns:
        dict: {status, exit_code, output, duration}
    """
    # 优先使用前端编辑后传入的代码（回放前可在弹窗里修正 locator），否则用库中保存的
    code = (code_override or getattr(script_generation, "playwright_code", "") or "").strip()
    result = run_playwright_code(code, headless=headless, browser=browser, timeout=timeout)
    _update_gen_status(script_generation, result.get("status"),
                       "" if result.get("status") == "passed" else (result.get("error") or "")[:1000])
    return result


def _update_gen_status(gen, status, error):
    try:
        gen.status = status
        gen.error_message = error or ""
        gen.save(update_fields=["status", "error_message", "updated_at"])
    except Exception:  # noqa: BLE001
        pass


def build_codegen_command(base_url, output_file=None, language="python",
                           browser="chromium", device=None, save_login=False):
    """生成 playwright codegen 录制命令，供前端展示让用户复制到本机执行。

    codegen 在用户本机运行（需能访问被测站点），录制完成回传脚本到平台保存。

    Args:
        base_url: 被测系统地址
        output_file: 输出文件名（默认按 base_url 生成）
        language: python | javascript（决定 --target 与扩展名）
        browser: chromium | chrome | firefox | webkit
        device: 视口模拟，形如 "1280,720"；为空则不模拟
        save_login: True 时附加 --save-storage，浏览器登录态录制时保存
    """
    if not output_file:
        safe = re.sub(r"[^0-9A-Za-z]", "_", base_url or "site")[:40].rstrip("_")
        output_file = "recorded_%s.py" % safe
    target = "python" if language != "javascript" else "javascript"
    ext = "py" if target == "python" else "js"
    if not output_file.endswith("." + ext):
        output_file = re.sub(r"\.(py|js)$", "", output_file) + "." + ext

    parts = ["playwright codegen", "--target %s" % target, "--browser %s" % browser]
    if device:
        parts.append('--viewport-size "%s"' % device)
    if save_login:
        parts.append("--save-storage auth.json")
    parts.append("-o %s" % output_file)
    parts.append('"%s"' % base_url)
    return " ".join(parts)
