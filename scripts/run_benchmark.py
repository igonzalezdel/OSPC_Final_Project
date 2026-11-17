"""
Run the simulation once and append one timing row to a CSV in the format
of docs/timing_schema.md.

It wraps the two existing programs without changing them:
    sequential       -> src/simulation.py
    multiprocessing  -> src/parallel.py

Usage (from the repository root, inside a Slurm job):
    python scripts/run_benchmark.py --implementation multiprocessing \
        --workers 8 --scenarios 100000 --repetition 1 \
        --csv results/timings/strong_scaling.csv
"""

import argparse
import csv
import fcntl
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Columns agreed in docs/timing_schema.md, in the same order
SCHEMA_COLUMNS = [
    "timestamp_utc", "implementation", "git_commit", "dataset", "workers",
    "stations", "scenarios", "seed", "repetition", "load_s", "compute_s",
    "write_s", "elapsed_s", "node", "slurm_job_id", "node_load_1m",
]
# Extra columns after the agreed ones (useful for the overhead analysis)
EXTRA_COLUMNS = ["pool_startup_s", "cpus", "physical_cores", "kernel"]
COLUMNS = SCHEMA_COLUMNS + EXTRA_COLUMNS


# --------------------------------------------------
# 1. Information about the run
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


def cpus_and_cores():
    from src.parallel import cpus_and_cores as count
    return count()


# --------------------------------------------------
# 2. Run one execution
# --------------------------------------------------

def run_once(args, out_dir):
    common = ["--data", args.data, "--scenarios", str(args.scenarios),
              "--seed", str(args.seed), "--out", str(out_dir)]

    if args.implementation == "sequential":
        from src.simulation import main as simulate
        if args.workers != 1:
            raise SystemExit("the sequential implementation always uses 1 worker")
        start = time.perf_counter()
        summary = simulate(common)
        elapsed = time.perf_counter() - start
        timing = summary["timing_s"]
        return summary, {
            "load_s": timing["input"],
            "compute_s": timing["compute"],
            "write_s": timing["output"],
            "elapsed_s": elapsed,
            "pool_startup_s": 0.0,
            "kernel": "python",
        }

    from src.parallel import main as parallel
    start = time.perf_counter()
    summary = parallel(common + ["--workers", str(args.workers), "--kernel", args.kernel])
    elapsed = time.perf_counter() - start
    timing = summary["timing_s"]
    return summary, {
        "load_s": timing["input"],
        "compute_s": timing["compute"],
        "write_s": timing["output"],
        "elapsed_s": elapsed,
        "pool_startup_s": timing["pool_startup"],
        "kernel": args.kernel,
    }


# --------------------------------------------------
# 3. Check the row before saving it
# --------------------------------------------------

def check_row(row, args):
    problems = []
    for name in COLUMNS:
        if name not in row:
            problems.append(f"missing column {name}")
    for name in ["load_s", "compute_s", "write_s", "elapsed_s"]:
        if not row[name] >= 0:
            problems.append(f"{name} is negative or not a number: {row[name]}")
    parts = row["load_s"] + row["compute_s"] + row["write_s"]
    if row["elapsed_s"] + 0.01 < parts:
        problems.append(f"elapsed_s ({row['elapsed_s']:.3f}) is smaller than "
                        f"load + compute + write ({parts:.3f})")
    if row["workers"] != args.workers or row["scenarios"] != args.scenarios:
        problems.append("workers or scenarios in the output do not match the request")
    cores = row["physical_cores"]
    if cores != "" and args.workers > cores:
        problems.append(f"{args.workers} workers but only {cores} physical cores: "
                        f"ask Slurm for --cpus-per-task={2 * args.workers}")
    return problems


def append_row(path, row):
    # Several Slurm jobs write to the same CSV, so we lock the file while writing
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+", newline="", encoding="utf-8") as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        try:
            file.seek(0)
            header = next(csv.reader(file), [])
            if header and header != COLUMNS:
                raise SystemExit(f"{path} has different columns; use a new CSV file")
            file.seek(0, os.SEEK_END)
            writer = csv.DictWriter(file, fieldnames=COLUMNS, lineterminator="\n")
            if not header:
                writer.writeheader()
            writer.writerow(row)
        finally:
            fcntl.flock(file, fcntl.LOCK_UN)


# --------------------------------------------------
# 4. Main
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation", choices=["sequential", "multiprocessing"],
                        required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--scenarios", type=int, required=True)
    parser.add_argument("--repetition", type=int, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data", default="data/madrid_cercanias")
    parser.add_argument("--kernel", choices=["python", "numpy"], default="python")
    parser.add_argument("--csv", type=Path, default=Path("results/timings/timings.csv"))
    args = parser.parse_args()

    load_before = node_load_1m()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Scenario results are not needed for timing, so they go to a temporary folder
    with tempfile.TemporaryDirectory() as tmp:
        summary, timing = run_once(args, Path(tmp))

    cpus, cores = cpus_and_cores()
    row = {
        "timestamp_utc": timestamp,
        "implementation": args.implementation,
        "git_commit": git_commit(),
        "dataset": summary["dataset"],
        "workers": args.workers,
        "stations": summary["n_stations"],
        "scenarios": summary["n_scenarios"],
        "seed": summary["seed"],
        "repetition": args.repetition,
        "node": platform.node(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", ""),
        "node_load_1m": load_before,
        "cpus": cpus,
        "physical_cores": cores if cores is not None else "",
        **timing,
    }
    row["workers"] = summary.get("workers", 1)

    problems = check_row(row, args)
    if problems:
        print("TIMING ROW NOT SAVED:", *problems, sep="\n  ")
        raise SystemExit(1)

    for name in ["load_s", "compute_s", "write_s", "elapsed_s", "pool_startup_s"]:
        row[name] = round(row[name], 4)
    append_row(args.csv, row)
    print(f"{args.implementation} | {args.workers} workers | {args.scenarios} scenarios | "
          f"rep {args.repetition}: elapsed {row['elapsed_s']:.2f} s "
          f"(compute {row['compute_s']:.2f} s, startup {row['pool_startup_s']:.2f} s), "
          f"node load {load_before} -> {args.csv}")


if __name__ == "__main__":
    main()
