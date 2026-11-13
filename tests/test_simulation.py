# AI USE AND REFERENCES
#
# These tests were developed with assistance from Claude (Anthropic).
# AI assistance was used to choose hand-checkable examples and to decide
# which properties to test (agreed metric definitions, reproducibility,
# agreement with the NumPy shortest-path version, command-line run).
# The expected values below were calculated by hand (see comments).

import json
import tempfile
import unittest
from math import inf
from pathlib import Path

import numpy as np

from src.numpy_version import floyd_warshall_batch
from src.simulation import main, run_batch, scenario_metrics, shortest_times

# Ring of four stations 0-1-2-3-0 (minutes): 0-1 = 10, 1-2 = 10, 2-3 = 10, 3-0 = 25.
RING = np.array([
    [0,   10,  inf, 25],
    [10,  0,   10,  inf],
    [inf, 10,  0,   10],
    [25,  inf, 10,  0],
], dtype=float)

# 100 trips per day on every ordered pair, except 0 -> 1 which has 200
# (demand does not have to be symmetric).
DEMAND = np.full((4, 4), 100, dtype=int)
np.fill_diagonal(DEMAND, 0)
DEMAND[0, 1] = 200


def block(network, i, j):
    changed = network.copy()
    changed[i, j] = changed[j, i] = inf
    return changed


def delay(network, i, j, minutes):
    changed = network.copy()
    changed[i, j] += minutes
    changed[j, i] += minutes
    return changed


def metrics_for(scenario):
    baseline = shortest_times(RING)
    return scenario_metrics(baseline, shortest_times(scenario), DEMAND)


class TestMetricsByHand(unittest.TestCase):

    def test_one_blocked_link_only_adds_delay(self):
        # Block 0-1. The detour 0-3-2-1 takes 45 min, so
        #   0<->1: 10 -> 45 (+35),  0<->2: 20 -> 35 (+15). Nothing else changes.
        # delay = 200*35 (0->1) + 100*35 (1->0) + 100*15 (0->2) + 100*15 (2->0) = 13500
        m = metrics_for(block(RING, 0, 1))
        self.assertEqual(m["disconnected_pairs"], 0)
        self.assertEqual(m["lost_trips"], 0)
        self.assertAlmostEqual(m["extra_delay_min"], 13500.0)

    def test_network_splits_in_two(self):
        # Block 0-1 and 2-3: components {0,3} and {1,2}.
        # Lost pairs (i<j): (0,1) (0,2) (1,3) (2,3) = 4.
        # Lost trips: 200 (0->1) + 100 (1->0) + six other ordered pairs * 100 = 900.
        # The pairs still connected (1-2 and 0-3) keep their travel time: delay 0.
        scenario = block(block(RING, 0, 1), 2, 3)
        m = metrics_for(scenario)
        self.assertEqual(m["disconnected_pairs"], 4)
        self.assertEqual(m["lost_trips"], 900)
        self.assertAlmostEqual(m["extra_delay_min"], 0.0)

    def test_station_isolated(self):
        # Block 0-1 and 3-0: station 0 has no route. Pairs (0,1) (0,2) (0,3) = 3.
        # Trips: 200 + 100 + 4*100 = 700.
        scenario = block(block(RING, 0, 1), 0, 3)
        m = metrics_for(scenario)
        self.assertEqual(m["disconnected_pairs"], 3)
        self.assertEqual(m["lost_trips"], 700)
        self.assertAlmostEqual(m["extra_delay_min"], 0.0)

    def test_delayed_link(self):
        # 0-1 takes 25 instead of 10. 0<->1: +15, 0<->2: 20 -> 35 (+15).
        # delay = 200*15 + 100*15 + 100*15 + 100*15 = 7500
        m = metrics_for(delay(RING, 0, 1, 15))
        self.assertEqual(m["disconnected_pairs"], 0)
        self.assertEqual(m["lost_trips"], 0)
        self.assertAlmostEqual(m["extra_delay_min"], 7500.0)

    def test_no_disruption_gives_zero(self):
        m = metrics_for(RING.copy())
        self.assertEqual(m, {"disconnected_pairs": 0, "lost_trips": 0, "extra_delay_min": 0.0})

    def test_lost_trips_are_not_counted_as_delay(self):
        # In the split scenario the lost trips must not appear in extra_delay_min.
        m = metrics_for(block(block(RING, 0, 1), 2, 3))
        self.assertEqual(m["extra_delay_min"], 0.0)


class TestBatch(unittest.TestCase):

    def setUp(self):
        self.scenarios = np.array([
            block(RING, 0, 1),
            block(block(RING, 0, 1), 2, 3),
            delay(RING, 0, 1, 15),
        ])

    def test_run_batch_matches_hand_values(self):
        _, results = run_batch(RING, DEMAND, self.scenarios)
        self.assertEqual([r["scenario"] for r in results], [0, 1, 2])
        self.assertAlmostEqual(results[0]["extra_delay_min"], 13500.0)
        self.assertEqual(results[1]["lost_trips"], 900)
        self.assertAlmostEqual(results[2]["extra_delay_min"], 7500.0)

    def test_run_batch_is_deterministic(self):
        first = run_batch(RING, DEMAND, self.scenarios)[1]
        second = run_batch(RING, DEMAND, self.scenarios)[1]
        self.assertEqual(first, second)

    def test_sequential_and_numpy_shortest_times_agree(self):
        batch = floyd_warshall_batch(self.scenarios)
        for scenario, expected in zip(self.scenarios, batch):
            np.testing.assert_allclose(shortest_times(scenario), expected, rtol=1e-12)


class TestCommandLine(unittest.TestCase):

    DATASET = Path("data/madrid_cercanias")

    @unittest.skipUnless((DATASET / "network.csv").exists(), "Madrid dataset not available")
    def test_end_to_end_and_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a"
            second = Path(tmp) / "b"
            args = ["--data", str(self.DATASET), "--scenarios", "5", "--seed", "42"]
            main(args + ["--out", str(first)])
            main(args + ["--out", str(second)])

            # Same seed and size -> identical scenario results.
            self.assertEqual((first / "scenarios.csv").read_text(),
                             (second / "scenarios.csv").read_text())

            summary = json.loads((first / "summary.json").read_text())
            self.assertEqual(summary["seed"], 42)
            self.assertEqual(summary["n_scenarios"], 5)
            self.assertEqual(summary["workers"], 1)
            for key in ("disconnected_pairs", "lost_trips", "extra_delay_min"):
                self.assertIn(key, summary["aggregate"])
                self.assertIn(key, summary["units"])
            for key in ("input", "compute", "output"):
                self.assertGreaterEqual(summary["timing_s"][key], 0.0)

            rows = (first / "scenarios.csv").read_text().strip().splitlines()
            self.assertEqual(len(rows), 1 + 5)  # header + one row per scenario


if __name__ == "__main__":
    unittest.main()
