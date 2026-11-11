#!/bin/bash
#SBATCH --job-name=mpi_test
#SBATCH --ntasks=2
#SBATCH --cpus-per-task=1
#SBATCH --time=00:02:00
#SBATCH --output=mpi_test_%j.out

# Submit from this directory:  sbatch mpi_test.sh
source "$SLURM_SUBMIT_DIR/setup_env.sh"
srun python mpi_hello.py
# If srun does not start the MPI processes correctly, use instead:
# mpirun -n 2 python mpi_hello.py
