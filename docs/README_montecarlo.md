# Sequential Monte Carlo simulation

Author: Ander Díez. Task: Build the sequential Monte Carlo simulation
File: `src/simulation.py`. Tests: `tests/test_simulation.py`.

## What it does
The program answers: *if some railway links are blocked or delayed, how much
worse is the service for passengers?* It runs many random disruption scenarios
on the Madrid Cercanías network (60 stations) on one worker and reports the
impact of each scenario.

## How it fits with the rest of the project
| Step | Done by | Module |
|---|---|---|
| Network and passenger demand | Antoni | `data/madrid_cercanias/`, loaded by `src/railway_data.py` |
| Reproducible disruption scenarios | Helen | `src/scenarios.py` |
| Shortest travel times | Alexandra | `src/sequential.py` (`floyd_warshall`) |
| Connect everything and compute the impact metrics | Ander | `src/simulation.py` |

All formats follow `docs/interface.md`.

## What happens in one run
1. Load the network and demand (input time).
2. Generate the scenarios with the base seed (scenario `s` always depends only
   on the seed and `s`, so any number of workers will see the same scenarios).
3. Run `floyd_warshall()` once for the normal network.
4. For each scenario, run `floyd_warshall()` and compare with the normal network.
5. Compute the three metrics below (`inf` means "unreachable").
6. Write `scenarios.csv` and `summary.json` (output time).

Compute time (steps 2-5) is measured separately from input and output time.

## Metrics (definitions from `docs/interface.md`)
| Name | Unit | Meaning |
|---|---|---|
| `disconnected_pairs` | station pairs | Pairs `i < j` with a route in the normal network and none in the scenario. |
| `lost_trips` | trips per day | Demand of all ordered pairs that lost their route (both directions). |
| `extra_delay_min` | passenger-minutes per day | Sum of demand x extra travel time over pairs that are still connected. Lost trips are not included. |

## How to run
On the cluster, from the repository root:

    source /cvmfs/software.eessi.io/versions/2023.06/init/bash
    module load SciPy-bundle/2023.11-gfbf-2023b
    python -m src.simulation --scenarios 100 --out results/sequential_100

Options: `--data` (dataset folder, default `data/madrid_cercanias`),
`--scenarios` (problem size), `--seed` (default 42), `--min-disruptions`,
`--max-disruptions`, `--block-probability`, `--min-delay`, `--max-delay`, `--out`.

Example run on the cluster (100 scenarios, 60 stations): input 0.038 s,
compute 0.597 s, output under 0.001 s.

## Output files (in the `--out` folder)
- `scenarios.csv`: one row per scenario: number of disruptions, number blocked,
  and the three metrics.
- `summary.json`: seed, number of scenarios and stations, scenario parameters,
  units, mean/median/max/total of each metric, timing of input, compute and
  output, Python and NumPy versions, date.

The `results/` folder is ignored by git; regenerate it with the command above.

## How it is tested
    PYTHONPATH=.:$PYTHONPATH python tests/test_simulation.py

- Four hand-calculated cases on a 4-station ring (one blocked link, network split
  in two, isolated station, delayed link), with asymmetric demand to check that
  both directions are counted.
- A scenario without disruption gives zero in all metrics.
- The same input gives identical results twice (reproducibility).
- The sequential shortest times match the NumPy batch version.
- An end-to-end command-line run on the Madrid dataset writes the files and
  gives identical output for the same seed.

Note: `PYTHONPATH=.:$PYTHONPATH` keeps the path set by the SciPy module. Without
the `:$PYTHONPATH` part, NumPy is not found.

## Design decisions and limitations
- The metrics are computed with NumPy; the shortest-path step uses the
  sequential `floyd_warshall()` as the task requires.
- Ranking which link to restore first is not included (`docs/interface.md` says
  it will be implemented separately).
- Results come from synthetic disruptions on estimated demand (see
  `data/madrid_cercanias/metadata.json` for the dataset limitations).
- The scenario count needed for a 10-minute one-core run has to be measured on
  the cluster (see the task "Profile the baseline and choose an experiment size").

## Use of AI
`src/simulation.py` and `tests/test_simulation.py` were developed with
assistance from Claude (Anthropic) for the design, the metric calculation, the
command-line interface and the tests. The code was reviewed, run and tested on
the cluster by the author. Details are in the header comment of each file.
