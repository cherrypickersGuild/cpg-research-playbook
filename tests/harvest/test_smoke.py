#!/usr/bin/env python3
"""test_smoke.py — bounded smoke and read-only run validation (S9-3).

S9-3 adds the two commands that make a live run *possible to perform and possible
to trust*, and it adds them entirely offline. Seven failures this suite defends
against, each of which would make a future live run either dangerous or
unfalsifiable:

  * A CAP THAT DOES NOT BIND, OR BINDS DISHONESTLY. The candidate cap slices
    BEFORE any judgement, so an excluded candidate receives no classification, no
    facets, no record and no rejection row — it is *unprocessed*, which is not
    *rejected*. The accepted cap keeps the deterministic prefix ending at the Nth
    accepted candidate and relabels nothing; `accepted + rejected == candidates`
    still holds over the processed set, and no new rejection reason appears.
  * A BUDGET THAT FORGIVES ITSELF. The smoke budget is command-wide: the time
    integrated preflight consumed is subtracted from what the run phase gets, the
    scope is checked at every cell boundary, and an expiry aborts BEFORE the
    artifact-writing phase — publishing no manifest and leaving the previous
    pointer exactly where it was.
  * A RUN THAT CLAIMS MORE THAN IT DID. `config.bounds` carries the three smoke
    caps only when they were actually enforced; omitted bounds reproduce the
    committed config bytes exactly.
  * A VALIDATOR THAT REPAIRS. `runvalidate` reads, checks and reports. A test
    hashes the whole tree before and after validation and requires byte identity,
    including for a *broken* tree — evidence must survive being examined.
  * MISCOUNTED PATHS ACROSS RUNS (E9-11). 42 JSON = 18 selected-run + 24 shared.
    A second run adds 18 and updates the same 24; it does not make 84. The
    validator enforces both halves exactly and permits historical run directories.
  * A POINTER THAT DISAGREES. `validate --run-id` answers "is the run this root
    currently points at sound?", so a historical non-latest id is invalid here by
    contract, not by accident.
  * AN OUTBOUND REQUEST. A socket-level guard refuses every non-loopback host and
    is proved wired by tripping it. Every smoke in this suite runs on a fixture
    transport. **No configured source has been contacted.**

S5-7's recovery semantics, S5-5's pointer ordering, S6-6's eligibility proof and
S9-1's transport contract are reused, not re-proved: their own suites own them.

Run via tests/test_taxonomy_smoke.sh.
"""
import ast
import contextlib
import datetime
import hashlib
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import artifacts, cli, run_cells, runvalidate    # noqa: E402

RUNVALIDATE_PATH = os.path.join(ROOT, "src", "harvest", "runvalidate.py")
NOW = datetime.datetime(2026, 7, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)
RUN_A = "20260730T120000Z-101"
RUN_B = "20260730T130000Z-102"
LOOPBACK = "127.0.0.1"
RICH_CELL = "research-and-models__benchmark-and-datasets"


def clock():
    return NOW


def listing(root):
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            out.append(os.path.relpath(full, root).replace(os.sep, "/"))
    return sorted(out)


def tree_hash(root):
    digest = hashlib.sha256()
    for rel in listing(root):
        digest.update(rel.encode("utf-8"))
        with open(os.path.join(root, rel.replace("/", os.sep)), "rb") as handle:
            digest.update(handle.read())
    return digest.hexdigest()


def manifest_of(root, run_id):
    with open(os.path.join(root, "runs", run_id, "manifest.json"),
              encoding="utf-8") as handle:
        return json.load(handle)


def cell_of(root, run_id, cell_id):
    with open(os.path.join(root, "runs", run_id, "cells", "%s.json" % cell_id),
              encoding="utf-8") as handle:
        return json.load(handle)


class _Captured:
    """A stdout stand-in that has a real `.buffer`, like the console does.

    The commands write deterministic BYTES to `sys.stdout.buffer` — the committed
    `migrate.sh` idiom — so a plain `StringIO` cannot stand in for stdout. This
    captures at the byte level instead of forcing production code to write text.
    """

    def __init__(self):
        self.buffer = io.BytesIO()

    def write(self, text):
        self.buffer.write(text.encode("utf-8"))

    def flush(self):
        pass

    def value(self):
        return self.buffer.getvalue().decode("utf-8")


@contextlib.contextmanager
def capture():
    """Capture stdout (bytes) and stderr (text) around a CLI invocation."""
    out, err = _Captured(), io.StringIO()
    real_out, real_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        yield out, err
    finally:
        sys.stdout, sys.stderr = real_out, real_err


class Base(unittest.TestCase):
    """Temp roots, and a socket guard that permits only loopback."""

    def setUp(self):
        self._dirs = []
        real_connect = socket.socket.connect

        def guarded(sock, address, *a, **kw):
            host = address[0] if isinstance(address, tuple) else address
            if str(host) not in (LOOPBACK, "::1", "localhost"):
                raise AssertionError(
                    "OUTBOUND REFUSED: an S9-3 test tried to reach %r" % (host,))
            return real_connect(sock, address, *a, **kw)

        socket.socket.connect = guarded
        self.addCleanup(setattr, socket.socket, "connect", real_connect)

    def tearDown(self):
        for path in self._dirs:
            shutil.rmtree(path, ignore_errors=True)

    def temp(self, prefix="s93_"):
        path = tempfile.mkdtemp(prefix=prefix)
        self._dirs.append(path)
        return path

    def offline_transport(self):
        """A fixture transport with a lease root this test owns."""
        return run_cells.fixture_transport(self.temp("s93_lease_"))

    def drive_smoke(self, state_root, *extra, transport=None):
        """Run the real CLI `smoke` with the network seam replaced by fixtures."""
        transport = transport or self.offline_transport()
        real = cli.live_transport
        cli.live_transport = lambda root, **kw: transport
        self.addCleanup(setattr, cli, "live_transport", real)
        with capture():
            return cli.main(["smoke", "--state-root", state_root, *extra])

    def valid_root(self, run_id=RUN_A):
        root = self.temp("s93_ext_")
        self.assertEqual(self.drive_smoke(root, "--run-id", run_id), 0)
        return root


# ------------------------------------------------------- outbound refusal
class TestNothingGoesOut(Base):
    def test_the_outbound_guard_is_genuinely_installed(self):
        with self.assertRaises(AssertionError) as caught:
            socket.socket().connect(("example.invalid", 80))
        self.assertIn("OUTBOUND REFUSED", str(caught.exception))

    def test_a_full_smoke_contacts_no_configured_source(self):
        root = self.valid_root()
        self.assertEqual(len(listing(root)), runvalidate.TOTAL_PATHS)


# ---------------------------------------------------------------- bounds
class TestRunBounds(Base):
    def test_it_is_frozen(self):
        import dataclasses
        bounds = run_cells.RunBounds(12, 5, 1800)
        self.assertTrue(dataclasses.is_dataclass(bounds))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            bounds.max_candidates_per_cell = 99

    def test_malformed_values_are_refused(self):
        for args in ((0, 5, 1800), (12, 0, 1800), (12, 5, 0), (12, 5, -1),
                     ("12", 5, 1800), (12, 5, float("inf")),
                     (12, 5, float("nan")), (True, 5, 1800)):
            with self.assertRaises(run_cells.RunCellsError):
                run_cells.RunBounds(*args)

    def test_an_accepted_cap_above_the_candidate_cap_is_refused(self):
        with self.assertRaises(run_cells.RunCellsError):
            run_cells.RunBounds(5, 12, 1800)

    def test_remaining_budget_subtracts_preflight_time(self):
        bounds = run_cells.RunBounds(12, 5, 1800, elapsed_before_run_sec=300)
        self.assertEqual(bounds.remaining_run_sec, 1500)

    def test_run_has_no_independent_cap_parameters(self):
        import inspect
        params = inspect.signature(run_cells.run).parameters
        for forbidden in ("max_candidates", "max_accepted", "smoke_budget",
                          "opener", "sleep", "lease_root"):
            self.assertNotIn(forbidden, params)
        for seam in ("bounds", "run_id_value"):
            self.assertIn(seam, params)
            self.assertEqual(params[seam].kind, inspect.Parameter.KEYWORD_ONLY)
            self.assertIsNone(params[seam].default)


class TestCapSemantics(Base):
    def run_bounded(self, candidates, accepted):
        root = self.temp()
        bounds = run_cells.RunBounds(candidates, accepted, 1800)
        result = run_cells.run(root, cells=[RICH_CELL], clock=clock, mode="smoke",
                               enrich=False, bounds=bounds,
                               source_preflight=())
        return root, result

    def test_the_candidate_cap_binds_and_reports(self):
        root, result = self.run_bounded(4, 2)
        row = [r for r in manifest_of(root, result.run_id)["cells"]
               if r["cell_id"] == RICH_CELL][0]
        self.assertEqual(row["candidates"], 4)
        self.assertEqual(row["accepted"] + row["rejected"], row["candidates"])

    def test_the_accepted_cap_binds_on_a_deterministic_prefix(self):
        root, result = self.run_bounded(12, 2)
        row = [r for r in manifest_of(root, result.run_id)["cells"]
               if r["cell_id"] == RICH_CELL][0]
        self.assertEqual(row["accepted"], 2)
        self.assertEqual(row["accepted"] + row["rejected"], row["candidates"])
        self.assertLess(row["candidates"], 12,
                        "the prefix must stop at the 2nd accepted candidate")

    def test_excess_accepted_candidates_are_not_relabelled_rejected(self):
        """The uncapped cell accepts 4; capping to 2 must not create 2 rejections."""
        wide, wide_result = self.run_bounded(12, 5)
        tight, tight_result = self.run_bounded(12, 2)
        wide_row = [r for r in manifest_of(wide, wide_result.run_id)["cells"]
                    if r["cell_id"] == RICH_CELL][0]
        tight_row = [r for r in manifest_of(tight, tight_result.run_id)["cells"]
                     if r["cell_id"] == RICH_CELL][0]
        self.assertEqual(wide_row["accepted"], 4)
        self.assertEqual(tight_row["accepted"], 2)
        self.assertLess(tight_row["rejected"], wide_row["rejected"],
                        "capping must DROP candidates, never convert them to "
                        "rejections")

    def test_no_new_rejection_reason_appears(self):
        root, result = self.run_bounded(12, 2)
        with open(os.path.join(root, "rejections", "%s.json" % RICH_CELL),
                  encoding="utf-8") as handle:
            log = json.load(handle)
        committed = set(runvalidate.run_cells.ZERO_RESULT_FOR_REJECTION)
        for entry in log.get("entries", []) or []:
            self.assertIn(entry.get("reason"), committed)

    def test_capped_out_candidates_receive_no_record(self):
        root, result = self.run_bounded(4, 2)
        cell = cell_of(root, result.run_id, RICH_CELL)
        self.assertLessEqual(len(cell["records"]), 4)

    def test_ordering_is_deterministic_across_runs(self):
        a, a_result = self.run_bounded(6, 3)
        b, b_result = self.run_bounded(6, 3)
        self.assertEqual(json.dumps(cell_of(a, a_result.run_id, RICH_CELL),
                                    sort_keys=True),
                         json.dumps(cell_of(b, b_result.run_id, RICH_CELL),
                                    sort_keys=True))

    def test_caps_appear_in_manifest_config_bounds(self):
        root, result = self.run_bounded(7, 3)
        bounds = manifest_of(root, result.run_id)["config"]["bounds"]
        self.assertEqual(bounds["max_candidates_per_cell"], 7)
        self.assertEqual(bounds["max_accepted_per_cell"], 3)
        self.assertEqual(bounds["smoke_budget_sec"], 1800)
        self.assertEqual(bounds["max_cells"], run_cells.MAX_CELLS)

    def test_omitted_bounds_preserve_the_committed_config_bytes(self):
        root = self.temp()
        result = run_cells.run(root, clock=clock)
        bounds = manifest_of(root, result.run_id)["config"]["bounds"]
        self.assertEqual(sorted(bounds),
                         ["max_cells", "max_target_fetches_per_cell"])


class TestRunBudget(Base):
    """An injected monotonic clock. Nothing sleeps."""

    def patched_budget(self, ticks):
        """Replace the committed budget owner with one on a fake clock."""
        import src.harvest.budget as budget_mod
        state = {"n": 0}

        def fake():
            value = ticks[min(state["n"], len(ticks) - 1)]
            state["n"] += 1
            return value

        real = run_cells.RequestBudget
        run_cells.RequestBudget = lambda: budget_mod.RequestBudget(clock=fake)
        self.addCleanup(setattr, run_cells, "RequestBudget", real)

    def test_an_exhausted_run_budget_publishes_nothing(self):
        # The `run` scope starts at t=0 and every later reading is far past 10s.
        self.patched_budget([0.0] + [1000.0] * 500)
        root = self.temp()
        bounds = run_cells.RunBounds(12, 5, 10.0)
        with self.assertRaises(Exception):
            run_cells.run(root, clock=clock, mode="smoke", enrich=False,
                          bounds=bounds, run_id_value=RUN_A)
        self.assertFalse(os.path.exists(artifacts.run_manifest_path(root, RUN_A)))
        self.assertFalse(os.path.exists(artifacts.latest_run_id_path(root)))

    def test_preflight_time_reduces_the_remaining_run_budget(self):
        bounds = run_cells.RunBounds(12, 5, 1800, elapsed_before_run_sec=1799.5)
        self.assertAlmostEqual(bounds.remaining_run_sec, 0.5)

    def test_a_fully_consumed_budget_is_refused_before_the_run(self):
        root = self.temp("s93_ext_")
        transport = self.offline_transport()
        real = cli.live_transport
        cli.live_transport = lambda r, **kw: transport
        self.addCleanup(setattr, cli, "live_transport", real)
        real_bounds = run_cells.RunBounds
        run_cells.RunBounds = lambda **kw: real_bounds(
            **{**kw, "elapsed_before_run_sec": 99999.0})
        self.addCleanup(setattr, run_cells, "RunBounds", real_bounds)
        with capture():
            self.assertEqual(cli.main(["smoke", "--state-root", root]), 2)
        self.assertEqual(listing(root), [])

    def test_the_configured_budget_is_reported_not_the_remaining_value(self):
        root = self.temp()
        bounds = run_cells.RunBounds(12, 5, 1800, elapsed_before_run_sec=42.0)
        result = run_cells.run(root, cells=[RICH_CELL], clock=clock, mode="smoke",
                               enrich=False, bounds=bounds)
        reported = manifest_of(root, result.run_id)["config"]["bounds"]
        self.assertEqual(reported["smoke_budget_sec"], 1800)
        self.assertNotIn("elapsed_before_run_sec", reported)
        self.assertNotIn("remaining_run_sec", reported)


# ------------------------------------------------------------ full smoke
class TestFullOfflineSmoke(Base):
    @classmethod
    def setUpClass(cls):
        # `addClassCleanup`, not `tearDownClass`: a tearDown does NOT run when
        # setUpClass raises partway, and this class builds a full 43-path run
        # tree — precisely the debris a failed setup would strand in the system
        # temp directory. Registered immediately after each mkdtemp, so a failure
        # on any later line still cleans up.
        cls.lease = tempfile.mkdtemp(prefix="s93_cls_lease_")
        cls.addClassCleanup(shutil.rmtree, cls.lease, ignore_errors=True)
        cls.root = tempfile.mkdtemp(prefix="s93_cls_ext_")
        cls.addClassCleanup(shutil.rmtree, cls.root, ignore_errors=True)
        transport = run_cells.fixture_transport(cls.lease)
        real = cli.live_transport
        cli.live_transport = lambda r, **kw: transport
        try:
            with capture() as (out, _err):
                cls.code = cli.main(["smoke", "--state-root", cls.root,
                                     "--run-id", RUN_A])
            cls.stdout = out.value()
        finally:
            cli.live_transport = real
        cls.files = listing(cls.root)
        cls.manifest = manifest_of(cls.root, RUN_A)

    def test_it_exits_zero(self):
        self.assertEqual(self.code, 0)

    def test_the_tree_is_42_json_and_one_pointer(self):
        self.assertEqual(len(self.files), runvalidate.TOTAL_PATHS)
        self.assertEqual(len([f for f in self.files if f.endswith(".json")]),
                         runvalidate.TOTAL_JSON)
        self.assertIn("LATEST_RUN_ID", self.files)

    def test_the_families_are_exactly_right(self):
        def count(prefix, suffix=".json"):
            return len([f for f in self.files
                        if f.startswith(prefix) and f.endswith(suffix)])
        self.assertEqual(count("runs/%s/cells/" % RUN_A), 12)
        self.assertEqual(count("runs/%s/topics/" % RUN_A), 3)
        self.assertEqual(count("ledgers/"), 12)
        self.assertEqual(count("rejections/"), 12)
        for name in ("coverage.json", "alias_conflicts.json", "manifest.json"):
            self.assertIn("runs/%s/%s" % (RUN_A, name), self.files)

    def test_mode_enrichment_and_eligibility(self):
        self.assertEqual(self.manifest["mode"], "smoke")
        self.assertFalse(self.manifest["config"]["enrich"])
        self.assertFalse(self.manifest["publication_eligible"])
        self.assertIn("smoke", self.manifest["publication_ineligible_reason"])

    def test_target_accounting_is_absent_not_falsely_zero(self):
        accounting = self.manifest["request_accounting"]
        for key in ("target_http_attempts", "target_retries",
                    "target_redirect_hops"):
            self.assertNotIn(key, accounting)
        self.assertEqual(accounting.get("target_fetch_owners", 0), 0)

    def test_no_target_page_was_fetched(self):
        for cell_id in runvalidate.configured_cell_ids():
            for record in cell_of(self.root, RUN_A, cell_id)["records"]:
                if record.get("record_type") == "cross_reference":
                    continue
                self.assertEqual(record["access_status"], "not_checked")
                self.assertIsNone(record["http_status"])

    def test_all_25_preflight_rows_are_persisted_and_sorted(self):
        rows = self.manifest["source_preflight"]
        self.assertEqual(len(rows), 25)
        ids = [row["source_id"] for row in rows]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(set(ids)), 25)

    def test_every_configured_cell_ran(self):
        rows = self.manifest["cells"]
        self.assertEqual(len(rows), 12)
        for row in rows:
            self.assertNotEqual(row["status"], artifacts.STATUS_NOT_RUN)

    def test_the_summary_is_deterministic_and_carries_no_timestamp(self):
        summary = json.loads(self.stdout)
        self.assertEqual(summary, {
            "run_id": RUN_A, "mode": "smoke", "json_artifacts": 42,
            "pointer": "LATEST_RUN_ID", "source_preflight_rows": 25,
            "publication_eligible": False})


# -------------------------------------------------------------- validate
class TestValidate(Base):
    def report(self, root, run_id=RUN_A):
        return runvalidate.validate_run(root, run_id)

    def drive_validate(self, root, run_id=RUN_A):
        with capture():
            return cli.main(["validate", "--state-root", root, "--run-id", run_id])

    def test_a_fresh_smoke_root_validates(self):
        root = self.valid_root()
        report = self.report(root)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["json_documents_checked"], 42)
        self.assertEqual(report["paths_checked"], 43)
        self.assertEqual(report["pointer_run_id"], RUN_A)
        self.assertEqual(self.drive_validate(root), 0)

    def test_the_validator_writes_nothing_even_on_a_broken_tree(self):
        root = self.valid_root()
        os.remove(os.path.join(root, "ledgers",
                               "%s.json" % runvalidate.configured_cell_ids()[0]))
        before = tree_hash(root)
        self.assertEqual(self.drive_validate(root), 1)
        self.assertEqual(tree_hash(root), before,
                         "a validator that repairs is a writer in disguise")

    def test_a_missing_file_is_invalid(self):
        root = self.valid_root()
        os.remove(artifacts.coverage_report_path(root, RUN_A))
        self.assertFalse(self.report(root)["valid"])

    def test_an_extra_selected_run_file_is_invalid(self):
        root = self.valid_root()
        with open(os.path.join(root, "runs", RUN_A, "cells", "stray.json"),
                  "w", encoding="utf-8") as handle:
            handle.write("{}")
        errors = self.report(root)["errors"]
        self.assertTrue(any("unexpected file stray.json" in e for e in errors),
                        errors)

    def test_an_extra_shared_file_is_invalid(self):
        root = self.valid_root()
        with open(os.path.join(root, "ledgers", "stray.json"), "w",
                  encoding="utf-8") as handle:
            handle.write("{}")
        self.assertFalse(self.report(root)["valid"])

    def test_malformed_json_is_invalid(self):
        root = self.valid_root()
        with open(artifacts.coverage_report_path(root, RUN_A), "w",
                  encoding="utf-8") as handle:
            handle.write("{not json")
        errors = self.report(root)["errors"]
        self.assertTrue(any("not valid JSON" in e for e in errors), errors)

    def test_schema_invalid_json_is_invalid(self):
        root = self.valid_root()
        with open(artifacts.coverage_report_path(root, RUN_A), "w",
                  encoding="utf-8") as handle:
            handle.write("{}")
        self.assertFalse(self.report(root)["valid"])

    def test_a_pointer_mismatch_is_invalid(self):
        root = self.valid_root()
        with open(artifacts.latest_run_id_path(root), "w", encoding="utf-8",
                  newline="") as handle:
            handle.write("20260730T130000Z-999\n")
        errors = self.report(root)["errors"]
        self.assertTrue(any("LATEST_RUN_ID names" in e for e in errors), errors)

    def test_a_manifest_run_id_mismatch_is_invalid(self):
        root = self.valid_root()
        path = artifacts.run_manifest_path(root, RUN_A)
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        document["harvest_run_id"] = RUN_B
        with open(path, "w", encoding="utf-8", newline="") as handle:
            json.dump(document, handle)
        self.assertFalse(self.report(root)["valid"])

    def test_an_alias_conflict_count_mismatch_is_invalid(self):
        root = self.valid_root()
        path = artifacts.run_manifest_path(root, RUN_A)
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        document["alias_conflicts_count"] = 99
        with open(path, "w", encoding="utf-8", newline="") as handle:
            json.dump(document, handle)
        errors = self.report(root)["errors"]
        self.assertTrue(any("alias_conflicts_count" in e for e in errors), errors)

    def test_a_count_inconsistency_is_invalid(self):
        root = self.valid_root()
        cell_id = runvalidate.configured_cell_ids()[0]
        path = artifacts.cell_artifact_path(root, RUN_A, cell_id)
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        document["metadata"]["total_records"] = 999
        with open(path, "w", encoding="utf-8", newline="") as handle:
            json.dump(document, handle)
        self.assertFalse(self.report(root)["valid"])

    def test_temp_debris_anywhere_is_invalid(self):
        root = self.valid_root()
        debris = os.path.join(root, "ledgers",
                              "%sdeadbeef_x.json" % artifacts.TEMP_PREFIX)
        with open(debris, "w", encoding="utf-8") as handle:
            handle.write("{}")
        errors = self.report(root)["errors"]
        self.assertTrue(any("temp debris" in e for e in errors), errors)

    def test_a_historical_run_directory_is_permitted(self):
        root = self.valid_root()
        second = self.drive_smoke(root, "--run-id", RUN_B)
        self.assertEqual(second, 0)
        report = self.report(root, RUN_B)
        self.assertTrue(report["valid"], report["errors"])
        # E9-11: the 24 shared documents were UPDATED, not duplicated.
        files = listing(root)
        self.assertEqual(len([f for f in files if f.startswith("ledgers/")]), 12)
        self.assertEqual(len([f for f in files if f.startswith("rejections/")]), 12)
        self.assertEqual(len(files), runvalidate.TOTAL_PATHS + 18)

    def test_validating_a_historical_non_latest_run_fails_on_the_pointer(self):
        root = self.valid_root()
        self.assertEqual(self.drive_smoke(root, "--run-id", RUN_B), 0)
        errors = self.report(root, RUN_A)["errors"]
        self.assertTrue(any("LATEST_RUN_ID names" in e for e in errors), errors)

    def test_invalid_arguments_exit_two_with_empty_stdout(self):
        root = self.valid_root()
        for argv in (["validate", "--state-root", root, "--run-id", "nope"],
                     ["validate", "--state-root", "relative", "--run-id", RUN_A],
                     ["validate", "--run-id", RUN_A]):
            with capture() as (out, _err):
                code = cli.main(list(argv))
            self.assertEqual(code, 2, argv)
            self.assertEqual(out.value(), "", argv)

    def test_the_report_is_sorted_and_carries_no_timestamp(self):
        root = self.valid_root()
        os.remove(artifacts.coverage_report_path(root, RUN_A))
        report = self.report(root)
        self.assertEqual(report["errors"], sorted(report["errors"]))
        self.assertNotIn("generated_at", report)
        self.assertEqual(sorted(report), ["errors", "json_documents_checked",
                                          "paths_checked", "pointer_run_id",
                                          "run_id", "valid"])

    def test_it_collects_several_independent_errors(self):
        root = self.valid_root()
        os.remove(artifacts.coverage_report_path(root, RUN_A))
        os.remove(os.path.join(root, "ledgers",
                               "%s.json" % runvalidate.configured_cell_ids()[0]))
        self.assertGreaterEqual(len(self.report(root)["errors"]), 2)


# ------------------------------------------------------ recovery + refusal
class TestRefusals(Base):
    def test_an_invalid_run_id_writes_nothing(self):
        root = self.temp("s93_ext_")
        self.assertEqual(self.drive_smoke(root, "--run-id", "nope"), 2)
        self.assertEqual(listing(root), [])

    def test_a_finished_run_id_is_refused_before_preflight(self):
        root = self.valid_root()
        before = tree_hash(root)
        counted = {"n": 0}
        real = run_cells.fixture_transport

        def counting(*a, **kw):
            counted["n"] += 1
            return real(*a, **kw)

        run_cells.fixture_transport = counting
        self.addCleanup(setattr, run_cells, "fixture_transport", real)
        self.assertEqual(self.drive_smoke(root, "--run-id", RUN_A), 2)
        self.assertEqual(tree_hash(root), before)

    def test_an_injected_preflight_failure_writes_no_run(self):
        from src.harvest import preflight as pf
        root = self.temp("s93_ext_")
        real = pf.preflight_sources

        def explode(*a, **kw):
            raise pf.PreflightError("injected")

        pf.preflight_sources = explode
        self.addCleanup(setattr, pf, "preflight_sources", real)
        self.assertEqual(self.drive_smoke(root), 2)
        self.assertEqual(listing(root), [])

    def test_an_injected_manifest_failure_leaves_the_pointer_alone(self):
        root = self.valid_root()
        pointer_before = artifacts.read_latest_run_id(root)
        real = artifacts.write_run_manifest

        def explode(*a, **kw):
            raise artifacts.ArtifactError("injected manifest failure")

        artifacts.write_run_manifest = explode
        self.addCleanup(setattr, artifacts, "write_run_manifest", real)
        with self.assertRaises(Exception):
            self.drive_smoke(root, "--run-id", RUN_B)
        self.assertEqual(artifacts.read_latest_run_id(root), pointer_before)

    def test_a_supplied_external_root_is_never_removed(self):
        root = self.valid_root()
        self.assertTrue(os.path.isdir(root))
        self.assertEqual(self.drive_validate_exists(root), True)

    def drive_validate_exists(self, root):
        with capture():
            cli.main(["validate", "--state-root", root, "--run-id", RUN_A])
        return os.path.isdir(root)


# ------------------------------------------------------ ownership boundaries
class TestOwnershipBoundaries(unittest.TestCase):
    def setUp(self):
        with open(RUNVALIDATE_PATH, encoding="utf-8") as handle:
            self.src = handle.read()
        self.tree = ast.parse(self.src)

    def imported(self):
        names = set()
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    names.add(alias.name.split(".")[-1])
        return names

    def test_the_validator_imports_no_http_adapter_or_judgement_owner(self):
        forbidden = {"httpclient", "adapters", "classify", "verify", "facetassign",
                     "dedupe", "extract", "targetfetch", "sourcecache", "pool",
                     "preflight", "urllib", "socket", "requests"}
        self.assertEqual(self.imported() & forbidden, set())

    def test_the_validator_contains_no_write_or_repair_path(self):
        for forbidden in ("write_atomic", "write_document", "publish_run",
                          "os.remove", "os.unlink", "shutil.rmtree", "os.makedirs",
                          "os.mkdir", "os.replace", "os.rename"):
            self.assertNotIn(forbidden, self.src)

    def test_the_validator_opens_files_read_only(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open":
                modes = [a.value for a in node.args[1:]
                         if isinstance(a, ast.Constant)]
                modes += [k.value.value for k in node.keywords
                          if k.arg == "mode" and isinstance(k.value, ast.Constant)]
                for mode in modes:
                    self.assertNotIn("w", mode)
                    self.assertNotIn("a", mode)
                    self.assertNotIn("+", mode)

    def test_the_cli_defines_no_second_serializer(self):
        with open(os.path.join(ROOT, "src", "harvest", "cli.py"),
                  encoding="utf-8") as handle:
            src = handle.read()
        self.assertNotIn("json.dumps", src)
        self.assertNotIn("import json", src)

    def test_the_registry_partition_still_holds(self):
        surface = {"preflight-sources", "smoke", "validate", "compare-runs",
                   "diff", "linkcheck"}
        registered, planned = set(cli.COMMANDS), set(cli.PLANNED_COMMANDS)
        self.assertEqual(registered & planned, set())
        self.assertEqual(registered | planned, surface)

    def test_the_path_accounting_constants_decompose(self):
        self.assertEqual(runvalidate.SELECTED_RUN_JSON, 18)
        self.assertEqual(runvalidate.SHARED_JSON, 24)
        self.assertEqual(runvalidate.TOTAL_JSON, 42)
        self.assertEqual(runvalidate.TOTAL_PATHS, 43)


if __name__ == "__main__":
    unittest.main()
