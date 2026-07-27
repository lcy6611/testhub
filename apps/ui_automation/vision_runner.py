# -*- coding: utf-8 -*-
"""
方案二：独立视觉执行流水线。
不依赖 browser-use Agent，使用 Playwright + 视觉模型「截图 → 模型决策 → 执行动作」闭环，
避免 output_format/refusal 等与 browser-use 的兼容问题。
"""
import asyncio
import base64
import json
import logging
import re
import os
import ast
import time

logger = logging.getLogger('django')

# 默认最大步数（视觉/文本/自动模式统一）
DEFAULT_MAX_STEPS = 50
# 默认最大执行时长（秒），超时强制终止
DEFAULT_MAX_DURATION_SECONDS = 300
# 连续相同动作次数超过此次数即判定卡住并停止
REPEAT_ACTION_THRESHOLD = 3
# 连续无法解析动作次数超过此次数即停止
MAX_CONSECUTIVE_PARSE_FAILURES = 5


def _is_headless() -> bool:
    """
    方案二默认使用有头模式，便于观察浏览器行为。
    若设置环境变量 VISION_HEADLESS=1/true，则启用无头。
    """
    v = (os.getenv("VISION_HEADLESS") or "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _coerce_headless(value):
    """安全解析 headless（避免字符串 'false' 被当作 True）。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ('1', 'true', 'yes', 'y', 'on'):
        return True
    if s in ('0', 'false', 'no', 'n', 'off', ''):
        return False
    return bool(value)

def _get_vision_llm():
    """使用 browser_use_vision 配置创建视觉模型，仅用于方案二流水线。"""
    from apps.requirement_analysis.models import AIModelConfig
    from openai import OpenAI
    cfg = AIModelConfig.objects.filter(role='browser_use_vision', is_active=True).first()
    if not cfg or not getattr(cfg, 'api_key', None):
        return None
    base_url = getattr(cfg, 'base_url', '') or ''
    # 有些网关需要 /v1；这里不强制拼接，保持与配置一致
    client = OpenAI(api_key=cfg.api_key, base_url=base_url)
    return {
        'client': client,
        'model': getattr(cfg, 'model_name', '') or '',
        'base_url': base_url,
    }


def _extract_first_url(task_description: str) -> str | None:
    """从任务描述中提取第一个 URL。"""
    if not task_description:
        return None
    # 先匹配完整 http(s) URL
    m = re.search(r'https?://[^\s，,。；;]+', task_description)
    if m:
        return m.group(0).rstrip('，,。；;')
    # 再匹配 www.xxx
    m = re.search(r'www\.[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9]', task_description)
    if m:
        return 'https://' + m.group(0).rstrip('，,。；;')
    return None


def _normalize_malformed_json(content: str) -> str:
    """
    修复视觉模型常见 JSON 错误，便于后续 json.loads。
    - "x":292, 195, "y":24 → "x":292, "y":195（裸数字 195 视为 y）
    - 多段 {...}, {...} 只保留第一段
    """
    if not content or not content.strip().startswith('{'):
        return content
    # 多段对象只取第一段
    depth = 0
    end = -1
    for i, c in enumerate(content):
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end > 0:
        content = content[:end]
    # "x": N, 裸数字, "y" 或 "x": N, 裸数字 } → "x": N, "y": 裸数字
    content = re.sub(
        r'"x"\s*:\s*(\d+)\s*,\s*(\d+)\s*,\s*"y"\s*:\s*\d+',
        r'"x": \1, "y": \2',
        content,
        count=1,
    )
    content = re.sub(
        r'"x"\s*:\s*(\d+)\s*,\s*(\d+)\s*\}\s*',
        r'"x": \1, "y": \2 } ',
        content,
        count=1,
    )
    # "x": N, 裸数字, 后面是逗号或 }（没有 "y":）→ 补上 "y": 裸数字，保留原结尾符
    def _fix_x_bare_y(m):
        return f'"x": {m.group(1)}, "y": {m.group(2)}{m.group(3)}'
    content = re.sub(
        r'"x"\s*:\s*(\d+)\s*,\s*(\d+)(\s*[,}])',
        _fix_x_bare_y,
        content,
        count=1,
    )
    return content.strip()


def _parse_action_from_response(content: str) -> dict | None:
    """从模型返回文本中解析 JSON 动作。"""
    if not content or not isinstance(content, str):
        return None
    content = content.strip()
    # 去掉 markdown 代码块
    if '```' in content:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if match:
            content = match.group(1).strip()
        else:
            content = re.sub(r'```[a-z]*', '', content).replace('```', '').strip()
    # 找第一个 { ... }（可能含嵌套，用括号匹配）
    start = content.find('{')
    if start >= 0:
        depth = 0
        for i in range(start, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    content = content[start : i + 1]
                    break
    content = _normalize_malformed_json(content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 兼容单引号的 python dict 输出：{'action': 'click', 'x': 100, 'y': 200}
        try:
            obj = ast.literal_eval(content)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None


def _extract_xy(action: dict) -> tuple[int, int] | None:
    """
    兼容多种坐标格式：
    - {"x": 100, "y": 200}
    - {"coordinate": [100, 200]}
    - {"coordinate": "100,200"} / "100 200"
    """
    try:
        if isinstance(action.get('x'), (int, float)) and isinstance(action.get('y'), (int, float)):
            return int(action['x']), int(action['y'])
        coord = action.get('coordinate') or action.get('coords')
        if isinstance(coord, list) and len(coord) >= 2:
            return int(coord[0]), int(coord[1])
        if isinstance(coord, str):
            m = re.search(r'(-?\d+)\s*[, ]\s*(-?\d+)', coord)
            if m:
                return int(m.group(1)), int(m.group(2))
    except Exception:
        return None
    return None


def _action_to_natural_language(act: str, action: dict) -> str:
    """将动作转为自然语言描述，便于执行日志和报告阅读。"""
    act = (act or '').lower()
    if act == 'click':
        xy = _extract_xy(action)
        if xy:
            return f"在页面坐标 ({xy[0]}, {xy[1]}) 处点击"
        return "点击页面某处"
    if act == 'type':
        xy = _extract_xy(action)
        text_val = (action.get('text') or '').strip()
        if xy and text_val:
            return f"在坐标 ({xy[0]}, {xy[1]}) 处输入：{text_val}"
        if text_val:
            return f"输入文本：{text_val}"
        return "在输入框输入内容"
    if act == 'navigate':
        url = (action.get('url') or '').strip()
        if url:
            return f"导航至：{url}"
        return "执行页面导航"
    if act == 'done':
        msg = (action.get('message') or '').strip()
        success = action.get('success', True)
        if msg:
            return f"任务结束（{'成功' if success else '未完成'}）：{msg}"
        return "任务结束" if success else "任务未完成"
    return f"执行动作：{act}"


def _salvage_action_from_text(text: str) -> dict | None:
    """
    当模型输出不是合法 JSON/Dict 时，尝试从原始文本中“抢救”出 action + 坐标 + text。
    主要覆盖：
    - {"action": "click", "x":292, 195, "y":24} / "x":756, 38}, {"action":"click"}
    - {'action': 'click', 'x': 586, 239}  (y 丢失，但有两个数字)
    - {'action': 'type', 'x':659, 12, 2, 244,'text':'华天软件'} (乱入多个数字)
    """
    if not text:
        return None
    t = text.strip()
    # action
    m = re.search(r"(?:action|动作)\s*['\"]?\s*[:=]\s*['\"]?([a-zA-Z_]+)", t)
    act = (m.group(1).lower() if m else None)
    if not act:
        # 尝试直接找 click/type/navigate/done
        m2 = re.search(r"\b(click|type|navigate|done)\b", t, re.I)
        act = m2.group(1).lower() if m2 else None
    if not act:
        return None

    # 优先从 "x": N, M 或 'x': N, M 解析 (x,y)，避免把无关数字当坐标
    xy = None
    xym = re.search(r"['\"]x['\"]\s*:\s*(\d+)\s*,\s*(\d+)", t)
    if xym:
        xy = (int(xym.group(1)), int(xym.group(2)))
    if not xy:
        nums = re.findall(r"-?\d+", t)
        if len(nums) >= 2:
            xy = (int(nums[0]), int(nums[1]))

    out: dict = {"action": act}
    if xy and act in ("click", "type"):
        out["x"], out["y"] = xy
    # text
    if act == "type":
        mt = re.search(r"(?:text|内容)\s*['\"]?\s*[:=]\s*['\"]([^'\"]{1,100})['\"]", t)
        if mt:
            out["text"] = mt.group(1)
    # url
    if act == "navigate":
        mu = re.search(r"https?://[^\s'\"，,。；;]+", t)
        if mu:
            out["url"] = mu.group(0)
    return out


def _write_gif_from_frames(frames: list, out_path: str, duration_ms: int = 500, descriptions: list | None = None) -> None:
    """将 PNG 字节列表合成为 GIF，可选在每帧上方绘制中文描述（与文本模型 GIF 一致）。"""
    if not frames or not out_path:
        return
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        images = []
        desc_list = list(descriptions) if descriptions else []
        while len(desc_list) < len(frames):
            desc_list.append('')
        desc_list = desc_list[:len(frames)]
        bar_h = 44
        font_size = 16  # 字幕字号整体比之前小 2 号（18 -> 16）
        font = None
        for _ in (0,):
            # 1) 优先通过 fontconfig 找到可用中文字体（最稳，避免路径不一致）
            try:
                import subprocess
                for family in ("WenQuanYi Zen Hei", "Noto Sans CJK SC", "Noto Sans CJK"):
                    try:
                        p = subprocess.check_output(["fc-match", "-f", "%{file}", family], text=True).strip()
                        if p and p != "":  # 有些环境可能返回空
                            font = ImageFont.truetype(p, font_size)
                            break
                    except Exception:
                        continue
                if font:
                    break
            except Exception:
                pass

            # 2) 常见 Linux 容器路径（备选）
            for p in (
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
            ):
                try:
                    font = ImageFont.truetype(p, font_size)
                    break
                except Exception:
                    continue
            if font:
                break

            # 3) Windows 本地开发环境优先用微软雅黑
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", font_size)
                break
            except Exception:
                pass

            # 4) 最后回退到 DejaVu / 默认字体（可能不支持中文）
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
                break
            except Exception:
                pass
            font = ImageFont.load_default()

        for i, raw in enumerate(frames):
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            w, h = img.size
            # 文本模型风格：在原图底部“压黑条”，不增加画布高度
            raw_text = (desc_list[i] or '').strip()
            step_index = i  # 第 0 帧为“已打开页面”，其余对应 Step 1,2,...
            if raw_text and not raw_text.startswith("步骤"):
                text = f"步骤 {step_index}: {raw_text}"
            else:
                text = raw_text or f"步骤 {step_index}"

            draw = ImageDraw.Draw(img)
            bar_y = max(0, h - bar_h)
            # 底部整条黑色横条
            draw.rectangle([0, bar_y, w, h], fill=(0, 0, 0))

            short = text[:80] + "..." if len(text) > 80 else text
            # 描述文本（略微靠下，避免太贴边）
            # 近似按字号居中（避免写死 22）
            draw.text((40, bar_y + (bar_h - (font_size + 6)) // 2), short, fill=(255, 255, 255), font=font)

            # 左侧步骤编号小方块
            try:
                badge_w, badge_h = 28, 28
                bx, by = 8, bar_y + (bar_h - badge_h) // 2
                # 有的 Pillow 版本没有 rounded_rectangle，这里做兼容
                if hasattr(draw, "rounded_rectangle"):
                    draw.rounded_rectangle([bx, by, bx + badge_w, by + badge_h], radius=6, fill=(0, 0, 0))
                else:
                    draw.rectangle([bx, by, bx + badge_w, by + badge_h], fill=(0, 0, 0))
                num_text = str(step_index)
                tw, th = draw.textsize(num_text, font=font)
                tx = bx + (badge_w - tw) / 2
                ty = by + (badge_h - th) / 2
                draw.text((tx, ty), num_text, fill=(255, 255, 255), font=font)
            except Exception:
                pass

            images.append(img.convert("P", palette=Image.ADAPTIVE, colors=256))
        if not images:
            return
        images[0].save(
            out_path,
            save_all=True,
            append_images=images[1:],
            duration=duration_ms,
            loop=0,
        )
        logger.info("[VisionRunner] GIF 已写入: %s (共 %d 帧)", out_path, len(images))
    except Exception as e:
        logger.warning("[VisionRunner] 生成 GIF 失败: %s", e)


async def _run_vision_loop(
    task_description: str,
    planned_tasks: list,
    llm,  # {'client': OpenAI, 'model': str, 'base_url': str}
    step_callback,
    should_stop,
    max_steps: int = DEFAULT_MAX_STEPS,
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    headless: bool | None = None,  # None=用环境变量/默认，True=无头，False=有头
    enable_gif: bool = False,
):
    """
    独立视觉循环：Playwright 截图 → 视觉模型 → 解析动作 → 执行。
    llm: 视觉模型 LLM 实例（在同步部分创建，避免异步上下文中调用 Django ORM）
    step_callback 为同步或异步函数 (dict) -> None，dict 含 type='log' 时 content 为日志。
    """
    from playwright.async_api import async_playwright

    if not llm:
        logger.error("[VisionRunner] 未配置 browser_use_vision，无法执行视觉流水线")
        if step_callback:
            try:
                await _append_log(step_callback, '\n[VisionRunner] 未配置视觉模型，请到配置中心添加 browser_use_vision。\n')
            except Exception as e:
                logger.warning("step_callback failed: %s", e)
        return _make_history([], task_description, planned_tasks, success=False)

    steps_log = []
    first_url = _extract_first_url(task_description)
    if not first_url:
        if step_callback:
            try:
                await _append_log(step_callback, '\n[VisionRunner] 未从任务描述中解析出 URL。\n')
            except Exception:
                pass
        return _make_history(steps_log, task_description, planned_tasks, success=False)

    system_prompt = (
        "你是一个浏览器自动化助手。我会给你当前页面的截图和任务描述。\n"
        "你必须只回复一个 JSON 对象，不要其他文字。格式如下之一：\n"
        "1) 点击: {\"action\":\"click\",\"x\":整数,\"y\":整数,\"evaluation\":\"简短中文判断本步操作是否有助于达成目标\"}\n"
        "2) 输入: {\"action\":\"type\",\"x\":整数,\"y\":整数,\"text\":\"要输入的文本\",\"evaluation\":\"简短中文判断是否正确输入\"}\n"
        "3) 导航: {\"action\":\"navigate\",\"url\":\"https://...\",\"evaluation\":\"简短中文判断目标页面是否正确\"}\n"
        "4) 完成: {\"action\":\"done\",\"success\":true或false,\"message\":\"简短说明\",\"evaluation\":\"本次任务整体是否成功以及原因\"}\n\n"
        "要求：\n"
        "- 所有字段必须放在一个 JSON 对象中，只能输出这个 JSON；\n"
        "- evaluation 必须是 5~20 个汉字的短句，明确说明“这一步是否达成上一步目标”，例如：\"成功：已正确输入用户名\"、\"失败：登录后仍停留在登录页\"。\n"
        "截图尺寸为 1280x720。坐标 (x,y) 为截图上的像素位置。"
    )

    use_headless = _coerce_headless(headless) if headless is not None else _is_headless()
    # 在 Linux 容器/无图形界面环境下无法启动有头浏览器，自动降级为无头
    if use_headless is False:
        try:
            import platform
            if platform.system() == 'Linux' and not (os.getenv('DISPLAY') or os.getenv('WAYLAND_DISPLAY')):
                use_headless = True
                await _append_log(
                    step_callback,
                    "\n[VisionRunner] 检测到无图形界面环境（未设置 DISPLAY/WAYLAND_DISPLAY），已强制切换为无头模式(headless=True)。\n"
                )
        except Exception:
            pass
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=use_headless,
            args=['--disable-blink-features=AutomationControlled'],
        )
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        )
        page = await context.new_page()
        try:
            await page.goto(first_url, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(1.5)
        except Exception as e:
            await _append_log(step_callback, f"\n[VisionRunner] 导航失败: {e}\n")
            await browser.close()
            return _make_history(steps_log, task_description, planned_tasks, success=False)

        await _append_log(step_callback, f"\n[执行模式] 浏览器步骤将使用: 视觉模型（方案二独立流水线）\n")
        await _append_log(step_callback, f"[VisionRunner] headless={use_headless}\n")
        await _append_log(step_callback, f"[Step 0] 已打开: {first_url}\n")
        await _append_log(step_callback, f"[VisionRunner] 终止条件: 最大步数={max_steps}, 超时={max_duration_seconds}秒, 重复动作={REPEAT_ACTION_THRESHOLD}次, 连续解析失败={MAX_CONSECUTIVE_PARSE_FAILURES}次\n")

        # GIF 录制：每步截图 + 对应中文描述，合成时描述绘在每帧上方（与文本模型 GIF 一致）
        gif_frames: list = []
        gif_descriptions: list = []  # 与 gif_frames 一一对应，用于在每帧上方绘制
        gif_output_path = os.path.join(os.getcwd(), 'agent_history.gif')
        if enable_gif:
            try:
                first_frame = await page.screenshot(type='png', full_page=False)
                gif_frames.append(first_frame)
                gif_descriptions.append("步骤 0: 已打开页面")
            except Exception:
                pass

        def _maybe_write_gif():
            if enable_gif and gif_frames:
                _write_gif_from_frames(gif_frames, gif_output_path, descriptions=gif_descriptions)

        # 重复动作检测：避免模型卡住时无限重复点击同一位置
        last_actions: list[str] = []
        consecutive_parse_failures = 0
        start_time = time.monotonic()

        for step_index in range(1, max_steps + 1):
            if await _check_stop(should_stop):
                await _append_log(step_callback, "\n[System] 任务已停止（用户/外部终止）。\n")
                break

            if max_duration_seconds > 0 and (time.monotonic() - start_time) >= max_duration_seconds:
                await _append_log(step_callback, f"\n[VisionRunner] 已达最大执行时长 {max_duration_seconds} 秒，强制终止。\n")
                break

            if step_index == max_steps:
                await _append_log(step_callback, f"\n[VisionRunner] 即将达到最大步数 {max_steps}，本步执行后结束。\n")

            try:
                screenshot_bytes = await page.screenshot(type='png', full_page=False)
                b64 = base64.standard_b64encode(screenshot_bytes).decode('utf-8')
                if enable_gif:
                    gif_frames.append(screenshot_bytes)
            except Exception as e:
                await _append_log(step_callback, f"\n[VisionRunner] 截图失败: {e}\n")
                break

            task_list = "\n".join([f"- {t.get('content', t.get('title', ''))}" for t in (planned_tasks or [])[:12]])
            user_text = f"任务：{task_description}\n\n子步骤：\n{task_list}\n\n请根据当前截图回复一个 JSON 动作（click/type/navigate/done）。"

            try:
                client = llm.get('client')
                model = llm.get('model')
                if not client or not model:
                    raise RuntimeError("视觉模型 client/model 未就绪")

                def _call():
                    return client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": user_text},
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                                ],
                            },
                        ],
                        max_tokens=256,
                        response_format={"type": "json_object"},
                    )

                try:
                    r = await asyncio.to_thread(_call)
                except Exception:
                    # 兼容不支持 response_format 的网关
                    def _call2():
                        return client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": user_text},
                                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                                    ],
                                },
                            ],
                            max_tokens=256,
                        )
                    r = await asyncio.to_thread(_call2)
                text = (r.choices[0].message.content or "").strip()
            except Exception as e:
                await _append_log(step_callback, f"\n[Step {step_index}](视觉模型) 调用失败: {e}\n")
                steps_log.append({'step': step_index, 'action': str(e), 'error': True})
                continue

            if not text:
                await _append_log(step_callback, f"\n[Step {step_index}](视觉模型) 返回为空\n")
                steps_log.append({'step': step_index, 'action': 'empty response', 'error': True})
                continue

            action = _parse_action_from_response(text)
            if not action or not action.get('action'):
                # 二次修正：把原始输出强制转成严格 JSON（不看图，成本低）
                raw_snippet = text.strip().replace('\n', '\\n')[:800]
                await _append_log(step_callback, f"[调试] 触发二次修正 JSON\n")
                try:
                    def _fix_json():
                        return client.chat.completions.create(
                            model=model,
                            messages=[
                                {
                                    "role": "system",
                                    "content": (
                                        "你是一个JSON修复器。把用户提供的内容转换成一个严格的 JSON 对象。"
                                        "要求：只能输出 JSON；必须使用双引号；不得输出代码块或多余文字。"
                                    ),
                                },
                                {"role": "user", "content": raw_snippet},
                            ],
                            max_tokens=256,
                            response_format={"type": "json_object"},
                        )
                    fr = await asyncio.to_thread(_fix_json)
                    fixed_text = (fr.choices[0].message.content or "").strip()
                    action = _parse_action_from_response(fixed_text) or action
                except Exception:
                    pass

                snippet = text.strip().replace('\n', '\\n')[:400]
                await _append_log(
                    step_callback,
                    f"\n[Step {step_index}](视觉模型) 执行: 无法解析动作\n"
                    f"[调试] 原始输出片段: {snippet}\n"
                )
                # 尝试抢救动作
                salvaged = _salvage_action_from_text(text)
                if salvaged and salvaged.get("action"):
                    action = salvaged
                    await _append_log(step_callback, f"[调试] 已抢救动作: {action}\n")
                else:
                    steps_log.append({'step': step_index, 'action': text[:200], 'error': True})
                    consecutive_parse_failures += 1
                    if consecutive_parse_failures >= MAX_CONSECUTIVE_PARSE_FAILURES:
                        await _append_log(step_callback, f"\n[VisionRunner] 连续 {MAX_CONSECUTIVE_PARSE_FAILURES} 次无法解析动作，终止执行。\n")
                        _maybe_write_gif()
                        await browser.close()
                        return _make_history(steps_log, task_description, planned_tasks, success=False)
                    continue

            act = action.get('action', '').lower()
            step_desc = _action_to_natural_language(act, action)

            # 从视觉模型返回的 JSON 中提取 evaluation 作为本步验证结论
            eval_text = (action.get('evaluation') or "").strip()

            # === 与文本模型对齐的日志输出格式 ===
            # 统一生成 [Step X] 块，包含思考 / 验证 / 执行动作 / 原始动作JSON，方便报告和前端解析
            try:
                import json as _json_module  # 局部导入，避免顶层依赖
                raw_actions_json = _json_module.dumps(action, ensure_ascii=False)
            except Exception:
                raw_actions_json = str(action)

            log_lines = [f"\n[Step {step_index}]"]
            # 视觉模型没有独立 thinking，这里仍然用自然语言动作描述
            log_lines.append(f"思考(thinking): {step_desc}")
            # 验证信息：优先使用模型返回的 evaluation，没有则退回到通用描述
            if eval_text:
                log_lines.append(f"验证(evaluation_previous_goal): {eval_text}")
            else:
                log_lines.append("验证(evaluation_previous_goal): 视觉模型根据当前截图判断需要执行上述操作。")
            log_lines.append(f"执行动作: {step_desc}")
            log_lines.append(f"原始动作JSON: {raw_actions_json}")
            await _append_log(step_callback, "\n".join(log_lines) + "\n")

            # GIF 描述仍然使用 step_desc，生成的字幕更自然
            if enable_gif and gif_frames:
                gif_descriptions.append(step_desc)  # 与当前帧对应，合成时绘在图片上方

            # 成功解析并得到动作，重置连续解析失败计数
            consecutive_parse_failures = 0

            try:
                # 记录动作签名，检测重复
                sig = None
                if act in ('click', 'type'):
                    xy = _extract_xy(action)
                    if xy:
                        sig = f"{act}:{xy[0]},{xy[1]}"
                elif act == 'navigate':
                    sig = f"navigate:{(action.get('url') or '').strip()}"
                else:
                    sig = act

                if sig:
                    last_actions.append(sig)
                    last_actions = last_actions[-6:]
                    if len(last_actions) >= REPEAT_ACTION_THRESHOLD and len(set(last_actions[-REPEAT_ACTION_THRESHOLD:])) == 1:
                        await _append_log(step_callback, f"\n[VisionRunner] 检测到连续 {REPEAT_ACTION_THRESHOLD} 次相同动作 {sig}，判定卡住并停止。\n")
                        _maybe_write_gif()
                        await browser.close()
                        return _make_history(steps_log, task_description, planned_tasks, success=False)

                if act == 'done':
                    await _notify_task_completed(step_callback, step_index, planned_tasks or [])
                    success = action.get('success', True)
                    msg = action.get('message', '') or ''
                    if step_callback:
                        try:
                            if asyncio.iscoroutinefunction(step_callback):
                                await step_callback({'type': 'done_result', 'success': success, 'text': msg})
                            else:
                                step_callback({'type': 'done_result', 'success': success, 'text': msg})
                        except Exception:
                            pass
                    steps_log.append({'step': step_index, 'action': 'done', 'success': success, 'message': msg, 'description': step_desc, 'thinking': step_desc, 'evaluation': eval_text})
                    _maybe_write_gif()
                    await browser.close()
                    return _make_history(steps_log, task_description, planned_tasks, success=success)

                if act == 'click':
                    xy = _extract_xy(action)
                    if not xy:
                        raise ValueError(f"missing x/y in action: {action}")
                    x, y = xy
                    await page.mouse.click(x, y)
                    steps_log.append({'step': step_index, 'action': f'click({x},{y})', 'description': step_desc, 'thinking': step_desc, 'evaluation': eval_text})
                    await _notify_task_completed(step_callback, step_index, planned_tasks or [])
                elif act == 'type':
                    xy = _extract_xy(action)
                    if not xy:
                        raise ValueError(f"missing x/y in action: {action}")
                    x, y = xy
                    text_val = action.get('text', '') or ''
                    await page.mouse.click(x, y)
                    await page.keyboard.type(text_val, delay=50)
                    steps_log.append({'step': step_index, 'action': f'type({x},{y},{text_val[:20]}...)', 'description': step_desc, 'thinking': step_desc, 'evaluation': eval_text})
                    await _notify_task_completed(step_callback, step_index, planned_tasks or [])
                elif act == 'navigate':
                    url = (action.get('url') or '').strip()
                    if url:
                        await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                        await asyncio.sleep(1)
                    steps_log.append({'step': step_index, 'action': f'navigate({url})', 'description': step_desc, 'thinking': step_desc, 'evaluation': eval_text})
                    await _notify_task_completed(step_callback, step_index, planned_tasks or [])
                else:
                    steps_log.append({'step': step_index, 'action': act, 'raw': action, 'description': step_desc, 'thinking': step_desc, 'evaluation': eval_text})
            except Exception as e:
                await _append_log(step_callback, f"  执行失败: {e}\n")
                steps_log.append({'step': step_index, 'action': act, 'error': str(e), 'description': step_desc, 'thinking': step_desc, 'evaluation': eval_text})

        # 正常走出循环：已达最大步数或超时
        if step_index >= max_steps:
            await _append_log(step_callback, f"\n[VisionRunner] 已达最大步数 {max_steps}，停止执行。\n")
        _maybe_write_gif()
        await browser.close()
    return _make_history(steps_log, task_description, planned_tasks, success=False)


async def _notify_task_completed(step_callback, step_index: int, planned_tasks: list):
    """通知前端：对应子任务已完成，便于执行报告中「待执行」更新为「已完成」。"""
    if not step_callback or not planned_tasks or step_index < 1:
        return
    task_id = min(step_index, len(planned_tasks))
    try:
        if asyncio.iscoroutinefunction(step_callback):
            await step_callback({'task_id': task_id, 'status': 'completed'})
        else:
            step_callback({'task_id': task_id, 'status': 'completed'})
    except Exception as e:
        logger.debug("_notify_task_completed failed: %s", e)


async def _append_log(step_callback, content: str):
    """追加日志，如果异步回调失败（sync_to_async 需要 Django 上下文）则降级为仅记录"""
    if not content or not step_callback:
        return
    try:
        if asyncio.iscoroutinefunction(step_callback):
            await step_callback({'type': 'log', 'content': content})
        else:
            step_callback({'type': 'log', 'content': content})
    except Exception as e:
        # sync_to_async 在 asyncio.run() 创建的事件循环中可能失败（缺少 Django 上下文）
        # 这里只记录，不中断执行；views 层会在同步线程中定期保存日志
        logger.debug("_append_log failed (may need Django async context): %s", e)


async def _check_stop(should_stop) -> bool:
    if not should_stop:
        return False
    if asyncio.iscoroutinefunction(should_stop):
        return await should_stop()
    return should_stop()


def _make_history(steps_log, task_description: str, planned_tasks: list, success: bool):
    """返回与 run_full_process 兼容的 history 形状。"""
    class History:
        steps = []
        performance_metrics = None
        execution_history = None
    h = History()
    h.steps = steps_log
    h.performance_metrics = {
        'total_steps': len(steps_log),
        'execution_mode': 'vision',
        'use_vision': True,
        'model_name': 'vision_runner_v2',
    }
    h.execution_history = {
        'task_description': task_description,
        'planned_tasks': planned_tasks or [],
        'total_steps': len(steps_log),
        'execution_mode': 'vision',
        'success': success,
    }
    return h


async def _run_vision_pipeline_async(
    task_description: str,
    planned_tasks: list,
    llm,  # 视觉模型 LLM，在同步部分创建
    step_callback=None,
    should_stop=None,
    max_steps: int = DEFAULT_MAX_STEPS,
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    headless: bool | None = None,
    enable_gif: bool = False,
):
    """
    方案二：独立视觉流水线（异步版本）。
    接收已解析的 planned_tasks 和视觉模型 LLM，直接跑视觉循环。
    """
    logger.info("[VisionRunner] 方案二视觉流水线启动（异步部分）")

    # 视觉循环（Playwright + 视觉模型）
    return await _run_vision_loop(
        task_description,
        planned_tasks,
        llm,
        step_callback,
        should_stop,
        max_steps=max_steps,
        max_duration_seconds=max_duration_seconds,
        headless=headless,
        enable_gif=enable_gif,
    )


def run_vision_pipeline_sync(
    task_description: str,
    analysis_callback=None,
    step_callback=None,
    should_stop=None,
    enable_gif=False,
    case_name=None,
    headless: bool | None = None,
):
    """
    方案二：独立视觉流水线入口（同步包装）。
    先做任务解析（文本模型，同步），调用 analysis_callback（同步线程），再跑视觉循环（异步）。
    """
    from .ai_agent import analyze_task_sync
    from asgiref.sync import sync_to_async

    logger.info("[VisionRunner] 方案二视觉流水线启动")

    # 1) 任务解析（复用文本模型，同步调用）
    try:
        planned_tasks = analyze_task_sync(task_description, execution_mode='text')
    except Exception as e:
        logger.warning("[VisionRunner] 任务解析失败: %s", e)
        planned_tasks = []

    # 2) 调用 analysis_callback（在同步线程中，异步回调需要特殊处理）
    # 注意：如果 analysis_callback 是异步的且使用了 sync_to_async，需要在 Django 异步上下文中运行
    # 这里我们尝试直接运行，如果失败则跳过（由 views 层在同步线程中直接保存）
    if analysis_callback:
        try:
            if asyncio.iscoroutinefunction(analysis_callback):
                # 异步回调：尝试在新事件循环中运行
                # 如果 sync_to_async 失败，views 层会在同步线程中直接保存
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(analysis_callback(planned_tasks))
                    loop.close()
                except Exception as async_err:
                    # sync_to_async 需要 Django 上下文，这里可能失败
                    logger.debug("[VisionRunner] analysis_callback async failed (expected in sync thread): %s", async_err)
                    # 不抛出异常，让 views 层在同步线程中直接保存
            else:
                analysis_callback(planned_tasks)
        except Exception as e:
            logger.warning("[VisionRunner] analysis_callback failed: %s", e)

    # 3) 在同步部分创建视觉模型 LLM（避免在异步上下文中调用 Django ORM）
    llm = _get_vision_llm()
    if not llm:
        logger.error("[VisionRunner] 未配置 browser_use_vision，无法执行视觉流水线")
        return _make_history([], task_description, planned_tasks, success=False)

    # 4) 异步部分：视觉循环（Playwright + 视觉模型）
    return asyncio.run(_run_vision_pipeline_async(
        task_description,
        planned_tasks,
        llm,  # 传入已创建的 LLM
        step_callback,
        should_stop,
        max_steps=DEFAULT_MAX_STEPS,
        max_duration_seconds=DEFAULT_MAX_DURATION_SECONDS,
        headless=headless,
        enable_gif=enable_gif,
    ))
