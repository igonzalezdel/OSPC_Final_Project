# AI USE AND REFERENCES
#
# This module was developed with assistance from Claude (Anthropic).
# AI assistance was used to design the process pool, the chunking of
# scenario numbers, the per-scenario seeding and the timing. It reuses
# the metric code of the sequential simulation (src/simulation.py) and the
# scenario rules of src/scenarios.py, and it was tested against the
# sequential version (tests/test_parallel.py).
#
# Prompts included requests to parallelise independent Monte Carlo
# scenarios with multiprocessing, keep results identical to the sequential
# run, and avoid nested NumPy threads inside worker processes.
#
# References:
# https://docs.python.org/3/library/multiprocessing.html
# https://numpy.org/doc/stable/reference/random/parallel.html (SeedSequence.spawn)

"""Parallel Monte Carlo simulation with a pool of worker processes.

Same scenarios, same Floyd-Warshall and same metrics as src/simulation.py,
but the scenario numbers 0..N-1 are split into chunks and the chunks are
shared between `--workers` processes.

Each worker builds its own scenarios from (seed, scenario number), so:
  - the main process never holds all N scenarios in memory
    (the sequential run needs ~5.5 GB at 100,000 scenarios);
  - scenario generation also runs in parallel;
  - the results are identical for 1, 2, 4, ... 32 workers.

Usage (from the repository root):

    python -m src.parallel --workers 8 --scenarios 100000 --out results/parallel_w8

`scenarios.csv` has the same columns and values as the sequential run, so the
two files can be compared directly.
"""

import os

# One thread per worker process. These must be set before NumPy is imported,
# otherwise each worker could start its own BLAS threads and they would compete
# for the same cores (nested parallelism).
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse
import csv
import json
import multiprocessing as mp
import platform
import time
from datetime import date
from pathlib import Path

import numpy as np

from src.railway_data import load_railway_data
from src.simulation import METRICS, UNITS, aggregate, scenario_metrics, shortest_times
from src.numpy_version import floyd_warshall_numpy


# --------------------------------------------------
# 1. One scenario from (seed, scenario number)
# --------------------------------------------------

def available_links(network):
    # Same list and order as generate_disruption_scenarios (upper triangle)
    return np.argwhere(np.triu(np.isfinite(network), k=1))


def build_scenario(network, links, seed, number, params):
    """Rebuild scenario `number` exactly as src/scenarios.py does.

    SeedSequence(seed).spawn(N)[number] is the same as
    SeedSequence(seed, spawn_key=(number,)), so a worker can create
    scenario `number` without creating the ones before it.
    """
    rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(number,)))
    scenario = network.copy()

    n_disruptions = rng.integers(params["min_disruptions"], params["max_disruptions"] + 1)
    chosen = rng.choice(len(links), size=n_disruptions, replace=False)

    n_blocked = 0
    for index in chosen:
        i, j = links[index]
        if rng.random() < params["block_probability"]:
            scenario[i, j] = scenario[j, i] = np.inf
            n_blocked += 1
        else:
            delay = int(rng.integers(params["min_delay"], params["max_delay"] + 1))
            scenario[i, j] += delay
            scenario[j, i] += delay

    return scenario, int(n_disruptions), n_blocked


# --------------------------------------------------
# 2. Worker side
# --------------------------------------------------

# Read-only data, set once per worker by init_worker (not sent with every task)
_shared = {}


def init_worker(network, demand, baseline, links, seed, params, kernel):
    _shared.update(network=network, demand=demand, baseline=baseline,
                   links=links, seed=seed, params=params, kernel=kernel)


def solve(matrix, kernel):
    if kernel == "numpy":
        return floyd_warshall_numpy(matrix)
    return shortest_times(matrix)  # pure Python Floyd-Warshall, same as the baseline


def run_chunk(bounds):
    """Run scenarios start..stop-1 and return one result row per scenario."""
    start, stop = bounds
    s = _shared
    rows = []
    for number in range(start, stop):
        scenario, n_disruptions, n_blocked = build_scenario(
            s["network"], s["links"], s["seed"], number, s["params"])
        disrupted = solve(scenario, s["kernel"])
        metrics = scenario_metrics(s["baseline"], disrupted, s["demand"])
        rows.append({"scenario": number, "n_disruptions": n_disruptions,
                     "n_blocked": n_blocked, **metrics})
    return rows


# --------------------------------------------------
# 3. Main process: split the work and collect results
# --------------------------------------------------

def make_chunks(n_scenarios, workers, chunks_per_worker):
    """Split 0..N-1 into about workers * chunks_per_worker contiguous ranges.

    Several chunks per worker balance the load (some scenarios are slower),
    while keeping the number of messages between processes small.
    """
    n_chunks = max(1, min(n_scenarios, workers * chunks_per_worker))
    edges = np.linspace(0, n_scenarios, n_chunks + 1).astype(int)
    return [(int(a), int(b)) for a, b in zip(edges[:-1], edges[1:]) if b > a]


def run_parallel(network, demand, n_scenarios, workers, seed, params,
                 kernel="python", chunks_per_worker=4):
    """Return (rows sorted by scenario, timing dict)."""
    baseline = solve(network, kernel)  # undisrupted network, once
    links = available_links(network)
    if params["max_disruptions"] > len(links):
        raise ValueError("There are not enough available links.")
    chunks = make_chunks(n_scenarios, workers, chunks_per_worker)

    t0 = time.perf_counter()
    pool = mp.get_context("spawn").Pool(
        processes=workers,
        initializer=init_worker,
        initargs=(network, demand, baseline, links, seed, params, kernel),
    )
    # Tiny task so the start-up cost of the workers is measured on its own
    pool.map(_ping, range(workers), chunksize=1)
    startup_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    rows = []
    with pool:
        for chunk_rows in pool.imap_unordered(run_chunk, chunks):
            rows.extend(chunk_rows)
    compute_s = time.perf_counter() - t0

    # Chunks finish in any order; sorting makes the output independent of it
    rows.sort(key=lambda r: r["scenario"])
    return rows, {"pool_startup": startup_s, "compute": compute_s, "n_chunks": len(chunks)}


def _ping(_):
    return os.getpid()


def cpus_and_cores():
    """Logical CPUs this process may use, and how many physical cores they are.

    On the cluster Slurm gives whole cores, and each core shows up as 2 CPUs
    (hyperthreads). Two workers on the same core compete for it, so the
    scaling runs need one physical core per worker.
    """
    if not hasattr(os, "sched_getaffinity"):
        return os.cpu_count(), None
    cpus = sorted(os.sched_getaffinity(0))
    cores = set()
    for cpu in cpus:
        topology = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        try:
            package = (topology / "physical_package_id").read_text().strip()
            core = (topology / "core_id").read_text().strip()
        except OSError:
            return len(cpus), None
        cores.add((package, core))
    return len(cpus), len(cores)


# --------------------------------------------------
# 4. Output files
# --------------------------------------------------

def write_scenario_csv(path, rows):
    # Same columns as src/simulation.py so the two files can be diffed
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["scenario", "n_disruptions", "n_blocked"] + METRICS)
        for r in rows:
            writer.writerow([r["scenario"], r["n_disruptions"], r["n_blocked"]]
                            + [r[name] for name in METRICS])


def append_timing_row(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(row), lineterminator="\n")
        if new_file:
            writer.writeheader()
        writer.writerow(row)


# --------------------------------------------------
# 5. Command line
# --------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Parallel (multiprocessing) Monte Carlo railway disruption simulation.")
    parser.add_argument("--workers", type=int, default=1,
                        help="number of worker processes (1, 2, 4, 8, 16, 32)")
    parser.add_argument("--data", default="data/madrid_cercanias")
    parser.add_argument("--scenarios", type=int, default=20, help="problem size")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-disruptions", type=int, default=1)
    parser.add_argument("--max-disruptions", type=int, default=3)
    parser.add_argument("--block-probability", type=float, default=0.5)
    parser.add_argument("--min-delay", type=int, default=5)
    parser.add_argument("--max-delay", type=int, default=30)
    parser.add_argument("--kernel", choices=["python", "numpy"], default="python",
                        help="Floyd-Warshall used inside each worker (python = same as baseline)")
    parser.add_argument("--chunks-per-worker", type=int, default=4)
    parser.add_argument("--out", default=None,
                        help="output folder (default results/parallel_w<workers>_<scenarios>)")
    parser.add_argument("--timing-csv", default=None,
                        help="append one timing row to this CSV (for scaling runs)")
    parser.add_argument("--repetition", type=int, default=0,
                        help="repetition number, only written to the timing CSV")
    args = parser.parse_args(argv)

    if args.workers < 1:
        parser.error("--workers must be at least 1")
    if args.scenarios < 1:
        parser.error("--scenarios must be at least 1")

    wall_start = time.perf_counter()

    t0 = time.perf_counter()
    data = load_railway_data(args.data)
    network, demand = data["network"], data["demand"]
    input_s = time.perf_counter() - t0

    params = {
        "min_disruptions": args.min_disruptions,
        "max_disruptions": args.max_disruptions,
        "block_probability": args.block_probability,
        "min_delay": args.min_delay,
        "max_delay": args.max_delay,
    }
    rows, timing = run_parallel(network, demand, args.scenarios, args.workers,
                                args.seed, params, args.kernel, args.chunks_per_worker)

    n_cpus, n_cores = cpus_and_cores()

    out_dir = Path(args.out or f"results/parallel_w{args.workers}_{args.scenarios}")
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    write_scenario_csv(out_dir / "scenarios.csv", rows)
    output_s = time.perf_counter() - t0
    total_s = time.perf_counter() - wall_start

    summary = {
        "version": "multiprocessing",
        "kernel": args.kernel,
        "workers": args.workers,
        "chunks": timing["n_chunks"],
        "seed": args.seed,
        "n_scenarios": args.scenarios,
        "n_stations": int(network.shape[0]),
        "scenario_parameters": {
            "min_disruptions": args.min_disruptions,
            "max_disruptions": args.max_disruptions,
            "block_probability": args.block_probability,
            "min_delay_min": args.min_delay,
            "max_delay_min": args.max_delay,
        },
        "dataset": data["metadata"].get("dataset_name", args.data),
        "units": UNITS,
        "aggregate": aggregate(rows),
        "timing_s": {
            "input": input_s,
            "pool_startup": timing["pool_startup"],
            "compute": timing["compute"],
            "output": output_s,
            "total": total_s,
        },
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "node": platform.node(),
        "cpus_available": n_cpus,
        "physical_cores_available": n_cores,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "date": date.today().isoformat(),
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    if args.timing_csv:
        append_timing_row(args.timing_csv, {
            "version": "multiprocessing",
            "kernel": args.kernel,
            "workers": args.workers,
            "scenarios": args.scenarios,
            "repetition": args.repetition,
            "input_s": round(input_s, 4),
            "pool_startup_s": round(timing["pool_startup"], 4),
            "compute_s": round(timing["compute"], 4),
            "output_s": round(output_s, 4),
            "total_s": round(total_s, 4),
            "cpus": n_cpus,
            "physical_cores": n_cores if n_cores is not None else "",
            "slurm_job_id": summary["slurm_job_id"] or "",
            "node": summary["node"],
            "date": summary["date"],
        })

    available = n_cores if n_cores is not None else n_cpus
    if available and args.workers > available:
        print(f"WARNING: {args.workers} workers but only {available} physical cores "
              f"({n_cpus} CPUs). Timings will not show real speedup.")
    print(f"{args.scenarios} scenarios, {args.workers} workers ({args.kernel}): "
          f"startup {timing['pool_startup']:.2f} s, compute {timing['compute']:.2f} s, "
          f"total {total_s:.2f} s -> {out_dir}/")
    return summary


if __name__ == "__main__":
    main()
