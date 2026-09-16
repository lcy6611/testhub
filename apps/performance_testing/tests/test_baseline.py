# -*- coding: utf-8 -*-
"""B2：性能基线劣化比对（纯逻辑，不依赖数据库）。"""
from django.test import SimpleTestCase

from apps.performance_testing import baseline as bl


class CompareTests(SimpleTestCase):
    BASE = {"avg_response_time": 100, "p95": 200, "p99": 300, "throughput": 1000}

    def test_rt_degradation_beyond_tolerance(self):
        degraded, items = bl.compare(
            self.BASE, {**self.BASE, "p95": 260}, {}    # P95 +30% > 默认 20%
        )
        self.assertTrue(degraded)
        p95 = next(i for i in items if i["metric"] == "p95")
        self.assertEqual(p95["change_pct"], 30.0)
        self.assertTrue(p95["degraded"])

    def test_tps_drop_within_tolerance_is_ok(self):
        degraded, items = bl.compare(self.BASE, {**self.BASE, "throughput": 950}, {})
        self.assertFalse(degraded)
        tps = next(i for i in items if i["metric"] == "throughput")
        self.assertEqual(tps["direction"], "higher_better")
        self.assertFalse(tps["degraded"])

    def test_tps_drop_beyond_tolerance_is_degraded(self):
        degraded, _ = bl.compare(self.BASE, {**self.BASE, "throughput": 700}, {})
        self.assertTrue(degraded)

    def test_custom_tolerance_can_suppress_degradation(self):
        degraded, _ = bl.compare({"p95": 200}, {"p95": 260}, {"rt_degrade_pct": 50})
        self.assertFalse(degraded)

    def test_empty_baseline_yields_nothing(self):
        degraded, items = bl.compare({}, {"p95": 100}, {})
        self.assertFalse(degraded)
        self.assertEqual(items, [])

    def test_zero_baseline_value_is_skipped(self):
        _, items = bl.compare({"p95": 0}, {"p95": 100}, {})
        self.assertEqual(items, [])


class ToleranceTests(SimpleTestCase):
    def test_defaults_filled(self):
        self.assertEqual(bl.merge_tolerance(None), bl.DEFAULT_TOLERANCE)

    def test_invalid_values_fall_back_to_default(self):
        merged = bl.merge_tolerance({"rt_degrade_pct": "abc", "tps_degrade_pct": 5})
        self.assertEqual(merged["rt_degrade_pct"], bl.DEFAULT_TOLERANCE["rt_degrade_pct"])
        self.assertEqual(merged["tps_degrade_pct"], 5)


class SummaryToMetricsTests(SimpleTestCase):
    def test_dict_and_object_both_supported(self):
        from apps.performance_testing.models import PerformanceSummary

        as_dict = bl.summary_to_metrics({"avg_response_time": 12.5, "throughput": 88})
        self.assertEqual(as_dict["avg_response_time"], 12.5)
        self.assertEqual(as_dict["throughput"], 88)

        obj = PerformanceSummary(avg_response_time=1, p95=2, p99=3, throughput=4)
        as_obj = bl.summary_to_metrics(obj)
        self.assertEqual(as_obj, {"avg_response_time": 1.0, "p95": 2.0, "p99": 3.0, "throughput": 4.0})

    def test_none_returns_empty(self):
        self.assertEqual(bl.summary_to_metrics(None), {})
