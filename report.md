# NumPy Implementation, Disruption Scenario Generation and Railway Data Loading – Helen's Contribution

## AI Use and Acknowledgement

ChatGPT (OpenAI) was used as an AI assistance tool throughout the development of this contribution. It helped clarify NumPy operations, vectorization, random number generation, data loading, validation and testing concepts, as well as reviewing the code documentation and report structure. The code was reviewed, adapted and tested to ensure consistency with the project's requirements and agreed interface.

## 1. Overview

My contribution focuses on three aspects of the project:

- **NumPy optimization:** Implementing vectorized and batch versions of the Floyd–Warshall algorithm.
- **Disruption scenario generation:** Creating reproducible scenarios of railway connection blockages and delays.
- **Railway data loading:** Developing reusable functions to load and validate railway network and passenger-demand data.

The main files are:

- `numpy_version.py`
- `scenarios.py`
- `railway_data.py`
- `test_correctness.py`
- `test_scenarios.py`

## 2. NumPy Implementation – `numpy_version.py`

This file contains two implementations:

- **`floyd_warshall_numpy(distance_matrix)`:** Calculates shortest paths for a single network using NumPy broadcasting instead of the two inner loops of the traditional algorithm.
- **`floyd_warshall_batch(distance_matrices)`:** Processes multiple disruption scenarios simultaneously using a three-dimensional NumPy array.

Both functions validate their inputs, preserve the original matrices and return the shortest-distance matrices.

## 3. Correctness Tests – `test_correctness.py`

This file uses Python's `unittest` framework and SciPy's Floyd–Warshall implementation as a reference.

Seven tests cover:

- Agreement with SciPy's results.
- Consistency between individual and batch calculations.
- Blocked connections and disconnected stations.
- Preservation of the original input matrix.
- Rejection of invalid inputs.

**Result:** All seven tests passed.

## 4. Disruption Scenario Generation – `scenarios.py`

This file implements `generate_disruption_scenarios()`, which creates different versions of the original railway network by randomly applying disruptions.

Each scenario starts from a fresh copy of the original network. Existing connections are selected without replacement and are either blocked (`np.inf`) or assigned an additional travel-time delay.

The current default parameters are:

| Parameter | Default |
|---|---:|
| Number of scenarios | 100 |
| Random seed | 42 |
| Disruptions per scenario | 1–3 |
| Probability of blockage | 50% |
| Delay range | 5–30 minutes |

These are configurable initial assumptions that can be adjusted after group agreement.

### Reproducibility and Output

The generator uses NumPy's `SeedSequence` to create an independent random stream for each scenario. This ensures that results are reproducible and independent of the number of MPI workers used.

It returns a three-dimensional NumPy array with shape `(scenarios, stations, stations)` and a list of records describing each disruption.

## 5. Railway Data Loading and Validation – `railway_data.py`

This file provides reusable functions for loading railway datasets and checking their compatibility with the agreed interface in `docs/interface.md`.

Its main functions are:

- **`load_railway_data()`:** Loads station names, the railway network matrix, passenger-demand matrix and dataset metadata.
- **`validate_network()`:** Checks matrix dimensions, symmetry, non-negative travel times, missing values and zero diagonal.
- **`validate_demand()`:** Checks matrix dimensions, non-negative integer demand values and zero diagonal. Demand is allowed to be asymmetric.
- **`load_station_names()`:** Loads station names while preserving the agreed station indexing.
- **`get_dataset_info()`:** Retrieves dataset information, units and provenance metadata.

The loader uses NumPy arrays and follows the project's agreed data structure, allowing the loaded network to be used by the sequential and NumPy implementations.

The module was committed and pushed to the shared `main` branch under:

`feat(data): add reusable railway data loader`

The final railway dataset was prepared separately by another team member and tested with the loader.

## 6. Scenario Tests and Overall Testing

The `test_scenarios.py` file contains seven tests covering:

- Reproducibility with the same random seed.
- Number and dimensions of generated scenarios.
- Symmetry and zero diagonal values.
- Preservation of the original network.
- Consistency between individual and batch Floyd–Warshall calculations.
- Rejection of invalid inputs.

**Previously verified results:**

- Scenario generation tests: 7 passed.
- Complete project test suite: 18 passed, including tests developed by other team members.

## 7. Current Status and Next Steps

The NumPy implementations, reproducible scenario generator and reusable railway data loader have been developed and integrated into the shared project.

Remaining tasks include:

- Agreeing on the final disruption parameters.
- Benchmarking NumPy vectorization and batch processing against the sequential implementation.
- Integrating generated scenarios with MPI.
- Analysing execution time, speedup, efficiency and scalability.

**Summary:** My contribution provides optimized shortest-path calculations, reproducible railway disruption scenarios and reusable data-loading and validation functions to support the project's railway network simulations.

