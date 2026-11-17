# Checkpoint Smoke Test — 15 November 2026

## Purpose

Verify that the railway simulation runs in the University HPC environment, that sequential and multiprocessing implementations produce identical results for a small workload, and that the sequential simulation can execute successfully as a Slurm batch job.

These are functionality and reproducibility checks, not performance benchmarks.

## Environment

- Cluster: IE University HPC
- Python: 3.11.5
- NumPy: 1.26.2
- SciPy: 1.11.4
- Module: `SciPy-bundle/2023.11-gfbf-2023b`
- Dataset: Madrid Cercanías, 60 stations
- Test workload: 5 scenarios, seed 42

## Tests and Results

| Test | Result |
|---|---|
| Sequential simulation | PASS — generated `scenarios.csv` and `summary.json` |
| Multiprocessing simulation, 2 workers | PASS — generated both output files |
| Sequential vs. multiprocessing CSV comparison | PASS — `diff` exit code `0` |
| Sequential Slurm batch job | PASS — job 30332 completed with exit code `0:0` |
| Direct sequential vs. Slurm CSV comparison | PASS — `diff` exit code `0` |

## Slurm Execution Evidence

- Job ID: `30332`
- Compute node: `haskell`
- Job state: `COMPLETED`
- Exit code: `0:0`
- Slurm elapsed time: `00:00:01`
- Original output: `baseline_run_30332.out`
- Preserved log: `docs/validation/baseline_run_30332.out`

## Limitations

The five-scenario workload was used only to verify execution and correctness.

The interactive JupyterLab session provided two logical CPUs corresponding to one physical core. Therefore, the two-worker test was not suitable for evaluating parallel speedup.

The full scaling experiments require controlled Slurm allocations, larger workloads and at least five repetitions per configuration.

## AI USE AND REFERENCES

This validation report was drafted with ChatGPT (OpenAI) assistance. AI was used to explain the HPC testing workflow, interpret Slurm job records and structure the documentation. Prompts included requests to verify sequential and parallel execution, explain environment modules, compare outputs and document smoke-test evidence.

The commands were executed and the results checked by the author on the University HPC cluster.