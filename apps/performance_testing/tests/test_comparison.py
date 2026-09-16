# -*- coding: utf-8 -*-
"""B3：多轮对照快照的文本压缩（纯逻辑，不依赖数据库）。"""
from django.test import SimpleTestCase

from apps.performance_testing import comparison as cmp_mod


class TrimSnapshotTests(SimpleTestCase):
    def _snapshot(self):
        return {
            "reference_execution_no": "PERF_AAAA",
            "metric_keys": cmp_mod.METRIC_KEYS,
            "executions": [
                {"execution_id": "PERF_AAAA", "is_reference": True,
                 "summary": {"throughput": 100.0, "avg_response_time": 10.0, "p95": 20.0, "error_rate": 0.0},
                 "delta_pct": {"throughput": 0.0, "p95": 0.0}},
                {"execution_id": "PERF_BBBB", "is_reference": False,
                 "summary": {"throughput": 80.0, "avg_response_time": 12.0, "p95": 30.0, "error_rate": 1.5},
                 "delta_pct": {"throughput": -20.0, "p95": 50.0}},
            ],
            "step_comparison": [{
                "step_name": "登录",
                "values": [
                    {"execution_id": "PERF_AAAA", "throughput": 50.0, "avg": 9.0, "p95": 18.0, "error_rate": 0.0},
                    {"execution_id": "PERF_BBBB", "throughput": 40.0, "avg": 11.0, "p95": 28.0, "error_rate": 2.0},
                ],
            }],
        }

    def test_matrix_lines_include_reference_and_deltas(self):
        text = cmp_mod.trim_snapshot_for_ai(self._snapshot())
        self.assertIn("基准执行: PERF_AAAA", text)
        self.assertIn("PERF_BBBB", text)
        self.assertIn("50.00", text)      # ΔP95
        self.assertIn("-20.00", text)     # ΔTPS

    def test_step_comparison_section_included(self):
        text = cmp_mod.trim_snapshot_for_ai(self._snapshot())
        self.assertIn("接口级对比", text)
        self.assertIn("登录", text)

    def test_missing_numbers_rendered_as_dash(self):
        snapshot = {"executions": [{"execution_id": "X", "summary": {}, "delta_pct": {}}]}
        self.assertIn("-", cmp_mod.trim_snapshot_for_ai(snapshot))

    def test_max_chars_respected(self):
        text = cmp_mod.trim_snapshot_for_ai(self._snapshot(), max_chars=40)
        self.assertLessEqual(len(text), 40)
