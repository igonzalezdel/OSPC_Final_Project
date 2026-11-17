#!/bin/bash
# Submit the whole strong-scaling sweep: one Slurm job per worker count,
# plus the sequential reference. All rows go to the same timing CSV.
#
# The cluster nodes (fortran, haskell, julia) are not equally fast, so all
# jobs of one sweep must run on the SAME node. Pass the node as 4th argument.
#
# Usage, from the repository root (not with sbatch, just bash):
#   bash slurm/submit_strong_scaling.sh <scenarios> <reps> [csv] [node]
#   bash slurm/submit_strong_scaling.sh 100000 5 results/timings/strong_scaling_haskell.csv haskell
#   bash slurm/submit_strong_scaling.sh 2000 2 results/timings/test.csv            # quick test, any node

SCENARIOS=${1:?usage: bash slurm/submit_strong_scaling.sh <scenarios> <reps> [csv] [node]}
REPS=${2:?usage: bash slurm/submit_strong_scaling.sh <scenarios> <reps> [csv] [node]}
CSV=${3:-results/timings/strong_scaling.csv}
NODE=${4:-}

NODE_OPTION=()
if [ -n "$NODE" ]; then
    NODE_OPTION=(--nodelist="$NODE")
fi

mkdir -p logs
sbatch "${NODE_OPTION[@]}" --cpus-per-task=2 slurm/benchmark.sh sequential 1 "$SCENARIOS" "$REPS" "$CSV"
for WORKERS in 1 2 4 8 16 32; do
    sbatch "${NODE_OPTION[@]}" --cpus-per-task=$((2 * WORKERS)) slurm/benchmark.sh multiprocessing "$WORKERS" "$SCENARIOS" "$REPS" "$CSV"
done
echo "Submitted 7 jobs${NODE:+ on $NODE}. Check with: squeue -u \$USER"
