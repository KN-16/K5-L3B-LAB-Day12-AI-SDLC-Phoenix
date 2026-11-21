import unittest

from chonoi.bench import summarize
from chonoi.contract import load_contract
from chonoi.soak import run_soak


class Phase4Tests(unittest.TestCase):
    def test_bench_uses_mean_of_slowest_ceil_one_percent(self):
        report = summarize([10.0] * 99 + [40.0, 60.0], 234.5)
        self.assertEqual(report["frames"], 101)
        self.assertAlmostEqual(report["measured_s"], 1.09)
        self.assertAlmostEqual(report["avg_fps"], 101 / 1.09)
        self.assertAlmostEqual(report["p1_low_fps"], 20.0)
        self.assertEqual(report["load_ms"], 234)

    def test_soak_crosses_day_five_in_one_session(self):
        tuning = load_contract()["tuning"]
        tuning["gather"]["duration_s"] = tuning["quan"]["duration_s"] = 1 / 60
        result = run_soak(tuning, 7, 6)
        self.assertEqual((result["days_completed"], result["crashes"]), (6, 0))
        self.assertEqual([row["day"] for row in result["results"]], list(range(1, 7)))
