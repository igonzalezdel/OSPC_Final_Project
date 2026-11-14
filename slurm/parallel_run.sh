#!/bin/bash
# AI USE: written with assistance from Claude (Anthropic), reviewed by the author.
#
# Run the multiprocessing driver with W workers, R times, and append one
# timing row per run to results/timings_multiprocessing.csv.
#
# IMPORTANT: on this cluster Slurm counts each physical core as 2 CPUs
# (hyperthreads). For one physical core per worker, ask for 2 x W CPUs.
# With --cpus-per-task=W the workers share W/2 cores and the speedup is wrong
# (measured: 2 workers on 2 CPUs gave 1.2x instead of ~2x).
#
# Submit from the repository root, for example:
#
#   sbatch --cpus-per-task=2  slurm/parallel_run.sh 1  100000 5
#   sbatch --cpus-per-task=16 slurm/parallel_run.sh 8  100000 5
#   sbatch --cpus-per-task=64 slurm/parallel_run.sh 32 100000 5
#
# Quick test first (a few seconds):
#   sbatch --cpus-per-task=8 slurm/parallel_run.sh 4 2000 1
#
#SBATCH --job-name=parallel_run
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --output=parallel_run_%j.out

WORKERS=${1:?usage: sbatch --cpus-per-task=2W slurm/parallel_run.sh <workers> <scenarios> [repetitions]}
SCENARIOS=${2:?usage: sbatch --cpus-per-task=2W slurm/parallel_run.sh <workers> <scenarios> [repetitions]}
REPS=${3:-1}

if [ "${SLURM_CPUS_PER_TASK:-1}" -lt $((2 * WORKERS)) ]; then
    echo "WARNING: $WORKERS workers need --cpus-per-task=$((2 * WORKERS)) for one physical core each (got ${SLURM_CPUS_PER_TASK:-1})"
fi

type module >/dev/null 2>&1 || source /cvmfs/software.eessi.io/versions/2023.06/init/bash
module load SciPy-bundle/2023.11-gfbf-2023b
# One thread per worker process (no nested NumPy/BLAS threads)
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

echo "node: $(hostname)   job: $SLURM_JOB_ID   workers: $WORKERS   scenarios: $SCENARIOS   reps: $REPS"
lscpu | grep -E "Model name|^CPU\(s\)"
python - <<'EOF'
from src.parallel import cpus_and_cores
cpus, cores = cpus_and_cores()
print(f"allocated: {cpus} CPUs = {cores} physical cores")
EOF

for REP in $(seq 1 "$REPS"); do
    python -m src.parallel \
        --workers "$WORKERS" \
        --scenarios "$SCENARIOS" \
        --out "results/parallel_w${WORKERS}_${SCENARIOS}_rep${REP}" \
        --timing-csv results/timings_multiprocessing.csv \
        --repetition "$REP"
done
