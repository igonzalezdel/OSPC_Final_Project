#!/bin/bash
# AI USE: written with assistance from Claude (Anthropic), reviewed by the author.
#
# Run the multiprocessing driver with W workers, R times, and append one
# timing row per run to results/timings_multiprocessing.csv.
#
# The number of CPUs must match the number of workers, so pass it to sbatch too.
# Submit from the repository root, for example:
#
#   sbatch --cpus-per-task=1  slurm/parallel_run.sh 1  100000 5
#   sbatch --cpus-per-task=8  slurm/parallel_run.sh 8  100000 5
#   sbatch --cpus-per-task=32 slurm/parallel_run.sh 32 100000 5
#
# Quick test first (a few seconds):
#   sbatch --cpus-per-task=4 slurm/parallel_run.sh 4 2000 1
#
#SBATCH --job-name=parallel_run
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --output=parallel_run_%j.out

WORKERS=${1:?usage: sbatch --cpus-per-task=W slurm/parallel_run.sh <workers> <scenarios> [repetitions]}
SCENARIOS=${2:?usage: sbatch --cpus-per-task=W slurm/parallel_run.sh <workers> <scenarios> [repetitions]}
REPS=${3:-1}

if [ "${SLURM_CPUS_PER_TASK:-1}" -lt "$WORKERS" ]; then
    echo "WARNING: $WORKERS workers but only ${SLURM_CPUS_PER_TASK:-1} CPUs. Use sbatch --cpus-per-task=$WORKERS"
fi

type module >/dev/null 2>&1 || source /cvmfs/software.eessi.io/versions/2023.06/init/bash
module load SciPy-bundle/2023.11-gfbf-2023b
# One thread per worker process (no nested NumPy/BLAS threads)
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

echo "node: $(hostname)   job: $SLURM_JOB_ID   workers: $WORKERS   scenarios: $SCENARIOS   reps: $REPS"
lscpu | grep -E "Model name|^CPU\(s\)"

for REP in $(seq 1 "$REPS"); do
    python -m src.parallel \
        --workers "$WORKERS" \
        --scenarios "$SCENARIOS" \
        --out "results/parallel_w${WORKERS}_${SCENARIOS}_rep${REP}" \
        --timing-csv results/timings_multiprocessing.csv \
        --repetition "$REP"
done
