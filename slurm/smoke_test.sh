#!/bin/bash

# AI USE AND REFERENCES
#
# The initial version of this Slurm script was developed with
# assistance from ChatGPT (OpenAI, https://chatgpt.com)
#
# I used ChatGPT to understand how Slurm works, learn the
# purpose of its directives, and develop a basic test job
# I also reviewed and refined the script and its comments
#
# Prompts included requests to explain Slurm, its resource
# allocation directives, and how to submit and monitor a
# small batch job
#
# References:
# Existing project scripts:
# - slurm/baseline_run.sh
# - slurm/profile_baseline.sh


# We tell Slurm what resources our test job needs
# We use the CPU partition and request one task with one CPU
# Since this is a small test, we only need 1 GB of memory
# We also set a maximum execution time of two minutes
#SBATCH --job-name=ospc_smoke
#SBATCH --partition=cpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:02:00

# We save the job output and errors in separate files
# Slurm replaces %j with the job ID so each run has its own files
#SBATCH --output=logs/smoke_%j.out
#SBATCH --error=logs/smoke_%j.err


# We stop the script if a command fails or a variable is missing
set -euo pipefail

# We move to the folder where we submitted the job
# This ensures we run commands from our project directory
cd "$SLURM_SUBMIT_DIR"

# We print information about the job and the node running it
# This helps us identify where and when our test was executed
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "CPUs allocated: $SLURM_CPUS_PER_TASK"
echo "Date (UTC): $(date -u)"

# We record the node's one-minute load average
# This helps us understand how busy the node was during the test
echo "Node load: $(cut -d ' ' -f 1 /proc/loadavg)"

# We run a simple Python calculation to check that Python works
# We do not run the railway simulation yet because this is only a test
python -c 'print("Test result:", sum(range(1000)))'

# If we reach this line, all previous commands completed successfully
echo "Smoke test completed successfully"

