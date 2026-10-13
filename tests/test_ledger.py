import os
import unittest

from model_route_ledger.ledger import build, load_trace
from model_route_ledger.pricing import cost
from model_route_ledger.router import Policy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY = Policy.load(os.path.join(ROOT, "fixtures", "policy.json"))


def step(kind, inp, out=100, cached=0, ts=None):
    return {"kind": kind, "input_tokens": inp, "cached_tokens": cached, "output_tokens": out, "ts": ts}


class TestPricing(unittest.TestCase):
    def test_haiku_cliff_prices_whole_request(self):
        below, k1 = cost("haiku-5.5", 100_000, 0, 0)
        above, k2 = cost("haiku-5.5", 100_001, 0, 0)
        self.assertEqual(k1, "haiku-5.5")
        self.assertEqual(k2, "haiku-5.5>100k")
        self.assertGreater(above, below * 4.9)

    def test_cache_reads_count_toward_cliff(self):
        _, k = cost("haiku-5.5", 10_000, 95_000, 0)
        self.assertEqual(k, "haiku-5.5>100k")


class TestLedger(unittest.TestCase):
    def test_demo_fixture_passes(self):
        led = build(load_trace(os.path.join(ROOT, "fixtures", "our_agent_day_2026-10-13.json")), POLICY)
        self.assertTrue(led["pass"])
        self.assertGreater(led["savings"], 0.5)

    def test_public_drafts_stay_on_sonnet(self):
        led = build({"steps": [step("draft_public_reply", 3000)]}, POLICY)
        self.assertEqual(led["rows"][0]["model"], "sonnet-5.5")

    def test_cliff_gate_fails(self):
        led = build({"steps": [step("log_check", 90_000)]}, POLICY, haiku_inflation=1.3)
        self.assertEqual(led["rows"][0]["price_key"], "haiku-5.5>100k")
        self.assertFalse(led["pass"])

    def test_days_to_cliff_forecast(self):
        steps = [step("log_check", 40_000, ts="2026-10-13T00:00:00+08:00"),
                 step("log_check", 50_000, ts="2026-10-14T00:00:00+08:00")]
        led = build({"steps": steps}, POLICY, haiku_inflation=1.0)
        self.assertAlmostEqual(led["log_growth_per_day"], 10_000, delta=1)
        self.assertAlmostEqual(led["days_to_cliff"], 5.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()
