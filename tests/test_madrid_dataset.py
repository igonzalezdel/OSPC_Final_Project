
# AI USE AND REFERENCES
#
# Tests written with assistance from Claude (Anthropic) and checked
# by running them against the committed dataset.

import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import floyd_warshall as scipy_floyd_warshall

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.railway_data import load_railway_data
from src.numpy_version import floyd_warshall_numpy

DATASET = Path(__file__).resolve().parents[1] / "data" / "madrid_cercanias"


class TestMadridDataset(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data = load_railway_data(DATASET)
        cls.network = cls.data["network"]
        cls.demand = cls.data["demand"]

    def test_loads_with_agreed_format(self):
        n = len(self.data["station_names"])
        self.assertEqual(n, 60)
        self.assertEqual(self.network.shape, (n, n))
        self.assertEqual(self.demand.shape, (n, n))

    def test_every_station_has_a_link(self):
        links_per_station = np.isfinite(self.network).sum(axis=1) - 1
        self.assertTrue((links_per_station >= 1).all())

    def test_all_stations_reachable(self):
        distances = floyd_warshall_numpy(self.network)
        self.assertTrue(np.isfinite(distances).all())

    def test_matches_scipy(self):
        expected = scipy_floyd_warshall(
            np.where(np.isinf(self.network), 0, self.network), directed=False)
        np.testing.assert_allclose(floyd_warshall_numpy(self.network), expected)

    def test_demand_close_to_renfe_boardings(self):
        # Row sums come from real boardings; rounding to integers moves them slightly
        total = self.demand.sum()
        expected = self.data["metadata"]["daily_trips_in_demand"]
        self.assertEqual(total, expected)
        self.assertGreater(total, 800_000)

    def test_peak_and_offpeak_files_load(self):
        for name in ["demand_peak.csv", "demand_offpeak.csv"]:
            matrix = np.loadtxt(DATASET / name, delimiter=",", dtype=int, ndmin=2)
            self.assertEqual(matrix.shape, self.demand.shape)
            self.assertTrue((np.diag(matrix) == 0).all())


if __name__ == "__main__":
    unittest.main()
