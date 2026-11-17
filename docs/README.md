
# Technical Documentation

This directory contains the technical documentation for our railway disruption simulation project, including implementation details, HPC experiments, performance measurements, and validation.

For the project overview, setup instructions, and reproducible execution workflow, see the [main README](../README.md).

## 1. Simulation and Implementation

These documents explain how the railway simulation works and how the sequential and parallel implementations are structured.

| Document | Description |
|---|---|
| [Railway Data Interface](interface.md) | Defines the common data structures, disruption scenarios, simulation outputs, and metrics used across the project. |
| [Sequential Monte Carlo Simulation](README_montecarlo.md) | Explains the sequential simulation, scenario processing, algorithm, output metrics, and implementation decisions. |
| [Parallel Implementation](README_parallel.md) | Describes the multiprocessing approach, worker allocation, correctness considerations, and execution workflow. |

## 2. HPC and Performance Analysis

These documents explain how performance experiments are executed on the University's HPC cluster and how their results are recorded and interpreted.

| Document | Description |
|---|---|
| [Benchmarking](benchmarking.md) | Documents the benchmark scripts, Slurm execution workflow, timing collection, and validation of measurements. |
| [Timing CSV Schema](timing_schema.md) | Defines the timing fields, experiment configurations, and metadata recorded to support reproducibility. |
| [Baseline Profiling](profiling/profiling.md) | Presents the sequential baseline, profiling measurements, and rationale for the selected experiment size. |
| [Raw Timing Data](timings/README.md) | Provides access to the HPC timing datasets used for performance comparisons. |

### Strong-Scaling Results

The initial strong-scaling experiment uses a fixed workload of 100,000 simulation scenarios, with five repetitions per configuration and worker counts of 1, 2, 4, 8, 16, and 32.

The measurements were collected on the same HPC node (`haskell`).

- [Strong-scaling plots](plots/strong_scaling_elapsed_s.png) — measured versus ideal speedup and parallel efficiency.
- [Scaling summary CSV](plots/strong_scaling_elapsed_s.csv) — median runtimes, min–max variation, speedup, and efficiency.
- [Raw benchmark measurements](timings/strong_scaling_haskell.csv) — the underlying HPC timing records.
- [Plotting script](../scripts/plot_scaling.py) — generates the figures and summary CSV from the recorded measurements.
- [Scaling interpretation](scaling_interpretation.md) — Amdahl model compared with the measured speedup, measured overhead, and the wall-time versus allocated core-time trade-off.
- [Amdahl comparison plot](plots/strong_scaling_elapsed_s_amdahl.png) — measured, ideal and Amdahl-predicted speedup and efficiency.

Speedup is calculated relative to the one-worker multiprocessing baseline. The figures illustrate how performance changes as additional workers are allocated to the same workload.

## 3. Validation and Reproducibility

These resources document the checks performed to verify that the implementations execute correctly and produce comparable results.

| Document | Description |
|---|---|
| [Checkpoint Validation](validation/checkpoint_smoke_test.md) | Records small-scale sequential and multiprocessing equivalence checks and successful Slurm execution evidence. |
| [Project Tests](../tests/) | Contains tests for the simulation, data, scenarios, and parallel implementation. |

## 4. Repository Navigation

The main project components are organized as follows:

| Directory | Purpose |
|---|---|
| [`data/`](../data/) | Railway network, passenger demand data, source information, and assumptions. |
| [`src/`](../src/) | Sequential and parallel simulation implementations. |
| [`scripts/`](../scripts/) | Benchmarking, profiling, plotting, validation, and dataset preparation utilities. |
| [`slurm/`](../slurm/) | HPC batch-job scripts and execution configurations. |
| [`tests/`](../tests/) | Correctness and reproducibility tests. |
| [`mpi_check/`](../mpi_check/) | MPI environment setup and verification on the HPC cluster. |

## AI USE AND REFERENCES

This documentation index was prepared with assistance from ChatGPT (OpenAI).

We used ChatGPT to review the repository organization, improve documentation clarity, and structure the available technical resources so that the project's implementation, experiments, and results are easier to navigate.

Prompts included requests to:

- Review the GitHub repository structure and documentation organization
- Suggest improvements to README files and repository navigation
- Organize and refine the documentation index for clarity and consistency
- Verify references against the existing project files

The documentation links and descriptions were reviewed against the existing repository.

**References**

- [Main project README](../README.md)
- [Railway Data Interface](interface.md)
- [Sequential Monte Carlo Simulation](README_montecarlo.md)
- [Parallel Implementation](README_parallel.md)
- [Benchmarking](benchmarking.md)
- [Timing CSV Schema](timing_schema.md)
- [Baseline Profiling](profiling/profiling.md)
- [Checkpoint Validation](validation/checkpoint_smoke_test.md)
