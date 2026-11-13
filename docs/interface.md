# Railway Data Interface

This file is the agreed format for the railway data, the disruption
scenarios and the simulation results. Every script in this project
should read and write data in this format, so that anyone can work on
the next tasks without rewriting someone else's code.

If you need to change something here, tell the group first and update
this file in the same commit.

## 1. Stations

- There are `n` stations, numbered `0` to `n-1`.
- This number is the row and column index in every matrix below.
- Station names are stored in a list in the same order:
  `station_names[i]` is the name of station `i`.

## 2. Railway network (adjacency matrix)

- A NumPy array of type `float`, with shape `(n, n)`.
- `network[i, j]` is the direct travel time from station `i` to
  station `j`, in **minutes**.
- `np.inf` means there is no direct connection between `i` and `j`.
- The diagonal is `0` (travelling from a station to itself takes no time).
- Travel times are never negative and never `NaN`.
- The network is **undirected**: trains run both ways with the same
  travel time, so `network[i, j] == network[j, i]`. The matrix must be
  symmetric.

## 3. Passenger demand

- A NumPy array of type `int`, with shape `(n, n)`, using the same
  station order as the network.
- `demand[i, j]` is the number of passenger trips per day from
  station `i` to station `j`.
- The diagonal is `0`.
- Demand does **not** have to be symmetric: more people can travel
  from `i` to `j` than from `j` to `i`.

## 4. Disruption scenarios

A scenario is a copy of the normal network with some links changed.

- **Blocked link:** set the travel time to `np.inf` in both directions,
  `network[i, j]` and `network[j, i]`.
- **Delayed link:** add the delay, in minutes, to the travel time in
  both directions. For example, a 10-minute link with a 15-minute delay
  becomes 25 minutes.
- A single scenario has shape `(n, n)`.
- Many scenarios can be stacked into one array of shape
  `(scenarios, n, n)`. Scenario `s` is `scenarios[s]`.
- Every scenario must still follow the rules of Section 2
  (symmetric, no negative values, no `NaN`, diagonal `0`).

### Random numbers

- The base seed is `42`.
- Each scenario gets its own random stream:

  ```python
  seeds = np.random.SeedSequence(42).spawn(num_scenarios)
  rng = np.random.default_rng(seeds[s])   # random generator for scenario s
  ```

- The stream belongs to the **scenario**, not to the worker. This way,
  scenario `s` is always the same, whether we use 1 worker or 32, and
  the parallel results can be compared with the sequential ones.

## 5. Passing a matrix to the shortest-path functions

The two existing implementations accept the same values in different
Python types. Neither file needs to change.

```python
import numpy as np
from src.sequential import floyd_warshall
from src.numpy_version import floyd_warshall_numpy, floyd_warshall_batch

# network: NumPy float array, shape (n, n), as in Section 2

# Sequential version: needs a list of lists
distances_list, next_station = floyd_warshall(network.tolist())
distances = np.array(distances_list)

# NumPy version: takes the array directly
distances = floyd_warshall_numpy(network)

# NumPy batch version: many scenarios at once, shape (scenarios, n, n)
all_distances = floyd_warshall_batch(scenarios)
```

`np.inf` and `math.inf` are the same value, so `.tolist()` keeps the
missing links correct. All versions return shortest travel times in
minutes, with `inf` where no route exists.

## 6. Simulation results

First compute the shortest travel times of the normal network
(`baseline`) and of each scenario (`disrupted`). Then report three
values for each scenario.

Passenger-based metrics sum over ordered origin-destination pairs
`i != j`, while disconnected station pairs are counted only once
using `i < j`.

| Name | Type | Unit | Definition |
|---|---|---|---|
| `disconnected_pairs` | int | station pairs | Pairs `i < j` that have a route in `baseline` but no route in `disrupted`. Each pair is counted once because the network is undirected. |
| `lost_trips` | int | trips per day | Sum of `demand[i, j]` over all ordered pairs `i != j` that are reachable in `baseline` but unreachable in `disrupted`. Passenger trips in both directions are counted. |
| `extra_delay_min` | float | passenger-minutes per day | Sum of `demand[i, j] * (disrupted[i, j] - baseline[i, j])` over all ordered pairs `i != j` where both baseline and disrupted travel times are finite. |

Although the railway network is undirected, passenger demand may
differ by direction. Therefore, disconnected station pairs are
counted once, but passenger trips and delays include both directions.

Lost trips are not included in `extra_delay_min`, because their delay
would be infinite. They are counted in `lost_trips` instead.

### Comparing results

- `disconnected_pairs` and `lost_trips` must match **exactly** between
  the sequential and parallel versions.
- `extra_delay_min` is compared with a tolerance
  (`np.isclose(a, b, rtol=1e-9)`), because adding floating-point
  numbers in a different order can change the last digits.

### Future extension: restoration priorities

The three outputs above measure the impact of each disruption.
Identifying which blocked connections should be restored first
will be implemented separately.

This will require an agreed ranking rule based on how much restoring
each connection reduces disruption impacts, including how to
account for disconnected journeys.
