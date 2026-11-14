# AI USE AND REFERENCES
#
# This script was developed with assistance from Claude (Anthropic).
# AI assistance was used to structure the comparison, choose the tolerance
# and write the exit codes. It was run on the cluster before the scaling runs.

"""Check that the parallel driver gives the same results as the sequential run.

Runs src/simulation.py once and src/parallel.py once per worker count, all
with the same seed and scenarios, and compares every scenario:

  - n_disruptions, n_blocked, disconnected_pairs, lost_trips (integers):
    must be exactly equal.
  - extra_delay_min (float): must agree within rel 1e-9 / abs 1e-6
    passenger-minutes. Each scenario is computed by the same code, with the
    same operations in the same order, whatever the number of workers, so the
    values should be bit-identical. The small tolerance only allows for a
    different floating-point summation order (for example --kernel numpy);
    1e-6 passenger-minutes is far below anything that matters (a typical
    scenario has ~10^5 to 10^6 passenger-minutes of delay).

Exit code 0 if every comparison passes, 1 otherwise, so a Slurm job or CI
fails visibly on any disagreement.

Usage (from the repository root):

    python scripts/check_equivalence.py --scenarios 500 --workers 1 2 4 8 16 32
"""

import argparse
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.parallel import main as parallel_main  # noqa: E402
from src.simulation import main as sequential_main  # noqa: E402

INTEGER_COLUMNS = ["scenario", "n_disruptions", "n_blocked", "disconnected_pairs", "lost_trips"]
FLOAT_COLUMNS = ["extra_delay_min"]
RTOL, ATOL = 1e-9, 1e-6


def compare(expected, actual):
    """Return a list of problems (empty list = equal)."""
    problems = []
    if len(expected) != len(actual):
        return [f"{len(actual)} scenarios instead of {len(expected)}"]
    for column in INTEGER_COLUMNS:
        wrong = (expected[column].to_numpy() != actual[column].to_numpy())
        if wrong.any():
            first = int(np.argmax(wrong))
            problems.append(f"{column}: {int(wrong.sum())} scenarios differ "
                            f"(first: scenario {first}, {expected[column].iloc[first]} "
                            f"vs {actual[column].iloc[first]})")
    for column in FLOAT_COLUMNS:
        a, b = expected[column].to_numpy(), actual[column].to_numpy()
        wrong = ~np.isclose(a, b, rtol=RTOL, atol=ATOL)
        if wrong.any():
            problems.append(f"{column}: {int(wrong.sum())} scenarios differ "
                            f"(max abs diff {np.abs(a - b).max():.3g})")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", default="data/madrid_cercanias")
    parser.add_argument("--scenarios", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32])
    parser.add_argument("--kernel", choices=["python", "numpy"], default="python")
    parser.add_argument("--out", default=None, help="keep outputs here (default: temporary folder)")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(args.out or tmp)
        common = ["--data", args.data, "--scenarios", str(args.scenarios), "--seed", str(args.seed)]

        t0 = time.perf_counter()
        sequential_main(common + ["--out", str(root / "sequential")])
        expected = pd.read_csv(root / "sequential" / "scenarios.csv")
        print(f"sequential: {time.perf_counter() - t0:.1f} s")

        failed = False
        for workers in args.workers:
            folder = root / f"parallel_w{workers}"
            parallel_main(common + ["--workers", str(workers), "--kernel", args.kernel,
                                    "--out", str(folder)])
            actual = pd.read_csv(folder / "scenarios.csv")
            problems = compare(expected, actual)
            identical = (expected.equals(actual))
            if problems:
                failed = True
                print(f"FAIL  workers={workers}")
                for p in problems:
                    print(f"      {p}")
            else:
                note = "bit-identical" if identical else f"within rtol={RTOL}, atol={ATOL}"
                print(f"PASS  workers={workers}  ({args.scenarios} scenarios, {note})")

    print("RESULT:", "FAIL" if failed else "all worker counts match the sequential run")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
