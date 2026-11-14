# AI USE AND REFERENCES
#
# This module was developed with assistance from Claude (Anthropic).
# AI assistance was used to design the metric calculation, the command-line
# interface, the timing and the output files. The code follows the agreed
# interface in docs/interface.md and reuses the shared modules
# (railway_data.py, scenarios.py, sequential.py). It was reviewed and tested
# by the author.

"""Sequential Monte Carlo simulation of railway disruptions (one worker).

For the undisrupted network and for each disruption scenario, the shortest
travel times between all stations are computed with floyd_warshall().
Each scenario is then compared with the normal network and three impact
metrics are reported (definitions in docs/interface.md, Section 6):

  disconnected_pairs  station pairs i < j that had a route and now have none
  lost_trips          daily trips (both directions) on pairs that lost their route
  extra_delay_min     passenger-minutes per day of extra travel time on pairs
                      that are still connected

Usage (from the repository root):

    python -m src.simulation --data data/madrid_cercanias --scenarios 100 \
        --seed 42 --out results/sequential_100

The scenarios depend only on (seed, scenario number), so the same input always
gives the same output.
"""

import argparse
import csv
import json
import platform
import time
from datetime import date
from pathlib import Path

import numpy as np

from src.railway_data import load_railway_data
from src.scenarios import generate_disruption_scenarios
from src.sequential import floyd_warshall

METRICS = ["disconnected_pairs", "lost_trips", "extra_delay_min"]

UNITS = {
    "travel_time": "minutes",
    "disconnected_pairs": "station pairs (each pair counted once)",
    "lost_trips": "passenger trips per day",
    "extra_delay_min": "passenger-minutes per day",
}


# --------------------------------------------------
# 1. Shortest travel times for one network
# --------------------------------------------------

def shortest_times(network):
    """Run the sequential Floyd-Warshall on a NumPy matrix (see interface.md, Sec. 5)."""
    distances, _ = floyd_warshall(network.tolist())
    return np.array(distances, dtype=float)


# --------------------------------------------------
# 2. Impact metrics of one scenario
# --------------------------------------------------

def scenario_metrics(baseline, disrupted, demand):
    """Compare two shortest-time matrices and return the three agreed metrics.

    inf means "unreachable". Only pairs i != j are considered.
    """
    n = baseline.shape[0]
    off_diagonal = ~np.eye(n, dtype=bool)

    reachable_before = np.isfinite(baseline) & off_diagonal
    reachable_after = np.isfinite(disrupted) & off_diagonal

    # Pairs that had a route and lost it.
    lost = reachable_before & ~reachable_after

    # Pairs connected both before and after.
    still_connected = reachable_before & reachable_after

    # Each unordered pair once (upper triangle) because the network is undirected.
    disconnected_pairs = int(np.triu(lost, k=1).sum())

    # Trips and delays count both directions of travel.
    lost_trips = int(demand[lost].sum())

    extra_time = np.where(still_connected, disrupted - baseline, 0.0)
    extra_delay_min = float((demand * extra_time).sum())

    return {
        "disconnected_pairs": disconnected_pairs,
        "lost_trips": lost_trips,
        "extra_delay_min": extra_delay_min,
    }


# --------------------------------------------------
# 3. Run a whole batch of scenarios
# --------------------------------------------------

def run_batch(network, demand, scenarios):
    """Return (baseline times, list of metric dicts, one per scenario)."""
    baseline = shortest_times(network)  # undisrupted network, computed once
    results = []
    for number, scenario in enumerate(scenarios):
        disrupted = shortest_times(scenario)
        metrics = scenario_metrics(baseline, disrupted, demand)
        results.append({"scenario": number, **metrics})
    return baseline, results


def aggregate(results):
    summary = {}
    for name in METRICS:
        values = np.array([r[name] for r in results], dtype=float)
        summary[name] = {
            "mean": float(values.mean()),
            "median": float(np.median(values)),
            "max": float(values.max()),
            "total": float(values.sum()),
        }
    return summary


# --------------------------------------------------
# 4. Output files
# --------------------------------------------------

def write_scenario_csv(path, results, records):
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["scenario", "n_disruptions", "n_blocked"] + METRICS)
        for result, record in zip(results, records):
            disruptions = record["disruptions"]
            blocked = sum(1 for d in disruptions if d["type"] == "blocked")
            writer.writerow(
                [result["scenario"], len(disruptions), blocked]
                + [result[name] for name in METRICS]
            )


# --------------------------------------------------
# 5. Command line
# --------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Sequential Monte Carlo railway disruption simulation."
    )
    parser.add_argument("--data", default="data/madrid_cercanias",
                        help="dataset folder (stations.csv, network.csv, demand.csv, metadata.json)")
    parser.add_argument("--scenarios", type=int, default=20,
                        help="number of disruption scenarios (problem size)")
    parser.add_argument("--seed", type=int, default=42, help="base random seed")
    parser.add_argument("--min-disruptions", type=int, default=1)
    parser.add_argument("--max-disruptions", type=int, default=3)
    parser.add_argument("--block-probability", type=float, default=0.5)
    parser.add_argument("--min-delay", type=int, default=5)
    parser.add_argument("--max-delay", type=int, default=30)
    parser.add_argument("--out", default="results/sequential_run",
                        help="output folder (summary.json and scenarios.csv)")
    args = parser.parse_args(argv)

    # ---- input (loading data) ----
    t0 = time.perf_counter()
    data = load_railway_data(args.data)
    network, demand = data["network"], data["demand"]
    input_s = time.perf_counter() - t0

    # ---- compute: scenario generation, then all shortest paths and metrics ----
    t0 = time.perf_counter()
    scenarios, records = generate_disruption_scenarios(
        network,
        num_scenarios=args.scenarios,
        seed=args.seed,
        min_disruptions=args.min_disruptions,
        max_disruptions=args.max_disruptions,
        block_probability=args.block_probability,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
    )
    generation_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    _, results = run_batch(network, demand, scenarios)
    shortest_path_s = time.perf_counter() - t0

    # ---- output (writing files) ----
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    write_scenario_csv(out_dir / "scenarios.csv", results, records)
    output_s = time.perf_counter() - t0

    summary = {
        "version": "sequential",
        "workers": 1,
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
        "aggregate": aggregate(results),
        "timing_s": {
            "input": input_s,
            "compute": generation_s + shortest_path_s,
            "compute_scenario_generation": generation_s,
            "compute_shortest_paths_and_metrics": shortest_path_s,
            "output": output_s,
        },
        "python": platform.python_version(),
        "numpy": np.__version__,
        "date": date.today().isoformat(),
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print(f"{args.scenarios} scenarios, {network.shape[0]} stations: "
          f"input {input_s:.3f} s, compute {generation_s + shortest_path_s:.3f} s, "
          f"output {output_s:.3f} s -> {out_dir}/")
    return summary


if __name__ == "__main__":
    main()
