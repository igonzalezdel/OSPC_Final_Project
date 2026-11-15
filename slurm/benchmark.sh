#!/bin/bash
# Benchmark job: Alexandra's template (slurm/benchmark_template.sh) with the
# simulation integrated. One job = one configuration, repeated REPS times.
# Each run appends one row to the timing CSV (columns: docs/timing_schema.md).
#
# Usage, from the repository root (logs/ must exist: mkdir -p logs):
#   sbatch --cpus-per-task=<2 x workers> slurm/benchmark.sh <implementation> <workers> <scenarios> <reps> [csv]
#
#   sbatch --cpus-per-task=2  slurm/benchmark.sh sequential      1  100000 5
#   sbatch --cpus-per-task=16 slurm/benchmark.sh multiprocessing 8  100000 5
#
# On this cluster one physical core = 2 Slurm CPUs, so ask for 2 CPUs per worker
# (see docs/README_parallel.md). 32 workers = 64 CPUs, the per-user maximum.
# For the full strong-scaling sweep use slurm/submit_strong_scaling.sh.
#SBATCH --job-name=railway_benchmark
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/benchmark_%j.out
#SBATCH --error=logs/benchmark_%j.err

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

IMPLEMENTATION=${1:?usage: benchmark.sh <sequential|multiprocessing> <workers> <scenarios> <reps> [csv]}
WORKERS=${2:?missing workers}
SCENARIOS=${3:?missing scenarios}
REPS=${4:?missing repetitions}
CSV=${5:-results/timings/strong_scaling.csv}

type module >/dev/null 2>&1 || source /cvmfs/software.eessi.io/versions/2023.06/init/bash
module load SciPy-bundle/2023.11-gfbf-2023b

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Allocated CPUs: $SLURM_CPUS_PER_TASK"
echo "Date (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Node load: $(cut -d ' ' -f 1 /proc/loadavg)"
echo "Git commit: $(git rev-parse HEAD)"
echo "Run: $IMPLEMENTATION, $WORKERS workers, $SCENARIOS scenarios, $REPS repetitions -> $CSV"

if [ "$SLURM_CPUS_PER_TASK" -lt $((2 * WORKERS)) ]; then
    echo "ERROR: $WORKERS workers need --cpus-per-task=$((2 * WORKERS))" >&2
    exit 2
fi

for REP in $(seq 1 "$REPS"); do
    python scripts/run_benchmark.py \
        --implementation "$IMPLEMENTATION" \
        --workers "$WORKERS" \
        --scenarios "$SCENARIOS" \
        --repetition "$REP" \
        --csv "$CSV"
done

echo "Finished: $REPS rows added to $CSV"
