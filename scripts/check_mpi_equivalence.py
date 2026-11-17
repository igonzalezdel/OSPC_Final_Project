# AI USE AND REFERENCES
#
# This script was developed with assistance from Claude (Anthropic). It reuses
# the comparison rules of scripts/check_equivalence.py (Antoni Gendra) and
# starts the MPI program with srun or mpirun for each number of ranks.

"""Check that the MPI version gives the same results as the sequential run.

Runs src/simulation.py once and src/mpi_simulation.py once per number of ranks,
all with the same seed and scenarios, and compares every scenario with the
rules of scripts/check_equivalence.py (counts exactly equal, extra_delay_min
within rel 1e-9 / abs 1e-6). Exit code 0 if everything matches, 1 otherwise.

Usage, from the repository root:

    # inside a Slurm job with enough tasks (see slurm/check_mpi_equivalence.sh)
    python scripts/check_mpi_equivalence.py --scenarios 500 --ranks 1 2 4 8 16 --launcher srun

    # on a laptop with an MPI installation
    python scripts/check_mpi_equivalence.py --scenarios 200 --ranks 1 2 4 --launcher mpirun
"""

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from check_equivalence import RTOL, ATOL, compare  # noqa: E402
from src.simulation import main as sequential_main  # noqa: E402


def launch_command(launcher, ranks):
    if launcher == "srun":
        return ["srun", "-n", str(ranks)]
    return [launcher, "-n", str(ranks)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", default="data/madrid_cercanias")
    parser.add_argument("--scenarios", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ranks", type=int, nargs="+", default=[1, 2, 4, 8, 16])
    parser.add_argument("--kernel", choices=["python", "numpy"], default="python")
    parser.add_argument("--launcher", choices=["srun", "mpirun", "mpiexec"], default="srun")
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
        for ranks in args.ranks:
            folder = root / f"mpi_r{ranks}"
            command = launch_command(args.launcher, ranks) + [
                sys.executable, "-m", "src.mpi_simulation"] + common + [
                "--kernel", args.kernel, "--out", str(folder)]
            done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            if done.returncode != 0:
                failed = True
                print(f"FAIL  ranks={ranks}: the MPI run exited with code {done.returncode}")
                print(done.stderr[-1500:])
                continue
            summary_ranks = pd.read_json(folder / "summary.json", typ="series")["ranks"]
            actual = pd.read_csv(folder / "scenarios.csv")
            problems = compare(expected, actual)
            if summary_ranks != ranks:
                problems.append(f"summary.json says {summary_ranks} ranks, expected {ranks}")
            if problems:
                failed = True
                print(f"FAIL  ranks={ranks}")
                for p in problems:
                    print(f"      {p}")
            else:
                note = "bit-identical" if expected.equals(actual) else f"within rtol={RTOL}, atol={ATOL}"
                print(f"PASS  ranks={ranks}  ({args.scenarios} scenarios, {note})")

    print("RESULT:", "FAIL" if failed else "all rank counts match the sequential run")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
