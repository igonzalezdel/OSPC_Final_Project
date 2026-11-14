#!/bin/bash
# AI USE: written with assistance from Claude (Anthropic), reviewed by the author.
#
# Step 2 of the baseline profiling: one full sequential run at the chosen size,
# with /usr/bin/time -v for CPU usage, peak memory and I/O counters.
# Submit from the repository root:   sbatch slurm/baseline_run.sh 70000
#SBATCH --job-name=baseline_run
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:45:00
#SBATCH --output=baseline_run_%j.out

SCENARIOS=${1:?usage: sbatch slurm/baseline_run.sh <number of scenarios>}

type module >/dev/null 2>&1 || source /cvmfs/software.eessi.io/versions/2023.06/init/bash
module load SciPy-bundle/2023.11-gfbf-2023b
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

echo "node: $(hostname)   job: $SLURM_JOB_ID   scenarios: $SCENARIOS"
lscpu | grep -E "Model name|^CPU\(s\)"

OUT=results/baseline_${SCENARIOS}
if [ -x /usr/bin/time ]; then
    /usr/bin/time -v python -m src.simulation --scenarios "$SCENARIOS" --out "$OUT"
else
    echo "/usr/bin/time not found, using bash time"
    time python -m src.simulation --scenarios "$SCENARIOS" --out "$OUT"
fi
cat "$OUT/summary.json"
