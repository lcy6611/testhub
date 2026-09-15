"""
ASGI config for backend project.
支持 Daphne (WebSocket) 和 runserver (仅 HTTP) 两种模式，并可选挂载 MCP 协议端点。
"""

import os
import logging

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

django_asgi_app = get_asgi_application()

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------- #
# MCP 协议端点分流（最小侵入，不影响现有 HTTP/WebSocket 流量）
# - 仅对精确路径 /api/mcp 与 /api/mcp/ 拦截到 FastMCP 子应用
# - mcp 包不可用时整体跳过，/api/mcp 由 DRF 兜底视图处理
# - server.py 仅在函数内惰性 import mcp，故 import 本模块不依赖 mcp 已安装
# --------------------------------------------------------------------- #
MCP_PATHS = ('/api/mcp', '/api/mcp/')
mcp_bridge = None
try:
    import importlib.util
    if importlib.util.find_spec('mcp') is not None:
        from apps.mcp.server import mcp_bridge as _mcp_bridge
        mcp_bridge = _mcp_bridge
        logger.info("MCP 协议端点已挂载：/api/mcp 分流到 FastMCP")
    else:
        logger.warning("未检测到 mcp 包，/api/mcp 由 DRF 兜底视图处理")
except Exception as e:  # noqa: BLE001
    logger.warning("MCP 桥接初始化跳过（DRF 不受影响）：%s", e)


async def mcp_aware_http_app(scope, receive, send):
    """HTTP 入口：MCP 精确路径交给 FastMCP 桥，其余请求走 Django。"""
    if mcp_bridge is not None and scope.get('type') == 'http':
        path = scope.get('path', '')
        if path in MCP_PATHS:
            await mcp_bridge(scope, receive, send)
            return
    await django_asgi_app(scope, receive, send)


try:
    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter, URLRouter
    from apps.app_automation import routing as app_automation_routing
    from apps.performance_testing import routing as performance_routing

    # 各模块的 WebSocket 路由在这里汇总（新增模块只需 append 一次）
    websocket_urlpatterns = (
        list(app_automation_routing.websocket_urlpatterns)
        + list(performance_routing.websocket_urlpatterns)
    )

    application = ProtocolTypeRouter({
        "http": mcp_aware_http_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })
    logger.info("ASGI 已启用 WebSocket 支持 (需通过 Daphne 或 uvicorn/daphne 启动)")
except ImportError:
    application = django_asgi_app
    logger.warning("channels 未安装，WebSocket 不可用，仅支持 HTTP")
except Exception as e:
    application = django_asgi_app
    logger.warning(f"WebSocket 初始化失败: {e}，降级为仅 HTTP 模式")
