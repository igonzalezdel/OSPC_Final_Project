# AI USE AND REFERENCES
#
# This module was developed with assistance from Claude (Anthropic).
# AI assistance was used to design the split of scenario numbers between MPI
# ranks, the gather of the results on rank 0, the timing of communication, and
# the tests. It reuses the scenario rebuild and the metric code of
# src/parallel.py and src/simulation.py, and it was tested against the
# sequential version (tests/test_mpi_simulation.py).
#
# Prompts included requests to run the railway Monte Carlo simulation with
# mpi4py, give each rank its own block of independent scenarios, keep the
# results identical to the sequential run, and record communication time.
#
# References:
# https://mpi4py.readthedocs.io/en/stable/tutorial.html
# https://numpy.org/doc/stable/reference/random/parallel.html (SeedSequence.spawn)
# mpi_check/README.md (verified cluster setup: module and srun launcher)

"""MPI version of the railway Monte Carlo simulation (mpi4py).

Same scenarios, same Floyd-Warshall and same metrics as src/simulation.py.
The scenario numbers 0..N-1 are split into one contiguous block per MPI rank.

    rank 0 loads the data  --bcast-->  every rank
    every rank: baseline once, then its own block of scenarios
    every rank  --gather-->  rank 0 sorts, writes scenarios.csv and summary.json

Scenario `s` is built from (seed, s) only (see src/parallel.py), so the output
is identical for 1, 2, 4, ... 32 ranks and identical to the sequential run.
Only two messages are sent: one broadcast of the inputs and one gather of the
results (6 numbers per scenario).

Usage on the cluster (from the repository root, inside a Slurm job):

    srun python -m src.mpi_simulation --scenarios 100000 --out results/mpi_r8

On a laptop with an MPI installation:

    mpirun -n 4 python -m src.mpi_simulation --scenarios 1000 --out results/mpi_r4
"""

import os

# One thread per rank: the ranks are the parallelism. Must be set before NumPy
# is imported (src.parallel also does this).
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse
import csv
import fcntl
import json
import platform
import subprocess
import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

from src.parallel import (available_links, build_scenario, cpus_and_cores,
                          solve, write_scenario_csv)
from src.railway_data import load_railway_data
from src.simulation import METRICS, UNITS, aggregate

ROOT = Path(__file__).resolve().parents[1]

# Columns of the array each rank sends to rank 0 (one row per scenario)
COLUMNS = ["scenario", "n_disruptions", "n_blocked"] + METRICS

# Agreed columns of docs/timing_schema.md, in the same order, then the extras
# that only make sense for MPI. Rows can be joined with the other versions on
# the first 16 columns.
SCHEMA_COLUMNS = [
    "timestamp_utc", "implementation", "git_commit", "dataset", "workers",
    "stations", "scenarios", "seed", "repetition", "load_s", "compute_s",
    "write_s", "elapsed_s", "node", "slurm_job_id", "node_load_1m",
]
EXTRA_COLUMNS = ["comm_s", "bcast_s", "gather_s", "compute_min_s", "compute_mean_s",
                 "nodes", "cpus_per_rank", "kernel"]


# --------------------------------------------------
# 1. Split of the work
# --------------------------------------------------

def block_bounds(n_scenarios, size, rank):
    """Scenario numbers [start, stop) of one rank.

    Contiguous blocks that differ in length by at most 1 scenario. If there are
    fewer scenarios than ranks, the last ranks get an empty block.
    """
    base, extra = divmod(n_scenarios, size)
    start = rank * base + min(rank, extra)
    stop = start + base + (1 if rank < extra else 0)
    return start, stop


def compute_block(network, demand, baseline, links, seed, params, start, stop, kernel):
    """Run scenarios start..stop-1 and return an array (stop-start, 6)."""
    from src.simulation import scenario_metrics
    block = np.zeros((stop - start, len(COLUMNS)), dtype=np.float64)
    for row, number in enumerate(range(start, stop)):
        scenario, n_disruptions, n_blocked = build_scenario(
            network, links, seed, number, params)
        metrics = scenario_metrics(baseline, solve(scenario, kernel), demand)
        block[row] = [number, n_disruptions, n_blocked] + [metrics[m] for m in METRICS]
    return block


def rows_from_array(array):
    """Back to one dict per scenario. Counts are exact in float64 (< 2**53)."""
    rows = []
    for values in array:
        row = {}
        for name, value in zip(COLUMNS, values):
            row[name] = float(value) if name == "extra_delay_min" else int(value)
        rows.append(row)
    return rows


# --------------------------------------------------
# 2. The simulation on one communicator
# --------------------------------------------------

def run_simulation(comm, args, mpi_info=None):
    """Run on every rank. Returns the summary on rank 0 and None elsewhere.

    `comm` only needs Get_rank, Get_size, Barrier, bcast and gather, so the
    tests can use a thread-based stand-in without an MPI installation.
    """
    rank, size = comm.Get_rank(), comm.Get_size()
    params = {
        "min_disruptions": args.min_disruptions,
        "max_disruptions": args.max_disruptions,
        "block_probability": args.block_probability,
        "min_delay": args.min_delay,
        "max_delay": args.max_delay,
    }

    comm.Barrier()
    wall_start = time.perf_counter()

    # --- input: rank 0 reads the files ---
    t0 = time.perf_counter()
    payload = None
    if rank == 0:
        data = load_railway_data(args.data)
        payload = (data["network"], data["demand"], data["metadata"])
    input_s = time.perf_counter() - t0

    # --- communication 1: broadcast the inputs ---
    comm.Barrier()
    t0 = time.perf_counter()
    network, demand, metadata = comm.bcast(payload, root=0)
    comm.Barrier()
    bcast_s = time.perf_counter() - t0

    if params["max_disruptions"] > len(available_links(network)):
        raise ValueError("There are not enough available links.")

    # --- compute: baseline once per rank, then this rank's block ---
    start, stop = block_bounds(args.scenarios, size, rank)
    comm.Barrier()
    t_compute = time.perf_counter()
    baseline = solve(network, args.kernel)
    links = available_links(network)
    local = compute_block(network, demand, baseline, links, args.seed, params,
                          start, stop, args.kernel)
    local_s = time.perf_counter() - t_compute
    comm.Barrier()  # not timed: so the gather below does not include waiting for slow ranks

    # --- communication 2: collect the results on rank 0 ---
    t0 = time.perf_counter()
    gathered = comm.gather((local, local_s, platform.node(), cpus_and_cores()[0]), root=0)
    comm.Barrier()
    gather_s = time.perf_counter() - t0

    if rank != 0:
        return None

    # --- output (rank 0 only) ---
    blocks = [g[0] for g in gathered]
    rows = rows_from_array(np.concatenate(blocks))  # blocks are in rank order = scenario order
    rank_compute = [g[1] for g in gathered]
    compute_s = max(rank_compute)  # the parallel compute time is that of the slowest rank
    nodes = sorted({g[2] for g in gathered})
    out_dir = Path(args.out or f"results/mpi_r{size}_{args.scenarios}")
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    write_scenario_csv(out_dir / "scenarios.csv", rows)
    output_s = time.perf_counter() - t0
    total_s = time.perf_counter() - wall_start

    summary = {
        "version": "mpi",
        "kernel": args.kernel,
        "workers": size,
        "ranks": size,
        "nodes": nodes,
        "seed": args.seed,
        "n_scenarios": args.scenarios,
        "n_stations": int(network.shape[0]),
        "scenarios_per_rank": [int(b.shape[0]) for b in blocks],
        "scenario_parameters": {
            "min_disruptions": args.min_disruptions,
            "max_disruptions": args.max_disruptions,
            "block_probability": args.block_probability,
            "min_delay_min": args.min_delay,
            "max_delay_min": args.max_delay,
        },
        "dataset": metadata.get("dataset_name", args.data),
        "units": UNITS,
        "aggregate": aggregate(rows),
        "timing_s": {
            "input": input_s,
            "bcast": bcast_s,
            "compute": compute_s,
            "gather": gather_s,
            "output": output_s,
            "total": total_s,
        },
        "compute_per_rank_s": {
            "min": min(rank_compute),
            "mean": float(np.mean(rank_compute)),
            "max": max(rank_compute),
        },
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "cpus_per_rank": gathered[0][3],
        "python": platform.python_version(),
        "numpy": np.__version__,
        "mpi": mpi_info or {},
        "date": date.today().isoformat(),
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print(f"{args.scenarios} scenarios, {size} ranks on {len(nodes)} node(s) ({args.kernel}): "
          f"input {input_s:.3f} s, bcast {bcast_s:.3f} s, compute {compute_s:.2f} s, "
          f"gather {gather_s:.3f} s, output {output_s:.3f} s, total {total_s:.2f} s "
          f"-> {out_dir}/")
    return summary


# --------------------------------------------------
# 3. Timing CSV (docs/timing_schema.md + MPI columns)
# --------------------------------------------------

def git_commit():
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        changed = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                 cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return commit + ("-modified" if changed else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def node_load_1m():
    try:
        return float(Path("/proc/loadavg").read_text().split()[0])
    except OSError:
        return ""


def timing_row(summary, repetition):
    t = summary["timing_s"]
    return {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "implementation": "mpi",
        "git_commit": git_commit(),
        "dataset": summary["dataset"],
        "workers": summary["ranks"],
        "stations": summary["n_stations"],
        "scenarios": summary["n_scenarios"],
        "seed": summary["seed"],
        "repetition": repetition,
        "load_s": round(t["input"], 4),
        "compute_s": round(t["compute"], 4),
        "write_s": round(t["output"], 4),
        "elapsed_s": round(t["total"], 4),
        "node": ",".join(summary["nodes"]),
        "slurm_job_id": summary["slurm_job_id"] or "",
        "node_load_1m": node_load_1m(),
        "comm_s": round(t["bcast"] + t["gather"], 4),
        "bcast_s": round(t["bcast"], 4),
        "gather_s": round(t["gather"], 4),
        "compute_min_s": round(summary["compute_per_rank_s"]["min"], 4),
        "compute_mean_s": round(summary["compute_per_rank_s"]["mean"], 4),
        "nodes": len(summary["nodes"]),
        "cpus_per_rank": summary["cpus_per_rank"],
        "kernel": summary["kernel"],
    }


def append_timing_row(path, row):
    """Append one row; the lock keeps rows whole if several jobs write at once."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        try:
            writer = csv.DictWriter(file, fieldnames=SCHEMA_COLUMNS + EXTRA_COLUMNS,
                                    lineterminator="\n")
            if file.tell() == 0:
                writer.writeheader()
            writer.writerow(row)
        finally:
            fcntl.flock(file, fcntl.LOCK_UN)


# --------------------------------------------------
# 4. Command line
# --------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="MPI (mpi4py) Monte Carlo railway disruption simulation. "
                    "Start it with srun or mpirun; the number of ranks is the worker count.")
    parser.add_argument("--data", default="data/madrid_cercanias")
    parser.add_argument("--scenarios", type=int, default=20, help="problem size")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-disruptions", type=int, default=1)
    parser.add_argument("--max-disruptions", type=int, default=3)
    parser.add_argument("--block-probability", type=float, default=0.5)
    parser.add_argument("--min-delay", type=int, default=5)
    parser.add_argument("--max-delay", type=int, default=30)
    parser.add_argument("--kernel", choices=["python", "numpy"], default="python",
                        help="Floyd-Warshall used by each rank (python = same as the baseline)")
    parser.add_argument("--out", default=None,
                        help="output folder (default results/mpi_r<ranks>_<scenarios>)")
    parser.add_argument("--timing-csv", default=None,
                        help="append one timing row to this CSV (for scaling runs)")
    parser.add_argument("--repetition", type=int, default=0,
                        help="repetition number, only written to the timing CSV")
    return parser


def main(argv=None):
    import mpi4py  # imported here so the rest of the module needs no MPI
    from mpi4py import MPI

    args = build_parser().parse_args(argv)
    if args.scenarios < 1:
        raise SystemExit("--scenarios must be at least 1")

    comm = MPI.COMM_WORLD
    info = {"mpi4py": mpi4py.__version__,
            "library": MPI.Get_library_version().split("\n")[0],
            "standard": ".".join(str(v) for v in MPI.Get_version())}
    summary = run_simulation(comm, args, info)

    if summary is not None and args.timing_csv:
        append_timing_row(args.timing_csv, timing_row(summary, args.repetition))
    return summary


if __name__ == "__main__":
    main()
