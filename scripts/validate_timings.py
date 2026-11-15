"""
Check a timing CSV written by scripts/run_benchmark.py and print a summary
(median, min, max and spread per configuration).

Usage:
    python scripts/validate_timings.py results/timings/strong_scaling.csv --min-reps 5
"""

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_benchmark import COLUMNS, SCHEMA_COLUMNS  # noqa: E402

NUMBERS = ["workers", "stations", "scenarios", "seed", "repetition",
           "load_s", "compute_s", "write_s", "elapsed_s"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--min-reps", type=int, default=5)
    args = parser.parse_args()

    with open(args.csv, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        header = reader.fieldnames or []
        rows = list(reader)

    errors, warnings = [], []
    if header[:len(SCHEMA_COLUMNS)] != SCHEMA_COLUMNS:
        errors.append("columns do not match docs/timing_schema.md")
    if header != COLUMNS:
        warnings.append("extra columns differ from scripts/run_benchmark.py")

    groups = defaultdict(list)
    for line, row in enumerate(rows, start=2):
        for name in SCHEMA_COLUMNS:
            if row.get(name, "") == "":
                errors.append(f"line {line}: empty {name}")
        try:
            for name in NUMBERS:
                row[name] = float(row[name])
        except ValueError as problem:
            errors.append(f"line {line}: not a number ({problem})")
            continue
        if row["elapsed_s"] + 0.01 < row["load_s"] + row["compute_s"] + row["write_s"]:
            errors.append(f"line {line}: elapsed_s smaller than load + compute + write")
        key = (row["implementation"], row["kernel"], int(row["scenarios"]), int(row["workers"]))
        groups[key].append(row)

    for key, group in groups.items():
        reps = sorted(int(r["repetition"]) for r in group)
        if len(set(reps)) != len(reps):
            errors.append(f"{key}: repeated repetition numbers {reps}")
        if len(reps) < args.min_reps:
            warnings.append(f"{key}: only {len(reps)} repetitions (want {args.min_reps})")
        if len({r["git_commit"] for r in group}) > 1:
            warnings.append(f"{key}: runs come from different git commits")
        if len({int(r["seed"]) for r in group}) > 1:
            errors.append(f"{key}: different seeds in the same configuration")

    print(f"{args.csv}: {len(rows)} rows, {len(groups)} configurations\n")
    print(f"{'implementation':16} {'kernel':7} {'scenarios':>9} {'workers':>7} {'reps':>4} "
          f"{'median s':>9} {'min s':>8} {'max s':>8} {'spread':>7} {'load 1m':>8}")
    for key in sorted(groups):
        times = [r["elapsed_s"] for r in groups[key]]
        loads = [float(r["node_load_1m"]) for r in groups[key] if r["node_load_1m"]]
        median = statistics.median(times)
        spread = (max(times) - min(times)) / median * 100
        load = statistics.median(loads) if loads else float("nan")
        print(f"{key[0]:16} {key[1]:7} {key[2]:9d} {key[3]:7d} {len(times):4d} "
              f"{median:9.2f} {min(times):8.2f} {max(times):8.2f} {spread:6.1f}% {load:8.1f}")

    for message in warnings:
        print("WARNING:", message)
    for message in errors:
        print("ERROR:", message)
    if errors:
        raise SystemExit(1)
    print("\nOK: timing CSV is valid")


if __name__ == "__main__":
    main()
