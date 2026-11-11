#!/bin/bash
# setup_env.sh - load the software environment used by this project.
# Usage: source setup_env.sh   (do not execute it; it must run in your shell)

# Make the `module` command available (it is missing in some non-interactive shells)
type module >/dev/null 2>&1 || source /cvmfs/software.eessi.io/versions/2023.06/init/bash

# mpi4py and a matching Open MPI come from the cluster's EESSI software stack.
# Modules must share the same toolchain suffix (here: 2023b).
module load mpi4py/3.1.5-gompi-2023b
