# -*- coding: utf-8 -*-
"""需要数据库的用例（分享直链 / WebSocket 鉴权 / 清理命令 / 环境互斥）。

⚠️ 为什么文件名不以 ``test`` 开头（即不参与 ``manage.py test`` 的自动发现）：

   本平台**全新数据库**上的迁移链目前跑不通（既有问题，与本模块无关）：
   1. ``requirement_analysis/0021、0022`` 种子迁移在库中没有任何用户时硬编码
      ``created_by_id = 1``，外键必然失败（本次已顺手修好）；
   2. ``ui_automation`` 有迁移要删除仍被外键引用的列 ``ai_suite_id``，仍然失败。

   只要被发现的测试集合里存在任何 ``TestCase``，Django 就会去建测试库，
   从而整个测试套件被上面两个问题带崩。因此把这些用例单独放到本文件，
   让纯逻辑用例照常自动发现并保持全绿。

   待平台迁移链修好后，显式运行本文件即可（用例本身是完整可用的）：

       python manage.py test apps.performance_testing.tests.db_requiring_cases --noinput
       # 也可以只跑其中一个类
       python manage.py test apps.performance_testing.tests.db_requiring_cases.ShareEndpointTests --noinput

   在迁移链修好之前，可临时用「克隆开发库结构 + --keepdb」绕过（本模块 23 个用例已用此法
   验证为全绿）：先把开发库的表结构与 ``django_migrations`` 记录复制到 ``test_<库名>``，
   再执行上面命令并加 ``--keepdb``。因为迁移记录已齐全，migrate 会成为空操作。
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
