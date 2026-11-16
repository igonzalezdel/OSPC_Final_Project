# Railway Disruption Simulation

**Operating Systems & Parallel Computing | Group 4 | IE University**

## 1. Overview

Our project studies how disruptions to Madrid's Cercanías railway network affect passenger journeys and how parallel computing can reduce the time needed to analyze these disruptions.

We use **Monte Carlo simulation** to generate scenarios in which railway connections are blocked or delayed. For each scenario, we apply the **Floyd–Warshall algorithm** to calculate shortest travel times between stations and measure the impact on network connectivity and passenger journeys.

The project has two objectives:

- **Disruption analysis:** Estimate the effect of blocked and delayed connections on passenger journeys
- **Performance analysis:** Compare sequential and parallel implementations, identify computational bottlenecks, and evaluate scalability on the University's HPC cluster

The main workload parameter is the number of simulated scenarios. This allows us to run small correctness tests before moving to larger performance experiments.

## 2. Dataset and Simulation

### Dataset

Our default dataset is located in `data/madrid_cercanias/` and represents 60 Madrid Cercanías stations.

| File | Description |
|---|---|
| `stations.csv` | Station identifiers and names |
| `network.csv` | Direct travel times between stations |
| `demand.csv` | Estimated daily passenger demand between stations |
| `metadata.json` | Data sources, assumptions, and limitations |

The railway network is represented by a symmetric adjacency matrix. Each entry contains the direct travel time between two stations, in minutes. Infinity (`inf`) indicates that no direct connection exists.

The passenger-demand matrix contains estimated daily journeys between each origin–destination pair. Demand can differ by direction, even though the railway network is undirected.

The dataset combines Renfe Cercanías GTFS timetable information with 2018 station-level ridership data. Origin–destination demand is estimated using a gravity model rather than directly observed. Further details are available in `data/madrid_cercanias/metadata.json`.

### Disruption scenarios

Each scenario starts from the original railway network and randomly modifies selected connections:

- **Blocked connection:** The link is removed by setting its travel time to infinity
- **Delayed connection:** Additional minutes are added to the link's travel time

The default simulation parameters are:

| Parameter | Default |
|---|---:|
| Random seed | 42 |
| Disruptions per scenario | 1–3 |
| Probability of blocking a selected connection | 0.5 |
| Additional delay | 5–30 minutes |

We use scenario-specific random-number streams to ensure that the same scenario can be reproduced regardless of which worker processes it.

### Simulation workflow

For each run, we:

1. Load the network and passenger-demand data
2. Calculate shortest travel times for the undisrupted network
3. Generate the requested disruption scenarios
4. Recalculate shortest travel times for each disrupted network
5. Compare the disrupted and original networks
6. Save the scenario results and aggregate statistics

Since scenarios are independent, they can be distributed among multiple worker processes.

### Impact metrics

We calculate three metrics for each scenario:

| Metric | Definition | Unit |
|---|---|---|
| `disconnected_pairs` | Previously connected station pairs that become unreachable after the disruption, counting each unordered pair once | Station pairs |
| `lost_trips` | Estimated daily passenger demand between origin–destination pairs that were reachable before but become unreachable afterward | Trips/day |
| `extra_delay_min` | Additional shortest travel time multiplied by estimated daily demand, summed over journeys that remain connected | Passenger-minutes/day |

A blocked connection does not necessarily make stations unreachable, since alternative routes may exist.

We count each disconnected station pair once, but passenger-based metrics include both travel directions because demand can differ between them. Journeys that become impossible are counted under `lost_trips`, not `extra_delay_min`.

These metrics describe **estimated impacts under simulated disruptions**, not observed passenger cancellations or delays.

The full definitions are available in `docs/interface.md`.

## 3. Repository Structure

The main files used in the current simulation workflow are:

```text
OSPC_Final_Project/
├── data/madrid_cercanias/     # Railway network and demand data
├── src/
│   ├── railway_data.py        # Data loading and validation
│   ├── scenarios.py           # Disruption scenario generation
│   ├── sequential.py          # Sequential Floyd-Warshall
│   ├── numpy_version.py       # NumPy-vectorized Floyd-Warshall
│   ├── simulation.py          # Sequential Monte Carlo simulation
│   └── parallel.py            # Multiprocessing simulation
├── slurm/                     # HPC job submission scripts
├── scripts/                   # Validation and benchmarking utilities
├── tests/                     # Correctness tests
├── docs/                      # Technical documentation and evidence
└── README.md
```

Repository: https://github.com/igonzalezdel/OSPC_Final_Project

## 4. HPC Setup

We run the project on the IE University HPC cluster through JupyterLab:

https://jupyter.iesci.tech:8085

Open a terminal and navigate to the repository:

```bash
cd ~/OSPC_Final_Project
```

### Software environment

The environment used for our verified checkpoint runs was:

| Component | Version |
|---|---|
| Python | 3.11.5 |
| NumPy | 1.26.2 |
| SciPy | 1.11.4 |
| EESSI module | `SciPy-bundle/2023.11-gfbf-2023b` |

Load the scientific Python environment:

```bash
type module >/dev/null 2>&1 || source /cvmfs/software.eessi.io/versions/2023.06/init/bash
module load SciPy-bundle/2023.11-gfbf-2023b
```

Verify that the required libraries are available:

```bash
python --version
python -c "import numpy, scipy; print(numpy.__version__, scipy.__version__)"
```

The module must be loaded again when opening a new terminal session. Our Slurm scripts load it automatically.

All commands below should be executed from the repository root.

## 5. Quick Start: Small Reproducible Run

We use a small configuration with **five scenarios and seed 42** to verify the execution and correctness of the sequential and multiprocessing implementations.

This configuration completed in well under five minutes on the HPC cluster during our November 15, 2026 tests. Slurm queue waiting time is separate.

### Step 1 — Run the sequential simulation

```bash
python -m src.simulation --scenarios 5 --seed 42 --out results/readme_seq_test
```

This runs five disruption scenarios using the sequential implementation and saves the results to:

```text
results/readme_seq_test/
├── scenarios.csv
└── summary.json
```

The output directory is created automatically.

### Step 2 — Run the multiprocessing simulation

```bash
python -m src.parallel --workers 2 --scenarios 5 --seed 42 --kernel python --out results/readme_par_test
```

This runs the same scenarios using two worker processes.

The `--kernel python` option selects the same Floyd–Warshall implementation used by the sequential baseline.

Results are saved to:

```text
results/readme_par_test/
├── scenarios.csv
└── summary.json
```

### Step 3 — Compare the results

```bash
diff -u results/readme_seq_test/scenarios.csv results/readme_par_test/scenarios.csv
echo $?
```

The `diff` command compares the CSV files line by line.

If the files are identical, it prints nothing and returns exit code `0`.

**Verified result:** Our sequential and two-worker multiprocessing runs produced identical CSV files on November 15, 2026.

This verifies equivalence for the small tested configuration. Broader correctness checks are available in `tests/` and `scripts/check_equivalence.py`.

**Note:** The interactive JupyterLab session used for this test had access to two logical CPUs on one physical core. The two workers therefore shared a core. These runs verify functionality but are not suitable for measuring parallel speedup.

## 6. Running Jobs with Slurm

Slurm is the workload manager used to schedule jobs and allocate computing resources on the HPC cluster.

We use direct terminal execution for small tests and debugging. Performance measurements for the project must be obtained through Slurm batch jobs.

### Sequential batch job

Submit a five-scenario sequential simulation:

```bash
sbatch slurm/baseline_run.sh 5
```

The existing script requests:

| Resource | Allocation |
|---|---|
| Tasks | 1 |
| CPUs per task | 1 |
| Memory | 8 GB |
| Maximum wall time | 45 minutes |

The time limit is the maximum permitted job duration, not the expected runtime of this small test.

Slurm returns a job ID when the submission is accepted.

Check active jobs:

```bash
squeue -u "$USER"
```

Check the result of a particular job, replacing `JOB_ID` with the number returned by Slurm:

```bash
sacct -j JOB_ID --format=JobID,JobName,State,ExitCode,Elapsed
```

A successful execution should report `COMPLETED` and exit code `0:0`.

The job log is written to:

`baseline_run_JOB_ID.out`

For five scenarios, the simulation outputs are saved in `results/baseline_5/`.

### Verify the Slurm results

Compare the batch-job output with the direct sequential run:

```bash
diff -u results/readme_seq_test/scenarios.csv results/baseline_5/scenarios.csv
echo $?
```

An exit code of `0` confirms that the CSV files match.

Our verified Slurm execution on November 15, 2026 produced:

| Field | Result |
|---|---|
| Job ID | 30332 |
| Node | `haskell` |
| State | `COMPLETED` |
| Exit code | `0:0` |
| Slurm elapsed time | 1 second |
| Comparison with direct sequential run | Identical results |

The execution log is preserved in `docs/validation/baseline_run_30332.out`.

### Multiprocessing batch job

The repository also includes `slurm/parallel_run.sh` for executing multiprocessing simulations through Slurm.

For example, the script supports the following two-worker configuration:

```bash
sbatch --cpus-per-task=4 slurm/parallel_run.sh 2 5 1
```

The arguments specify:

- `--cpus-per-task=4`: Four logical CPUs
- `2`: Two worker processes
- `5`: Five scenarios
- `1`: One repetition

On this cluster, each physical core has two hardware threads. We therefore request two logical CPUs per worker when allocating one physical core per worker.

The script is configured to write:

- Scenario results to `results/parallel_w2_5_rep1/`
- Timing records to `results/timings_multiprocessing.csv`
- Slurm output to `parallel_run_JOB_ID.out`

This specific parallel Slurm command has not yet been included in our verified checkpoint tests.

## 7. Understanding the Output Files

Each simulation produces two main files.

### `scenarios.csv`

Contains one row per simulated disruption scenario:

```text
scenario,n_disruptions,n_blocked,disconnected_pairs,lost_trips,extra_delay_min
```

The first three columns identify the scenario and its disruptions. The remaining columns contain the calculated passenger-impact metrics.

### `summary.json`

Contains:

- Simulation configuration and random seed
- Number of scenarios and stations
- Dataset information and metric units
- Mean, median, maximum, and total for each metric
- Execution timing breakdown
- Software versions and available execution metadata

The sequential version records input loading, scenario generation, shortest-path computation, and output-writing times.

The multiprocessing version additionally records worker startup time, allowing us to examine parallelization overhead.

Aggregate totals are calculated across the simulated scenarios. They should not be interpreted as observed impacts across actual calendar days.

## 8. Performance Experiments

The five-scenario examples above are intended for correctness and reproducibility checks. They are not used to calculate official speedup or parallel efficiency.

### Sequential baseline and profiling

Our existing baseline profiling selected **100,000 scenarios** as the full-scale workload.

The recorded sequential execution took approximately **603.7 seconds (10 minutes and 4 seconds)**, with peak resident memory of **5.53 GiB**.

Profiling showed that shortest-path computation dominates runtime, making the measured workload primarily CPU-bound.

The methodology and results are documented in [docs/profiling/profiling.md](docs/profiling/profiling.md).

### Strong and weak scaling

For **strong scaling**, we keep the number of scenarios fixed and increase the number of workers:

`1, 2, 4, 8, 16, 32`

We measure execution time, speedup, parallel efficiency, and variation between repetitions.

For **weak scaling**, we increase the number of scenarios proportionally to the worker count and examine how execution time changes.

Our official measurements must:

- Run through Slurm batch jobs
- Include at least five repetitions per configuration
- Report the median and variation between runs
- Separate computation time from input and output time
- Record the compute node, Slurm job ID, and node load
- Account for relevant overhead and resource limitations

The timing-data specification is documented in [docs/timing_schema.md](docs/timing_schema.md).

### Benchmark integration

The repository includes `slurm/benchmark.sh` and `slurm/submit_strong_scaling.sh` for coordinating repeated benchmark runs.

These scripts depend on `scripts/run_benchmark.py`, whose integration and validation must be confirmed before using the complete benchmarking pipeline.

The scripts currently specify `results/timings/strong_scaling.csv` as the default strong-scaling timing output.

We will update this section with the validated benchmark commands, initial scaling plots, and corresponding timing data once the integration is complete.

## 9. Validation and Reproducibility

Our November 15, 2026 checkpoint verified:

- Sequential simulation execution
- Two-worker multiprocessing execution
- Identical sequential and multiprocessing results
- Successful sequential execution through Slurm
- Identical results between direct and Slurm execution

The supporting files are available in:

- [Checkpoint validation report](docs/validation/checkpoint_smoke_test.md)
- [Slurm execution log](docs/validation/baseline_run_30332.out)

Generated `results/` and `logs/` directories are excluded from Git. Some Slurm scripts also create logs in the repository root, so these files should be reviewed before staging changes.

For the final submission, we will preserve the required raw timing CSVs, plotting code, and experimental scripts in GitHub rather than relying on local HPC outputs.

**Final reproducibility check:** Once the benchmarking pipeline is complete, we will test the entire workflow from a fresh repository clone on the HPC cluster and update this README with the verified commands and output locations.

## 10. Troubleshooting

| Problem | Suggested check |
|---|---|
| `ModuleNotFoundError: No module named 'numpy'` | Load `SciPy-bundle/2023.11-gfbf-2023b` in the current terminal |
| Python cannot find project modules or input data | Confirm that the command is being run from the repository root |
| Job no longer appears in `squeue` | Use `sacct` to check whether it completed or failed |
| Warning about insufficient physical cores | Check the Slurm CPU allocation relative to the worker count |
| JupyterLab server stops or restarts | Reopen the terminal, return to the repository, and reload the module |
| Benchmark runner cannot be found | Confirm that the required benchmarking code has been merged into the current branch |

## AI USE AND REFERENCES

This README was prepared with assistance from ChatGPT (OpenAI).

We used ChatGPT to help structure the documentation, explain the HPC execution workflow, interpret Slurm output, clarify the simulation metrics, and review the reproducibility instructions against the existing implementation.

Prompts included requests to:

- Explain the setup and use of HPC environment modules and Slurm commands
- Interpret simulation results and resource-allocation information
- Check the equivalence of sequential and multiprocessing outputs
- Document a small reproducible checkpoint configuration
- Review the README for technical accuracy, clarity, and consistency with the project

The checkpoint commands were executed on the University HPC cluster, and the reported results were verified against the generated outputs.

**References**

- Official Operating Systems & Parallel Computing group project assignment
- `data/madrid_cercanias/metadata.json`
- `docs/interface.md`
- `src/simulation.py`
- `src/parallel.py`
- `slurm/baseline_run.sh`
- `slurm/parallel_run.sh`
- `docs/profiling/profiling.md`
- `docs/timing_schema.md`
- `docs/validation/checkpoint_smoke_test.md`
