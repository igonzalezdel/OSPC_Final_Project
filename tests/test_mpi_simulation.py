# AI USE AND REFERENCES
#
# Tests written with assistance from Claude (Anthropic) and checked by
# running them. The algorithm (split, compute, gather) is tested with a
# thread-based stand-in for the MPI communicator, so these tests need no MPI
# installation. One extra test starts real MPI processes and is skipped when
# mpi4py or a working mpirun is not available (it runs on the cluster).

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import numpy as np

from src.mpi_simulation import (block_bounds, build_parser, rows_from_array,
                                run_simulation, SCHEMA_COLUMNS, EXTRA_COLUMNS,
                                append_timing_row, timing_row)
from src.simulation import main as sequential_main

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "madrid_cercanias"


class ThreadWorld:
    """Shared state for N fake ranks that run as threads."""

    def __init__(self, size):
        self.size = size
        self.barrier = threading.Barrier(size)
        self.slots = [None] * size
        self.box = None


class ThreadComm:
    """Just the calls src/mpi_simulation.py uses: Get_rank, Get_size, Barrier, bcast, gather."""

    def __init__(self, world, rank):
        self.world, self.rank = world, rank

    def Get_rank(self):
        return self.rank

    def Get_size(self):
        return self.world.size

    def Barrier(self):
        self.world.barrier.wait()

    def bcast(self, obj, root=0):
        if self.rank == root:
            self.world.box = obj
        self.world.barrier.wait()
        value = self.world.box
        self.world.barrier.wait()
        return value

    def gather(self, obj, root=0):
        self.world.slots[self.rank] = obj
        self.world.barrier.wait()
        result = list(self.world.slots) if self.rank == root else None
        self.world.barrier.wait()
        return result


def run_fake_mpi(size, argv):
    """Run run_simulation on `size` fake ranks; return the summary of rank 0."""
    args = build_parser().parse_args(argv)
    world = ThreadWorld(size)
    results, errors = [None] * size, []

    def target(rank):
        try:
            results[rank] = run_simulation(ThreadComm(world, rank), args)
        except BaseException as error:  # noqa: BLE001 - reported below
            errors.append(error)
            world.barrier.abort()

    threads = [threading.Thread(target=target, args=(r,)) for r in range(size)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise errors[0]
    assert all(r is None for r in results[1:])
    return results[0]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.reader(file))


class TestBlockBounds(unittest.TestCase):

    def test_blocks_cover_every_scenario_once(self):
        for n in (1, 5, 7, 100, 101):
            for size in (1, 2, 3, 4, 8, 32):
                numbers = []
                for rank in range(size):
                    start, stop = block_bounds(n, size, rank)
                    numbers.extend(range(start, stop))
                self.assertEqual(numbers, list(range(n)), (n, size))

    def test_blocks_differ_by_at_most_one(self):
        for n, size in [(100000, 32), (101, 8), (7, 4), (3, 8)]:
            lengths = [b - a for a, b in (block_bounds(n, size, r) for r in range(size))]
            self.assertLessEqual(max(lengths) - min(lengths), 1)

    def test_known_split(self):
        self.assertEqual([block_bounds(10, 4, r) for r in range(4)],
                         [(0, 3), (3, 6), (6, 8), (8, 10)])

    def test_more_ranks_than_scenarios(self):
        self.assertEqual([block_bounds(2, 4, r) for r in range(4)],
                         [(0, 1), (1, 2), (2, 2), (2, 2)])


class TestRowsFromArray(unittest.TestCase):

    def test_types_and_values(self):
        array = np.array([[3, 2, 1, 7, 1234, 98765.5]])
        row = rows_from_array(array)[0]
        self.assertEqual(row, {"scenario": 3, "n_disruptions": 2, "n_blocked": 1,
                               "disconnected_pairs": 7, "lost_trips": 1234,
                               "extra_delay_min": 98765.5})
        self.assertIsInstance(row["lost_trips"], int)
        self.assertIsInstance(row["extra_delay_min"], float)


@unittest.skipUnless(DATA.exists(), "Madrid dataset not available")
class TestSameAsSequential(unittest.TestCase):

    def test_ranks_give_identical_files(self):
        n = 40
        with tempfile.TemporaryDirectory() as tmp:
            seq_dir = Path(tmp) / "seq"
            sequential_main(["--scenarios", str(n), "--seed", "7", "--out", str(seq_dir)])
            expected = (seq_dir / "scenarios.csv").read_bytes()
            for size in (1, 2, 3, 5, 8):
                out = Path(tmp) / f"mpi{size}"
                summary = run_fake_mpi(size, ["--scenarios", str(n), "--seed", "7",
                                              "--out", str(out)])
                # byte-identical, not just close: same code, same order of operations
                self.assertEqual((out / "scenarios.csv").read_bytes(), expected, size)
                self.assertEqual(summary["ranks"], size)
                self.assertEqual(sum(summary["scenarios_per_rank"]), n)

    def test_more_ranks_than_scenarios(self):
        with tempfile.TemporaryDirectory() as tmp:
            seq_dir, out = Path(tmp) / "seq", Path(tmp) / "mpi"
            sequential_main(["--scenarios", "3", "--out", str(seq_dir)])
            run_fake_mpi(5, ["--scenarios", "3", "--out", str(out)])
            self.assertEqual((out / "scenarios.csv").read_bytes(),
                             (seq_dir / "scenarios.csv").read_bytes())

    def test_summary_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            summary = run_fake_mpi(3, ["--scenarios", "12", "--seed", "42", "--out", str(out)])
            saved = json.loads((out / "summary.json").read_text())
            self.assertEqual(saved["version"], "mpi")
            self.assertEqual(saved["seed"], 42)
            self.assertEqual(saved["n_scenarios"], 12)
            self.assertEqual(saved["n_stations"], 60)
            self.assertTrue({"disconnected_pairs", "lost_trips", "extra_delay_min"}
                            <= set(saved["units"]))
            for key in ["input", "bcast", "compute", "gather", "output", "total"]:
                self.assertGreaterEqual(saved["timing_s"][key], 0, key)
            # compute time = time of the slowest rank
            self.assertAlmostEqual(saved["timing_s"]["compute"],
                                   saved["compute_per_rank_s"]["max"])
            self.assertLessEqual(saved["compute_per_rank_s"]["min"],
                                 saved["compute_per_rank_s"]["mean"])
            # aggregate matches the sequential aggregate for the same scenarios
            seq = sequential_main(["--scenarios", "12", "--seed", "42",
                                   "--out", str(Path(tmp) / "seq")])
            self.assertEqual(saved["aggregate"], seq["aggregate"])

    def test_timing_row_has_agreed_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_fake_mpi(2, ["--scenarios", "6", "--out", str(Path(tmp) / "r")])
            csv_path = Path(tmp) / "timings" / "mpi.csv"
            append_timing_row(csv_path, timing_row(summary, 1))
            append_timing_row(csv_path, timing_row(summary, 2))
            rows = read_csv(csv_path)
            self.assertEqual(rows[0], SCHEMA_COLUMNS + EXTRA_COLUMNS)
            self.assertEqual(len(rows), 3)  # header + 2 rows, header written once
            record = dict(zip(rows[0], rows[1]))
            self.assertEqual(record["implementation"], "mpi")
            self.assertEqual(record["workers"], "2")
            self.assertEqual(record["scenarios"], "6")


def real_mpi_launcher():
    """Command start that really launches 2 MPI processes, or None."""
    try:
        import mpi4py  # noqa: F401
    except ImportError:
        return None
    for launcher in ("mpirun", "mpiexec"):
        if shutil.which(launcher):
            probe = [launcher, "-n", "2", sys.executable, "-c",
                     "from mpi4py import MPI; print('size', MPI.COMM_WORLD.Get_size())"]
            try:
                out = subprocess.run(probe, capture_output=True, text=True, timeout=60).stdout
            except (OSError, subprocess.TimeoutExpired):
                continue
            if "size 2" in out:
                return launcher
    return None


@unittest.skipUnless(DATA.exists(), "Madrid dataset not available")
@unittest.skipIf(real_mpi_launcher() is None, "no working mpirun/mpi4py with 2 ranks")
class TestRealMpi(unittest.TestCase):

    def test_two_real_ranks_match_sequential(self):
        launcher = real_mpi_launcher()
        with tempfile.TemporaryDirectory() as tmp:
            seq_dir, out = Path(tmp) / "seq", Path(tmp) / "mpi"
            sequential_main(["--scenarios", "30", "--out", str(seq_dir)])
            env = dict(os.environ, PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""))
            subprocess.run([launcher, "-n", "2", sys.executable, "-m", "src.mpi_simulation",
                            "--scenarios", "30", "--out", str(out)],
                           cwd=ROOT, env=env, check=True, capture_output=True, timeout=300)
            self.assertEqual((out / "scenarios.csv").read_bytes(),
                             (seq_dir / "scenarios.csv").read_bytes())
            self.assertEqual(json.loads((out / "summary.json").read_text())["ranks"], 2)


if __name__ == "__main__":
    unittest.main()
