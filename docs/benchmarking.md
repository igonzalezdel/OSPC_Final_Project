# Benchmark runs and timing CSV

Task: Integrate Slurm jobs and validate timing CSV output (Iñigo González del Rey).

## Files

| File | What it does |
|---|---|
| `scripts/run_benchmark.py` | Runs `src/simulation.py` (sequential) or `src/parallel.py` (multiprocessing) once and appends one row to the timing CSV |
| `scripts/validate_timings.py` | Checks the CSV and prints median, min, max and spread per configuration |
| `slurm/benchmark.sh` | `slurm/benchmark_template.sh` with the simulation integrated: one job = one configuration x N repetitions |
| `slurm/submit_strong_scaling.sh` | Submits the whole strong-scaling sweep: sequential + 1, 2, 4, 8, 16, 32 workers |

The CSV has the 16 columns of `docs/timing_schema.md`, in the same order, plus 4 extra columns:
`pool_startup_s` (time to start the workers, for the overhead analysis), `cpus`, `physical_cores` and `kernel`.

How the columns are filled:

| Column | Source |
|---|---|
| `load_s`, `compute_s`, `write_s` | the program's own timers (`timing_s` in `summary.json`) |
| `elapsed_s` | timed around the whole run, so it includes pool start-up |
| `git_commit` | `git rev-parse --short HEAD`, with `-modified` if tracked files were changed |
| `node_load_1m` | `/proc/loadavg`, read just before the run starts |

`run_benchmark.py` refuses to save a row if a value is missing or negative, if `elapsed_s` is smaller than load + compute + write, or if there are more workers than physical cores. Several jobs can write to the same CSV at once because the file is locked while a row is written.

## How to run

From the repository root on the cluster:

    bash slurm/submit_strong_scaling.sh 100000 5 results/timings/strong_scaling_haskell.csv haskell
    python scripts/validate_timings.py results/timings/strong_scaling_haskell.csv --min-reps 5

The 4th argument pins all jobs to one node. Always use it for scaling runs (see "One node per sweep" below).

One configuration only:

    mkdir -p logs
    sbatch --cpus-per-task=16 slurm/benchmark.sh multiprocessing 8 100000 5

Cluster rules we found:

- One physical core = 2 Slurm CPUs, so each worker needs 2 CPUs (`--cpus-per-task = 2 x workers`).
- Each user can use at most 64 CPUs at once. The JupyterHub session takes 2, so the 32-worker job (64 CPUs) only starts after stopping the Jupyter server (File > Hub Control Panel > Stop My Server).
- `fortran` can be reserved for other users (`scontrol show reservation`); jobs that would overlap a reservation wait.
- The three nodes are not equally fast, so all jobs of one sweep must run on the same node (see below).

## Validation test (15 Nov 2026)

`bash slurm/submit_strong_scaling.sh 2000 2 results/timings/test.csv`, jobs 30114-30120, then `validate_timings.py`: 14 rows, 7 configurations, no errors.

| Implementation | Workers | Median (s) | Speedup vs 1 worker | Node load 1m |
|---|---|---|---|---|
| sequential | 1 | 13.35 | | 1.6 |
| multiprocessing | 1 | 13.49 | 1.0x | 1.6 |
| multiprocessing | 2 | 7.03 | 1.9x | 1.4 |
| multiprocessing | 4 | 3.72 | 3.6x | 2.2 |
| multiprocessing | 8 | 2.47 | 5.5x | 4.8 |
| multiprocessing | 16 | 1.60 | 8.4x | 4.8 |
| multiprocessing | 32 | 2.09 | 6.5x | 123.3 |

This is a small test (2,000 scenarios), so it only checks that every configuration runs and writes valid rows; the timings are not the scaling result.
Two things it already shows: the parallel driver with 1 worker costs almost the same as the sequential program (13.49 s vs 13.35 s), and the 32-worker run was slower than 16 workers while the node load was 123, so other jobs on the node can change our timings. That is why every row records `node_load_1m`.

## Strong scaling, 100,000 scenarios (16 Nov 2026)

File: `docs/timings/strong_scaling_haskell.csv`. 35 runs, all on node `haskell`, 5 repetitions per configuration, Python kernel, seed 42.

| Implementation | Workers | Median (s) | Min-max (s) | Spread | Speedup | Efficiency | Node load 1m |
|---|---|---|---|---|---|---|---|
| sequential | 1 | 582.16 | 575.02-591.13 | 2.8% | | | 5.6 |
| multiprocessing | 1 | 590.58 | 587.04-592.52 | 0.9% | 1.00x | 100% | 5.4 |
| multiprocessing | 2 | 296.81 | 296.68-301.08 | 1.5% | 1.99x | 99% | 13.7 |
| multiprocessing | 4 | 149.24 | 147.62-157.25 | 6.5% | 3.96x | 99% | 10.4 |
| multiprocessing | 8 | 92.06 | 91.62-92.46 | 0.9% | 6.42x | 80% | 13.2 |
| multiprocessing | 16 | 47.64 | 47.13-47.86 | 1.5% | 12.40x | 78% | 18.9 |
| multiprocessing | 32 | 24.70 | 24.52-25.10 | 2.4% | 23.91x | 75% | 19.6 |

Speedup = median time with 1 worker / median time with p workers. Efficiency = speedup / p.

Observations:

- 32 workers bring the run from 591 s to 24.7 s (23.9x).
- Scaling is close to perfect up to 4 workers (99% efficiency). Efficiency drops to 80% at 8 workers and then stays at 75-78%. This is a step, not the gradual decline Amdahl's law predicts from the 0.54% serial fraction measured in profiling (7.7x at 8, 14.8x at 16, 27.4x at 32). Explaining it is part of the Amdahl task.
- The parallel driver with 1 worker is 1.4% slower than the sequential program (590.6 s vs 582.2 s), so the cost of the driver itself is small.
- Spread is at most 6.5% and node load stayed between 5 and 20 during the runs.

## One node per sweep

The first full sweep (`docs/timings/strong_scaling.csv`, 15 Nov) was submitted without choosing a node. Slurm placed the sequential run on `julia`, 1-4 workers on `fortran` and 8-32 workers on `haskell`. The nodes run at different speeds: the sequential program took 654 s on `julia`, against 604 s on `haskell` in the profiling run and 582 s in the sweep above. A speedup that divides a time from one node by a time from another is not a valid strong-scaling result, so that file is kept only as evidence of the difference between nodes.

`slurm/submit_strong_scaling.sh` now takes the node as a 4th argument and pins every job to it with `--nodelist`. The second sweep (`strong_scaling_haskell.csv`) was submitted before that change, but all 35 runs landed on `haskell` (see the `node` column), so it is a valid single-node result. The `git_commit` column records the code version each run used.
