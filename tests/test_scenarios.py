# AI USE AND REFERENCES
#
# The initial design of these tests was developed with assistance
# from ChatGPT (OpenAI).
# AI assistance was used to clarify how to test reproducibility,
# matrix properties, input validation, and NumPy integration.
# The tests were adapted to match the project's agreed interface.

import unittest
import numpy as np

from src.scenarios import generate_disruption_scenarios
from src.numpy_version import (
    floyd_warshall_numpy,
    floyd_warshall_batch
)


# --------------------------------------------------
# 1. Create an example railway network for testing
# --------------------------------------------------

class TestDisruptionScenarios(unittest.TestCase):

    def setUp(self):
        self.network = np.array([
            [0, 10, 15, np.inf],
            [10, 0, 20, 25],
            [15, 20, 0, 12],
            [np.inf, 25, 12, 0]
        ], dtype=float)

    # --------------------------------------------------
    # 2. Test reproducibility with the same seed
    # --------------------------------------------------

    def test_reproducibility(self):

        scenarios_1, records_1 = generate_disruption_scenarios(
            self.network,
            num_scenarios=5,
            seed=42
        )

        scenarios_2, records_2 = generate_disruption_scenarios(
            self.network,
            num_scenarios=5,
            seed=42
        )

        self.assertTrue(np.array_equal(scenarios_1, scenarios_2))
        self.assertEqual(records_1, records_2)

    # --------------------------------------------------
    # 3. Test scenario count and matrix dimensions
    # --------------------------------------------------

    def test_scenario_count_and_shape(self):

        scenarios, records = generate_disruption_scenarios(
            self.network,
            num_scenarios=5,
            seed=42
        )

        self.assertEqual(scenarios.shape, (5, 4, 4))
        self.assertEqual(len(records), 5)

    # --------------------------------------------------
    # 4. Test symmetry and zero diagonal
    # --------------------------------------------------

    def test_symmetry_and_zero_diagonal(self):

        scenarios, _ = generate_disruption_scenarios(
            self.network,
            num_scenarios=5,
            seed=42
        )

        for scenario in scenarios:

            np.testing.assert_allclose(scenario, scenario.T)

            np.testing.assert_array_equal(
                np.diag(scenario),
                np.zeros(4)
            )

    # --------------------------------------------------
    # 5. Test that the original network is not modified
    # --------------------------------------------------

    def test_original_network_unchanged(self):

        original_network = self.network.copy()

        generate_disruption_scenarios(
            self.network,
            num_scenarios=5,
            seed=42
        )

        np.testing.assert_array_equal(
            self.network,
            original_network
        )

    # --------------------------------------------------
    # 6. Test integration with NumPy Floyd-Warshall
    # --------------------------------------------------

    def test_batch_matches_individual(self):

        scenarios, _ = generate_disruption_scenarios(
            self.network,
            num_scenarios=5,
            seed=42
        )

        batch_results = floyd_warshall_batch(scenarios)

        individual_results = np.array([
            floyd_warshall_numpy(scenario)
            for scenario in scenarios
        ])

        np.testing.assert_allclose(
            batch_results,
            individual_results
        )

    # --------------------------------------------------
    # 7. Test invalid network dimensions
    # --------------------------------------------------

    def test_invalid_network_dimensions(self):

        invalid_network = np.array([
            [0, 10, 15],
            [10, 0, 20]
        ])

        with self.assertRaises(ValueError):

            generate_disruption_scenarios(
                invalid_network,
                num_scenarios=5,
                seed=42
            )

    # --------------------------------------------------
    # 8. Test invalid scenario count
    # --------------------------------------------------

    def test_invalid_scenario_count(self):

        with self.assertRaises(ValueError):

            generate_disruption_scenarios(
                self.network,
                num_scenarios=0,
                seed=42
            )
