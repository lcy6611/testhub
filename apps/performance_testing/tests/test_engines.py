# -*- coding: utf-8 -*-
"""B7：引擎注册表 + 内置引擎产出 JTL（后者用本机 HTTP 服务做真实压测）。"""
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from apps.performance_testing import engines
from apps.performance_testing.engines import locust_engine as locust_mod
from apps.performance_testing.engines.builtin import BuiltinEngine, _json_path_get
from apps.performance_testing.engines.locust_engine import LocustEngine
from apps.performance_testing.result_parser import parse_jtl


class RegistryTests(SimpleTestCase):
    def test_unknown_engine_falls_back_to_jmeter(self):
        """保持历史行为：脏数据不该让执行失败。"""
        self.assertEqual(engines.normalize(None), "JMETER")
        self.assertEqual(engines.normalize(""), "JMETER")
        self.assertEqual(engines.normalize("nope"), "JMETER")
        self.assertEqual(engines.normalize("builtin"), "BUILTIN")

    def test_status_covers_all_three_engines(self):
        names = [i["name"] for i in engines.engine_status(force=True)]
        self.assertEqual(names, ["JMETER", "BUILTIN", "LOCUST"])

    def test_builtin_always_available(self):
        status = {i["name"]: i for i in engines.engine_status(force=True)}
        self.assertTrue(status["BUILTIN"]["available"])

    def test_get_engine_class_rejects_jmeter(self):
        """JMeter 走 executor 原有链路，不经引擎类。"""
        with self.assertRaises(engines.EngineError):
            engines.get_engine_class("JMETER")
        self.assertIs(engines.get_engine_class("BUILTIN"), BuiltinEngine)


class JsonPathTests(SimpleTestCase):
    def test_nested_and_index_access(self):
        data = {"a": {"b": [{"c": 42}]}}
        self.assertEqual(_json_path_get(data, "$.a.b[0].c"), 42)

    def test_missing_path_returns_none(self):
        self.assertIsNone(_json_path_get({"a": 1}, "$.x.y"))


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/missing-404"):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = b'{"ok": true, "msg": "hello"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.do_GET()

    def log_message(self, *args):
        pass


class BuiltinEngineRunTests(SimpleTestCase):
    """用本机 HTTP 服务真实跑一遍内置引擎，断言产物能被既有解析器读出。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        super().tearDownClass()

    def _config(self, url, assertion=True):
        return {
            "thread_groups": [{
                "name": "g",
                "variables": [],
                "samplers": [{
                    "name": "探活",
                    "method": "GET",
                    "url": url,
                    "headers": [],
                    "params": [],
                    "body": "",
                    "assertions": [{"type": "response_code", "value": "200"}] if assertion else [],
                }],
            }],
        }

    def test_prepare_rejects_empty_sampler_list(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(engines.EngineError):
                BuiltinEngine({"thread_groups": []}, {}, tmp).prepare()

    def test_prepare_rejects_too_many_users(self):
        with TemporaryDirectory() as tmp:
            cfg = self._config(f"http://127.0.0.1:{self.port}/")
            with self.assertRaises(engines.EngineError):
                BuiltinEngine(cfg, {"thread_count": 99999}, tmp).prepare()

    def test_run_writes_parseable_jtl(self):
        with TemporaryDirectory() as tmp:
            cfg = self._config(f"http://127.0.0.1:{self.port}/")
            run_opts = {"thread_count": 2, "ramp_up": 0, "duration": 5, "loops": 2}
            result = BuiltinEngine(cfg, run_opts, tmp).run()
            self.assertEqual(result["returncode"], 0)

            jtl = Path(result["jtl_path"])
            self.assertTrue(jtl.exists())
            header = jtl.read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(header, ",".join(engines.JTL_COLUMNS))

            parsed = parse_jtl(str(jtl))
            self.assertFalse(parsed.get("error"))
            # 2 个用户 × 2 轮 × 1 个请求
            self.assertEqual(parsed["summary"]["total_samples"], 4)
            self.assertEqual(parsed["summary"]["error_count"], 0)
            self.assertEqual(parsed["metrics"][0]["sample_label"], "探活")

    def test_failed_assertion_recorded_as_error(self):
        with TemporaryDirectory() as tmp:
            cfg = self._config(f"http://127.0.0.1:{self.port}/")
            # 断言期望 404，但服务返回 200 → 样本应记为失败
            cfg["thread_groups"][0]["samplers"][0]["assertions"] = [{"type": "response_code", "value": "404"}]
            result = BuiltinEngine(cfg, {"thread_count": 1, "ramp_up": 0, "duration": 3, "loops": 1}, tmp).run()
            parsed = parse_jtl(result["jtl_path"])
            self.assertEqual(parsed["summary"]["error_count"], 1)
            self.assertEqual(parsed["summary"]["error_rate"], 100.0)

    def test_unreachable_target_recorded_as_error(self):
        with TemporaryDirectory() as tmp:
            # 127.0.0.1:1 基本必然连接失败，且不能让引擎抛异常
            cfg = self._config("http://127.0.0.1:1/")
            result = BuiltinEngine(cfg, {"thread_count": 1, "ramp_up": 0, "duration": 3, "loops": 1}, tmp).run()
            self.assertEqual(result["returncode"], 0)
            parsed = parse_jtl(result["jtl_path"])
            self.assertEqual(parsed["summary"]["error_count"], 1)

    def test_variable_substitution_in_url(self):
        with TemporaryDirectory() as tmp:
            cfg = self._config("http://127.0.0.1:{{port}}/")
            cfg["thread_groups"][0]["variables"] = [{"name": "port", "value": str(self.port)}]
            parsed = None
            engine = BuiltinEngine(cfg, {"thread_count": 1, "ramp_up": 0, "duration": 3, "loops": 1}, tmp)
            result = engine.run()
            parsed = parse_jtl(result["jtl_path"])
            self.assertEqual(parsed["summary"]["error_count"], 0)


@unittest.skipUnless(locust_mod.is_available(), "未安装 locust，跳过 Locust 引擎运行用例")
class LocustEngineRunTests(SimpleTestCase):
    """用本机 HTTP 服务真实跑一遍 Locust 引擎（未装 locust 时自动跳过）。

    覆盖真实运行路径：生成 locustfile → 起 locust 子进程 → events.request 钩子写 JTL
    → 既有 result_parser 能解析。同时验证按循环次数停止（users × loops × 每轮请求数）。
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        super().tearDownClass()

    def _config(self):
        return {
            "thread_groups": [{
                "name": "g",
                "variables": [],
                "samplers": [{
                    "name": "探活",
                    "method": "GET",
                    "url": f"http://127.0.0.1:{self.port}/",
                    "headers": [],
                    "params": [],
                    "body": "",
                    "assertions": [],
                }],
            }],
        }

    def test_prepare_rejects_empty_steps(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(engines.EngineError):
                LocustEngine({"thread_groups": []}, {}, tmp).prepare()

    def test_run_writes_parseable_jtl_and_honours_loops(self):
        with TemporaryDirectory() as tmp:
            engine = LocustEngine(
                self._config(),
                {"thread_count": 2, "ramp_up": 1, "duration": 60, "loops": 2},
                tmp,
            )
            result = engine.run()

            jtl = Path(result["jtl_path"])
            self.assertTrue(jtl.exists(), "Locust 未产出 JTL")
            header = jtl.read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(header, ",".join(engines.JTL_COLUMNS))

            parsed = parse_jtl(str(jtl))
            self.assertFalse(parsed.get("error"))
            # 2 用户 × 2 轮 × 1 个请求 —— 达标即停，而不是跑满 60s
            self.assertEqual(parsed["summary"]["total_samples"], 4)
            self.assertEqual(parsed["summary"]["error_count"], 0)
            self.assertEqual(parsed["metrics"][0]["sample_label"], "探活")

    def test_http_error_status_counted_as_failure(self):
        """与 JMeter/Locust 一致：非 2xx 记为失败样本。"""
        with TemporaryDirectory() as tmp:
            cfg = self._config()
            cfg["thread_groups"][0]["samplers"][0]["url"] = f"http://127.0.0.1:{self.port}/missing-404"
            result = LocustEngine(
                cfg, {"thread_count": 1, "ramp_up": 1, "duration": 60, "loops": 1}, tmp
            ).run()
            parsed = parse_jtl(result["jtl_path"])
            self.assertEqual(parsed["summary"]["total_samples"], 1)
            self.assertEqual(parsed["summary"]["error_count"], 1)
