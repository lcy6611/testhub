"""需要数据库的用例（分享直链 / WebSocket 鉴权 / 清理命令 / 环境互斥）。

运行方式与其他测试一致，无需额外参数：

    python manage.py test apps.performance_testing.tests --noinput
    # 或只跑本模块
    python manage.py test apps.performance_testing.tests.test_db_cases --noinput

历史备注：本文件曾名为 ``db_requiring_cases.py``（故意不以 test 开头、不参与自动发现），
原因是当时平台**全新数据库的迁移链跑不通**，任何 TestCase 都会触发建测试库、
进而把整个套件带崩。相关迁移问题已修复：

- ``requirement_analysis/0021、0022`` 种子迁移在库中无用户时硬编码 ``created_by_id=1``
  → 改为无用户则跳过种子写入；
- ``ui_automation/0009`` 删列前未摘外键（MySQL 1828），且裸 SQL 硬编码
  ``auth_user`` 与 ``int`` 类型（本项目用 ``users_user`` + ``bigint``，报 1824）
  → 改为先摘外键再删列，表名与 FK 列类型按项目配置动态推导。

现在已恢复正常自动发现。
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.performance_testing.models import (
    PerformanceBaseline,
    PerformanceEnvironment,
    PerformanceExecution,
    PerformanceScript,
)


class ShareTokenModelTests(TestCase):
    """B4：分享令牌的签发 / 过期 / 撤销。"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="share_u", password="x")
        self.script = PerformanceScript.objects.create(name="s", created_by=self.user)
        self.execution = PerformanceExecution.objects.create(
            execution_id="PERF_SHARE_TEST", script=self.script, status="COMPLETED"
        )

    def test_default_not_shared(self):
        self.assertFalse(self.execution.share_enabled)
        self.assertIsNone(self.execution.share_token)

    def test_generate_token_enables_sharing(self):
        token = self.execution.generate_share_token(7)
        self.execution.refresh_from_db()
        self.assertTrue(token)
        self.assertTrue(self.execution.share_enabled)
        self.assertIsNotNone(self.execution.share_expires_at)

    def test_regenerate_replaces_token(self):
        first = self.execution.generate_share_token(0)
        second = self.execution.generate_share_token(0)
        self.assertNotEqual(first, second)
        self.execution.refresh_from_db()
        self.assertIsNone(self.execution.share_expires_at)  # 0 天＝永不过期

    def test_expired_token_disables_sharing(self):
        self.execution.generate_share_token(1)
        self.execution.share_expires_at = timezone.now() - timedelta(days=1)
        self.execution.save(update_fields=["share_expires_at"])
        self.assertFalse(self.execution.share_enabled)

    def test_revoke_clears_token(self):
        self.execution.generate_share_token(7)
        self.execution.revoke_share_token()
        self.execution.refresh_from_db()
        self.assertIsNone(self.execution.share_token)
        self.assertFalse(self.execution.share_enabled)


class ShareEndpointTests(TestCase):
    """B4：分享端点（匿名可访问、过期 / 撤销 / 穿越防护）。"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="share_api", password="x")
        self.script = PerformanceScript.objects.create(name="s", created_by=self.user)
        self.execution = PerformanceExecution.objects.create(
            execution_id="PERF_SHARE_API", script=self.script, status="COMPLETED"
        )
        self.auth = APIClient()
        self.auth.force_authenticate(user=self.user)
        self.anon = APIClient()

    def _share_url(self, suffix="share-link"):
        return f"/api/performance-testing/executions/{self.execution.pk}/{suffix}/"

    def test_share_link_requires_completed_execution(self):
        self.execution.status = "RUNNING"
        self.execution.save(update_fields=["status"])
        resp = self.auth.post(self._share_url(), {})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.data)

    def test_share_link_reports_missing_report(self):
        resp = self.auth.post(self._share_url(), {})
        self.assertEqual(resp.status_code, 400)

    def test_revoke_returns_success(self):
        resp = self.auth.post(self._share_url("revoke-share-link"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])

    def test_public_report_rejects_bad_token(self):
        resp = self.anon.get("/api/performance-testing/shared/definitely-not-a-token/report/")
        self.assertEqual(resp.status_code, 404)

    def test_public_report_rejects_expired_token(self):
        token = self.execution.generate_share_token(1)
        self.execution.share_expires_at = timezone.now() - timedelta(minutes=1)
        self.execution.save(update_fields=["share_expires_at"])
        resp = self.anon.get(f"/api/performance-testing/shared/{token}/report/")
        self.assertEqual(resp.status_code, 404)

    def test_public_asset_blocks_path_traversal(self):
        token = self.execution.generate_share_token(7)
        resp = self.anon.get(
            f"/api/performance-testing/shared/{token}/report_file/",
            {"path": "../../settings.py"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_public_endpoints_do_not_require_login(self):
        """未登录也必须能打到分享端点（否则会返回 401 而不是 404）。"""
        token = self.execution.generate_share_token(7)
        resp = self.anon.get(f"/api/performance-testing/shared/{token}/report/")
        self.assertNotEqual(resp.status_code, 401)


class ConsumerAuthTests(TransactionTestCase):
    """B6：WebSocket 订阅鉴权（JWT / 分享令牌 / 无效令牌 / 已登录）。

    必须用 TransactionTestCase：消费者的 ``_token_valid`` 带
    ``@database_sync_to_async``，会在**另一个线程的连接**上查库；
    TestCase 把每个用例包在事务里，跨连接读写会触发
    "You can't execute queries until the end of the 'atomic' block"。
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ws_u", password="x")
        self.script = PerformanceScript.objects.create(name="s", created_by=self.user)
        self.execution = PerformanceExecution.objects.create(
            execution_id="PERF_WS_TEST", script=self.script, status="RUNNING"
        )

    def _consumer(self, user=None):
        from django.contrib.auth.models import AnonymousUser

        from apps.performance_testing.consumers import PerfExecutionConsumer

        consumer = PerfExecutionConsumer()
        consumer.scope = {"user": user or AnonymousUser(), "query_string": b""}
        return consumer

    def _token_valid(self, token):
        from asgiref.sync import async_to_sync

        return async_to_sync(self._consumer()._token_valid)(token)

    def test_valid_jwt_accepted(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        access = str(RefreshToken.for_user(self.user).access_token)
        self.assertTrue(self._token_valid(access))

    def test_valid_share_token_accepted(self):
        self.assertTrue(self._token_valid(self.execution.generate_share_token(7)))

    def test_expired_share_token_rejected(self):
        token = self.execution.generate_share_token(7)
        self.execution.share_expires_at = timezone.now() - timedelta(minutes=1)
        self.execution.save(update_fields=["share_expires_at"])
        self.assertFalse(self._token_valid(token))

    def test_garbage_token_rejected(self):
        self.assertFalse(self._token_valid("not-a-jwt-nor-share-token"))

    def test_authenticated_user_needs_no_token(self):
        from asgiref.sync import async_to_sync

        self.assertTrue(async_to_sync(self._consumer(user=self.user)._authenticate)())


class CleanupCommandTests(TestCase):
    """B8：cleanup_perf_data 的保留策略与安全约定。"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="clean_u", password="x")
        self.script = PerformanceScript.objects.create(name="s", created_by=self.user)

    def _execution(self, name, days_ago, status="COMPLETED"):
        execution = PerformanceExecution.objects.create(
            execution_id=name, script=self.script, status=status
        )
        when = timezone.now() - timedelta(days=days_ago)
        PerformanceExecution.objects.filter(pk=execution.pk).update(
            created_at=when, completed_at=when
        )
        execution.refresh_from_db()
        return execution

    def test_dry_run_deletes_nothing(self):
        execution = self._execution("PERF_OLD", 90)
        call_command("cleanup_perf_data", "--days", "30", "--dry-run", verbosity=0)
        self.assertTrue(PerformanceExecution.objects.filter(pk=execution.pk).exists())

    def test_old_removed_recent_kept(self):
        old = self._execution("PERF_OLD2", 90)
        fresh = self._execution("PERF_FRESH", 1)
        call_command("cleanup_perf_data", "--days", "30", verbosity=0)
        self.assertFalse(PerformanceExecution.objects.filter(pk=old.pk).exists())
        self.assertTrue(PerformanceExecution.objects.filter(pk=fresh.pk).exists())

    def test_running_execution_never_deleted(self):
        running = self._execution("PERF_RUNNING", 90, status="RUNNING")
        call_command("cleanup_perf_data", "--days", "30", verbosity=0)
        self.assertTrue(PerformanceExecution.objects.filter(pk=running.pk).exists())

    def test_baseline_source_kept_by_default(self):
        source = self._execution("PERF_BASE_SRC", 90)
        PerformanceBaseline.objects.create(script=self.script, execution=source, metrics={"p95": 1})
        call_command("cleanup_perf_data", "--days", "30", verbosity=0)
        self.assertTrue(PerformanceExecution.objects.filter(pk=source.pk).exists())

    def test_baseline_source_deleted_when_forced(self):
        source = self._execution("PERF_BASE_SRC2", 90)
        PerformanceBaseline.objects.create(script=self.script, execution=source, metrics={"p95": 1})
        call_command(
            "cleanup_perf_data", "--days", "30", "--include-baseline-sources", verbosity=0
        )
        self.assertFalse(PerformanceExecution.objects.filter(pk=source.pk).exists())


class EnvironmentActivationTests(TestCase):
    """B5：环境激活的同作用域互斥。"""

    def test_only_one_global_environment_active(self):
        first = PerformanceEnvironment.objects.create(name="g1", scope="GLOBAL", is_active=True)
        second = PerformanceEnvironment.objects.create(name="g2", scope="GLOBAL", is_active=True)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)
