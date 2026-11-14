
# Timing CSV Schema

## AI USE AND REFERENCES

The initial version of this documentation was developed with
assistance from ChatGPT (OpenAI, https://chatgpt.com)

I used ChatGPT to understand HPC performance measurements,
define the timing CSV structure, and relate it to the existing
sequential simulation and Slurm scripts

Prompts included requests to explain timing measurements,
identify the information needed for reproducible benchmarks,
and document the CSV columns and their units

References:
- Official OSPC group project assignment
- docs/interface.md
- docs/README_montecarlo.md
- src/simulation.py
- slurm/baseline_run.sh
- slurm/profile_baseline.sh


## Purpose

We use a CSV file to record the performance of our railway
disruption simulation on the HPC cluster

Each row represents one complete execution of the simulation

We record the configuration, execution times, and HPC information
so we can compare sequential and parallel performance


## CSV Structure

We will use the following column names:

timestamp_utc,implementation,git_commit,dataset,workers,stations,scenarios,seed,repetition,load_s,compute_s,write_s,elapsed_s,node,slurm_job_id,node_load_1m

### Experiment Information

| Column | Description |
|---|---|
| timestamp_utc | Date and time of the execution in UTC |
| implementation | Simulation version, such as sequential or parallel |
| git_commit | Git commit identifying the code used |
| dataset | Dataset used for the simulation |
| workers | Number of parallel workers |
| stations | Number of stations in the railway network |
| scenarios | Number of Monte Carlo scenarios processed |
| seed | Random seed used to reproduce the scenarios |
| repetition | Repetition number for the same configuration |

### Timing Measurements

| Column | Description | Unit |
|---|---|---|
| load_s | Time spent loading the input data | seconds |
| compute_s | Time spent generating and processing scenarios | seconds |
| write_s | Time spent writing simulation results | seconds |
| elapsed_s | Total elapsed time for the complete execution | seconds |

### HPC Information

| Column | Description |
|---|---|
| node | Name of the compute node |
| slurm_job_id | Job identifier assigned by Slurm |
| node_load_1m | One-minute load average of the compute node |


## How We Measure Execution Time

We separate execution time into three stages:

1. Loading the railway network and passenger demand
2. Generating disruption scenarios and running the simulation
3. Writing the simulation results

We use Python's time.perf_counter() to measure execution time
in seconds

The existing sequential simulation already records input,
computation, and output times in its summary.json file

We can map these existing values to our CSV columns:

- timing_s.input becomes load_s
- timing_s.compute becomes compute_s
- timing_s.output becomes write_s

The current output timer measures the scenario CSV writing step
The final benchmark implementation must define and validate
the complete output timing consistently

We will also measure elapsed_s separately to include the
complete execution time and any additional overhead

We do not assume that elapsed_s is exactly equal to the
sum of the three individual measurements


## Scaling Experiments

### Strong Scaling

We keep the problem size fixed and increase the number
of workers

We plan to test 1, 2, 4, 8, 16, and 32 workers

We compare execution times to calculate speedup
and parallel efficiency

### Weak Scaling

We increase the workload proportionally to the number
of workers

This allows us to study whether the parallel implementation
can handle larger workloads efficiently


## Repetitions and Reproducibility

We repeat each experimental configuration at least five times

We use the median execution time and report the variation
between runs

We record the random seed to keep disruption scenarios
reproducible across different worker counts

We also record the Git commit, node, job ID, date,
and node load to help identify differences between runs

The one-minute node load average represents overall
system load rather than the CPU utilization of our job

All performance measurements will run through Slurm
batch jobs rather than Jupyter notebook timing


## Slurm Smoke Test Validation

We successfully submitted and executed a small Slurm test

- Job ID: 29806
- Node: haskell
- Allocated CPUs: 1
- State: COMPLETED
- Exit code: 0:0
- Elapsed time: 1 second
- Python test result: 499500
- Error log: empty

The test confirmed that Slurm can execute our script,
run Python, and save stdout and stderr in separate files

The local output files are stored in logs/
and are excluded from Git


## Next Steps

This document defines the planned timing CSV structure

The benchmark integration task will connect this schema
to the validated sequential and parallel implementations

We will generate real timing rows only after integrating
and testing the simulation runner

We will not include invented measurements
