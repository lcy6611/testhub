# -*- coding: utf-8 -*-
"""B5：压测环境叠加（纯逻辑，不依赖数据库）。"""
from django.test import SimpleTestCase

from apps.performance_testing import environment as env_mod


class _Env:
    """轻量替身，避免为纯逻辑测试引入数据库。"""

    def __init__(self, **kw):
        self.id = kw.get("id", 1)
        self.name = kw.get("name", "prod")
        self.base_url = kw.get("base_url", "")
        self.headers = kw.get("headers", {})
        self.variables = kw.get("variables", [])
        self.verify_ssl = kw.get("verify_ssl", False)


class RewriteUrlTests(SimpleTestCase):
    def test_origin_replaced_and_query_kept(self):
        self.assertEqual(
            env_mod.rewrite_url("http://dev.local/api/login?x=1", "https://prod.example.com"),
            "https://prod.example.com/api/login?x=1",
        )

    def test_base_url_path_prefix_is_prepended(self):
        self.assertEqual(
            env_mod.rewrite_url("http://dev.local/api/login", "https://prod.example.com/v1"),
            "https://prod.example.com/v1/api/login",
        )

    def test_existing_prefix_not_duplicated(self):
        self.assertEqual(
            env_mod.rewrite_url("https://prod.example.com/v1/api/login", "https://prod.example.com/v1"),
            "https://prod.example.com/v1/api/login",
        )

    def test_relative_path_joined_to_base(self):
        self.assertEqual(
            env_mod.rewrite_url("/api/login", "https://prod.example.com/v1"),
            "https://prod.example.com/v1/api/login",
        )

    def test_empty_base_url_keeps_url_unchanged(self):
        self.assertEqual(env_mod.rewrite_url("http://dev.local:8080/a", ""), "http://dev.local:8080/a")

    def test_invalid_base_url_keeps_url_unchanged(self):
        self.assertEqual(env_mod.rewrite_url("http://dev.local/a", "not-a-url"), "http://dev.local/a")


class MergeVariablesTests(SimpleTestCase):
    def test_env_overrides_same_name_and_keeps_both_uniques(self):
        merged = env_mod.merge_variables(
            [{"name": "token", "value": "script"}, {"name": "only_script", "value": "s"}],
            [{"name": "token", "value": "env"}, {"name": "only_env", "value": "e"}],
        )
        as_map = {m["name"]: m["value"] for m in merged}
        self.assertEqual(as_map["token"], "env")
        self.assertEqual(as_map["only_script"], "s")
        self.assertEqual(as_map["only_env"], "e")

    def test_unnamed_entries_ignored(self):
        merged = env_mod.merge_variables([], [{"name": "  "}, {"value": "x"}])
        self.assertEqual(merged, [])


class BuildEffectiveConfigTests(SimpleTestCase):
    def _config(self):
        return {
            "thread_groups": [{
                "name": "g",
                "variables": [{"name": "token", "value": "script"}],
                "samplers": [{
                    "name": "s1",
                    "url": "http://dev.local/api/login",
                    "headers": [{"name": "X-Env", "value": "dev"}, {"name": "A", "value": "1"}],
                }],
            }],
        }

    def test_sampler_url_rewritten_and_env_header_overrides(self):
        out = env_mod.build_effective_config(
            self._config(),
            _Env(base_url="https://prod.example.com/v1", headers={"X-Env": "prod"},
                 variables=[{"name": "token", "value": "env"}]),
        )
        sampler = out["thread_groups"][0]["samplers"][0]
        self.assertEqual(sampler["url"], "https://prod.example.com/v1/api/login")
        headers = {h["name"]: h["value"] for h in sampler["headers"]}
        self.assertEqual(headers["X-Env"], "prod")   # 环境覆盖
        self.assertEqual(headers["A"], "1")          # 脚本独有保留

    def test_source_config_not_mutated(self):
        source = self._config()
        env_mod.build_effective_config(source, _Env(base_url="https://prod.example.com"))
        self.assertEqual(source["thread_groups"][0]["samplers"][0]["url"], "http://dev.local/api/login")

    def test_no_environment_returns_equivalent_copy(self):
        source = self._config()
        self.assertEqual(env_mod.build_effective_config(source, None), source)

    def test_environment_marker_recorded(self):
        out = env_mod.build_effective_config(self._config(), _Env(id=9, name="stg"))
        self.assertEqual(out["_environment"]["id"], 9)
        self.assertEqual(out["_environment"]["name"], "stg")
