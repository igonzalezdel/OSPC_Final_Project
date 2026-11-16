#!/bin/bash
# Submit the whole strong-scaling sweep: one Slurm job per worker count,
# plus the sequential reference. All rows go to the same timing CSV.
#
# Usage, from the repository root (not with sbatch, just bash):
#   bash slurm/submit_strong_scaling.sh <scenarios> <reps> [csv]
#   bash slurm/submit_strong_scaling.sh 100000 5
#   bash slurm/submit_strong_scaling.sh 2000 2 results/timings/test.csv   # quick test

SCENARIOS=${1:?usage: bash slurm/submit_strong_scaling.sh <scenarios> <reps> [csv]}
REPS=${2:?usage: bash slurm/submit_strong_scaling.sh <scenarios> <reps> [csv]}
CSV=${3:-results/timings/strong_scaling.csv}

mkdir -p logs
sbatch --cpus-per-task=2 slurm/benchmark.sh sequential 1 "$SCENARIOS" "$REPS" "$CSV"
for WORKERS in 1 2 4 8 16 32; do
    sbatch --cpus-per-task=$((2 * WORKERS)) slurm/benchmark.sh multiprocessing "$WORKERS" "$SCENARIOS" "$REPS" "$CSV"
done
echo "Submitted 7 jobs. Check with: squeue -u \$USER"
