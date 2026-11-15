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

    bash slurm/submit_strong_scaling.sh 100000 5          # full sweep -> results/timings/strong_scaling.csv
    python scripts/validate_timings.py results/timings/strong_scaling.csv --min-reps 5

One configuration only:

    mkdir -p logs
    sbatch --cpus-per-task=16 slurm/benchmark.sh multiprocessing 8 100000 5

Cluster rules we found:

- One physical core = 2 Slurm CPUs, so each worker needs 2 CPUs (`--cpus-per-task = 2 x workers`).
- Each user can use at most 64 CPUs at once. The JupyterHub session takes 2, so the 32-worker job (64 CPUs) only starts after stopping the Jupyter server (File > Hub Control Panel > Stop My Server).
- `fortran` can be reserved for other users (`scontrol show reservation`); jobs that would overlap a reservation wait.

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
