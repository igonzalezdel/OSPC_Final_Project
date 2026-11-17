#!/bin/bash
# AI USE: written with assistance from Claude (Anthropic), reviewed by the author.
#
# MPI benchmark job: one job = one number of ranks, repeated REPS times.
# Each run appends one row to the timing CSV (docs/timing_schema.md + MPI columns).
# The environment (cluster modules, srun launcher) is the one verified in
# mpi_check/ ("README.md").
#
# The number of ranks is the number of Slurm tasks, so give it to sbatch:
#   sbatch --ntasks=<ranks> --cpus-per-task=2 slurm/mpi_run.sh <ranks> <scenarios> <reps> [csv] [kernel]
#
#   sbatch --ntasks=2  --cpus-per-task=2 slurm/mpi_run.sh 2  2000   2     # quick test
#   sbatch --ntasks=8  --cpus-per-task=2 slurm/mpi_run.sh 8  100000 5
#
# One rank = one physical core = 2 Slurm CPUs on this cluster (see docs/README_parallel.md),
# so 32 ranks = 64 CPUs, the per-user maximum. All ranks stay on one node so the
# results compare with the multiprocessing version (same machine, no network).
# Submit from the repository root (logs/ must exist: mkdir -p logs).
#SBATCH --job-name=railway_mpi
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=2
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/mpi_%j.out
#SBATCH --error=logs/mpi_%j.err

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

RANKS=${1:?usage: mpi_run.sh <ranks> <scenarios> <reps> [csv] [kernel]}
SCENARIOS=${2:?missing scenarios}
REPS=${3:?missing repetitions}
CSV=${4:-results/timings/mpi_scaling.csv}
KERNEL=${5:-python}

if [ "$SLURM_NTASKS" -ne "$RANKS" ]; then
    echo "ERROR: asked for $RANKS ranks but Slurm gave $SLURM_NTASKS tasks." >&2
    echo "       Use: sbatch --ntasks=$RANKS --cpus-per-task=2 slurm/mpi_run.sh ..." >&2
    exit 2
fi

type module >/dev/null 2>&1 || source /cvmfs/software.eessi.io/versions/2023.06/init/bash
module load SciPy-bundle/2023.11-gfbf-2023b   # NumPy, pandas
module load mpi4py/3.1.5-gompi-2023b          # mpi4py + Open MPI (verified in mpi_check/)

export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1

echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Ranks: $RANKS   CPUs per rank: $SLURM_CPUS_PER_TASK"
echo "Date (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Node load: $(cut -d ' ' -f 1 /proc/loadavg)"
echo "Git commit: $(git rev-parse HEAD)"
echo "Run: mpi, $RANKS ranks, $SCENARIOS scenarios, $REPS repetitions, kernel $KERNEL -> $CSV"

for REP in $(seq 1 "$REPS"); do
    srun python -m src.mpi_simulation \
        --scenarios "$SCENARIOS" \
        --kernel "$KERNEL" \
        --repetition "$REP" \
        --timing-csv "$CSV" \
        --out "results/mpi_runs/r${RANKS}_s${SCENARIOS}_job${SLURM_JOB_ID}_rep${REP}"
done

echo "Finished: $REPS rows added to $CSV"
