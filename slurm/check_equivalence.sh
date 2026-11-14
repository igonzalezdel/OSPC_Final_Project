#!/bin/bash
# AI USE: written with assistance from Claude (Anthropic), reviewed by the author.
#
# Check that the parallel driver matches the sequential run for
# 1, 2, 4, 8, 16 and 32 workers before any timing run.
# This checks correctness only, not speed, so 32 workers can share fewer cores.
# Submit from the repository root:   sbatch slurm/check_equivalence.sh [scenarios]
#SBATCH --job-name=check_equivalence
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=check_equivalence_%j.out

SCENARIOS=${1:-500}

type module >/dev/null 2>&1 || source /cvmfs/software.eessi.io/versions/2023.06/init/bash
module load SciPy-bundle/2023.11-gfbf-2023b
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

echo "node: $(hostname)   job: $SLURM_JOB_ID   scenarios: $SCENARIOS"
python scripts/check_equivalence.py --scenarios "$SCENARIOS" --workers 1 2 4 8 16 32
STATUS=$?
echo "exit code: $STATUS"
exit $STATUS
