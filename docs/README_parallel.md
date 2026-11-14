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
Task: Check that sequential and parallel results match (Antoni Gendra).
Script: `scripts/check_equivalence.py`. Slurm: `slurm/check_equivalence.sh`.

The script runs the sequential simulation once and the parallel driver for
1, 2, 4, 8, 16 and 32 workers with the same seed, then compares every scenario:

| Column | Rule |
|---|---|
| `n_disruptions`, `n_blocked`, `disconnected_pairs`, `lost_trips` | exactly equal |
| `extra_delay_min` | rel 1e-9, abs 1e-6 passenger-minutes |

Why that tolerance: each scenario runs the same code with the same operations
in the same order whatever the number of workers, so the values should be
bit-identical (and they are). The tolerance only allows for a different
floating-point summation order, e.g. with `--kernel numpy`; 1e-6
passenger-minutes is negligible next to the ~10^5-10^6 passenger-minutes of a
typical scenario.

It exits with code 1 on any disagreement, so the Slurm job fails visibly.

    sbatch slurm/check_equivalence.sh 500

Results:
- Laptop VM, 200 scenarios: all worker counts bit-identical.
- Cluster (`haskell`), 2,000 scenarios: sequential and 2 workers bit-identical (`cmp`).

`tests/test_parallel.py` also checks 1-3 workers and that every rebuilt
scenario matches `generate_disruption_scenarios` exactly.

## Cores, not CPUs
Slurm on this cluster counts each physical core as 2 CPUs (hyperthreads).
Two workers on one core compete for it: in the JupyterHub session (2 CPUs =
1 core) 2 workers gave only 1.2x (12.27 s to 10.05 s, 2,000 scenarios).
For the scaling runs ask for **2 CPUs per worker**. The driver prints a warning
when there are fewer physical cores than workers, and records CPUs and
physical cores in `summary.json` and the timing CSV.

## How to run
On the cluster, from the repository root:

    sbatch --cpus-per-task=8  slurm/parallel_run.sh 4 2000 1      # quick test
    sbatch --cpus-per-task=16 slurm/parallel_run.sh 8 100000 5    # 8 workers, 5 repetitions

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

First cluster test (job 29796, 2,000 scenarios): 4 workers on `--cpus-per-task=4`
(2 physical cores) took 4.80 s compute vs 12.27 s sequential, 2.6x.
