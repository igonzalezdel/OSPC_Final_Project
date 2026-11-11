

# AI USE AND REFERENCES
#
# The initial implementation of the NumPy-vectorized Floyd-Warshall
# algorithm was developed with assistance from ChatGPT
# (OpenAI, https://chatgpt.com).
#
# I used ChatGPT to understand NumPy broadcasting, explore how to
# vectorize the Floyd-Warshall algorithm, investigate batch processing
# of multiple railway disruption scenarios, and review the code.
#
# I also reviewed and refined the implementation to understand
# the operations and ensure that the results are correct.
#
# Prompts included requests to explain NumPy broadcasting, convert
# the standard Floyd-Warshall algorithm into a vectorized version,
# and investigate processing multiple distance matrices together.
#
# References:
# https://numpy.org/doc/stable/user/basics.broadcasting.html
# https://numpy.org/doc/stable/reference/generated/numpy.minimum.html


import numpy as np


def floyd_warshall_numpy(distance_matrix):
    """
    Calculate the shortest travel times between all stations
    using NumPy vectorization.

    Input:
        distance_matrix: Square matrix of direct travel times.
                         np.inf means there is no direct connection.

    Returns:
        distances: Matrix containing the shortest travel times.
    """

    # Create a copy so that the original matrix is not modified.
    distances = np.array(distance_matrix, dtype=float, copy=True)

    # Check that the input is a square matrix.
    if distances.ndim != 2 or distances.shape[0] != distances.shape[1]:
        raise ValueError("The distance matrix must be square.")

    # Check that travel times are non-negative and not NaN.
    if np.isnan(distances).any() or (distances < 0).any():
        raise ValueError("Travel times must be non-negative and cannot contain NaN.")

    # Get the number of stations in the network.
    n = distances.shape[0]

    # Consider each station as an intermediate station.
    for k in range(n):

        # Calculate alternative routes through station k.
        # NumPy broadcasting adds the column and row together.
        new_distances = (
            distances[:, k:k+1] + distances[k:k+1, :]
        )

        # Keep the shortest distance between every pair of stations.
        distances = np.minimum(distances, new_distances)

    return distances


def floyd_warshall_batch(distance_matrices):
    """
    Calculate shortest travel times for multiple railway disruption
    scenarios using NumPy broadcasting.

    Input:
        distance_matrices: Three-dimensional array containing
                           multiple distance matrices.
                           Shape: (scenarios, stations, stations).

    Returns:
        distances: Three-dimensional array containing the shortest
                   travel times for every scenario.
    """

    # Create a copy so that the original matrices are not modified.
    distances = np.array(distance_matrices, dtype=float, copy=True)

    # Check that the input contains square matrices.
    if distances.ndim != 3 or distances.shape[1] != distances.shape[2]:
        raise ValueError("Input must contain multiple square matrices.")

    # Check that travel times are non-negative and not NaN.
    if np.isnan(distances).any() or (distances < 0).any():
        raise ValueError("Travel times must be non-negative and cannot contain NaN.")

    # Get the number of stations in each network.
    n = distances.shape[1]

    # Consider each station as an intermediate station.
    for k in range(n):

        # Calculate alternative routes through station k
        # for all scenarios simultaneously.
        new_distances = (
            distances[:, :, k:k+1] +
            distances[:, k:k+1, :]
        )

        # Keep the shortest distances for every scenario.
        distances = np.minimum(distances, new_distances)

    return distances

