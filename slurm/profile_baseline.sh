#!/bin/bash
#
# Step 1 of the baseline profiling: measure a few problem sizes on ONE core,
# run cProfile, and print how many scenarios give a 10-minute sequential run.
# Submit from the repository root:   sbatch slurm/profile_baseline.sh
#SBATCH --job-name=profile_baseline
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=profile_baseline_%j.out

type module >/dev/null 2>&1 || source /cvmfs/software.eessi.io/versions/2023.06/init/bash
module load SciPy-bundle/2023.11-gfbf-2023b

# One worker must really use one core: stop NumPy/BLAS from opening extra threads
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

echo "node: $(hostname)   job: $SLURM_JOB_ID   cpus: $SLURM_CPUS_PER_TASK"
lscpu | grep -E "Model name|^CPU\(s\)|Thread|Core|Socket|L3"
free -g | head -2

python scripts/profile_baseline.py --sizes 1000 4000 16000 --profile-size 2000 \
    --target-minutes 10 --out results/profiling
