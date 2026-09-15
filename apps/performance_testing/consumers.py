"""压测执行实时推送。

沿用 `apps.app_automation` 的消费者范式：一个执行一个 group，
执行侧的监控线程通过 `executor.push_update()` 往 group 里发消息。

鉴权（防未授权订阅任意 execution_id 造成信息泄露）：
1. 已登录（AuthMiddlewareStack 的 session）；
2. 或 query 里带有效 JWT（前端 SPA 走这条，`?token=<access>`）；
3. 或 query 里带有效且未过期的分享令牌（匿名看分享报告时用）。
"""
from __future__ import annotations

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class PerfExecutionConsumer(AsyncJsonWebsocketConsumer):
    """订阅单次压测执行的实时进度。

    连接后主动回推一次当前状态，避免前端「刚好错过上一条推送」时白屏；
    后续增量由 group_send 驱动。channels/Redis 不可用时前端降级为轮询。
    """

    async def connect(self):
        try:
            if not await self._authenticate():
                await self.close()
                return
            self.execution_id = self.scope["url_route"]["kwargs"]["execution_id"]
            self.group_name = f"perf_execution_{self.execution_id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            await self.send_json(await self._current_state())
        except Exception as exc:  # noqa: BLE001
            logger.error("压测 WebSocket 连接失败: %s", exc)
            await self.close()

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "group_name"):
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception as exc:  # noqa: BLE001
            logger.error("压测 WebSocket 断开处理失败: %s", exc)

    async def receive_json(self, content, **kwargs):
        """前端可主动发 {"action": "ping"} 保活。"""
        if (content or {}).get("action") == "ping":
            await self.send_json({"type": "pong"})

    async def execution_update(self, event):
        try:
            await self.send_json(event)
        except Exception as exc:  # noqa: BLE001
            logger.error("压测 WebSocket 推送失败: %s", exc)

    # ------------------------------------------------------------------ #
    async def _authenticate(self) -> bool:
        user = self.scope.get("user")
        if user is not None and getattr(user, "is_authenticated", False):
            return True
        token = self._query_param("token")
        if not token:
            return False
        return await self._token_valid(token)

    def _query_param(self, name: str):
        qs = self.scope.get("query_string", b"")
        if isinstance(qs, bytes):
            qs = qs.decode("utf-8")
        return parse_qs(qs).get(name, [None])[0]

    @database_sync_to_async
    def _token_valid(self, token: str) -> bool:
        """JWT 优先，其次分享令牌。"""
        from django.utils import timezone

        from .models import PerformanceExecution

        try:
            from rest_framework_simplejwt.tokens import AccessToken

            AccessToken(token)
            return True
        except Exception:  # noqa: BLE001  不是合法 JWT，继续按分享令牌校验
            pass

        execution = PerformanceExecution.objects.filter(share_token=token).first()
        if not execution:
            return False
        if execution.share_expires_at and execution.share_expires_at < timezone.now():
            return False
        return True

    async def _current_state(self):
        @database_sync_to_async
        def _load():
            from .models import PerformanceExecution

            execution = PerformanceExecution.objects.filter(pk=self.execution_id).first()
            if not execution:
                return {"type": "execution_update", "status": "NOT_FOUND"}
            return {
                "type": "execution_update",
                "execution_id": execution.pk,
                "execution_no": execution.execution_id,
                "status": execution.status,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "duration": execution.duration,
                "sla_result": execution.sla_result,
                "verdict": execution.verdict,
                "snapshot": True,
            }

        return await _load()
