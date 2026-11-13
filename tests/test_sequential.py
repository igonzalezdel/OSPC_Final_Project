# AI USE AND REFERENCES
#
# The initial version of these tests was generated with ChatGPT
# (OpenAI, https://chatgpt.com).
#
# I worked with ChatGPT to understand Python testing, decide which
# checks were useful for our algorithm, and refine the code and
# comments through several iterations.
#
# Prompts included requests to test Floyd-Warshall and route
# reconstruction, explain unittest, compare results with SciPy,
# and simplify the testing approach.
#
# Reference:
# https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csgraph.floyd_warshall.html

import unittest
from math import inf
import numpy as np
from scipy.sparse.csgraph import floyd_warshall as scipy_floyd_warshall

from src.sequential import floyd_warshall, reconstruct_path


# We use this same example for more than one test, so we only
# need to define the network once.
# Each value represents a direct travel time in minutes.
network = [
    [0,   2,   inf, inf, 20],
    [2,   0,   3,   inf, inf],
    [inf, 3,   0,   2,   inf],
    [inf, inf, 2,   0,   2],
    [20,  inf, inf, 2,   0]
]


# Each test checks a different aspect of our algorithm.
class TestFloydWarshall(unittest.TestCase):

    def test_shortest_route(self):
        # Check that the algorithm finds a faster route from A to E
        # through B, C and D, rather than taking the direct connection.
        distances, next_station = floyd_warshall(network)

        # assertEqual checks whether the result matches the answer
        # we expect: 2 + 3 + 2 + 2 = 9 minutes.
        self.assertEqual(distances[0][4], 9)

        # Check that reconstruct_path returns the correct stations
        # in order, using their positions in the original matrix.
        route = reconstruct_path(0, 4, next_station)
        self.assertEqual(route, [0, 1, 2, 3, 4])

    def test_no_available_route(self):
        # In this network, A and B are connected but C is isolated.
        # We want to check what happens when no route exists.
        disconnected_network = [
            [0,   2,   inf],
            [2,   0,   inf],
            [inf, inf, 0]
        ]

        distances, next_station = floyd_warshall(disconnected_network)

        # The travel time should remain infinite, and there
        # should be no route to reconstruct.
        self.assertEqual(distances[0][2], inf)
        self.assertIsNone(reconstruct_path(0, 2, next_station))

    def test_original_matrix_unchanged(self):
        # Save a copy of the original network before running
        # Floyd-Warshall, so we can check that it stays unchanged.
        original_network = [row.copy() for row in network]

        floyd_warshall(network)

        # Check that the original direct travel times are preserved.
        self.assertEqual(network, original_network)

    def test_matches_scipy(self):
        # Our function returns two matrices: the shortest travel times
        # and the information needed to reconstruct the routes.
        # Here, we only need the travel times, so we use _ to ignore
        # the second result (next_station).
        our_distances, _ = floyd_warshall(network)

        # SciPy uses a NumPy array, so we convert our matrix
        # before passing it to the library.
        scipy_distances = scipy_floyd_warshall(
            np.array(network, dtype=float),
            directed=True
        )

        # Compare the entire distance matrices.
        # assert_allclose allows small numerical differences.
        np.testing.assert_allclose(our_distances, scipy_distances)


# Run the tests when this file is executed directly.
if __name__ == "__main__":
    unittest.main()
