"""Minimal MPI check: every process prints its rank, the total, and its node."""
from mpi4py import MPI

comm = MPI.COMM_WORLD
print(f"rank {comm.Get_rank()} of {comm.Get_size()} on {MPI.Get_processor_name()}")
