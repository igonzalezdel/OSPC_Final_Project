# AI USE AND REFERENCES
#
# The initial implementation of the scaling plot script was developed
# with assistance from Claude (Anthropic, https://claude.ai).
#
# I used Claude to understand our timing CSV format, explore how to
# calculate speedup and efficiency from repeated runs, decide how to
# mark preliminary results, and improve and correct the wording of
# the comments and documentation. I also used Claude to help with the
# structure and layout of the documentation and to clean it up.
#
# I also tested the script on a small timing CSV to understand the
# output and check that the results are calculated correctly.
#
# Prompts included requests to read docs/timing_schema.md and
# scripts/run_benchmark.py, calculate median speedup and efficiency
# with the min-max spread, and mark plots with too few repetitions
# as preliminary.
#
# References:
# https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.errorbar.html
# https://docs.python.org/3/library/statistics.html#statistics.median

"""
Plot strong-scaling speedup and efficiency from a timing CSV.

The CSV is the one written by scripts/run_benchmark.py, with the columns
described in docs/timing_schema.md. This script only reads measured rows:
it never invents or fills in missing timings.

For every worker count it takes the median of the repeated runs (and the
minimum and maximum, to show the spread), then calculates:

    speedup    S(p) = T1 / Tp
    efficiency E(p) = S(p) / p

T1 is the median time of the baseline:
    --baseline sequential       -> the sequential implementation (default)
    --baseline multiprocessing  -> multiprocessing with 1 worker
The chosen baseline is written on the plot and in the summary table.

If any configuration has fewer than --min-reps repetitions (5 by default),
or any row was not run through Slurm, the plot is marked PRELIMINARY.

Usage (from the repository root):
    python scripts/plot_scaling.py results/timings/strong_scaling.csv
    python scripts/plot_scaling.py results/timings/pilot.csv --scenarios 2000
    python scripts/plot_scaling.py results/timings/strong_scaling.csv \
        --metric compute_s --baseline multiprocessing

Outputs (in --out-dir, default results/plots/):
    strong_scaling_<metric>.png       speedup and efficiency plot
    strong_scaling_<metric>.csv       the numbers behind the plot

On the cluster, matplotlib may need its own module:
    module load matplotlib/3.8.2-gfbf-2023b
"""

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # write image files without needing a screen
import matplotlib.pyplot as plt

# Columns we need from docs/timing_schema.md
REQUIRED = ["implementation", "dataset", "workers", "scenarios", "seed",
            "repetition", "compute_s", "elapsed_s", "node", "slurm_job_id",
            "git_commit"]

# Worker counts planned in the assignment and in docs/timing_schema.md
PLANNED_WORKERS = [1, 2, 4, 8, 16, 32]


# --------------------------------------------------
# 1. Read and filter the CSV
# --------------------------------------------------

def read_rows(path):
    with open(path, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        header = reader.fieldnames or []
        missing = [name for name in REQUIRED if name not in header]
        if missing:
            sys.exit(f"{path} is missing columns: {', '.join(missing)}")
        rows = list(reader)

    for row in rows:
        row["workers"] = int(row["workers"])
        row["scenarios"] = int(row["scenarios"])
        row["seed"] = int(row["seed"])
        row["repetition"] = int(row["repetition"])
        row["compute_s"] = float(row["compute_s"])
        row["elapsed_s"] = float(row["elapsed_s"])
        # Older CSVs may not have a kernel column
        row["kernel"] = row.get("kernel") or "unknown"
    return rows


def select_rows(rows, args):
    """Keep the rows of the implementation we plot and of its baseline."""
    selected = []
    for row in rows:
        if args.scenarios is not None and row["scenarios"] != args.scenarios:
            continue
        if args.kernel is not None and row["kernel"] != args.kernel:
            continue
        is_main = row["implementation"] == args.implementation
        is_baseline = (row["implementation"] == args.baseline
                       and row["workers"] == 1)
        if is_main or is_baseline:
            selected.append(row)
    return selected


def check_comparable(rows):
    """All compared rows must share dataset, scenario count, seed and kernel."""
    problems = []
    for name in ["dataset", "scenarios", "seed", "kernel"]:
        values = sorted({str(row[name]) for row in rows})
        if len(values) > 1:
            problems.append(f"  {name}: {values}")
    if problems:
        sys.exit("The selected rows cannot be compared, they differ in:\n"
                 + "\n".join(problems)
                 + "\nUse --scenarios and/or --kernel to choose one configuration.")


# --------------------------------------------------
# 2. Statistics per worker count
# --------------------------------------------------

def summarise(times):
    return {
        "reps": len(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
    }


def scaling_table(rows, args):
    baseline_times = [row[args.metric] for row in rows
                      if row["implementation"] == args.baseline and row["workers"] == 1]
    if not baseline_times:
        sys.exit(f"No {args.baseline} rows with 1 worker: cannot calculate T1.")
    baseline = summarise(baseline_times)
    t1 = baseline["median"]

    by_workers = defaultdict(list)
    for row in rows:
        if row["implementation"] == args.implementation:
            by_workers[row["workers"]].append(row[args.metric])
    if not by_workers:
        sys.exit(f"No {args.implementation} rows found.")

    table = []
    for workers in sorted(by_workers):
        stats = summarise(by_workers[workers])
        speedup = t1 / stats["median"]
        table.append({
            "workers": workers,
            "reps": stats["reps"],
            "median_s": stats["median"],
            "min_s": stats["min"],
            "max_s": stats["max"],
            "speedup": speedup,
            # The slowest run gives the lowest speedup and the fastest the highest
            "speedup_low": t1 / stats["max"],
            "speedup_high": t1 / stats["min"],
            "efficiency": speedup / workers,
        })
    return baseline, table


# --------------------------------------------------
# 3. Warnings: is this the final figure or a pilot?
# --------------------------------------------------

def find_warnings(rows, baseline, table, args):
    warnings = []
    if baseline["reps"] < args.min_reps:
        warnings.append(f"baseline has only {baseline['reps']} repetitions "
                        f"(the assignment requires at least {args.min_reps})")
    for line in table:
        if line["reps"] < args.min_reps:
            warnings.append(f"{line['workers']} workers: only {line['reps']} "
                            f"repetitions (need {args.min_reps})")
    if any(not row["slurm_job_id"] for row in rows):
        warnings.append("some rows were not run through Slurm (empty slurm_job_id): "
                        "they are not valid for the report")
    missing = [p for p in PLANNED_WORKERS if p not in {line["workers"] for line in table}]
    if missing:
        warnings.append(f"no measurements for {missing} workers")
    if len({row["git_commit"] for row in rows}) > 1:
        warnings.append("rows come from different git commits")
    return warnings


# --------------------------------------------------
# 4. Plot and save
# --------------------------------------------------

def plot(rows, baseline, table, warnings, args):
    workers = [line["workers"] for line in table]
    speedup = [line["speedup"] for line in table]
    below = [line["speedup"] - line["speedup_low"] for line in table]
    above = [line["speedup_high"] - line["speedup"] for line in table]
    efficiency = [line["efficiency"] for line in table]

    figure, (left, right) = plt.subplots(1, 2, figsize=(12, 5))

    # Speedup against the ideal line S(p) = p
    ideal = sorted(set(workers) | {1})
    left.plot(ideal, ideal, "--", color="grey", label="Ideal (S = p)")
    left.errorbar(workers, speedup, yerr=[below, above], marker="o", capsize=4,
                  label=f"Measured median (min–max of runs)")
    left.set_xscale("log", base=2)
    left.set_yscale("log", base=2)
    left.set_xticks(ideal, [str(p) for p in ideal])
    left.set_yticks(ideal, [str(p) for p in ideal])
    left.set_xlabel("Workers (p)")
    left.set_ylabel("Speedup  T1 / Tp")
    left.set_title("Speedup")
    left.grid(True, which="both", alpha=0.3)
    left.legend()

    # Efficiency against the ideal value 1
    right.axhline(1.0, linestyle="--", color="grey", label="Ideal (E = 1)")
    right.plot(workers, efficiency, marker="o", label="Measured")
    right.set_xscale("log", base=2)
    right.set_xticks(ideal, [str(p) for p in ideal])
    right.set_ylim(0, max(1.1, max(efficiency) * 1.1))
    right.set_xlabel("Workers (p)")
    right.set_ylabel("Efficiency  S / p")
    right.set_title("Parallel efficiency")
    right.grid(True, alpha=0.3)
    right.legend()

    first = rows[0]
    baseline_name = ("sequential implementation" if args.baseline == "sequential"
                     else "multiprocessing with 1 worker")
    title = (f"Strong scaling – {args.implementation}, {first['scenarios']} scenarios, "
             f"kernel {first['kernel']}, metric {args.metric}")
    if warnings or args.preliminary:
        title = "PRELIMINARY – " + title
    figure.suptitle(title, fontweight="bold",
                    color="firebrick" if (warnings or args.preliminary) else "black")

    nodes = ", ".join(sorted({row["node"] for row in rows}))
    commits = ", ".join(sorted({row["git_commit"] for row in rows}))
    footer = (f"T1 = median of {baseline['reps']} runs of the {baseline_name} "
              f"({baseline['median']:.2f} s).  Source: {args.csv.name}.  "
              f"Nodes: {nodes}.  Commit: {commits}.")
    figure.text(0.5, 0.01, footer, ha="center", fontsize=8)
    figure.tight_layout(rect=(0, 0.04, 1, 0.95))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    image = args.out_dir / f"strong_scaling_{args.metric}.png"
    figure.savefig(image, dpi=150)
    plt.close(figure)
    return image


def save_table(baseline, table, args):
    path = args.out_dir / f"strong_scaling_{args.metric}.csv"
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["baseline", args.baseline, "baseline_reps", baseline["reps"],
                         "T1_median_s", round(baseline["median"], 4)])
        writer.writerow(["workers", "reps", "median_s", "min_s", "max_s",
                         "speedup", "speedup_low", "speedup_high", "efficiency"])
        for line in table:
            writer.writerow([line["workers"], line["reps"]]
                            + [round(line[name], 4) for name in
                               ["median_s", "min_s", "max_s", "speedup",
                                "speedup_low", "speedup_high", "efficiency"]])
    return path


# --------------------------------------------------
# 5. Main
# --------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", type=Path, help="timing CSV from scripts/run_benchmark.py")
    parser.add_argument("--metric", choices=["elapsed_s", "compute_s"], default="elapsed_s",
                        help="time column to use (default: elapsed_s)")
    parser.add_argument("--implementation", default="multiprocessing",
                        help="implementation whose scaling we plot (default: multiprocessing)")
    parser.add_argument("--baseline", choices=["sequential", "multiprocessing"],
                        default="sequential", help="what T1 is (default: sequential)")
    parser.add_argument("--scenarios", type=int, help="only use rows with this scenario count")
    parser.add_argument("--kernel", help="only use rows with this kernel (python or numpy)")
    parser.add_argument("--min-reps", type=int, default=5,
                        help="repetitions required for a final figure (default: 5)")
    parser.add_argument("--preliminary", action="store_true",
                        help="always mark the plot as preliminary")
    parser.add_argument("--out-dir", type=Path, default=Path("results/plots"))
    args = parser.parse_args(argv)

    rows = select_rows(read_rows(args.csv), args)
    if not rows:
        sys.exit("No rows match the selected options.")
    check_comparable(rows)

    baseline, table = scaling_table(rows, args)
    warnings = find_warnings(rows, baseline, table, args)
    image = plot(rows, baseline, table, warnings, args)
    numbers = save_table(baseline, table, args)

    print(f"T1 = {baseline['median']:.3f} s (median of {baseline['reps']} "
          f"{args.baseline} runs, metric {args.metric})\n")
    print(f"{'workers':>7} {'reps':>4} {'median s':>9} {'min s':>8} {'max s':>8} "
          f"{'speedup':>8} {'efficiency':>10}")
    for line in table:
        print(f"{line['workers']:7d} {line['reps']:4d} {line['median_s']:9.3f} "
              f"{line['min_s']:8.3f} {line['max_s']:8.3f} {line['speedup']:8.2f} "
              f"{line['efficiency']:10.2f}")
    for message in warnings:
        print("WARNING:", message)
    if warnings:
        print("\nThe plot is marked PRELIMINARY.")
    print(f"\nSaved {image} and {numbers}")


if __name__ == "__main__":
    main()
