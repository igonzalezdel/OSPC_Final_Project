# AI USE AND REFERENCES
#
# ChatGPT (OpenAI) assisted with the design and documentation
# of this serial-fraction estimation script, including the
# interpretation of Amdahl's law and the profile-based estimate.
# The calculations and implementation were reviewed and tested
# against the project's benchmark data.


#!/usr/bin/env python3
"""
Estimate the serial fraction using:
1. Measured speedups and Amdahl's law.
2. A profile-based non-compute time proportion.

Input:
    docs/timings/strong_scaling_haskell.csv

The measured effective fraction is not necessarily the algorithm's
true theoretical serial fraction. It can also reflect system overhead.
"""

import csv
import statistics
from pathlib import Path


# ============================================================
# 1. FILE AND PROFILE INPUTS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
TIMING_FILE = ROOT / "docs" / "timings" / "strong_scaling_haskell.csv"

# Values taken from docs/profiling/profiling.md.
PROFILE_LOAD_S = 0.002
PROFILE_SCENARIO_GENERATION_S = 3.13
PROFILE_WRITE_S = 0.15
PROFILE_TOTAL_WALL_S = 603.7


# ============================================================
# 2. LOAD TIMING DATA
# ============================================================

with TIMING_FILE.open("r", newline="") as file:
    rows = list(csv.DictReader(file))

if not rows:
    raise ValueError("The timing CSV contains no data.")

# Check that the CSV contains the expected configurations.
expected_workers = {1, 2, 4, 8, 16, 32}
available_workers = {
    int(row["workers"])
    for row in rows
    if row["implementation"] == "multiprocessing"
}

if not expected_workers.issubset(available_workers):
    raise ValueError("One or more expected worker configurations are missing.")


# ============================================================
# 3. CALCULATE MEDIAN TIMINGS
# ============================================================

def median_for(implementation, workers, column):
    """Return the median timing for one configuration."""
    values = [
        float(row[column])
        for row in rows
        if row["implementation"] == implementation
        and int(row["workers"]) == workers
    ]

    if not values:
        raise ValueError(
            f"No data for {implementation}, {workers} workers."
        )

    return statistics.median(values)


baseline = median_for("multiprocessing", 1, "elapsed_s")

print("\nMEDIAN TIMINGS")
print("-" * 78)
print(
    f"{'Workers':>8} {'Load (s)':>12} {'Compute (s)':>14} "
    f"{'Write (s)':>12} {'Startup (s)':>13} {'Elapsed (s)':>13}"
)

for workers in sorted(expected_workers):
    load = median_for("multiprocessing", workers, "load_s")
    compute = median_for("multiprocessing", workers, "compute_s")
    write = median_for("multiprocessing", workers, "write_s")
    startup = median_for("multiprocessing", workers, "pool_startup_s")
    elapsed = median_for("multiprocessing", workers, "elapsed_s")

    print(
        f"{workers:>8} {load:>12.4f} {compute:>14.4f} "
        f"{write:>12.4f} {startup:>13.4f} {elapsed:>13.4f}"
    )


# ============================================================
# 4. EFFECTIVE SERIAL FRACTION: AMDAHL'S LAW
# ============================================================

print("\nEFFECTIVE SERIAL FRACTION")
print("-" * 78)
print(f"Baseline: one-worker multiprocessing, median = {baseline:.4f} s")
print(
    f"{'Workers':>8} {'Elapsed (s)':>13} {'Speedup':>12} "
    f"{'Efficiency':>13} {'f_eff':>12}"
)

for workers in (8, 16, 32):
    elapsed = median_for("multiprocessing", workers, "elapsed_s")

    # Speedup relative to the one-worker multiprocessing baseline.
    speedup = baseline / elapsed

    # Parallel efficiency = speedup divided by worker count.
    efficiency = speedup / workers

    # Amdahl's law rearranged to estimate the effective serial fraction.
    f_eff = (workers / speedup - 1) / (workers - 1)

    print(
        f"{workers:>8} {elapsed:>13.4f} {speedup:>11.3f}x "
        f"{efficiency * 100:>12.2f}% {f_eff * 100:>11.3f}%"
    )


# ============================================================
# 5. PROFILE-BASED NON-COMPUTE PROPORTION
# ============================================================

profile_non_compute = (
    PROFILE_LOAD_S
    + PROFILE_SCENARIO_GENERATION_S
    + PROFILE_WRITE_S
)

profile_fraction = profile_non_compute / PROFILE_TOTAL_WALL_S

print("\nPROFILE-BASED ESTIMATE")
print("-" * 78)
print(f"Load time:                 {PROFILE_LOAD_S:.3f} s")
print(f"Scenario generation time:  {PROFILE_SCENARIO_GENERATION_S:.3f} s")
print(f"Write time:                {PROFILE_WRITE_S:.3f} s")
print(f"Non-compute total:         {profile_non_compute:.3f} s")
print(f"Sequential wall time:      {PROFILE_TOTAL_WALL_S:.3f} s")
print(
    f"Profile-based proportion: {profile_fraction * 100:.4f}%"
)

print("\nNote: The profile-based proportion is a proxy, not an exact")
print("theoretical serial fraction. The effective Amdahl estimates")
print("also include implementation and system effects.")

