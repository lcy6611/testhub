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
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from django.conf import settings
from django.utils import timezone


VIDEO_SIZE = {"width": 1280, "height": 720}


def _video_duration(video_path):
    """获取视频时长（秒），失败返回 None。"""
    if not video_path or not os.path.exists(video_path):
        return None
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps and frames:
            return round(frames / fps, 2)
    except Exception:  # noqa: BLE001
        pass
    return None


def _inject_video_options(code, video_dir):
    """在 Python Playwright 脚本中注入录屏参数。

    codegen 默认生成 `context = browser.new_context()`，我们通过替换/追加参数
    让它把视频存到指定目录；录制结束后即可拿到 webm 回放文件。
    """
    marker = f"VIDEO_DIR = {video_dir!r}\n"
    video_args = f"record_video_dir=VIDEO_DIR, record_video_size={VIDEO_SIZE!r}"
    # 1) 最常见：无参 new_context()
    if 'browser.new_context()' in code:
        code = code.replace('browser.new_context()', f'browser.new_context({video_args})')
    else:
        # 2) 简单有参情况（单行、无嵌套括号）
        def repl(m):
            existing = m.group(1).strip()
            return f'browser.new_context({video_args}, {existing})' if existing else f'browser.new_context({video_args})'
        code = re.sub(r'browser\.new_context\(([^)]*)\)', repl, code)
    return marker + code


def _collect_video(video_dir, script_id=None):
    """从 Playwright 录屏目录收集 webm 视频，移动到 MEDIA_ROOT/replay_videos/ 并返回 URL。

    Playwright 可能为每个 page 生成一个 webm，且文件名的字典序不一定代表时间先后，
    因此按修改时间取最晚（通常对应最后一个 page / 包含最多操作）的文件。
    """
    if not video_dir or not os.path.isdir(video_dir):
        return None, None
    webms = [p for p in os.listdir(video_dir) if p.endswith('.webm')]
    if not webms:
        return None, None
    # 取修改时间最晚的视频片段，避免只拿到早期空白/短片段
    webms.sort(key=lambda p: os.path.getmtime(os.path.join(video_dir, p)), reverse=True)
    video_path = os.path.join(video_dir, webms[0])

    target_dir = os.path.join(settings.MEDIA_ROOT, 'replay_videos')
    os.makedirs(target_dir, exist_ok=True)
    ts = timezone.now().strftime('%Y%m%d_%H%M%S_%f')
    fname = f"replay_{script_id or 'adhoc'}_{ts}.webm"
    target = os.path.join(target_dir, fname)
    shutil.move(video_path, target)
    media_url = settings.MEDIA_URL
    if not media_url.endswith('/'):
        media_url += '/'
    return f"{media_url}replay_videos/{fname}", _video_duration(target)


def run_playwright_code(code, headless=None, browser="chromium", timeout=300,
                        language="python", record_video=False, script_id=None):
    """直接执行一段 Playwright 代码（不依赖 ORM 实例），返回执行结果。

    Args:
        code: 待执行的脚本文本（Python 或 JavaScript）
        headless: None=沿用脚本原设置；True/False=把无参 launch() 改为对应 headless
        browser: 仅作记录，codegen 脚本已自带浏览器选择
        timeout: 单脚本执行超时（秒）
        language: python | javascript（决定解释器与扩展名）
        record_video: 是否在执行过程中录制浏览器视频（仅 Python Playwright）
        script_id: 用于生成视频文件名前缀的脚本 ID

    Returns:
        dict: {status, exit_code, output, duration, video_url, video_duration}
    """
    code = (code or "").strip()
    if not code:
        return {"status": "failed", "error": "脚本为空，无法执行", "exit_code": None, "output": "", "video_url": None, "video_duration": None}

    # 仅在脚本用无参 launch() 时注入 headless 设置，避免污染已显式指定参数的 launch
    if headless is True:
        code = code.replace("launch()", "launch(headless=True)")
    elif headless is False:
        code = code.replace("launch()", "launch(headless=False)")

    video_dir = None
    if record_video and language == "python":
        try:
            video_dir = tempfile.mkdtemp(prefix="pw_video_", dir="/tmp")
            code = _inject_video_options(code, video_dir)
        except Exception:  # noqa: BLE001
            video_dir = None

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
        video_url, video_duration = (_collect_video(video_dir, script_id=script_id)
                                     if video_dir else (None, None))
        return {
            "status": "passed" if ok else "failed",
            "exit_code": proc.returncode,
            "output": output[-4000:],
            "duration": elapsed,
            "video_url": video_url,
            "video_duration": video_duration,
        }
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "执行超时（>%ss）" % timeout, "exit_code": None, "output": "", "video_url": None, "video_duration": None}
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "error": str(e), "exit_code": None, "output": "", "video_url": None, "video_duration": None}
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        if video_dir:
            try:
                shutil.rmtree(video_dir, ignore_errors=True)
            except OSError:
                pass


def run_recorded_script(script_generation, headless=None, browser="chromium", timeout=300,
                        code_override=None, record_video=False):
    """执行一条 UiScriptGeneration 的录制脚本（playwright_code 字段）。

    兼容旧的录制任务链路；新链路推荐直接用 TestScript 的「执行」端点。

    Returns:
        dict: {status, exit_code, output, duration, video_url, video_duration}
    """
    # 优先使用前端编辑后传入的代码（回放前可在弹窗里修正 locator），否则用库中保存的
    code = (code_override or getattr(script_generation, "playwright_code", "") or "").strip()
    result = run_playwright_code(
        code, headless=headless, browser=browser, timeout=timeout,
        record_video=record_video, script_id=getattr(script_generation, "id", None),
    )
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
