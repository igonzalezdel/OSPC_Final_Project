# AI USE AND REFERENCES
#
# Tests written with assistance from Claude (Anthropic) and checked by
# running them. They compare the parallel driver with the sequential
# simulation and with src/scenarios.py.

import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.parallel import (available_links, build_scenario, main as parallel_main,
                          make_chunks, run_parallel)
from src.railway_data import load_railway_data
from src.scenarios import generate_disruption_scenarios
from src.simulation import main as sequential_main

DATA = Path(__file__).resolve().parents[1] / "data" / "madrid_cercanias"
PARAMS = {"min_disruptions": 1, "max_disruptions": 3, "block_probability": 0.5,
          "min_delay": 5, "max_delay": 30}


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.reader(file))


class TestScenarioRebuild(unittest.TestCase):

    def test_same_scenarios_as_scenarios_py(self):
        # A worker rebuilding scenario s on its own must get exactly the
        # matrix that generate_disruption_scenarios creates for s.
        network = load_railway_data(DATA)["network"]
        expected, records = generate_disruption_scenarios(network, num_scenarios=300, seed=42)
        links = available_links(network)
        for s in range(300):
            scenario, n_disruptions, n_blocked = build_scenario(network, links, 42, s, PARAMS)
            np.testing.assert_array_equal(scenario, expected[s])
            self.assertEqual(n_disruptions, len(records[s]["disruptions"]))
            blocked = sum(d["type"] == "blocked" for d in records[s]["disruptions"])
            self.assertEqual(n_blocked, blocked)


class TestChunks(unittest.TestCase):

    def test_chunks_cover_every_scenario_once(self):
        for n, workers in [(1, 1), (10, 4), (1000, 32), (7, 32)]:
            chunks = make_chunks(n, workers, 4)
            covered = [s for a, b in chunks for s in range(a, b)]
            self.assertEqual(covered, list(range(n)))


class TestSameResultsAsSequential(unittest.TestCase):

    def test_csv_identical_for_any_worker_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            sequential_main(["--data", str(DATA), "--scenarios", "120",
                             "--out", f"{tmp}/seq"])
            expected = read_rows(f"{tmp}/seq/scenarios.csv")
            for workers in [1, 2, 3]:
                parallel_main(["--data", str(DATA), "--scenarios", "120",
                               "--workers", str(workers), "--out", f"{tmp}/w{workers}",
                               "--timing-csv", f"{tmp}/timings.csv"])
                self.assertEqual(read_rows(f"{tmp}/w{workers}/scenarios.csv"), expected)
            # one timing row per run, plus the header
            self.assertEqual(len(read_rows(f"{tmp}/timings.csv")), 4)

    def test_numpy_kernel_gives_same_metrics(self):
        data = load_railway_data(DATA)
        python_rows, _ = run_parallel(data["network"], data["demand"], 60, 2, 42, PARAMS, "python")
        numpy_rows, _ = run_parallel(data["network"], data["demand"], 60, 2, 42, PARAMS, "numpy")
        for a, b in zip(python_rows, numpy_rows):
            self.assertEqual(a["disconnected_pairs"], b["disconnected_pairs"])
            self.assertEqual(a["lost_trips"], b["lost_trips"])
            self.assertAlmostEqual(a["extra_delay_min"], b["extra_delay_min"], places=6)


if __name__ == "__main__":
    unittest.main()
