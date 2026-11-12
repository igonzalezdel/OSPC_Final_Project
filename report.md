# NumPy Implementation and Disruption Scenario Generation – Helen's Contribution

## AI Use and Acknowledgement

ChatGPT (OpenAI) was used as an AI assistance tool throughout the development of this contribution. It helped clarify NumPy operations, vectorization, random number generation, reproducibility and testing concepts, as well as reviewing and improving the code documentation and report structure. The code was reviewed, adapted and tested to ensure consistency with the project's requirements and agreed interface.

## 1. Overview

My contribution focuses on two aspects of the project:

- **NumPy optimization:** Implementing vectorized and batch versions of the Floyd–Warshall algorithm to calculate shortest travel times.
- **Disruption scenario generation:** Creating reproducible Monte Carlo scenarios to simulate railway connection blockages and delays.

The contribution consists of four main files:

- `numpy_version.py`
- `test_correctness.py`
- `scenarios.py`
- `test_scenarios.py`

## 2. NumPy Implementation – `numpy_version.py`

This file contains two implementations:

- **`floyd_warshall_numpy(distance_matrix)`:** Calculates shortest paths for a single railway network. It replaces the two inner loops of the traditional Floyd–Warshall algorithm with NumPy broadcasting.
- **`floyd_warshall_batch(distance_matrices)`:** Extends the vectorized approach to process multiple disruption scenarios simultaneously using a three-dimensional NumPy array.

Both functions validate their inputs, preserve the original matrices and return the shortest-distance matrices.

## 3. Correctness Tests – `test_correctness.py`

This file uses Python's `unittest` framework and SciPy's Floyd–Warshall implementation as a reference to verify the NumPy algorithms.

It contains seven tests covering:

- Agreement with SciPy's results.
- Consistency between individual and batch calculations.
- Blocked connections and disconnected stations.
- Preservation of the original input matrix.
- Rejection of invalid inputs.

**Result:** All seven tests passed.

## 4. Disruption Scenario Generation – `scenarios.py`

This file implements `generate_disruption_scenarios()`, which creates different versions of the original railway network by randomly applying disruptions.

Each scenario starts from a fresh copy of the original network. Existing connections are selected without replacement, and each selected connection is either:

- **Blocked:** Its travel time is set to infinity (`np.inf`) in both directions.
- **Delayed:** A random delay is added to its travel time in both directions.

The current default simulation parameters are:

| Parameter | Default |
|---|---:|
| Number of scenarios | 100 |
| Random seed | 42 |
| Disruptions per scenario | 1–3 |
| Probability of blockage | 50% |
| Delay range | 5–30 minutes |

These are configurable initial assumptions and can be adjusted after group agreement.

### Reproducibility

The generator uses NumPy's `SeedSequence` to create an independent random stream for each scenario. This ensures that the same seed and parameters produce the same scenarios, independently of how many MPI workers are used later.

### Output

The function returns:

1. A three-dimensional NumPy array containing all modified railway networks, with shape `(scenarios, stations, stations)`.
2. A list of records describing each disruption, including the affected link, disruption type and delay duration when applicable.

The generated matrices can be passed directly to the NumPy batch implementation or distributed among the sequential and MPI implementations.

## 5. Scenario Tests – `test_scenarios.py`

This file contains seven tests verifying:

- Reproducibility with the same random seed.
- Correct number and dimensions of generated scenarios.
- Symmetry and zero diagonal values.
- Preservation of the original network.
- Consistency between individual and batch Floyd–Warshall calculations.
- Rejection of invalid network dimensions and scenario counts.

**Results:**

- Scenario generation tests: 7 passed.
- Complete project test suite: 18 passed, including tests developed by other team members.

## 6. Current Status and Next Steps

The implementations have been tested using a synthetic railway network. They are designed to follow the input format defined in `docs/interface.md`.

Remaining tasks:

- Integrate the final railway dataset.
- Agree on the final disruption parameters with the group.
- Benchmark NumPy vectorization and batch processing against the sequential implementation.
- Integrate the generated scenarios with MPI.
- Analyse execution time, speedup, efficiency and scalability.

**Summary:** My contribution provides the NumPy shortest-path implementations and the reproducible disruption scenarios needed to evaluate railway network performance under different conditions.

