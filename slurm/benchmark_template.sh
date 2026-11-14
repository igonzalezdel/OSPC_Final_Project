
#!/bin/bash

# AI USE AND REFERENCES
#
# The initial version of this Slurm benchmark template was generated
# with ChatGPT (OpenAI, https://chatgpt.com).
#
# I used ChatGPT to understand how to prepare a reusable Slurm
# script for our performance experiments, based on the existing
# HPC scripts in our project.
#
# I also reviewed and refined the code and comments, particularly
# the resource settings and the parts that still need integration.
#
# Prompts included requests to create a Slurm benchmark template,
# explain its configuration and logging, and identify which parts
# should remain pending until the simulation is integrated.
#
# References:
# - slurm/baseline_run.sh
# - slurm/profile_baseline.sh
# - slurm/smoke_test.sh


# We request the resources needed for our initial benchmark setup
# We use one node, one task, and one CPU as in the sequential baseline
# We start with the same memory and time limits used by our team
# These settings will need adjustment for the parallel experiments
#SBATCH --job-name=railway_benchmark
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:45:00

# We save normal output and errors in separate files
# Slurm replaces %j with the unique job ID
#SBATCH --output=logs/benchmark_%j.out
#SBATCH --error=logs/benchmark_%j.err


# We stop execution if a command fails or a variable is missing
set -euo pipefail

# We move to the directory where we submitted the job
cd "$SLURM_SUBMIT_DIR"

# We load the same software environment used by our baseline scripts
type module >/dev/null 2>&1 || source /cvmfs/software.eessi.io/versions/2023.06/init/bash
module load SciPy-bundle/2023.11-gfbf-2023b

# We limit extra threads created by numerical libraries
# This helps us avoid using more CPU threads than intended
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# We record information about the job and its execution environment
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Allocated CPUs: $SLURM_CPUS_PER_TASK"
echo "Date (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Node load: $(cut -d ' ' -f 1 /proc/loadavg)"
echo "Git commit: $(git rev-parse HEAD)"

# We will integrate the validated simulation command here
# We must confirm how the parallel driver receives its arguments
# before configuring the actual performance experiments
#
# TODO: Configure the number of workers and problem size
# TODO: Run the validated sequential or parallel simulation
# TODO: Save one timing CSV row per execution
# TODO: Verify the timing results and workload configuration

# We stop here to avoid treating an incomplete benchmark as successful
echo "Benchmark template only - simulation not integrated" >&2
exit 2
