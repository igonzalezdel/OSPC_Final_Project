#!/bin/bash
# Submit the MPI strong-scaling sweep: one Slurm job per number of ranks.
# All rows go to the same timing CSV. For the comparison with the sequential and
# multiprocessing versions use the same <scenarios> as slurm/submit_strong_scaling.sh.
#
# Usage, from the repository root (not with sbatch, just bash):
#   bash slurm/submit_mpi_scaling.sh <scenarios> <reps> [csv]
#   bash slurm/submit_mpi_scaling.sh 100000 5
#   bash slurm/submit_mpi_scaling.sh 2000 2 results/timings/mpi_test.csv   # quick test

SCENARIOS=${1:?usage: bash slurm/submit_mpi_scaling.sh <scenarios> <reps> [csv]}
REPS=${2:?usage: bash slurm/submit_mpi_scaling.sh <scenarios> <reps> [csv]}
CSV=${3:-results/timings/mpi_scaling.csv}

mkdir -p logs
for RANKS in 1 2 4 8 16 32; do
    sbatch --ntasks="$RANKS" --cpus-per-task=2 slurm/mpi_run.sh "$RANKS" "$SCENARIOS" "$REPS" "$CSV"
done
echo "Submitted 6 jobs. Check with: squeue -u \$USER"
