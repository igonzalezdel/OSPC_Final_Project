#!/bin/bash
# AI USE: written with assistance from Claude (Anthropic), reviewed by the author.
#
# Check that the MPI version matches the sequential run for 1, 2, 4, 8 and 16
# ranks before any timing run. Correctness only, not speed.
# Submit from the repository root:   sbatch slurm/check_mpi_equivalence.sh [scenarios]
#SBATCH --job-name=check_mpi
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=logs/check_mpi_%j.out

SCENARIOS=${1:-500}

type module >/dev/null 2>&1 || source /cvmfs/software.eessi.io/versions/2023.06/init/bash
module load SciPy-bundle/2023.11-gfbf-2023b
module load mpi4py/3.1.5-gompi-2023b
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

echo "node: $(hostname)   job: $SLURM_JOB_ID   scenarios: $SCENARIOS"
python scripts/check_mpi_equivalence.py --scenarios "$SCENARIOS" --ranks 1 2 4 8 16 --launcher srun
STATUS=$?
echo "exit code: $STATUS"
exit $STATUS
