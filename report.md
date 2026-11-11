# NumPy Implementation – Helen's Contribution

## 1. Overview

My contribution to the project focuses on implementing an optimized version of the Floyd–Warshall algorithm using NumPy.

The objective is to calculate the shortest travel times between all pairs of railway stations while reducing the number of Python loops required by the traditional sequential implementation.

I developed two approaches:

- **NumPy Vectorization:** Calculates shortest paths for one railway network using NumPy operations.
- **Batch Processing:** Extends the vectorized implementation to calculate shortest paths for multiple railway disruption scenarios simultaneously.

My contribution consists of two main files: `numpy_version.py` and `test_correctness.py`.

## 2. File 1: `numpy_version.py`

This file contains the two implementations of the Floyd–Warshall algorithm.

### A. `floyd_warshall_numpy(distance_matrix)`

This function calculates the shortest travel times between all pairs of stations in a single railway network.

Unlike the traditional sequential implementation, which uses three nested Python loops, this version keeps only the loop over intermediate stations and uses NumPy broadcasting to perform the calculations for all starting and destination stations simultaneously.

The main operations are:

1. Create a copy of the original distance matrix to avoid modifying the input.
2. Validate the matrix dimensions and values.
3. Iterate through each station as a possible intermediate station.
4. Calculate alternative routes through that station using NumPy broadcasting.
5. Compare the alternative routes with the current distances using `np.minimum()`.
6. Return the final shortest-distance matrix.

**Main optimization:** The two inner Python loops are replaced with NumPy matrix operations, allowing calculations to be performed on entire rows and columns simultaneously.

### B. `floyd_warshall_batch(distance_matrices)`

This function extends the previous implementation to process multiple railway networks simultaneously.

In our project, each matrix represents a different railway disruption scenario. For example, one scenario might involve a blocked connection between stations A and B, while another involves a blocked connection between stations B and C.

Instead of calling the single-network function separately for every scenario, this implementation uses a three-dimensional NumPy array:

`(number_of_scenarios, number_of_stations, number_of_stations)`

NumPy broadcasting then performs the shortest-path calculations across all scenarios simultaneously.

**Main optimization:** Multiple disruption scenarios can be processed together using the same loop over intermediate stations.

It is important to note that batch processing is an approach we want to evaluate, not an assumption that it will always be faster. Its performance still needs to be benchmarked.

## 3. File 2: `test_correctness.py`

This file checks whether both NumPy implementations produce correct results.

It uses Python's built-in `unittest` framework and SciPy's Floyd–Warshall implementation as an independent reference.

The file currently contains seven tests:

| Test | What it checks |
|---|---|
| `test_matches_scipy` | Compares the NumPy results with SciPy. |
| `test_batch_matches_individual_results` | Checks whether batch processing gives the same results as processing each scenario separately. |
| `test_blocked_connection` | Verifies that an alternative route is found when a direct connection is blocked. |
| `test_disconnected_stations` | Checks how the algorithm handles stations with no available route. |
| `test_original_matrix_unchanged` | Ensures that the original input matrix is not modified. |
| `test_invalid_input` | Checks that invalid matrices, negative values and NaN are rejected. |
| `test_invalid_batch_input` | Checks that invalid batch dimensions are rejected. |

**Current result:** All seven tests have passed successfully.

## 4. Current Data and Future Integration

At the moment, the tests use a small example railway network and artificially created disruption scenarios.

These examples are only being used to develop and verify the implementations while the group's final dataset is being prepared.

Once the final dataset is available, the distance matrices and disruption scenarios will be supplied from the actual railway data.

The functions in `numpy_version.py` are designed to work with different compatible distance matrices, so the core algorithm should not need to be rewritten.

## 5. Next Steps

The remaining work for my contribution is:

- Integrate the final railway dataset.
- Compare execution times against the sequential implementation.
- Evaluate whether batch processing improves performance compared with processing scenarios individually.
- Analyse and report the performance results.

**In summary:** My contribution provides a NumPy-vectorized and batch-processing alternative to the sequential Floyd–Warshall algorithm, together with tests to verify its correctness.
