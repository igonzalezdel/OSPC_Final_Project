# Parallel driver (multiprocessing)

Author: Antoni Gendra. Task: Build a parallel driver with adjustable worker count.
File: `src/parallel.py`. Tests: `tests/test_parallel.py`. Slurm: `slurm/parallel_run.sh`.

## What it does
Runs the same Monte Carlo simulation as `src/simulation.py` (same scenarios,
same Floyd-Warshall, same metrics) with a pool of `--workers` processes.
Scenarios are independent, so scenario numbers `0..N-1` are split into chunks
and the chunks are shared between the workers.

## Design choices
| Choice | Why |
|---|---|
| `multiprocessing.Pool` (processes, not threads) | Floyd-Warshall is pure Python, and the GIL lets only one thread run Python code at a time |
| Each worker builds its own scenarios from `(seed, s)` | The sequential run holds all 100,000 scenarios in memory (5.5 GB, see `docs/profiling/profiling.md`). Here the main process never does, and generation runs in parallel too |
| `SeedSequence(seed, spawn_key=(s,))` | Gives the same random numbers as `SeedSequence(seed).spawn(N)[s]` in `src/scenarios.py`, so results do not depend on the number of workers |
| Network, demand and baseline sent once per worker (`initializer`) | Not copied with every task |
| ~4 chunks per worker | Balances the load without many messages between processes |
| `OMP_NUM_THREADS=1` (set before importing NumPy and in the Slurm script) | Avoids nested library threads competing for the same cores |
| Results sorted by scenario | Chunks finish in any order; the output does not |

## Correctness
`scenarios.csv` is identical, byte for byte, to the sequential output for 1, 2
and 3 workers (`tests/test_parallel.py`). A test also checks that every rebuilt
scenario matches `generate_disruption_scenarios` exactly.

## How to run
On the cluster, from the repository root:

    sbatch --cpus-per-task=4 slurm/parallel_run.sh 4 2000 1      # quick test
    sbatch --cpus-per-task=8 slurm/parallel_run.sh 8 100000 5    # 8 workers, 5 repetitions

Or directly:

    python -m src.parallel --workers 8 --scenarios 100000 --timing-csv results/timings_multiprocessing.csv

Options: `--workers`, `--scenarios`, `--seed`, the scenario parameters of
`src/simulation.py`, `--kernel python|numpy` (Floyd-Warshall inside each worker;
`python` is the same code as the 603 s baseline), `--chunks-per-worker`,
`--out`, `--timing-csv`, `--repetition`.

## Output
- `scenarios.csv` and `summary.json`, same format as the sequential run, plus
  `workers`, `chunks`, node and Slurm job id.
- Timing is split into input, pool start-up, compute and output, so the
  start-up overhead of the workers can be shown separately in the scaling plot.
- With `--timing-csv`, one row per run is appended (version, workers, scenarios,
  repetition, timings, job id, node, date).

## First measurement (laptop VM with 2 cores, 400 scenarios)
| Workers | Compute | Speedup |
|---|---|---|
| 1 | 4.34 s | 1.0x |
| 2 | 2.29 s | 1.9x |

Pool start-up took 0.1-0.2 s. Cluster numbers come from the scaling runs.
