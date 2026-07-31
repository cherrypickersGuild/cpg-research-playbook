#!/usr/bin/env python3
"""test_recovery.py — recovery and re-run semantics (S5-7).

S5-6 proved a healthy run. This proves the unhealthy ones, and defines what a
second run does. Five properties, each asserted by actually breaking something
rather than by reading the code:

  * NOTHING PARTIAL IS EVER READABLE. Interrupt a run anywhere — before a rename,
    a third of the way through, with an OSError or with a KeyboardInterrupt — and
    every artifact on disk is either the complete previous one or the complete new
    one. There is no third state, and every file left behind still validates.
  * THE POINTER SURVIVES THE RUN THAT FAILED. `LATEST_RUN_ID` names a run whose
    manifest exists and validates, or it names nothing. A run that dies after
    writing its manifest but before advancing the pointer leaves the pointer on
    the PREVIOUS run — the manifest is orphaned, which is the safe direction.
  * THE SWEEPER PROVES OWNERSHIP. It removes the temp files this run created and
    refuses everything else: a foreign `.tmp_*` is left alone, and a finished
    artifact is never a candidate. A glob-and-delete sweeper would destroy another
    writer's in-flight file, which is a worse failure than the debris it cleans.
  * A FINISHED RUN IS NEVER RE-RUN. Repeating a `run_id` that already has a
    manifest is refused BEFORE the first byte is written, so the refusal costs the
    tree nothing — no double-counted ledger, no replaced rejection log.
  * A SECOND RUN CONTINUES DETERMINISTICALLY. Over unchanged inputs it reproduces
    byte-identical cell and topic artifacts modulo the run id and the stamp, the
    ledger ACCUMULATES without losing `first_seen_at`, a terminal outcome stays
    terminal, and the previous run's directory is left untouched.

Offline and temp-rooted throughout: no network, no concurrency, no production
state. Run via tests/test_taxonomy_recovery.sh.
"""
import datetime
import glob
import hashlib
import inspect
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import artifacts, run_cells, schema                  # noqa: E402

# Two distinct instants: a run id is derived from the clock, so two runs in one
# process need two instants to be two runs rather than a refused repeat.
T1 = datetime.datetime(2026, 7, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)
T2 = datetime.datetime(2026, 7, 31, 9, 30, 0, tzinfo=datetime.timezone.utc)
STAMP1 = "2026-07-30T12:00:00Z"
STAMP2 = "2026-07-31T09:30:00Z"

# One cell keeps the interruption tests fast and, more usefully, small enough
# that the exact file set can be asserted by hand. `benchmark-and-datasets` is
# the cell the corpus actually accepts records in, so the ledger tests have
# both an `accepted` and a `rejected` outcome to follow across runs.
CELL = "research-and-models__benchmark-and-datasets"
TOPIC = "research-and-models"


# --------------------------------------------------------------------- helpers
def listing(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            out.append(os.path.relpath(os.path.join(dirpath, name), root)
                       .replace("\\", "/"))
    return sorted(out)


def temps_under(root):
    return sorted(rel for rel in listing(root)
                  if os.path.basename(rel).startswith(artifacts.TEMP_PREFIX))


def read(root, rel):
    with open(os.path.join(root, rel), "rb") as handle:
        return handle.read()


def load(root, rel):
    return json.loads(read(root, rel).decode("utf-8"))


def tree_hash(root):
    digest = hashlib.sha256()
    for rel in listing(root):
        digest.update(rel.encode("utf-8"))
        digest.update(read(root, rel))
    return digest.hexdigest()


def snapshot(root):
    """Every path and its bytes, so "unchanged" can be asserted exactly."""
    return {rel: read(root, rel) for rel in listing(root)}


def diff_paths(left, right, path=""):
    """Every JSON path at which two documents disagree.

    Used instead of normalizing the fields a second run is allowed to change: a
    normalizer hides anything it was not told about, whereas this ENUMERATES the
    difference and lets the test assert the set exactly. If a second run ever
    starts moving a fifth field, that is a failure rather than a silent pass.
    """
    out = []
    if type(left) is not type(right):
        return [path or "/"]
    if isinstance(left, dict):
        for key in sorted(set(left) | set(right)):
            out.extend(diff_paths(left.get(key), right.get(key),
                                  "%s/%s" % (path, key)))
    elif isinstance(left, list):
        if len(left) != len(right):
            return [path or "/"]
        for index, (a, b) in enumerate(zip(left, right)):
            out.extend(diff_paths(a, b, "%s[%d]" % (path, index)))
    elif left != right:
        out.append(path or "/")
    return out


def leaf_names(paths):
    """The field names a difference set touches, with list indices dropped."""
    return {p.rsplit("/", 1)[-1] for p in paths}


def schema_for(rel):
    parts = rel.split("/")
    if parts[-1] == "manifest.json":
        return "run_manifest.v1.json"
    if parts[-1] == "coverage.json":
        return "coverage_report.v1.json"
    if parts[-1] == "alias_conflicts.json":
        return "alias_conflict.v1.json"
    return {"cells": "cell_artifact.v1.json", "topics": "topic_artifact.v1.json",
            "rejections": "rejection.v1.json", "ledgers": "ledger.v1.json"}[parts[-2]]


class RecoveryCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s5_recovery_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    # ------------------------------------------------------------------ runs
    def run_once(self, clock=T1, **kw):
        kw.setdefault("cells", [CELL])
        return run_cells.run(self.root, clock=lambda: clock, **kw)

    # -------------------------------------------------------------- breakage
    def break_replace(self, exc, after=0):
        """Make artifact renames fail, optionally after N successful ones.

        Scoped to destinations UNDER THE ARTIFACT ROOT on purpose. `HttpClient`'s
        domain leases are written atomically too, so an unscoped counter spends
        its budget on lease files during discovery and the run dies before it ever
        writes an artifact — the test would then pass while proving nothing about
        a half-written tree. Counting only artifact writes is what makes `after=2`
        mean "two artifacts landed, then it died".
        """
        real = os.replace
        root = os.path.abspath(self.root)
        state = {"n": 0}

        def boom(src, dst):
            if not os.path.abspath(dst).startswith(root):
                return real(src, dst)          # lease scratch, not an artifact
            if state["n"] >= after:
                raise exc
            state["n"] += 1
            return real(src, dst)

        os.replace = boom
        self.addCleanup(setattr, os, "replace", real)
        return state

    def break_unlink(self):
        """Make cleanup itself fail — the only way a temp file outlives its write."""
        real = os.unlink
        active = {"on": True}

        def boom(path, *a, **kw):
            if active["on"]:
                raise OSError("simulated: cannot remove %s" % path)
            return real(path, *a, **kw)

        os.unlink = boom
        self.addCleanup(setattr, os, "unlink", real)
        return active

    # ------------------------------------------------------------ assertions
    def assertEveryArtifactValidates(self, root=None):
        root = root or self.root
        for rel in listing(root):
            if rel == artifacts.LATEST_RUN_ID_NAME:
                continue
            self.assertEqual(schema.validate(load(root, rel), schema_for(rel)), [],
                             "%s is not a complete valid artifact" % rel)

    def assertNoDebris(self, root=None):
        self.assertEqual(temps_under(root or self.root), [])


# --------------------------------------------------- interruption before rename
class TestInterruptBeforeRename(RecoveryCase):
    def test_the_previous_run_is_untouched(self):
        first = self.run_once(T1)
        before = snapshot(self.root)

        self.break_replace(OSError("simulated crash"))
        with self.assertRaises(OSError):
            self.run_once(T2)

        after = {rel: read(self.root, rel) for rel in before}
        self.assertEqual(after, before, "the previous run's bytes changed")
        self.assertEqual(artifacts.read_latest_run_id(self.root), first.run_id)

    def test_the_pointer_still_names_a_valid_run(self):
        first = self.run_once(T1)
        self.break_replace(OSError("simulated crash"))
        with self.assertRaises(OSError):
            self.run_once(T2)
        self.assertEqual(artifacts.verify_latest_run_id(self.root), first.run_id)

    def test_no_temp_debris_survives(self):
        self.run_once(T1)
        self.break_replace(OSError("simulated crash"))
        with self.assertRaises(OSError):
            self.run_once(T2)
        self.assertNoDebris()

    def test_the_failed_run_wrote_no_readable_artifact(self):
        self.run_once(T1)
        self.break_replace(OSError("simulated crash"))
        with self.assertRaises(OSError):
            self.run_once(T2)
        second = artifacts.run_id(clock=lambda: T2)
        under_second = [rel for rel in listing(self.root)
                        if rel.startswith("runs/%s/" % second)]
        self.assertEqual(under_second, [])

    def test_a_first_run_that_crashes_leaves_no_pointer(self):
        self.break_replace(OSError("simulated crash"))
        with self.assertRaises(OSError):
            self.run_once(T1)
        self.assertIsNone(artifacts.read_latest_run_id(self.root))
        self.assertIsNone(artifacts.verify_latest_run_id(self.root))
        self.assertNoDebris()


# ------------------------------------------------------ interruption part-way
class TestInterruptPartWayThrough(RecoveryCase):
    def crash_after(self, n, exc=None):
        self.run_once(T1)
        self.break_replace(exc or OSError("simulated crash"), after=n)
        with self.assertRaises(type(exc) if exc else OSError):
            self.run_once(T2)
        return artifacts.run_id(clock=lambda: T2)

    def test_the_interruption_really_was_part_way_through(self):
        # Without this the rest of the class could pass vacuously on a run that
        # died before writing anything at all.
        second = self.crash_after(2)
        written = [rel for rel in listing(self.root)
                   if rel.startswith("runs/%s/" % second)]
        self.assertEqual(len(written), 2, written)

    def test_the_cross_run_ledger_was_not_half_updated(self):
        # The crash lands before the ledger write, so the ledger still reflects
        # run 1 alone. A run that died must not leave the durable cross-run
        # memory claiming it saw the corpus twice.
        self.crash_after(2)
        for entry in load(self.root, "ledgers/%s.json" % CELL)["entries"]:
            self.assertEqual(entry["seen_count"], 1, entry["identity_url"])
            self.assertEqual(entry["last_seen_at"], STAMP1)

    def test_everything_on_disk_is_still_a_complete_valid_artifact(self):
        # The property that matters: not "the run succeeded", but "nothing
        # half-written is readable". Every file, old or new, still validates.
        self.crash_after(2)
        self.assertEveryArtifactValidates()

    def test_the_pointer_did_not_move(self):
        first = self.run_once(T1)
        self.break_replace(OSError("simulated crash"), after=2)
        with self.assertRaises(OSError):
            self.run_once(T2)
        self.assertEqual(artifacts.verify_latest_run_id(self.root), first.run_id)

    def test_the_incomplete_run_has_no_manifest(self):
        self.crash_after(2)
        second = artifacts.run_id(clock=lambda: T2)
        self.assertFalse(os.path.exists(
            artifacts.run_manifest_path(self.root, second)))

    def test_no_debris_after_a_partial_run(self):
        self.crash_after(2)
        self.assertNoDebris()

    def test_a_keyboard_interrupt_behaves_the_same(self):
        # KeyboardInterrupt is a BaseException; an `except Exception` anywhere in
        # the write path would leak a temp file on every Ctrl-C.
        first = self.run_once(T1)
        self.break_replace(KeyboardInterrupt(), after=1)
        with self.assertRaises(KeyboardInterrupt):
            self.run_once(T2)
        self.assertNoDebris()
        self.assertEqual(artifacts.verify_latest_run_id(self.root), first.run_id)
        self.assertEveryArtifactValidates()


# ------------------------------------- interruption between manifest and pointer
class TestInterruptBetweenManifestAndPointer(RecoveryCase):
    def crash_at_pointer(self):
        real = artifacts.write_latest_run_id

        def boom(root, run_id_value):
            raise OSError("simulated crash advancing the pointer")

        artifacts.write_latest_run_id = boom
        self.addCleanup(setattr, artifacts, "write_latest_run_id", real)

    def test_the_pointer_still_names_the_previous_run(self):
        first = self.run_once(T1)
        self.crash_at_pointer()
        with self.assertRaises(OSError):
            self.run_once(T2)
        self.assertEqual(artifacts.read_latest_run_id(self.root), first.run_id)
        self.assertEqual(artifacts.verify_latest_run_id(self.root), first.run_id)

    def test_the_orphaned_manifest_is_complete_and_valid(self):
        # The manifest landing without the pointer is the SAFE direction: an
        # orphaned complete manifest is inert, whereas a pointer naming a
        # manifest that does not exist breaks the pointer's only promise.
        self.run_once(T1)
        self.crash_at_pointer()
        with self.assertRaises(OSError):
            self.run_once(T2)
        second = artifacts.run_id(clock=lambda: T2)
        doc = load(self.root, "runs/%s/manifest.json" % second)
        self.assertEqual(schema.validate(doc, "run_manifest.v1.json"), [])
        self.assertEqual(doc["harvest_run_id"], second)

    def test_no_pointer_at_all_when_the_first_run_dies_there(self):
        self.crash_at_pointer()
        with self.assertRaises(OSError):
            self.run_once(T1)
        self.assertIsNone(artifacts.read_latest_run_id(self.root))

    def test_the_orphaned_run_is_refused_rather_than_resumed(self):
        # No resume policy is invented here: the run that owns that manifest is
        # finished as far as the tree is concerned, so repeating it is refused and
        # the operator runs a fresh run_id.
        self.run_once(T1)
        self.crash_at_pointer()
        with self.assertRaises(OSError):
            self.run_once(T2)
        with self.assertRaises(run_cells.RunCellsError):
            self.run_once(T2)


# ------------------------------------------------------------------- sweeper
class TestSweeper(RecoveryCase):
    def path(self, name):
        return os.path.join(self.root, name)

    def test_a_stale_temp_is_swept_and_a_finished_artifact_is_not(self):
        target = self.path("a.json")
        artifacts.write_atomic(target, b"FINISHED\n")

        with artifacts.write_journal(owner="run-1") as journal:
            self.break_replace(OSError("simulated crash"))
            unlink = self.break_unlink()
            with self.assertRaises(OSError):
                artifacts.write_atomic(target, b"REPLACEMENT\n")
            # Cleanup could not complete, so the temp file outlived its write.
            self.assertEqual(len(temps_under(self.root)), 1)
            unlink["on"] = False

        self.assertEqual(temps_under(self.root), [], "the temp was not swept")
        self.assertEqual(len(journal.swept), 1)
        self.assertEqual(read(self.root, "a.json"), b"FINISHED\n",
                         "the finished artifact was damaged")

    def test_it_removes_only_what_it_watched_being_created(self):
        # A foreign temp file — another run's in-flight write — is left strictly
        # alone. Globbing for .tmp_* and deleting would destroy it.
        foreign = self.path(artifacts.TEMP_PREFIX + "deadbeef_foreign.json")
        with open(foreign, "wb") as handle:
            handle.write(b"NOT MINE\n")
        journal = artifacts.WriteJournal(owner="run-1")
        self.assertEqual(journal.sweep(), [])
        self.assertTrue(os.path.exists(foreign))

    def test_it_refuses_to_remove_a_path_that_is_not_a_temp_file(self):
        # Belt and braces: even told to, the sweeper only ever unlinks a name
        # carrying the temp prefix, so it cannot be talked into deleting an
        # artifact by a bad entry.
        target = self.path("a.json")
        artifacts.write_atomic(target, b"FINISHED\n")
        journal = artifacts.WriteJournal(owner="run-1")
        journal.note(target)
        self.assertEqual(journal.sweep(), [])
        self.assertTrue(os.path.exists(target))

    def test_sweeping_twice_is_a_no_op(self):
        journal = artifacts.WriteJournal(owner="run-1")
        temp = self.path(artifacts.TEMP_PREFIX + "abc_a.json")
        with open(temp, "wb") as handle:
            handle.write(b"x")
        journal.note(temp)
        self.assertEqual(len(journal.sweep()), 1)
        self.assertEqual(len(journal.sweep()), 1, "sweep is not idempotent")
        self.assertFalse(os.path.exists(temp))

    def test_a_temp_that_cannot_be_removed_stays_outstanding_and_does_not_raise(self):
        journal = artifacts.WriteJournal(owner="run-1")
        temp = self.path(artifacts.TEMP_PREFIX + "abc_a.json")
        with open(temp, "wb") as handle:
            handle.write(b"x")
        journal.note(temp)
        self.break_unlink()
        self.assertEqual(journal.sweep(), [])            # never raises
        self.assertEqual(journal.outstanding, (temp,))

    def test_a_renamed_temp_leaves_nothing_outstanding(self):
        with artifacts.write_journal(owner="run-1") as journal:
            artifacts.write_atomic(self.path("a.json"), b"{}\n")
            self.assertEqual(journal.outstanding, ())

    def test_the_journal_refuses_to_nest(self):
        # Two journals cannot both own the same temp file, so overlapping runs in
        # one process are refused rather than allowed to cross-attribute.
        with artifacts.write_journal(owner="run-1"):
            with self.assertRaises(artifacts.ArtifactError):
                with artifacts.write_journal(owner="run-2"):
                    pass

    def test_the_journal_is_released_even_when_the_body_raises(self):
        with self.assertRaises(ValueError):
            with artifacts.write_journal(owner="run-1"):
                raise ValueError("boom")
        with artifacts.write_journal(owner="run-2") as journal:
            self.assertEqual(journal.owner, "run-2")

    def test_writes_outside_a_journal_still_work(self):
        # The journal is optional: S5-1's writer is unchanged without one.
        artifacts.write_atomic(self.path("a.json"), b"{}\n")
        self.assertEqual(read(self.root, "a.json"), b"{}\n")

    def test_a_clean_run_sweeps_nothing(self):
        result = self.run_once(T1)
        self.assertEqual(result.swept, ())
        self.assertNoDebris()


# ------------------------------------------------------------- re-run refusal
class TestRepeatedRunIsRefused(RecoveryCase):
    def test_repeating_a_finished_run_id_raises(self):
        self.run_once(T1)
        with self.assertRaises(run_cells.RunCellsError):
            self.run_once(T1)

    def test_the_refusal_names_the_run_and_the_manifest(self):
        first = self.run_once(T1)
        with self.assertRaises(run_cells.RunCellsError) as caught:
            self.run_once(T1)
        self.assertIn(first.run_id, str(caught.exception))
        self.assertIn("manifest", str(caught.exception))

    def test_the_refusal_changes_nothing_on_disk(self):
        # Refused BEFORE the first byte: had it been refused at publication, the
        # ledger would already have counted every candidate twice.
        self.run_once(T1)
        before = tree_hash(self.root)
        with self.assertRaises(run_cells.RunCellsError):
            self.run_once(T1)
        self.assertEqual(tree_hash(self.root), before)

    def test_the_ledger_did_not_double_count(self):
        self.run_once(T1)
        entries = load(self.root, "ledgers/%s.json" % CELL)["entries"]
        with self.assertRaises(run_cells.RunCellsError):
            self.run_once(T1)
        again = load(self.root, "ledgers/%s.json" % CELL)["entries"]
        self.assertEqual(again, entries)
        for entry in again:
            self.assertEqual(entry["seen_count"], 1)

    def test_a_fresh_run_id_is_accepted(self):
        self.run_once(T1)
        second = self.run_once(T2)
        self.assertEqual(artifacts.verify_latest_run_id(self.root), second.run_id)

    def test_run_is_finished_is_the_predicate_publish_run_enforces(self):
        first = self.run_once(T1)
        self.assertTrue(artifacts.run_is_finished(self.root, first.run_id))
        self.assertFalse(artifacts.run_is_finished(self.root, "20990101T000000Z-1"))


# ------------------------------------------------------ deterministic continuation
_CONSECUTIVE = {}


def consecutive():
    """Two consecutive runs into ONE root, shared by the re-run assertions."""
    if not _CONSECUTIVE:
        root = tempfile.mkdtemp(prefix="s5_recovery_consecutive_")
        _CONSECUTIVE["root"] = root
        _CONSECUTIVE["first"] = run_cells.run(root, cells=[CELL], clock=lambda: T1)
        _CONSECUTIVE["second"] = run_cells.run(root, cells=[CELL], clock=lambda: T2)
    return _CONSECUTIVE["root"], _CONSECUTIVE["first"], _CONSECUTIVE["second"]


def tearDownModule():
    if _CONSECUTIVE:
        shutil.rmtree(_CONSECUTIVE["root"], ignore_errors=True)


class TestSecondRun(unittest.TestCase):
    def setUp(self):
        self.root, self.first, self.second = consecutive()

    # The four fields a second run is allowed to move, and nothing else. All
    # four are derived from the run instant, which is the one input that really
    # did change between the two runs: the run id encodes it, the two stamps are
    # it, and `freshness_score` is a function of "how old is this item NOW".
    # Five, exactly. `last_checked_at` joined at S6-5, which is what plan §10
    # predicted when target fetching arrived: the difference set grows to five and
    # is still ENUMERATED rather than normalized away, so a sixth moving field
    # fails here instead of passing silently.
    CLOCK_DERIVED = {"generated_at", "harvest_run_id", "discovered_at",
                     "freshness_score", "last_checked_at"}

    def artifact(self, kind, run_id, name):
        return load(self.root, "runs/%s/%s/%s.json" % (run_id, kind, name))

    def test_the_cell_artifact_differs_only_in_clock_derived_fields(self):
        differences = diff_paths(self.artifact("cells", self.first.run_id, CELL),
                                 self.artifact("cells", self.second.run_id, CELL))
        self.assertTrue(differences, "the two runs must at least differ in run id")
        self.assertEqual(leaf_names(differences), self.CLOCK_DERIVED)

    def test_the_topic_artifact_differs_only_in_clock_derived_fields(self):
        differences = diff_paths(self.artifact("topics", self.first.run_id, TOPIC),
                                 self.artifact("topics", self.second.run_id, TOPIC))
        self.assertTrue(differences)
        self.assertEqual(leaf_names(differences), self.CLOCK_DERIVED)

    def test_the_re_run_did_not_re_judge_anything(self):
        # relevance, quality and audience_fit are functions of the document, not
        # of when it was read, so a second run must reproduce them exactly. Only
        # freshness is allowed to move, and it is asserted separately.
        first = self.artifact("cells", self.first.run_id, CELL)["records"]
        second = self.artifact("cells", self.second.run_id, CELL)["records"]
        self.assertEqual(len(first), len(second))
        for a, b in zip(first, second):
            for field in ("record_id", "content_id", "identity_url", "topic",
                          "primary_category", "cell_id", "classification",
                          "relevance_score", "quality_score", "audience_fit_score"):
                self.assertEqual(a.get(field), b.get(field),
                                 "%s moved on a re-run" % field)

    def test_freshness_decayed_because_the_second_run_is_later(self):
        # The coupling is documented rather than hidden: an item read a day later
        # IS less fresh, and a re-run that reported the same freshness would be
        # the defect. Direction asserted, so the field cannot silently freeze.
        first = self.artifact("cells", self.first.run_id, CELL)["records"]
        second = self.artifact("cells", self.second.run_id, CELL)["records"]
        moved = 0
        for a, b in zip(first, second):
            if a.get("freshness_score") is None:
                continue
            self.assertLess(b["freshness_score"], a["freshness_score"])
            moved += 1
        self.assertGreater(moved, 0, "no record carried a freshness score")

    def test_the_cell_metadata_and_counts_are_reproduced(self):
        first = self.artifact("cells", self.first.run_id, CELL)["metadata"]
        second = self.artifact("cells", self.second.run_id, CELL)["metadata"]
        self.assertEqual(first, second)

    def test_the_two_runs_have_different_ids(self):
        self.assertNotEqual(self.first.run_id, self.second.run_id)

    def test_the_record_set_is_identical(self):
        self.assertEqual([r["record_id"] for r in self.second.records],
                         [r["record_id"] for r in self.first.records])

    def test_the_first_runs_directory_is_left_intact(self):
        for rel in listing(self.root):
            if not rel.startswith("runs/%s/" % self.first.run_id):
                continue
            self.assertEqual(schema.validate(load(self.root, rel),
                                             schema_for(rel)), [], rel)

    def test_the_first_runs_manifest_still_names_the_first_run(self):
        doc = load(self.root, "runs/%s/manifest.json" % self.first.run_id)
        self.assertEqual(doc["harvest_run_id"], self.first.run_id)
        self.assertEqual(doc["started_at"], STAMP1)

    def test_the_pointer_advanced_to_the_second_run(self):
        self.assertEqual(artifacts.verify_latest_run_id(self.root),
                         self.second.run_id)

    def test_both_run_directories_exist(self):
        for run_id in (self.first.run_id, self.second.run_id):
            self.assertTrue(os.path.exists(
                artifacts.run_manifest_path(self.root, run_id)), run_id)

    def test_no_debris_after_two_runs(self):
        self.assertEqual(temps_under(self.root), [])

    def test_the_second_manifest_is_truthful_about_its_own_run(self):
        doc = load(self.root, "runs/%s/manifest.json" % self.second.run_id)
        self.assertEqual(doc["started_at"], STAMP2)
        self.assertEqual(doc["finished_at"], STAMP2)
        rows = {row["cell_id"]: row for row in doc["cells"]}
        self.assertEqual(rows[CELL]["status"], run_cells.STATUS_OK)
        # Every other configured cell is still honestly `not_run` in this run —
        # a previous run having covered it changes nothing about this one.
        self.assertEqual(
            sum(1 for r in doc["cells"] if r["status"] == artifacts.STATUS_NOT_RUN),
            len(artifacts.configured_cell_rows()) - 1)


# --------------------------------------------------------------- ledger across runs
class TestLedgerAccumulates(unittest.TestCase):
    def setUp(self):
        self.root, self.first, self.second = consecutive()
        self.entries = load(self.root, "ledgers/%s.json" % CELL)["entries"]

    def test_first_seen_at_survives_the_second_run(self):
        for entry in self.entries:
            self.assertEqual(entry["first_seen_at"], STAMP1, entry["identity_url"])

    def test_last_seen_at_advances(self):
        for entry in self.entries:
            self.assertEqual(entry["last_seen_at"], STAMP2, entry["identity_url"])

    def test_seen_count_incremented_once_per_run(self):
        for entry in self.entries:
            self.assertEqual(entry["seen_count"], 2, entry["identity_url"])

    def test_the_entry_count_did_not_grow(self):
        # The same corpus seen twice is the same set of URLs, not twice as many.
        self.assertEqual(len(self.entries), len(self.first.manifest["cells"] and
                                                self.entries))
        self.assertEqual(
            len(self.entries),
            {row["cell_id"]: row for row in
             self.first.manifest["cells"]}[CELL]["candidates"])

    def test_a_terminal_outcome_stays_terminal(self):
        for entry in self.entries:
            self.assertIn(entry["outcome"], ("accepted", "rejected"))

    def test_both_outcomes_are_represented(self):
        # Otherwise "a terminal outcome stays terminal" would be vacuous.
        outcomes = {entry["outcome"] for entry in self.entries}
        self.assertEqual(outcomes, {"accepted", "rejected"})

    def test_an_accepted_entry_keeps_its_record_id(self):
        for entry in self.entries:
            if entry["outcome"] == "accepted":
                self.assertTrue(entry.get("record_id"))

    def test_a_rejected_entry_keeps_its_reason(self):
        for entry in self.entries:
            if entry["outcome"] == "rejected":
                self.assertTrue(entry.get("rejection_reason"))

    def test_the_ledger_still_validates(self):
        doc = load(self.root, "ledgers/%s.json" % CELL)
        self.assertEqual(schema.validate(doc, "ledger.v1.json"), [])
        self.assertEqual(doc["updated_at"], STAMP2)

    def test_entries_stay_sorted_by_identity_url(self):
        urls = [entry["identity_url"] for entry in self.entries]
        self.assertEqual(urls, sorted(urls))


# ------------------------------------------------------- rejections across runs
class TestRejectionLogAcrossRuns(unittest.TestCase):
    """The rejection log is per-cell and per-RUN, and the schema says so.

    `rejection.v1.json` is `additionalProperties: false` and carries exactly one
    `harvest_run_id`, so a log merged across runs could not name the run that
    produced its entries, and its entries — which carry no run field — would
    become indistinguishable and grow without bound. The cross-run guarantee that
    matters, and that is asserted here, is that a run never clobbers a cell it did
    not run.
    """

    def setUp(self):
        self.root, self.first, self.second = consecutive()

    def test_the_log_names_the_latest_run(self):
        doc = load(self.root, "rejections/%s.json" % CELL)
        self.assertEqual(doc["harvest_run_id"], self.second.run_id)
        self.assertEqual(doc["generated_at"], STAMP2)

    def test_the_entries_did_not_accumulate(self):
        doc = load(self.root, "rejections/%s.json" % CELL)
        rows = {row["cell_id"]: row for row in self.second.manifest["cells"]}
        self.assertEqual(len(doc["rejections"]), rows[CELL]["rejected"])

    def test_it_still_validates(self):
        self.assertEqual(schema.validate(
            load(self.root, "rejections/%s.json" % CELL), "rejection.v1.json"), [])


class TestAnotherCellsStateIsNotClobbered(RecoveryCase):
    """A run touches the cells it ran, and no others."""

    OTHER = "cases__case-studies"

    def test_a_later_run_of_a_different_cell_leaves_the_first_alone(self):
        self.run_once(T1, cells=[CELL])
        before = {rel: read(self.root, rel) for rel in
                  ("ledgers/%s.json" % CELL, "rejections/%s.json" % CELL)}

        run_cells.run(self.root, cells=[self.OTHER], clock=lambda: T2)

        after = {rel: read(self.root, rel) for rel in before}
        self.assertEqual(after, before,
                         "a run clobbered a cell it did not run")

    def test_the_second_cell_got_its_own_cross_run_state(self):
        self.run_once(T1, cells=[CELL])
        run_cells.run(self.root, cells=[self.OTHER], clock=lambda: T2)
        for rel in ("ledgers/%s.json" % self.OTHER,
                    "rejections/%s.json" % self.OTHER):
            self.assertTrue(os.path.exists(os.path.join(self.root, rel)), rel)
            self.assertEqual(schema.validate(load(self.root, rel),
                                             schema_for(rel)), [], rel)

    def test_both_runs_are_published_in_order(self):
        first = self.run_once(T1, cells=[CELL])
        second = run_cells.run(self.root, cells=[self.OTHER], clock=lambda: T2)
        self.assertNotEqual(first.run_id, second.run_id)
        self.assertEqual(artifacts.verify_latest_run_id(self.root), second.run_id)


# ----------------------------------------------------------------- the pointer
class TestVerifyLatestRunId(RecoveryCase):
    def test_an_empty_root_names_nothing(self):
        self.assertIsNone(artifacts.verify_latest_run_id(self.root))

    def test_a_finished_run_is_named_and_verified(self):
        first = self.run_once(T1)
        self.assertEqual(artifacts.verify_latest_run_id(self.root), first.run_id)

    def test_a_missing_manifest_is_caught(self):
        first = self.run_once(T1)
        os.unlink(artifacts.run_manifest_path(self.root, first.run_id))
        with self.assertRaises(artifacts.ArtifactError) as caught:
            artifacts.verify_latest_run_id(self.root)
        self.assertIn(first.run_id, str(caught.exception))

    def test_an_unreadable_manifest_is_caught(self):
        first = self.run_once(T1)
        with open(artifacts.run_manifest_path(self.root, first.run_id), "wb") as fh:
            fh.write(b"not json at all")
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.verify_latest_run_id(self.root)

    def test_an_invalid_manifest_is_caught(self):
        first = self.run_once(T1)
        path = artifacts.run_manifest_path(self.root, first.run_id)
        doc = json.loads(read(self.root, os.path.relpath(path, self.root)
                              .replace("\\", "/")).decode("utf-8"))
        del doc["cells"]
        with open(path, "wb") as fh:
            fh.write(json.dumps(doc).encode("utf-8"))
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.verify_latest_run_id(self.root)

    def test_a_manifest_naming_a_different_run_is_caught(self):
        first = self.run_once(T1)
        path = artifacts.run_manifest_path(self.root, first.run_id)
        doc = json.loads(read(self.root, os.path.relpath(path, self.root)
                              .replace("\\", "/")).decode("utf-8"))
        doc["harvest_run_id"] = "20990101T000000Z-7"
        with open(path, "wb") as fh:
            fh.write(json.dumps(doc).encode("utf-8"))
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.verify_latest_run_id(self.root)


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    def code(self, module):
        import ast
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                body = getattr(node, "body", None)
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    body.pop(0)
        return ast.unparse(tree)

    def test_the_repository_runtime_paths_are_never_created(self):
        for path in ("state/taxonomy_harvest", "data/harvested", "runs",
                     "LATEST_RUN_ID"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, path)), path)

    def test_recovery_introduced_no_concurrency(self):
        # CF-1 stays deferred: the journal is sequential and refuses to nest
        # rather than coordinating two runs (plan §9.1).
        for module in (artifacts, run_cells):
            src = self.code(module)
            for token in ("threading", "multiprocessing", "asyncio", "async def",
                          "await ", "Lock(", "Semaphore(", "concurrent.futures"):
                self.assertNotIn(token, src, "%s: %s" % (module.__name__, token))

    def test_the_sweeper_never_globs_for_temp_files(self):
        # Ownership is proved by having watched the write, not by pattern
        # matching the directory — a glob-and-delete sweeper would remove another
        # writer's in-flight file.
        src = self.code(artifacts)
        for token in ("glob.glob(", "os.listdir(", "os.scandir(", "iglob("):
            self.assertNotIn(token, src, token)

    def test_it_makes_no_live_request(self):
        src = self.code(artifacts)
        for token in ("socket", "urllib", "HttpClient", "FixtureOpener"):
            self.assertNotIn(token, src, token)

    def test_the_modules_expose_the_committed_recovery_contract(self):
        for name in ("WriteJournal", "write_journal", "run_is_finished",
                     "verify_latest_run_id"):
            self.assertTrue(hasattr(artifacts, name), name)

    # `test_the_driver_signature_did_not_change` lived here until S9-1 and was
    # DELETED, not replaced. It pinned `run()`'s parameter list to exactly the
    # five Stage 5 names, which is not a recovery property: this suite owns
    # repeat refusal, journal ownership, interruption cleanup and pointer
    # ordering, and every one of those assertions is untouched below and green.
    # The S9-1 interface contract has two proper owners — `test_cli.py` and
    # `test_run_cells.py::TestBoundary::test_the_entry_point_stays_omission_
    # compatible` — so restating it here only duplicated a guard in a file with
    # no claim to it. No replacement signature or progress guard was added, on
    # the S6-4 / S6-5 precedent for retiring a spent guard outright.

    def test_the_repeat_refusal_precedes_every_write(self):
        # Order is the whole contract, so it is asserted on the source too: the
        # refusal must sit before the journal and before any writer.
        src = inspect.getsource(run_cells.run)
        self.assertLess(src.index("run_is_finished("),
                        src.index("write_journal("))
        self.assertLess(src.index("run_is_finished("),
                        src.index("write_cell_artifact("))

    def test_the_pointer_is_still_written_after_the_manifest(self):
        src = inspect.getsource(artifacts.publish_run)
        self.assertLess(src.index("write_run_manifest("),
                        src.index("write_latest_run_id("))


if __name__ == "__main__":
    unittest.main(verbosity=2)
