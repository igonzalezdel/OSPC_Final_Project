# MPI version of the railway simulation

Author: Ander Díez. Task: Implement MPI version of the railway simulation.
Code: `src/mpi_simulation.py`. Tests: `tests/test_mpi_simulation.py`.
Slurm: `slurm/mpi_run.sh`, `slurm/submit_mpi_scaling.sh`, `slurm/check_mpi_equivalence.sh`.
Scripts: `scripts/check_mpi_equivalence.py`, `scripts/summarize_timings.py`.

## What it does
Runs the same Monte Carlo simulation as `src/simulation.py` (same scenarios,
same Floyd-Warshall, same three metrics, same output files) on several MPI
processes ("ranks") started with `srun`. It builds on the verified setup in
`mpi_check/` (module `mpi4py/3.1.5-gompi-2023b`, `srun` launcher) and reuses
Antoni's scenario rebuild (`src/parallel.py`) and the metric code of
`src/simulation.py`.

## How the work is divided
Scenarios are independent, so MPI needs only two messages:

| Step | What happens | MPI call |
|---|---|---|
| 1 | Rank 0 reads the network and demand | none |
| 2 | Rank 0 sends them to all ranks | `bcast` |
| 3 | Every rank computes the baseline once, then its own block of scenario numbers | none |
| 4 | Every rank sends its results (6 numbers per scenario) to rank 0 | `gather` |
| 5 | Rank 0 writes `scenarios.csv` and `summary.json` | none |

- **Division:** `block_bounds(N, size, rank)` gives each rank one contiguous block
  of scenario numbers; blocks differ by at most 1 scenario (100,000 scenarios on
  32 ranks: 3,125 each).
- **Reproducibility:** scenario `s` is built from `(seed, s)` only
  (`SeedSequence(seed, spawn_key=(s,))`), so the results do not depend on the
  number of ranks. Blocks are contiguous and gathered in rank order, so the
  rows come back already sorted by scenario.
- **Collect:** results travel as one NumPy array per rank (columns: scenario,
  n_disruptions, n_blocked and the three metrics). Counts are exact in float64.
  There is no floating-point reduction, so there is no summation-order effect.
- **No nested parallelism:** `OMP_NUM_THREADS=1` and the like, because the ranks
  are the parallelism.

## How to run
On the cluster, from the repository root (`mkdir -p logs` once):

    # quick test: 2 ranks, 2,000 scenarios, 2 repetitions
    sbatch --ntasks=2 --cpus-per-task=2 slurm/mpi_run.sh 2 2000 2 results/timings/mpi_test.csv

    # correctness first (sequential vs MPI for 1, 2, 4, 8, 16 ranks)
    sbatch slurm/check_mpi_equivalence.sh 500

    # full strong-scaling sweep, same size as the other versions
    bash slurm/submit_mpi_scaling.sh 100000 5

One rank = one physical core = 2 Slurm CPUs on this cluster (see
`docs/README_parallel.md`), so every job asks for `--cpus-per-task=2` per rank.
All ranks run on one node (`--nodes=1`), the same conditions as the
multiprocessing runs.

Inside a job the program is started with:

    srun python -m src.mpi_simulation --scenarios 100000 --out results/mpi_r8

Options are the same as `src/simulation.py`, plus `--kernel`, `--timing-csv`
and `--repetition`. On a computer with an MPI installation,
`mpirun -n 4 python -m src.mpi_simulation --scenarios 1000` works too.

## What is measured
`summary.json` and the timing CSV (columns of `docs/timing_schema.md`, plus
MPI columns) record, in seconds:

| Name | Meaning |
|---|---|
| `load_s` (input) | rank 0 reads the files |
| `bcast_s` | broadcast of the inputs to all ranks |
| `compute_s` | time of the slowest rank: baseline + its block of scenarios |
| `gather_s` | collecting the results on rank 0 |
| `comm_s` | `bcast_s + gather_s` = communication overhead |
| `write_s` (output) | rank 0 writes `scenarios.csv` |
| `elapsed_s` | wall time of the whole run, from after MPI start-up until the files are written |
| `compute_min_s`, `compute_mean_s` | fastest and mean rank, to see load imbalance (max is `compute_s`) |

Python start-up and `srun` launch time are not in `elapsed_s`. Compare
`elapsed_s` between versions, because the multiprocessing version also counts
only its own run.

Compare all versions with:

    python scripts/summarize_timings.py docs/timings/strong_scaling_haskell.csv docs/timings/mpi_scaling_haskell.csv --scenarios 100000

It prints the median time, speedup against the sequential run, parallel
efficiency and MPI communication time per configuration.

## How it is tested
    python -m unittest tests.test_mpi_simulation

- The split: blocks cover every scenario exactly once, differ by at most 1, and
  handle more ranks than scenarios.
- Algorithm on 1, 2, 3, 5 and 8 ranks, using a thread-based stand-in for the
  MPI communicator (so it runs without MPI): `scenarios.csv` is **byte-identical**
  to the sequential run, and `summary.json` aggregates are equal.
- The timing CSV has the agreed columns and the header is written once.
- Two real MPI processes (`mpirun -n 2`) match the sequential run. This test is
  skipped when `mpi4py` or `mpirun` is not available, so it is the one to check
  on the cluster.
- On the cluster, `scripts/check_mpi_equivalence.py` repeats the comparison with
  real `srun` runs for 1 to 16 ranks (same rules as
  `scripts/check_equivalence.py`: counts exact, `extra_delay_min` rel 1e-9,
  abs 1e-6).

## Expected communication overhead
Only two messages are sent: the inputs (60 x 60 network and demand, a few tens
of kB) and the results (about 48 bytes per scenario, 4.8 MB for 100,000
scenarios). Compute is about 6 ms per scenario, so the communication should be
a very small part of the total. What can limit speedup is, instead: the
sequential part on rank 0 (reading, sorting, writing the CSV), the slowest rank
setting the compute time, and, as with multiprocessing, hyperthreads if a
rank does not have its own core. The measured values are in the next section.

## Results
Full sweep on the cluster: 100,000 scenarios, seed 42, Python kernel, 60 stations,
node `haskell`, 5 repetitions per size (30 runs), one rank per physical core
(2 Slurm CPUs per rank). Raw rows: `docs/timings/mpi_scaling_haskell.csv`
(MPI runs of 15 Nov 2026, jobs 30307 to 30312 and a resubmission of the 32-rank
job). Values are medians of the 5 runs.

### MPI strong scaling
| Ranks | Elapsed (s) | Compute (s) | Communication (s) | Speedup (vs 1 rank) | Efficiency |
|---:|---:|---:|---:|---:|---:|
| 1 | 605.9 | 605.7 | 0.005 | 1.00 | 100% |
| 2 | 305.4 | 305.2 | 0.004 | 1.98 | 99% |
| 4 | 154.1 | 153.9 | 0.004 | 3.93 | 98% |
| 8 | 77.6 | 77.4 | 0.005 | 7.81 | 98% |
| 16 | 39.5 | 39.2 | 0.004 | 15.3 | 96% |
| 32 | 20.0 | 19.8 | 0.005 | 30.3 | 95% |

- **Communication is negligible.** Broadcast plus gather is about 5 ms in every
  run, around 0.03% of the 32-rank time and constant in the number of ranks (the
  results are 4.8 MB in total). The difference between `elapsed_s` and
  `compute_s` (about 0.2 s) is reading the data, sorting and writing the CSV on
  rank 0.
- **The remaining loss of efficiency (5% at 32 ranks) is inside the compute
  phase**, not in the messages: 605.7 s / 32 = 18.9 s would be ideal, 19.8 s was
  measured. We did not measure why (see Limitations).

### Comparison with the other versions (same node, `haskell`)
Sequential and multiprocessing values are medians from
`docs/timings/strong_scaling_haskell.csv` (Iñigo Gonzalez del Rey; runs of 16 Nov
2026). To compare the versions with each other, speedup and efficiency use one
common reference: the sequential run on `haskell` (582.2 s).

| Workers | Multiprocessing (s) | MPI (s) | Speedup mult. | Speedup MPI | Efficiency mult. | Efficiency MPI |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 590.6 | 605.9 | 0.99 | 0.96 | 99% | 96% |
| 2 | 296.8 | 305.4 | 1.96 | 1.91 | 98% | 95% |
| 4 | 149.2 | 154.1 | 3.90 | 3.78 | 98% | 94% |
| 8 | 92.1 | 77.6 | 6.32 | 7.50 | 79% | 94% |
| 16 | 47.6 | 39.5 | 12.2 | 14.7 | 76% | 92% |
| 32 | 24.7 | 20.0 | 23.6 | 29.1 | 74% | 91% |

What the table shows:
- From 1 to 4 workers both versions give almost the same time; MPI is 3% slower.
- From 8 workers, MPI is 16% to 19% faster than multiprocessing (77.6 s against
  92.1 s at 8, 20.0 s against 24.7 s at 32). Multiprocessing shows a drop in
  efficiency between 4 and 8 workers (`docs/scaling_interpretation.md`); the MPI
  runs do not show that drop.

### Why we do not claim MPI is better
The two sweeps were not run at the same moment. The multiprocessing runs have a
median node load of 13 to 20 for 2 to 32 workers (`node_load_1m`); the MPI runs
were made on another day, when other jobs on the node were different. Moving the
sequential reference between nodes also changes it by about 12% in Iñigo's file
(582 s on `haskell`, 653 s on `julia`). So the difference at 8 to 32 workers is
real in these measurements, but it can come from the state of the node and not
from the programming model. The design differences that could matter (MPI sends
one NumPy array per rank, while the multiprocessing pool sends lists of
dictionaries through queues) were not tested. To decide it, run
multiprocessing and MPI alternately in the same job on an idle node.

## How the team can teach it in the final presentation
1. Show that the work is "embarrassingly parallel": scenarios do not depend on
   each other.
2. Draw the picture of the table above: one `bcast`, local compute, one `gather`.
3. Say why the results do not depend on the number of ranks: the random numbers
   belong to the scenario number, not to the rank.
4. Show one speedup plot with the three versions and the communication time.
5. Explain what MPI adds compared with multiprocessing: it also works across
   nodes (not measured here), at the price of explicit messages.

## Limitations
- Only one node was used; multi-node runs were not tested.
- The MPI and multiprocessing sweeps were run on different days, so the
  difference between them is a measurement, not an explanation (see Results).
- The cause of the 5% efficiency loss at 32 ranks was not measured; the shared
  node (memory bandwidth, caches, clock speed) is a hypothesis.
- The static block split assumes scenarios cost about the same. The
  `compute_min_s` / `compute_s` columns show whether that holds.
- `tests/test_mpi_simulation.py` runs the real-MPI test only where `mpirun` works;
  on the cluster, correctness was checked with `slurm/check_mpi_equivalence.sh`
  (1, 2, 4, 8, 16 ranks, 500 scenarios: all byte-identical to the sequential run).

## Use of AI
`src/mpi_simulation.py`, its tests, the Slurm and helper scripts were developed
with assistance from Claude (Anthropic) for the design, the code and the tests.
The author reviews them and runs them on the cluster. Details are in the header
comment of each file.
