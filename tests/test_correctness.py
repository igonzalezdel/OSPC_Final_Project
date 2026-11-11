
# AI USE AND REFERENCES
#
# The initial version of these tests was developed with assistance
# from ChatGPT (OpenAI, https://chatgpt.com).
#
# I used ChatGPT to understand Python unit testing, verify the
# NumPy-vectorized Floyd-Warshall implementation against SciPy,
# and design tests for batch processing of railway disruption
# scenarios.
#
# I also reviewed and refined the tests to understand what each
# test checks and why it is necessary.
#
# Prompts included requests to compare NumPy results with SciPy,
# test multiple distance matrices, and check disconnected stations
# and blocked railway connections.
#
# Reference:
# https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csgraph.floyd_warshall.html


import unittest
import numpy as np
from scipy.sparse.csgraph import floyd_warshall as scipy_floyd_warshall

from src.numpy_version import (
    floyd_warshall_numpy,
    floyd_warshall_batch
)


#TEMPORARY TEST DATA: 
#This is a small railway network is only used to test
#whether NumPy implementation works correctly. 
#
#Once the final dataset is available we will use the real
#railway network for additional tests and performance benchmarks
# Each value represents a direct travel time in minutes.
# np.inf means there is no direct connection.
network = np.array([
    [0,   2,   np.inf, np.inf, 20],
    [2,   0,   3,      np.inf, np.inf],
    [np.inf, 3, 0,     2,      np.inf],
    [np.inf, np.inf, 2, 0,     2],
    [20, np.inf, np.inf, 2,     0]
], dtype=float)


class TestNumpyFloydWarshall(unittest.TestCase):

    def test_matches_scipy(self):
        # Calculate shortest travel times using our NumPy implementation.
        numpy_result = floyd_warshall_numpy(network)

        # Calculate the reference results using SciPy.
        scipy_result = scipy_floyd_warshall(
            network,
            directed=False
        )

        # Check that both implementations produce the same results.
        np.testing.assert_allclose(numpy_result, scipy_result)

    def test_batch_matches_individual_results(self):
	#TEMPORARY TEST DISRUPTIONS:
	#These scenarios simulate railway connections being blocked
	#Once the final dataset is available, we will generate disruption
	#scenarios using the real railway network and its connections. 

        scenario_1 = network.copy()
        scenario_1[0, 1] = np.inf
        scenario_1[1, 0] = np.inf

        scenario_2 = network.copy()
        scenario_2[1, 2] = np.inf
        scenario_2[2, 1] = np.inf

        # Combine the scenarios into one three-dimensional array.
        scenarios = np.array([scenario_1, scenario_2])

        # Process both scenarios using batch processing.
        batch_results = floyd_warshall_batch(scenarios)

        # Process each scenario individually.
        individual_results = np.array([
            floyd_warshall_numpy(scenario)
            for scenario in scenarios
        ])

        # Check that batch and individual calculations agree.
        np.testing.assert_allclose(
            batch_results,
            individual_results
        )

    def test_blocked_connection(self):
        # Block the direct connection between stations A and B.
        blocked_network = network.copy()
        blocked_network[0, 1] = np.inf
        blocked_network[1, 0] = np.inf

        # Calculate the new shortest travel times.
        result = floyd_warshall_numpy(blocked_network)

        # Check that an alternative route is found.
        # A -> E -> D -> C -> B = 20 + 2 + 2 + 3 = 27.
        self.assertEqual(result[0, 1], 27)

    def test_disconnected_stations(self):
        # Create a network where station C is isolated.
        disconnected_network = np.array([
            [0,   2,   np.inf],
            [2,   0,   np.inf],
            [np.inf, np.inf, 0]
        ])

        result = floyd_warshall_numpy(disconnected_network)

        # Check that no route exists between A and C.
        self.assertEqual(result[0, 2], np.inf)

    def test_original_matrix_unchanged(self):
        # Save a copy of the original network.
        original_network = network.copy()

        # Run the algorithm.
        floyd_warshall_numpy(network)

        # Check that the original network was not modified.
        np.testing.assert_array_equal(network, original_network)

    def test_invalid_input(self):
        # A non-square matrix should raise a ValueError.
        with self.assertRaises(ValueError):
            floyd_warshall_numpy([[0, 2, 3], [2, 0, 1]])

        # Negative travel times should raise a ValueError.
        with self.assertRaises(ValueError):
            floyd_warshall_numpy([[0, -2], [-2, 0]])

        # NaN values should raise a ValueError.
        with self.assertRaises(ValueError):
            floyd_warshall_numpy([[0, np.nan], [np.nan, 0]])

    def test_invalid_batch_input(self):
        # Batch input must contain square matrices.
        with self.assertRaises(ValueError):
            floyd_warshall_batch(np.array([
                [[0, 2, 3], [2, 0, 1]]
            ]))


if __name__ == "__main__":
    unittest.main()

