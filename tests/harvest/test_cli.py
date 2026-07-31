#!/usr/bin/env python3
"""test_cli.py — the live execution seam and CLI foundation (S9-1).

S9-1 makes a live run *constructible* without making one *happen*. That is a
narrow claim and an easy one to get wrong in either direction, so this suite
defends both edges:

  * OMISSION IS BYTE-COMPATIBLE. The four new `run()` seams — `transport`,
    `mode`, `enrich`, `source_preflight` — all default to the behaviour committed
    at `720f114c`. Two runs at one pinned clock, one using the old call shape and
    one passing every new argument explicitly as `None`, produce the SAME PATH SET
    and byte-identical files, compared file by file rather than by a tree hash: a
    tree hash passes on two empty trees.
  * THE TRANSPORT IS ATOMIC. `Transport` is frozen, and `run()` takes ONE
    transport rather than three independent opener / sleep / lease-root
    parameters, so a live opener can never be paired with the fixture's suppressed
    pacing. A test asserts that half-live API does not exist.
  * A SUPPLIED LEASE ROOT IS THE CALLER'S. It is used as given, never replaced by
    a temporary one, and never deleted. The temporary root `run()` creates for
    ITSELF still is.
  * MODE AND ENRICHMENT ARE HONEST. `mode="smoke"` reaches the manifest and is
    ineligible for publication through the committed
    `derive_publication_eligibility` — NO new predicate. `enrich=False` fetches no
    target page, records `config.enrich: false`, and reports the three `target_*`
    accounting keys as ABSENT rather than zero, because "the lane did not run" and
    "the lane ran and found nothing" are different answers (S6-6A).
  * NOTHING GOES OUT. Proved with a sentinel at the transport boundary, and proved
    NON-VACUOUSLY: the same sentinel, handed to `run()` as a transport opener, IS
    reached. A test that only observes the absence of a request proves nothing
    about whether it could have happened.
  * THE CLI LAYER JUDGES NOTHING. An AST scan of `cli.py` proves it owns no
    vocabulary, defines no matcher, canonicalizer, serializer, scorer or
    classifier, and imports no judgement module.

Not re-proved here, because they have committed owners: finished-run refusal and
interruption cleanup (`test_recovery.py`), pointer ordering (`test_manifest.py`),
publication eligibility (`test_eligibility.py`), target determinism
(`test_target_determinism.py`). Their wrappers run alongside this one.

Offline and temp-rooted throughout. No local recording server, no socket, no
external Stage 9 state root — S9-1 selects none.

Run via tests/test_taxonomy_cli.sh.
"""
import ast
import contextlib
import dataclasses
import datetime
import inspect
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import cli, httpclient, run_cells                # noqa: E402

NOW = datetime.datetime(2026, 7, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)
CLI_PATH = os.path.join(ROOT, "src", "harvest", "cli.py")
HARVEST_SH = os.path.join(ROOT, "scripts", "harvest", "harvest.sh")

# One cell, one source, no accepted record — enough to drive the transport
# without spending the whole fixture corpus on a test about plumbing.
SMALL_CELL = "cases__product-discovery"
# The one cell the committed corpus accepts records in. Used where a test needs
# real target-fetch work to be observable.
RICH_CELL = "research-and-models__benchmark-and-datasets"


def clock():
    return NOW


def listing(root):
    """Every file under `root`, repo-relative, sorted."""
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            out.append(os.path.relpath(full, root).replace(os.sep, "/"))
    return sorted(out)


def read(root, rel):
    with open(os.path.join(root, rel.replace("/", os.sep)), "rb") as handle:
        return handle.read()


def manifest_of(root, run_id):
    with open(os.path.join(root, "runs", run_id, "manifest.json"),
              encoding="utf-8") as handle:
        return json.load(handle)


class Sentinel:
    """An opener that records every call and refuses to perform one.

    This is the no-network proof's instrument. It stands where
    `httpclient.default_opener` would, so "no outbound request happened" becomes
    "the only thing that could have made one was never reached".
    """

    def __init__(self):
        self.calls = []

    def __call__(self, req, timeout=None):
        self.calls.append(getattr(req, "full_url", req))
        raise AssertionError("SENTINEL: an outbound request was attempted")


class CountingSleep:
    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)
        return None


class TempRoots(unittest.TestCase):
    """Every byte this suite writes lands under a directory it removes."""

    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for path in self._dirs:
            shutil.rmtree(path, ignore_errors=True)

    def temp(self, prefix="s91_"):
        path = tempfile.mkdtemp(prefix=prefix)
        self._dirs.append(path)
        return path


# ------------------------------------------------------------ transport shape
class TestTransportContract(TempRoots):
    def test_transport_is_frozen(self):
        transport = run_cells.fixture_transport(self.temp())
        self.assertTrue(dataclasses.is_dataclass(transport))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            transport.opener = Sentinel()

    def test_transport_carries_exactly_three_fields(self):
        names = [f.name for f in dataclasses.fields(run_cells.Transport)]
        self.assertEqual(names, ["opener", "sleep", "lease_root"])

    def test_run_has_no_half_live_multi_parameter_api(self):
        """One atomic seam, not three independent ones."""
        params = inspect.signature(run_cells.run).parameters
        for forbidden in ("opener", "sleep", "lease_root"):
            self.assertNotIn(forbidden, params,
                             "%r must not be a separate run() parameter: a live "
                             "opener could then inherit fixture pacing" % forbidden)
        self.assertIn("transport", params)
        for seam in ("transport", "mode", "enrich", "source_preflight"):
            self.assertIs(params[seam].default, None,
                          "%r must default to None so omission is compatible" % seam)
            self.assertEqual(params[seam].kind, inspect.Parameter.KEYWORD_ONLY)

    def test_bounds_is_not_accepted_at_s9_1(self):
        """E9-3: a parameter taken and ignored is worse than one absent."""
        self.assertNotIn("bounds", inspect.signature(run_cells.run).parameters)

    def test_fixture_transport_uses_the_fixture_opener_and_no_pacing(self):
        transport = run_cells.fixture_transport(self.temp())
        self.assertIsInstance(transport.opener,
                              run_cells.fixtures_mod.FixtureOpener)
        self.assertIs(transport.sleep, run_cells._no_pacing)
        self.assertIsNone(transport.sleep(9999))

    def test_run_cells_owns_no_live_constructor(self):
        """The live decision has ONE owner, and it is not this module."""
        source = open(os.path.join(ROOT, "src", "harvest", "run_cells.py"),
                      encoding="utf-8").read()
        self.assertNotIn("default_opener", source)


# --------------------------------------------------------- lease-root ownership
class TestLeaseRootOwnership(TempRoots):
    def test_a_supplied_lease_root_is_used_and_never_deleted(self):
        lease = self.temp("caller_leases_")
        root = self.temp()
        transport = run_cells.fixture_transport(lease)
        self.assertEqual(transport.lease_root, lease)
        run_cells.run(root, cells=[SMALL_CELL], clock=clock, transport=transport)
        self.assertTrue(os.path.isdir(lease),
                        "a caller-owned lease root must survive the run")

    def test_an_internally_created_lease_root_is_swept(self):
        before = set(os.listdir(tempfile.gettempdir()))
        run_cells.run(self.temp(), cells=[SMALL_CELL], clock=clock)
        after = set(os.listdir(tempfile.gettempdir()))
        leaked = [name for name in (after - before)
                  if name.startswith("harvest_leases_")]
        self.assertEqual(leaked, [], "run() must sweep the lease root it created")

    def test_a_supplied_transports_opener_and_sleep_are_actually_used(self):
        lease = self.temp("caller_leases_")
        inner = run_cells.fixture_transport(lease)
        sleeper = CountingSleep()

        class Counting:
            def __init__(self, wrapped):
                self.wrapped = wrapped
                self.calls = 0

            def __call__(self, req, timeout=None):
                self.calls += 1
                return self.wrapped(req, timeout=timeout)

        counting = Counting(inner.opener)
        transport = run_cells.Transport(opener=counting, sleep=sleeper,
                                        lease_root=lease)
        run_cells.run(self.temp(), cells=[SMALL_CELL], clock=clock,
                      transport=transport)
        self.assertGreater(counting.calls, 0,
                           "the supplied opener must be the one that is called")


# --------------------------------------------------------- byte compatibility
class TestOmissionIsByteCompatible(TempRoots):
    """The old call shape and the new all-None shape must be indistinguishable."""

    def test_full_tree_is_byte_identical_and_the_comparison_is_not_vacuous(self):
        old_root = self.temp("old_")
        new_root = self.temp("new_")

        old = run_cells.run(old_root, clock=clock)
        new = run_cells.run(new_root, clock=clock, transport=None, mode=None,
                            enrich=None, source_preflight=None)

        self.assertEqual(old.run_id, new.run_id)
        old_files, new_files = listing(old_root), listing(new_root)
        self.assertEqual(old_files, new_files)

        # Non-vacuity: this must be a real, record-bearing 43-path tree, not two
        # empty directories agreeing with each other.
        self.assertEqual(len(old_files), 43)
        self.assertTrue(any(p.endswith("/cells/%s.json" % RICH_CELL)
                            for p in old_files))
        manifest = manifest_of(old_root, old.run_id)
        self.assertGreater(sum(row.get("accepted", 0)
                               for row in manifest["cells"]), 0)

        for rel in old_files:
            self.assertEqual(read(old_root, rel), read(new_root, rel),
                             "%s differs between the old and new call shapes" % rel)

    def test_no_new_config_key_or_moving_field_appeared(self):
        root = self.temp()
        result = run_cells.run(root, clock=clock)
        config = manifest_of(root, result.run_id)["config"]
        self.assertEqual(
            sorted(config),
            ["bounds", "canonicalization_version", "cross_topic_policy", "enrich",
             "policy_version", "precedence_version", "topics"])
        self.assertEqual(sorted(config["bounds"]),
                         ["max_cells", "max_target_fetches_per_cell"])

    def test_fixture_directory_injection_still_works(self):
        """`fixtures_dir` is a committed contract; the seam must not swallow it."""
        corpus = self.temp("corpus_")
        src = os.path.join(ROOT, "tests", "fixtures", "harvest")
        for sub in ("sources", "robots", "targets"):
            shutil.copytree(os.path.join(src, sub), os.path.join(corpus, sub))
        os.remove(os.path.join(corpus, "sources", "fx_producthunt.json"))

        root = self.temp()
        result = run_cells.run(root, cells=[SMALL_CELL], clock=clock,
                               fixtures_dir=corpus)
        rows = {row["cell_id"]: row for row in
                manifest_of(root, result.run_id)["cells"]}
        self.assertEqual(rows[SMALL_CELL]["status"], "adapter_error",
                         "the injected corpus, not the committed one, must be read")


# --------------------------------------------------------- mode + enrichment
class TestModeAndEnrichmentHonesty(TempRoots):
    def test_smoke_mode_reaches_the_manifest_and_is_ineligible(self):
        root = self.temp()
        result = run_cells.run(root, cells=[RICH_CELL], clock=clock, mode="smoke")
        manifest = manifest_of(root, result.run_id)
        self.assertEqual(manifest["mode"], "smoke")
        self.assertFalse(manifest["publication_eligible"])
        self.assertIn("smoke", manifest["publication_ineligible_reason"])

    def test_no_new_eligibility_predicate_was_added(self):
        """The refusal must come from the committed derivation, not from here."""
        source = open(os.path.join(ROOT, "src", "harvest", "run_cells.py"),
                      encoding="utf-8").read()
        self.assertNotIn("publication_eligible=", source)
        self.assertNotIn("publication_ineligible_reason=", source)

    def test_omitted_mode_is_still_harvest(self):
        root = self.temp()
        result = run_cells.run(root, cells=[SMALL_CELL], clock=clock)
        self.assertEqual(manifest_of(root, result.run_id)["mode"], "harvest")

    def test_enrich_false_fetches_no_target_and_says_so(self):
        root = self.temp()
        result = run_cells.run(root, cells=[RICH_CELL], clock=clock, enrich=False)
        manifest = manifest_of(root, result.run_id)

        self.assertFalse(manifest["config"]["enrich"])
        accounting = manifest["request_accounting"]
        self.assertEqual(accounting.get("target_fetch_owners", 0), 0)
        # Absent, not zero: the lane never ran (S6-6A's sentinel).
        for key in ("target_http_attempts", "target_retries",
                    "target_redirect_hops"):
            self.assertNotIn(key, accounting)

        with open(os.path.join(root, "runs", result.run_id, "cells",
                               "%s.json" % RICH_CELL), encoding="utf-8") as fh:
            cell = json.load(fh)
        full = [r for r in cell["records"] if r["record_type"] == "full"]
        self.assertTrue(full, "this cell must produce records, or the test is vacuous")
        for record in full:
            self.assertEqual(record["access_status"], "not_checked")
            self.assertIsNone(record["http_status"])
            self.assertIsNone(record["content_hash"])

    def test_enrich_true_by_omission_still_fetches(self):
        root = self.temp()
        result = run_cells.run(root, cells=[RICH_CELL], clock=clock)
        manifest = manifest_of(root, result.run_id)
        self.assertTrue(manifest["config"]["enrich"])
        self.assertGreater(manifest["request_accounting"]["target_fetch_owners"], 0)
        self.assertIn("target_http_attempts", manifest["request_accounting"])

    def test_omitted_preflight_is_an_empty_array(self):
        root = self.temp()
        result = run_cells.run(root, cells=[SMALL_CELL], clock=clock)
        self.assertEqual(manifest_of(root, result.run_id)["source_preflight"], [])

    def test_supplied_preflight_rows_reach_the_manifest_unchanged(self):
        rows = [{"source_id": "producthunt", "result": "ok",
                 "url": "https://www.producthunt.com/feed", "http_status": 200},
                {"source_id": "nvidia-blog", "result": "infrastructure_error",
                 "reason": "timeout", "http_status": None}]
        root = self.temp()
        result = run_cells.run(root, cells=[SMALL_CELL], clock=clock,
                               source_preflight=rows)
        got = manifest_of(root, result.run_id)["source_preflight"]
        self.assertEqual(len(got), 2)
        self.assertEqual({row["source_id"] for row in got},
                         {"producthunt", "nvidia-blog"})
        self.assertEqual({row["result"] for row in got},
                         {"ok", "infrastructure_error"})

    def test_the_driver_assembles_no_preflight_row(self):
        source = open(os.path.join(ROOT, "src", "harvest", "run_cells.py"),
                      encoding="utf-8").read()
        self.assertNotIn(".preflight(", source)


# -------------------------------------------------------- state-root refusals
class TestStateRootValidation(TempRoots):
    def test_a_valid_external_path_is_accepted_and_not_created(self):
        external = os.path.join(self.temp("outside_"), "stage9")
        self.assertFalse(os.path.exists(external))
        resolved = cli.validate_state_root(external)
        self.assertEqual(os.path.normcase(resolved),
                         os.path.normcase(os.path.normpath(external)))
        self.assertFalse(os.path.exists(external),
                         "validation must not create the retained root")

    def test_spaces_survive(self):
        external = os.path.join(self.temp("out side_"), "a b", "stage 9")
        self.assertIn(" ", cli.validate_state_root(external))

    def test_empty_and_missing_are_refused(self):
        for bad in (None, "", "   ", 17):
            with self.assertRaises(cli.CliError):
                cli.validate_state_root(bad)

    def test_a_relative_path_is_refused(self):
        for bad in ("out", os.path.join("..", "out"), "./out"):
            with self.assertRaises(cli.CliError):
                cli.validate_state_root(bad)

    def test_the_repository_root_is_refused(self):
        with self.assertRaises(cli.CliError):
            cli.validate_state_root(ROOT)

    def test_a_descendant_of_the_repository_is_refused(self):
        with self.assertRaises(cli.CliError):
            cli.validate_state_root(os.path.join(ROOT, "tmp_stage9"))

    def test_the_four_prohibited_runtime_paths_are_refused(self):
        for prohibited in cli.PROHIBITED_RUNTIME_PATHS:
            with self.assertRaises(cli.CliError):
                cli.validate_state_root(os.path.join(ROOT, prohibited))

    def test_traversal_back_into_the_repository_is_refused(self):
        sneaky = os.path.join(ROOT, "..", os.path.basename(ROOT), "state")
        with self.assertRaises(cli.CliError):
            cli.validate_state_root(sneaky)

    def test_a_sibling_with_a_shared_prefix_is_not_treated_as_inside(self):
        sibling = ROOT + "-elsewhere"
        self.assertEqual(os.path.normcase(cli.validate_state_root(sibling)),
                         os.path.normcase(os.path.normpath(sibling)))

    def test_validation_creates_nothing_anywhere(self):
        external = os.path.join(self.temp("outside_"), "stage9")
        cli.validate_state_root(external)
        self.assertEqual(listing(os.path.dirname(external)), [])


# ------------------------------------------------------------ live transport
class TestLiveTransportConstruction(TempRoots):
    def test_it_yields_default_opener_real_sleep_and_a_locks_lease_root(self):
        import time as time_mod
        external = os.path.join(self.temp("outside_"), "stage9")
        transport = cli.live_transport(external)
        self.assertIs(transport.opener, httpclient.default_opener)
        self.assertIs(transport.sleep, time_mod.sleep)
        self.assertEqual(transport.lease_root,
                         os.path.join(os.path.normpath(external), "locks"))

    def test_construction_creates_no_directory_and_issues_no_request(self):
        external = os.path.join(self.temp("outside_"), "stage9")
        transport = cli.live_transport(external)
        self.assertFalse(os.path.exists(transport.lease_root))
        self.assertFalse(os.path.exists(external))

    def test_it_refuses_a_repository_state_root(self):
        with self.assertRaises(cli.CliError):
            cli.live_transport(os.path.join(ROOT, "state", "taxonomy_harvest"))

    def test_the_live_transport_is_inert_until_an_operational_handler_calls_it(self):
        """No non-operational path may reach the network decision.

        This was `test_no_operational_command_calls_it` until S9-2, and it
        asserted `cli.COMMANDS == {}` — a snapshot of a checkpoint where nothing
        was implemented yet, and therefore spent the moment `preflight-sources`
        was registered. Forbidding *every* operational caller was always the
        wrong claim: an operational command reaching the network is the point of
        the constructor, and S9-3 and S9-6 will add two more approved callers.

        The permanent property is the complement, and it is what this now proves:
        importing the module, building a parser, asking for help, naming an
        unimplemented command or passing a bad argument must ALL leave the
        constructor untouched. Only a handler that has been approved and
        registered may call it, and deliberately.

        That the valid `preflight-sources` path really does use the live
        transport, and really does clean up its lease root, is proved by
        `test_preflight.py`, which owns that command.
        """
        # Import time: proved statically, because a behavioural probe cannot
        # observe an import that already happened. No module-level statement may
        # call the constructor.
        with open(CLI_PATH, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in tree.body:
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    name = getattr(inner.func, "id", None) or getattr(
                        inner.func, "attr", None)
                    self.assertNotEqual(
                        name, "live_transport",
                        "importing cli.py must not construct a transport")

        calls = []
        real = cli.live_transport
        cli.live_transport = lambda *a, **kw: (calls.append(a), real(*a, **kw))[1]
        self.addCleanup(setattr, cli, "live_transport", real)

        # Parser construction.
        cli.add_state_root_argument(cli.build_parser("smoke", "x"))

        # Help, an unknown command, every command still declared planned, and an
        # operational command whose arguments are refused. Help legitimately
        # succeeds; the rest legitimately do not. Either way none of them may
        # construct a transport, which is what the final assertion checks.
        quiet = io.StringIO()
        with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
            self.assertEqual(cli.main(["--help"]), 0)
            self.assertEqual(cli.main(["-h"]), 0)
            for argv in ([], ["definitely-not-a-command"],
                         ["preflight-sources", "--sources", "nope"],
                         *[[name] for name in sorted(cli.PLANNED_COMMANDS)]):
                self.assertEqual(cli.main(list(argv)), 2,
                                 "%r must be refused with exit 2" % (argv,))

        self.assertEqual(calls, [],
                         "a non-operational or refused path constructed a live "
                         "transport: %r" % (calls,))


# ----------------------------------------------------------- no-network proof
class TestNothingGoesOut(TempRoots):
    def test_the_sentinel_is_genuinely_wired_and_would_trip(self):
        """Non-vacuity: prove the boundary the other test watches is real."""
        sentinel = Sentinel()
        lease = self.temp("caller_leases_")
        transport = run_cells.Transport(opener=sentinel, sleep=lambda s: None,
                                        lease_root=lease)
        run_cells.run(self.temp(), cells=[SMALL_CELL], clock=clock,
                      transport=transport)
        self.assertGreater(len(sentinel.calls), 0,
                           "the opener seam must actually reach the opener, or "
                           "the no-network assertion below proves nothing")

    def test_a_default_run_never_reaches_default_opener(self):
        sentinel = Sentinel()
        original = httpclient.default_opener
        httpclient.default_opener = sentinel
        try:
            run_cells.run(self.temp(), clock=clock)
        finally:
            httpclient.default_opener = original
        self.assertEqual(sentinel.calls, [],
                         "a default run must not reach the live opener")

    def test_a_default_run_never_sleeps_for_real(self):
        import time as time_mod
        sleeper = CountingSleep()
        original = time_mod.sleep
        time_mod.sleep = sleeper
        try:
            run_cells.run(self.temp(), cells=[SMALL_CELL], clock=clock)
        finally:
            time_mod.sleep = original
        self.assertEqual(sleeper.calls, [])

    def test_no_external_stage_9_root_was_created(self):
        for suspect in ("state/taxonomy_harvest", "data/harvested", "runs",
                        "LATEST_RUN_ID"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, suspect)))


# ------------------------------------------------------------- CLI behaviour
def run_cli(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "src.harvest.cli", *args],
                          cwd=cwd or ROOT, capture_output=True, text=True)


class TestCliSurface(unittest.TestCase):
    def test_help_exits_zero(self):
        proc = run_cli("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("usage:", proc.stdout)

    def test_no_arguments_exits_two(self):
        self.assertEqual(run_cli().returncode, 2)

    def test_an_unknown_command_exits_nonzero(self):
        proc = run_cli("definitely-not-a-command")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unknown command", proc.stderr)

    def test_no_planned_command_falsely_succeeds(self):
        for name in sorted(cli.PLANNED_COMMANDS):
            proc = run_cli(name)
            self.assertNotEqual(
                proc.returncode, 0,
                "%r must not exit 0: it is not implemented" % name)
            self.assertIn("NOT implemented", proc.stderr)

    def test_registered_and_planned_commands_partition_the_stage_9_surface(self):
        """The durable registry contract, valid at every Stage 9 checkpoint.

        This replaces two S9-1 snapshots — `COMMANDS == {}` and a fixed
        `PLANNED_COMMANDS` list — both of which were spent the moment S9-2
        registered its first command, and both of which would have been spent
        again at S9-3, S9-4 and S9-6. Neither is replaced by a new count: an
        assertion that exactly one command is registered is the same mistake with
        a different number.

        What is permanently true is a PARTITION. Every Stage 9 command is either
        implemented or planned, never both and never neither, and no seventh
        command exists. That statement survives each command moving from one side
        to the other, and it still fails loudly on the two things worth catching:
        a command registered without a plan entry, and an approved command that
        quietly vanishes from both registries.

        Which commands are on which side at a given checkpoint is a
        checkpoint-specific fact, and it belongs to the suite that owns that
        checkpoint — `test_preflight.py` proves `preflight-sources` is
        operational at S9-2.
        """
        surface = {"preflight-sources", "smoke", "validate", "compare-runs",
                   "diff", "linkcheck"}
        registered = set(cli.COMMANDS)
        planned = set(cli.PLANNED_COMMANDS)

        self.assertEqual(registered & planned, set(),
                         "a command cannot be both implemented and planned")
        self.assertEqual(registered | planned, surface)
        self.assertEqual(surface - (registered | planned), set(),
                         "an approved Stage 9 command disappeared from both "
                         "registries")
        self.assertEqual(registered - surface, set(),
                         "an unplanned command was registered")

        for name, handler in cli.COMMANDS.items():
            self.assertTrue(callable(handler),
                            "%r is registered but is not callable" % name)
        for name, owner in cli.PLANNED_COMMANDS.items():
            self.assertTrue(isinstance(owner, str) and owner.strip(),
                            "%r is planned but names no owning checkpoint" % name)

    def test_help_reports_implemented_and_planned_status_honestly(self):
        proc = run_cli("--help")
        self.assertEqual(proc.returncode, 0)
        for name in cli.COMMANDS:
            self.assertIn(name, proc.stdout,
                          "%r is implemented but absent from help" % name)
        for name, owner in cli.PLANNED_COMMANDS.items():
            self.assertIn(name, proc.stdout,
                          "%r is planned but absent from help" % name)
            self.assertIn(owner, proc.stdout,
                          "help must name the checkpoint that owns %r" % name)
        self.assertIn("NOT implemented", proc.stdout)

    def test_parser_helpers_exist_for_later_checkpoints(self):
        parser = cli.add_state_root_argument(cli.build_parser("smoke", "x"))
        args = parser.parse_args(["--state-root", "/tmp/a b"])
        self.assertEqual(args.state_root, "/tmp/a b")


class TestDispatcherShell(unittest.TestCase):
    def setUp(self):
        if shutil.which("bash") is None:
            self.skipTest("bash not available")

    def source(self):
        with open(HARVEST_SH, encoding="utf-8") as handle:
            return handle.read()

    def test_it_is_dispatch_only(self):
        src = self.source()
        for forbidden in ("eval", "git ", "curl", "wget", "mktemp", "$(cat",
                          "getopts", "while ", "urllib"):
            self.assertNotIn(forbidden, src,
                             "harvest.sh must stay a dispatcher: %r" % forbidden)
        self.assertIn("set -euo pipefail", src)
        self.assertIn('exec python -m src.harvest.cli "$@"', src)

    def test_it_documents_no_second_usage(self):
        self.assertNotIn("usage()", self.source())

    def test_help_through_the_shell_exits_zero(self):
        proc = subprocess.run(["bash", HARVEST_SH, "--help"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)

    def test_unknown_command_through_the_shell_preserves_the_exit_code(self):
        proc = subprocess.run(["bash", HARVEST_SH, "nope"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)

    def test_arguments_are_forwarded_verbatim_including_spaces(self):
        weird = "a b/c d"
        proc = subprocess.run(["bash", HARVEST_SH, weird],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn(weird, proc.stderr)


# ---------------------------------------------------------------- AST boundary
class TestCliJudgesNothing(unittest.TestCase):
    """`cli.py` routes and validates. Every decision has a committed owner."""

    FORBIDDEN_IMPORTS = {
        "classify", "verify", "facetassign", "dedupe", "extract", "coverage",
        "facets", "records", "urlkey", "slug", "aliases", "pool", "schema",
        "targetfetch", "sourcecache", "ledger", "scheduler", "budget",
        "request_key", "domainlease", "fixtures",
    }
    FORBIDDEN_DEF_SUBSTRINGS = (
        "classif", "score", "verif", "dedup", "canonical", "normalize",
        "normalise", "token", "match", "serial", "facet", "extract", "adjudicat",
    )

    def setUp(self):
        with open(CLI_PATH, encoding="utf-8") as handle:
            self.src = handle.read()
        self.tree = ast.parse(self.src)

    def imported_names(self):
        names = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[-1])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    names.add(alias.name.split(".")[-1])
        return names

    def test_it_imports_no_judgement_module(self):
        overlap = self.imported_names() & self.FORBIDDEN_IMPORTS
        self.assertEqual(overlap, set(),
                         "cli.py must not import judgement modules: %s" % overlap)

    def test_the_seam_imports_are_exactly_the_two_expected(self):
        self.assertIn("httpclient", self.imported_names())
        self.assertIn("run_cells", self.imported_names())

    def test_it_defines_no_matcher_scorer_or_serializer(self):
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                low = node.name.lower()
                for bad in self.FORBIDDEN_DEF_SUBSTRINGS:
                    self.assertNotIn(
                        bad, low,
                        "cli.py defines %r, which reads as pipeline judgement"
                        % node.name)

    def test_it_defines_no_second_serializer(self):
        self.assertNotIn("json.dumps", self.src)
        self.assertNotIn("import json", self.src)

    def test_it_compiles_no_regex_and_owns_no_vocabulary(self):
        self.assertNotIn("re.compile", self.src)
        self.assertNotIn("import re", self.src)

    def test_it_opens_no_config_or_schema_file(self):
        for bad in ("config/harvest", "schemas/harvest", "policy.v1.json",
                    "precedence.v1.json"):
            self.assertNotIn(bad, self.src)

    def test_it_starts_no_thread_process_or_async_work(self):
        for bad in ("threading", "multiprocessing", "asyncio", "concurrent."):
            self.assertNotIn(bad, self.src)


if __name__ == "__main__":
    unittest.main()
