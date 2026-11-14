# OSPC Final Project (Group 4)

## mpi4py check on the HPC cluster

`mpi4py` is not part of the course environment. This check confirms that it
runs inside a Slurm batch job, using the module already installed on the cluster.

### Files (`mpi_check/`)
| File | Purpose |
|---|---|
| `setup_env.sh` | Loads `mpi4py/3.1.5-gompi-2023b` (Open MPI 4.1.6). Use it with `source`. |
| `mpi_hello.py` | Each MPI process prints its rank, the total number of ranks and its node. |
| `mpi_test.sh` | Slurm job script: 2 tasks, launched with `srun`. |
| `example_output.txt` | Output of a successful run. |

### How to run (on the cluster terminal, no installation needed)

    git clone https://github.com/igonzalezdel/OSPC_Final_Project.git
    cd OSPC_Final_Project/mpi_check
    sbatch mpi_test.sh
    cat mpi_test_<jobid>.out

Expected output:

    rank 0 of 2 on <node>
    rank 1 of 2 on <node>

### Result
Verified on 11 Nov 2026 on node `fortran`: both ranks started correctly with `srun`.
Running both ranks on different nodes has not been tested yet.
If `srun` does not start the processes correctly, `mpirun -n 2 python mpi_hello.py`
is the fallback (commented in `mpi_test.sh`).

### Notes
- `module load` lines must be repeated in every job script; batch jobs do not
  inherit the interactive terminal's modules. `setup_env.sh` does this.
- A pip installation of mpi4py does not work here: it installs the Python wrapper
  but finds no MPI library. The cluster module is the working option.
