# -*- coding: utf-8 -*-
"""B1：SLA 阈值判定 + 验收目标判定（纯逻辑，不依赖数据库）。"""
from django.test import SimpleTestCase

from apps.performance_testing import sla, targets_eval
from apps.performance_testing.acceptance import evaluate_acceptance


class SlaEvaluateTests(SimpleTestCase):
    def test_not_enabled_returns_not_evaluated(self):
        result, detail = sla.evaluate({}, {"p95": 100})
        self.assertEqual(result, "NOT_EVALUATED")
        self.assertEqual(detail, [])

    def test_breach_marks_failed_with_per_metric_detail(self):
        result, detail = sla.evaluate(
            {"enabled": True, "thresholds": {"p95_response_time": 1000, "min_tps": 50}},
            {"p95": 1500, "throughput": 80},
        )
        self.assertEqual(result, "FAILED")
        by_metric = {d["metric"]: d for d in detail}
        self.assertFalse(by_metric["p95_response_time"]["passed"])
        self.assertTrue(by_metric["min_tps"]["passed"])

    def test_all_within_threshold_passes(self):
        result, _ = sla.evaluate(
            {"enabled": True, "thresholds": {"p95_response_time": 2000, "min_tps": 50}},
            {"p95": 1500, "throughput": 80},
        )
        self.assertEqual(result, "PASSED")

    def test_blank_thresholds_are_skipped(self):
        result, detail = sla.evaluate(
            {"enabled": True, "thresholds": {"p95_response_time": None, "min_tps": 50}},
            {"p95": 99999, "throughput": 80},
        )
        self.assertEqual(result, "PASSED")
        self.assertEqual([d["metric"] for d in detail], ["min_tps"])


class BreachDetectorTests(SimpleTestCase):
    """熔断要连续 N 个周期违规才触发，避免单点抖动误判。"""

    def _detector(self, window=2):
        return sla.BreachDetector(
            {"enabled": True, "abort_on_breach": True, "breach_window": window,
             "thresholds": {"p95_response_time": 100}},
            sample_interval=1,
        )

    def test_single_breach_does_not_trip(self):
        self.assertFalse(self._detector().check({"p95": 500}))

    def test_consecutive_breaches_trip(self):
        d = self._detector()
        d.check({"p95": 500})
        self.assertTrue(d.check({"p95": 500}))

    def test_compliant_sample_resets_streak(self):
        d = self._detector()
        d.check({"p95": 500})
        d.check({"p95": 10})     # 回到阈值内，连续计数清零
        self.assertFalse(d.check({"p95": 500}))

    def test_disabled_never_trips(self):
        d = sla.BreachDetector({"enabled": True, "abort_on_breach": False,
                                "thresholds": {"p95_response_time": 100}}, sample_interval=1)
        self.assertFalse(d.check({"p95": 500}))
        self.assertFalse(d.check({"p95": 500}))


class TargetsEvalTests(SimpleTestCase):
    def test_empty_targets_not_evaluated(self):
        verdict, details = targets_eval.evaluate_targets({}, [], {})
        self.assertEqual(verdict, "NOT_EVALUATED")
        self.assertEqual(details, [])

    def test_p95_over_target_fails(self):
        verdict, details = targets_eval.evaluate_targets(
            {"max_p95_rt": 1000},
            [{"sample_label": "登录", "p95": 1500, "avg": 300, "error_rate": 0}],
            {"throughput": 100},
        )
        self.assertEqual(verdict, "FAILED")
        self.assertTrue(any(d["metric"] == "P95响应时间" and d["result"] == "FAIL" for d in details))

    def test_overall_tps_shortfall_fails(self):
        verdict, details = targets_eval.evaluate_targets(
            {"min_tps": 100}, [{"sample_label": "A", "p95": 10, "avg": 5, "error_rate": 0}],
            {"throughput": 60},
        )
        self.assertEqual(verdict, "FAILED")
        overall = [d for d in details if d["step"] == "(整体)" and d["metric"] == "TPS"]
        self.assertEqual(len(overall), 1)
        self.assertEqual(overall[0]["result"], "FAIL")

    def test_all_within_targets_passes(self):
        verdict, _ = targets_eval.evaluate_targets(
            {"max_p95_rt": 1000, "min_tps": 50},
            [{"sample_label": "A", "p95": 100, "avg": 50, "error_rate": 0}],
            {"throughput": 200},
        )
        self.assertEqual(verdict, "PASSED")


class AcceptanceAggregateTests(SimpleTestCase):
    def test_both_dimensions_are_returned(self):
        fields = evaluate_acceptance(
            {"max_p95_rt": 5000},
            {"enabled": True, "thresholds": {"error_rate": 5}},
            {"p95": 100, "throughput": 200, "error_rate": 1},
            [{"sample_label": "A", "p95": 100, "avg": 50, "error_rate": 1}],
        )
        self.assertEqual(set(fields), {"sla_result", "sla_detail", "verdict", "verdict_details"})
        self.assertEqual(fields["sla_result"], "PASSED")
        self.assertEqual(fields["verdict"], "PASSED")

    def test_unconfigured_script_is_not_evaluated(self):
        fields = evaluate_acceptance(None, None, {"p95": 1}, [])
        self.assertEqual(fields["sla_result"], "NOT_EVALUATED")
        self.assertEqual(fields["verdict"], "NOT_EVALUATED")
