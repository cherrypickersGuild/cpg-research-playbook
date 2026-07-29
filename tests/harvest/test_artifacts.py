#!/usr/bin/env python3
"""test_artifacts.py — deterministic, atomic artifact writing (S5-1).

The properties that carry the weight:

  * IDENTICAL LOGICAL INPUT, IDENTICAL BYTES. Two dicts with the same content but
    different insertion order must serialize to the same bytes, or artifact
    hashing is worthless and every determinism proof downstream is decoration.
  * NOTHING PARTIAL IS EVER READABLE. A crash between write and rename must leave
    the PREVIOUS artifact intact and readable, and leave no debris. This is
    asserted by actually breaking `os.replace`, not by inspecting the code.
  * NOTHING INVALID REACHES DISK. A document that fails schema validation must
    leave the filesystem byte-for-byte as it was — no file, no truncation, no
    stale temp.
  * THE TEMP NAME IS UNIQUE. A fixed `<file>.tmp` is a shared name; two writers
    interleave through it. Uniqueness is asserted by capturing the real temp
    paths, not by reading the format string.

Every test writes under its own temp root. A test asserts the repository's real
`state/taxonomy_harvest/`, `data/harvested/` and `runs/` are never created.
Offline: no network, no fixtures, no pool, no records. Run via
tests/test_taxonomy_artifacts.sh.
"""
import ast
import datetime
import glob
import inspect
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import artifacts, schema  # noqa: E402

# A minimal document that really validates, so "valid" and "invalid" in these
# tests are the committed schema's judgement rather than this file's.
LEDGER = {
    "schema_version": 1,
    "cell_id": "cases__domain-applications",
    "updated_at": "2026-07-30T12:00:00Z",
    "entries": [],
}


class TempRootCase(unittest.TestCase):
    """Every write in this suite lands under `self.root` and nowhere else."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s5_artifacts_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def temps_in(self, directory):
        return glob.glob(os.path.join(directory, artifacts.TEMP_PREFIX + "*"))


# ------------------------------------------------------------- serialization
class TestSerialize(TempRootCase):
    def test_repeated_serialization_is_byte_identical(self):
        self.assertEqual(artifacts.serialize(LEDGER), artifacts.serialize(LEDGER))

    def test_key_order_does_not_change_the_bytes(self):
        shuffled = {k: LEDGER[k] for k in reversed(list(LEDGER))}
        self.assertNotEqual(list(shuffled), list(LEDGER))
        self.assertEqual(artifacts.serialize(shuffled), artifacts.serialize(LEDGER))

    def test_non_ascii_survives_unescaped(self):
        data = artifacts.serialize({"title": "삼성 — Ünicode"})
        self.assertIn("삼성 — Ünicode", data.decode("utf-8"))
        self.assertNotIn(b"\\u", data)

    def test_there_is_exactly_one_trailing_newline(self):
        data = artifacts.serialize(LEDGER)
        self.assertTrue(data.endswith(b"\n"))
        self.assertFalse(data.endswith(b"\n\n"))

    def test_line_endings_are_lf_even_on_windows(self):
        data = artifacts.serialize(LEDGER)
        self.assertNotIn(b"\r\n", data)
        self.assertIn(b"\n", data)

    def test_the_bytes_round_trip_to_the_same_document(self):
        self.assertEqual(json.loads(artifacts.serialize(LEDGER).decode("utf-8")), LEDGER)

    def test_it_is_indented_not_minified(self):
        # Artifacts are read by humans during audits; a single-line blob is not.
        self.assertIn(b"\n  ", artifacts.serialize(LEDGER))


# -------------------------------------------------------------- atomic write
class TestWriteAtomic(TempRootCase):
    def test_it_writes_the_bytes(self):
        target = self.path("a.json")
        artifacts.write_atomic(target, b"hello\n")
        with open(target, "rb") as fh:
            self.assertEqual(fh.read(), b"hello\n")

    def test_it_creates_missing_parent_directories(self):
        target = self.path("runs", "20260730T120000Z-1", "cells", "deep.json")
        artifacts.write_atomic(target, b"{}\n")
        self.assertTrue(os.path.exists(target))

    def test_it_leaves_no_temp_file_behind(self):
        target = self.path("a.json")
        artifacts.write_atomic(target, b"{}\n")
        self.assertEqual(self.temps_in(self.root), [])
        self.assertEqual(sorted(os.listdir(self.root)), ["a.json"])

    def test_it_overwrites_an_existing_artifact_completely(self):
        target = self.path("a.json")
        artifacts.write_atomic(target, b"aaaaaaaaaaaaaaaaaaaa\n")
        artifacts.write_atomic(target, b"bb\n")
        with open(target, "rb") as fh:
            self.assertEqual(fh.read(), b"bb\n")

    def test_it_refuses_text(self):
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.write_atomic(self.path("a.json"), "not bytes")
        self.assertFalse(os.path.exists(self.path("a.json")))

    def test_the_temp_name_is_unique_per_write_and_never_fixed(self):
        target = self.path("a.json")
        seen = []
        real_replace = os.replace

        def spy(src, dst):
            seen.append(src)
            return real_replace(src, dst)

        os.replace = spy
        try:
            for _ in range(25):
                artifacts.write_atomic(target, b"{}\n")
        finally:
            os.replace = real_replace

        self.assertEqual(len(seen), 25)
        self.assertEqual(len(set(seen)), 25, "temp names repeated")
        for src in seen:
            self.assertNotEqual(src, target + ".tmp")
            self.assertTrue(os.path.basename(src).startswith(artifacts.TEMP_PREFIX))
            self.assertEqual(os.path.dirname(src), os.path.dirname(target),
                             "temp must sit beside its destination, same filesystem")


# ------------------------------------------------------- crash and interruption
class TestAtomicityUnderFailure(TempRootCase):
    def break_replace(self, exc):
        real_replace = os.replace

        def boom(src, dst):
            raise exc

        os.replace = boom
        self.addCleanup(setattr, os, "replace", real_replace)

    def test_a_crash_before_rename_leaves_the_previous_artifact_intact(self):
        target = self.path("a.json")
        artifacts.write_atomic(target, b"ORIGINAL\n")
        self.break_replace(OSError("simulated crash"))
        with self.assertRaises(OSError):
            artifacts.write_atomic(target, b"REPLACEMENT\n")
        with open(target, "rb") as fh:
            self.assertEqual(fh.read(), b"ORIGINAL\n", "destination was damaged")

    def test_a_crash_before_rename_leaves_no_temp_debris(self):
        target = self.path("a.json")
        artifacts.write_atomic(target, b"ORIGINAL\n")
        self.break_replace(OSError("simulated crash"))
        with self.assertRaises(OSError):
            artifacts.write_atomic(target, b"REPLACEMENT\n")
        self.assertEqual(self.temps_in(self.root), [])
        self.assertEqual(sorted(os.listdir(self.root)), ["a.json"])

    def test_an_interruption_also_cleans_up(self):
        # KeyboardInterrupt is a BaseException; an `except Exception` cleanup
        # would silently leak a temp file on every Ctrl-C.
        target = self.path("a.json")
        self.break_replace(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            artifacts.write_atomic(target, b"{}\n")
        self.assertEqual(self.temps_in(self.root), [])
        self.assertFalse(os.path.exists(target))

    def test_a_first_write_that_crashes_creates_no_destination(self):
        target = self.path("a.json")
        self.break_replace(OSError("simulated crash"))
        with self.assertRaises(OSError):
            artifacts.write_atomic(target, b"{}\n")
        self.assertFalse(os.path.exists(target),
                         "a failed first write must not leave a partial file")


# --------------------------------------------------- validate before any bytes
class TestWriteDocument(TempRootCase):
    def test_a_valid_document_is_written_and_validates_on_disk(self):
        target = self.path("ledger.json")
        artifacts.write_document(target, LEDGER, "ledger.v1.json")
        with open(target, "rb") as fh:
            written = json.loads(fh.read().decode("utf-8"))
        self.assertEqual(written, LEDGER)
        self.assertEqual(schema.validate(written, "ledger.v1.json"), [])

    def test_an_invalid_document_writes_no_file(self):
        target = self.path("ledger.json")
        invalid = dict(LEDGER, unexpected_field=1)
        self.assertNotEqual(schema.validate(invalid, "ledger.v1.json"), [])
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.write_document(target, invalid, "ledger.v1.json")
        self.assertFalse(os.path.exists(target))
        self.assertEqual(os.listdir(self.root), [])

    def test_an_invalid_document_does_not_damage_an_existing_artifact(self):
        target = self.path("ledger.json")
        artifacts.write_document(target, LEDGER, "ledger.v1.json")
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.write_document(target, dict(LEDGER, unexpected_field=1),
                                     "ledger.v1.json")
        with open(target, "rb") as fh:
            self.assertEqual(json.loads(fh.read().decode("utf-8")), LEDGER)
        self.assertEqual(self.temps_in(self.root), [])

    def test_the_error_names_the_schema(self):
        with self.assertRaises(artifacts.ArtifactError) as caught:
            artifacts.write_document(self.path("x.json"), {"nope": 1}, "ledger.v1.json")
        self.assertIn("ledger.v1.json", str(caught.exception))

    def test_writing_the_same_document_twice_is_byte_identical(self):
        first, second = self.path("one.json"), self.path("two.json")
        artifacts.write_document(first, LEDGER, "ledger.v1.json")
        artifacts.write_document(second, {k: LEDGER[k] for k in reversed(list(LEDGER))},
                                 "ledger.v1.json")
        with open(first, "rb") as a, open(second, "rb") as b:
            self.assertEqual(a.read(), b.read())


# ------------------------------------------------------------------ run paths
class TestRunPaths(unittest.TestCase):
    def test_run_id_has_the_committed_format(self):
        clock = lambda: datetime.datetime(2026, 7, 30, 12, 0, 0,
                                          tzinfo=datetime.timezone.utc)
        self.assertEqual(artifacts.run_id(clock=clock, pid=4242),
                         "20260730T120000Z-4242")

    def test_run_id_is_injectable_and_therefore_reproducible(self):
        clock = lambda: datetime.datetime(2026, 1, 2, 3, 4, 5,
                                          tzinfo=datetime.timezone.utc)
        self.assertEqual(artifacts.run_id(clock=clock, pid=7),
                         artifacts.run_id(clock=clock, pid=7))

    def test_run_id_defaults_to_this_process(self):
        self.assertTrue(artifacts.run_id().endswith("-%d" % os.getpid()))

    def test_run_dir_is_under_the_injected_root(self):
        got = artifacts.run_dir("/tmp/somewhere", "20260730T120000Z-1")
        self.assertEqual(got, os.path.join("/tmp/somewhere", "runs",
                                           "20260730T120000Z-1"))

    def test_run_dir_creates_nothing(self):
        root = tempfile.mkdtemp(prefix="s5_rundir_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        artifacts.run_dir(root, "20260730T120000Z-1")
        self.assertEqual(os.listdir(root), [])

    def test_run_dir_refuses_an_empty_run_id(self):
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.run_dir("/tmp/somewhere", "")


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):
    """What the module DOES, read from its code rather than from its prose.

    These assertions walk the AST and ignore docstrings and comments on purpose:
    the module's own docstring names the checkpoints it excludes, so a plain
    substring scan would fail on the very sentence promising the exclusion.
    """

    def code_tokens(self):
        tree = ast.parse(inspect.getsource(artifacts))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    docstrings.add(doc)
        tokens = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                tokens.add(node.id)
            elif isinstance(node, ast.Attribute):
                tokens.add(node.attr)
            elif isinstance(node, ast.alias):
                tokens.add(node.name)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value not in docstrings:
                    tokens.add(node.value)
        return tokens

    def assertNoTokenContains(self, needle, tokens):
        hits = sorted(t for t in tokens if needle in t)
        self.assertEqual(hits, [], "%r appears in code as %r" % (needle, hits))

    def test_the_repository_runtime_paths_are_never_created(self):
        for path in ("state/taxonomy_harvest", "data/harvested", "runs"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, path)), path)

    def test_it_makes_no_network_request(self):
        tokens = self.code_tokens()
        for forbidden in ("socket", "requests", "urllib", "httpclient", "http.client"):
            self.assertNoTokenContains(forbidden, tokens)

    def test_it_knows_nothing_about_later_checkpoint_semantics(self):
        # The base (S5-1) is paths, bytes and schemas; S5-2 added the cell and
        # topic shapes on top. Ledger, rejection, coverage and manifest meaning
        # belong to S5-3 ... S5-5 and must not leak in early. This list shrinks
        # by exactly one entry as each of those checkpoints is approved.
        tokens = self.code_tokens()
        for later in ("ledger", "rejection", "coverage_report", "run_manifest",
                      "LATEST_RUN_ID"):
            self.assertNoTokenContains(later, tokens)

    def test_it_adds_no_locking_or_concurrency(self):
        tokens = self.code_tokens()
        for deferred in ("threading", "multiprocessing", "Lock", "lockdir", "flock"):
            self.assertNoTokenContains(deferred, tokens)

    def test_it_does_not_reimplement_schema_validation(self):
        tokens = self.code_tokens()
        self.assertIn("validate", tokens)
        self.assertIn("schema", tokens)
        self.assertNoTokenContains("jsonschema", tokens)

    def test_the_module_exposes_the_committed_contract(self):
        for name in ("serialize", "write_atomic", "write_document", "run_id",
                     "run_dir", "ArtifactError"):
            self.assertTrue(hasattr(artifacts, name), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
