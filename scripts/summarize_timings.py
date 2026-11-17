# AI USE AND REFERENCES
#
# This script was developed with assistance from Claude (Anthropic) to turn the
# timing CSVs (docs/timing_schema.md) into a comparison table: median time per
# configuration, speedup and parallel efficiency against the sequential run.

"""Compare sequential, multiprocessing and MPI timings.

Reads one or more timing CSVs (the 16 agreed columns of docs/timing_schema.md;
the MPI file has extra columns, which are ignored here except comm_s) and prints a
Markdown table with, for every (implementation, workers):

  runs        number of repetitions
  compute_s   median compute time
  elapsed_s   median total time of the run
  speedup     sequential elapsed_s / elapsed_s     (sequential = 1 worker, python kernel)
  efficiency  speedup / workers
  comm_s      median MPI communication time (broadcast + gather), MPI rows only

Usage:
    python scripts/summarize_timings.py results/timings/strong_scaling.csv results/timings/mpi_scaling.csv
"""

import argparse
import sys

import pandas as pd


def summarize(frames, scenarios=None):
    data = pd.concat(frames, ignore_index=True)
    if scenarios is not None:
        data = data[data["scenarios"] == scenarios]
    if data.empty:
        raise SystemExit("no rows to summarize")
    if "comm_s" not in data:
        data["comm_s"] = float("nan")
    grouped = data.groupby(["implementation", "workers"]).agg(
        runs=("elapsed_s", "size"),
        compute_s=("compute_s", "median"),
        elapsed_s=("elapsed_s", "median"),
        comm_s=("comm_s", "median"),
    ).reset_index()
    sequential = grouped[grouped["implementation"] == "sequential"]
    if not sequential.empty:
        base = float(sequential["elapsed_s"].iloc[0])
        grouped["speedup"] = base / grouped["elapsed_s"]
        grouped["efficiency"] = grouped["speedup"] / grouped["workers"]
    order = {"sequential": 0, "multiprocessing": 1, "mpi": 2}
    grouped["order"] = grouped["implementation"].map(order).fillna(9)
    return grouped.sort_values(["order", "workers"]).drop(columns="order")


def to_markdown(table):
    columns = list(table.columns)
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for _, row in table.iterrows():
        cells = []
        for name in columns:
            value = row[name]
            if isinstance(value, float):
                cells.append("" if pd.isna(value) else f"{value:.3f}" if abs(value) < 10 else f"{value:.1f}")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("csv", nargs="+", help="timing CSV files")
    parser.add_argument("--scenarios", type=int, default=None,
                        help="only rows with this problem size (default: all)")
    args = parser.parse_args(argv)
    frames = [pd.read_csv(path) for path in args.csv]
    table = summarize(frames, args.scenarios)
    print(to_markdown(table))
    return 0


if __name__ == "__main__":
    sys.exit(main())
