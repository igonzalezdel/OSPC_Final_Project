# Baseline profiling and experiment size

Task: Profile the baseline and choose an experiment size (Iñigo González del Rey).
Scripts: `scripts/profile_baseline.py`, `slurm/profile_baseline.sh`, `slurm/baseline_run.sh`.
Raw outputs are in this folder.

## Decision

| Parameter | Value |
|---|---|
| Dataset | `data/madrid_cercanias`, 60 stations |
| Scenarios (fixed for strong scaling) | **100,000** |
| Seed and scenario parameters | 42, 1-3 disruptions, block probability 0.5, delays 5-30 min (simulation defaults) |
| Sequential baseline (1 worker) | **603.7 s (10 min 4 s)**, job 29700 |
| Peak memory | **5.53 GiB** |

100,000 scenarios is the smallest round number that takes over 10 minutes on one core, which the brief asks for.

## Machine

Node `haskell`: 2 x AMD EPYC 9755 (128 cores each, 2 threads per core, 512 logical CPUs), 1 GiB L3, 440 GB RAM.
Python 3.11.5, NumPy 1.26.2 (EESSI module `SciPy-bundle/2023.11-gfbf-2023b`).
Jobs asked for 1 CPU (`--cpus-per-task=1`); Slurm shows 2 CPUs because it gives a full core (2 hyperthreads). `OMP_NUM_THREADS=1`, so the program uses one thread.
The node is shared with other jobs, so runtimes can vary between runs.

Tools used: Python timers for each part of the program, `/usr/bin/time -v` (CPU, memory, page faults, I/O), `resource` peak memory per size, and `cProfile` (dominant functions). `htop` is not needed because batch jobs run without a screen, and `/usr/bin/time -v` gives the same numbers in a form we can save.

## Step 1: how runtime grows with problem size (job 29697)

| Scenarios | Wall time | ms per scenario | CPU / wall | Peak memory |
|---|---|---|---|---|
| 1,000 | 6.0 s | 5.96 | 0.99 | 86 MB |
| 4,000 | 23.9 s | 5.93 | 1.00 | 257 MB |
| 16,000 | 97.6 s | 6.07 | 1.00 | 933 MB |

Runtime grows linearly: about 6.1 ms per scenario and no real fixed cost. The fit predicted 99,000 scenarios for 10 minutes; we rounded up to 100,000.

## Step 2: full baseline run, 100,000 scenarios (job 29700)

Time breakdown (from `summary.json`):

| Part | Time | Share |
|---|---|---|
| Load data | 0.002 s | 0.00% |
| Generate scenarios | 3.13 s | 0.52% |
| Floyd-Warshall + metrics | 600.08 s | 99.40% |
| Write results | 0.15 s | 0.02% |
| **Total (wall)** | **603.7 s** | |

From `/usr/bin/time -v`:

| Measure | Value | What it shows |
|---|---|---|
| CPU this job got | 99% | busy computing the whole time |
| User / system time | 602.7 s / 0.9 s | almost no time in the operating system |
| Max resident memory | 5,798,308 KB (5.53 GiB) | fits easily in the 8 GB we asked for |
| Major page faults / swaps | 0 / 0 | no waiting on disk for memory |
| File system inputs / outputs | 0 / 5,016 blocks (~2.5 MB) | very little I/O |
| Context switches (voluntary / involuntary) | 1,534 / 2,699 | few interruptions over 10 minutes |

## Step 3: where the time goes (cProfile, 2,000 scenarios)

| Function | cumtime | Share |
|---|---|---|
| `floyd_warshall` (`src/sequential.py`) | 33.73 s | 98.7% |
| `generate_disruption_scenarios` (`src/scenarios.py`) | 0.08 s | 0.2% |
| `scenario_metrics` (`src/simulation.py`) | 0.07 s | 0.2% |

cProfile slows the program down (34.2 s instead of ~12 s), so only the shares are meaningful.
Almost all of the time is spent inside the three nested Python loops of Floyd-Warshall (33.44 s tottime).

## What this means

- **CPU-bound, not memory- or I/O-bound.** CPU usage is 99-100%, there are no major page faults or swapping, and reading and writing take 0.15 s out of 604 s.
- **Almost everything can be parallelized.** Each scenario is independent, and 99.4% of the time is Floyd-Warshall + metrics. The serial part (load, generate, write) is 3.3 s, or **0.54%**.
- **Amdahl estimate.** With a serial fraction of 0.0054, the best possible speedup is about 1 / (0.0054 + 0.9946 / p): **27x at 32 workers**, and at most ~185x with unlimited workers. Real results will be lower because of the overhead of starting workers and moving data.
- **Memory is the risk for the parallel versions.** Memory grows by ~58 KB per scenario because `generate_disruption_scenarios` builds all 100,000 scenarios in one array before running anything (~2.9 GB for the array alone). If each worker receives a full copy, memory multiplies with the number of workers. Generating each scenario inside its worker from its seed would avoid this and also move the 3.1 s of generation into the parallel part.

## Is 100,000 feasible for repeated strong-scaling runs?

One strong-scaling sweep (1, 2, 4, 8, 16, 32 workers) at 100,000 scenarios takes about
604 s x (1 + 1/2 + 1/4 + 1/8 + 1/16 + 1/32) = **~20 minutes** if the speedup were perfect,
and costs about **1 core-hour** (each worker count uses p cores for 1/p of the time).

| Repetitions | Core-hours (ideal) | Wall time if run one after another |
|---|---|---|
| 5 (course brief minimum) | ~5 | ~1.7 h |
| 30 (task card) | ~30 | ~10 h |

Real runs will be slower than ideal, so these are lower bounds.
Repetitions are independent, so several jobs can be queued at the same time to cut the wall time.
Running too many at once on the shared node can slow each run down, though, so the timings get noisier.
Each 1-worker job also needs ~5.5 GB of memory.

Recommendation: keep 100,000 scenarios, because the brief requires at least 10 minutes on one core.
Do at least 5 repetitions per worker count, and more where the spread
