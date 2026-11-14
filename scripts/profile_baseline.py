
"""
Profile the sequential baseline and choose the experiment size.

For a few problem sizes (number of scenarios) it runs the one-worker
simulation in a fresh process and records:
  - input, compute and output time (from src/simulation.py)
  - scenario generation vs Floyd-Warshall + metrics time
  - CPU time / wall time (close to 1.0 means CPU-bound)
  - peak memory (RSS)
Then it runs cProfile once to see which functions take the time, fits
time = a + b * scenarios, and gives the number of scenarios needed for
the target runtime (default 10 minutes).

Usage (from the repository root, on the cluster inside a Slurm job):
    python scripts/profile_baseline.py --sizes 1000 4000 16000 --out results/profiling
"""

import argparse
import cProfile
import io
import json
import os
import platform
import pstats
import resource
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# --------------------------------------------------
# 1. One measured run (always in its own process)
# --------------------------------------------------

def single_run(scenarios, seed):
    from src.simulation import main as simulate

    with tempfile.TemporaryDirectory() as tmp:
        wall0, cpu0 = time.perf_counter(), time.process_time()
        summary = simulate(["--scenarios", str(scenarios), "--seed", str(seed), "--out", tmp])
        wall, cpu = time.perf_counter() - wall0, time.process_time() - cpu0

    # ru_maxrss is in KB on Linux
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    timing = summary["timing_s"]
    return {
        "scenarios": scenarios,
        "wall_s": wall,
        "cpu_s": cpu,
        "cpu_over_wall": cpu / wall,
        "peak_memory_mb": peak_mb,
        "input_s": timing["input"],
        "scenario_generation_s": timing["compute_scenario_generation"],
        "floyd_warshall_and_metrics_s": timing["compute_shortest_paths_and_metrics"],
        "output_s": timing["output"],
        "ms_per_scenario": 1000 * timing["compute_shortest_paths_and_metrics"] / scenarios,
    }


def run_in_new_process(scenarios, seed):
    # A new process per size so the peak memory of one size does not
    # carry over to the next one.
    cmd = [sys.executable, __file__, "--single", str(scenarios), "--seed", str(seed)]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=ROOT)
    return json.loads(out.stdout.strip().splitlines()[-1])


# --------------------------------------------------
# 2. Which functions take the time (cProfile)
# --------------------------------------------------

def profile_functions(scenarios, seed, top=15):
    from src.simulation import main as simulate

    profiler = cProfile.Profile()
    with tempfile.TemporaryDirectory() as tmp:
        profiler.enable()
        simulate(["--scenarios", str(scenarios), "--seed", str(seed), "--out", tmp])
        profiler.disable()

    text = io.StringIO()
    stats = pstats.Stats(profiler, stream=text).sort_stats("cumulative")
    stats.print_stats(top)
    return text.getvalue()


# --------------------------------------------------
# 3. Machine information
# --------------------------------------------------

def machine_info():
    cpu_model = ""
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    except OSError:
        cpu_model = platform.processor()
    return {
        "hostname": socket.gethostname(),
        "cpu_model": cpu_model,
        "cpus_on_node": os.cpu_count(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_cpus_per_task": os.environ.get("SLURM_CPUS_PER_TASK"),
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "python": platform.python_version(),
        "numpy": np.__version__,
    }


# --------------------------------------------------
# 4. Main
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 4000, 16000],
                        help="numbers of scenarios to measure")
    parser.add_argument("--profile-size", type=int, default=2000,
                        help="number of scenarios for the cProfile run")
    parser.add_argument("--target-minutes", type=float, default=10,
                        help="runtime the chosen problem size should reach on one worker")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("results/profiling"))
    parser.add_argument("--single", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.single:
        print(json.dumps(single_run(args.single, args.seed)))
        return

    args.out.mkdir(parents=True, exist_ok=True)

    runs = []
    for size in sorted(args.sizes):
        print(f"measuring {size} scenarios ...", flush=True)
        runs.append(run_in_new_process(size, args.seed))
        r = runs[-1]
        print(f"  wall {r['wall_s']:.1f} s, cpu/wall {r['cpu_over_wall']:.2f}, "
              f"peak {r['peak_memory_mb']:.0f} MB, {r['ms_per_scenario']:.2f} ms/scenario", flush=True)

    print(f"cProfile on {args.profile_size} scenarios ...", flush=True)
    top_functions = profile_functions(args.profile_size, args.seed)
    (args.out / "cprofile_top.txt").write_text(top_functions)

    # Fit time and memory as straight lines in the number of scenarios
    sizes = np.array([r["scenarios"] for r in runs], dtype=float)
    walls = np.array([r["wall_s"] for r in runs])
    mems = np.array([r["peak_memory_mb"] for r in runs])
    time_slope, time_fixed = np.polyfit(sizes, walls, 1)
    mem_slope, mem_fixed = np.polyfit(sizes, mems, 1)

    target_s = args.target_minutes * 60
    needed = int(np.ceil((target_s - time_fixed) / time_slope / 1000) * 1000)

    largest = runs[-1]
    serial_s = largest["input_s"] + largest["scenario_generation_s"] + largest["output_s"]
    result = {
        "machine": machine_info(),
        "dataset": "data/madrid_cercanias (60 stations)",
        "seed": args.seed,
        "runs": runs,
        "fit": {
            "seconds_per_scenario": time_slope,
            "fixed_seconds": time_fixed,
            "memory_mb_per_scenario": mem_slope,
            "fixed_memory_mb": mem_fixed,
        },
        "recommendation": {
            "target_minutes": args.target_minutes,
            "scenarios_needed": needed,
            "predicted_wall_minutes": (time_fixed + time_slope * needed) / 60,
            "predicted_peak_memory_gb": (mem_fixed + mem_slope * needed) / 1024,
        },
        "serial_share_largest_run": serial_s / largest["wall_s"],
    }
    (args.out / "profile.json").write_text(json.dumps(result, indent=2))

    rec = result["recommendation"]
    print()
    print(f"time per scenario: {1000 * time_slope:.2f} ms, fixed cost {time_fixed:.2f} s")
    print(f"memory per scenario: {1024 * mem_slope:.1f} KB")
    print(f"for {args.target_minutes:g} min on one worker: {needed} scenarios "
          f"(predicted {rec['predicted_wall_minutes']:.1f} min, "
          f"{rec['predicted_peak_memory_gb']:.2f} GB peak memory)")
    print(f"serial share (input + generation + output) at {largest['scenarios']} scenarios: "
          f"{100 * result['serial_share_largest_run']:.2f}%")
    print(f"results in {args.out}/profile.json and {args.out}/cprofile_top.txt")


if __name__ == "__main__":
    main()
