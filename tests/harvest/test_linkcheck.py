#!/usr/bin/env python3
"""test_linkcheck.py — bounded link-health re-checking (S9-6).

A linkcheck is the one Stage 9 command that reads a finished run and writes a new
one from it. That shape is why it needs its own suite: everything here is a way
link-checking silently corrupts the evidence it was meant to measure.

  * A MUTATED BASE RUN. The base directory is hashed before and after and must be
    byte-identical. A linkcheck that edited its input would destroy the dataset
    M2 and M3 exist to preserve.
  * A DELETED RECORD. A 404 today does not unmake a case that existed.
    `link_history` is append-only; the record count never falls and no prior entry
    is dropped or rewritten.
  * A SAMPLE THAT DEPENDS ON ITERATION ORDER. Selection is the first N in the
    committed `records.sort_key` order. Shuffling the base records must not change
    which are chosen.
  * A VACUOUS CHECK. The committed corpus's accepted targets are all reachable, so
    a suite built only on it would assert that link-checking works while never
    seeing a broken link. Synthetic base runs point at the committed 404 / 410 /
    301 target fixtures, and a stub reporting every target `ok` is proved to fail
    the anti-vacuity assertion.
  * A SILENT WIDENING. `--sample` above the committed target-fetch bound is
    REFUSED, never clamped.
  * LOST LINEAGE. `base_run_id` is written, differs from the new run, and names a
    run directory that exists.

Offline and temp-rooted: every byte lands under a directory this suite removes,
the transport is the committed fixture transport, and a socket guard refuses every
non-loopback connection and is proved wired by tripping it.

Run via tests/test_taxonomy_linkcheck.sh.
"""
import ast
import copy
import datetime
import hashlib
import json
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import artifacts, cli, linkcheck, run_cells, runvalidate  # noqa: E402
from src.harvest import records as records_mod                            # noqa: E402
from src.harvest import schema as schema_mod                              # noqa: E402
from src.harvest import targetfetch as targetfetch_mod                    # noqa: E402

NOW = datetime.datetime(2026, 7, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)
LATER = datetime.datetime(2026, 7, 30, 13, 0, 0, tzinfo=datetime.timezone.utc)
STAMP_LATER = "2026-07-30T13:00:00Z"
LOOPBACK = "127.0.0.1"

OK_URL = "https://tgt.harvest.test/ok-plain"
NOT_FOUND_URL = "https://tgt.harvest.test/not-found"
GONE_URL = "https://tgt.harvest.test/gone"
REDIRECT_URL = "https://tgt.harvest.test/redirect-permanent"


def tree_hash(directory):
    """Path-and-bytes digest of a whole directory. Order-independent by sorting."""
    digest = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            digest.update(os.path.relpath(full, directory).replace(os.sep, "/")
                          .encode("utf-8"))
            with open(full, "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest()


class Base(unittest.TestCase):
    """Temp roots, and a socket guard that permits only loopback."""

    def setUp(self):
        real_connect = socket.socket.connect

        def guarded(sock, address, *a, **kw):
            host = address[0] if isinstance(address, tuple) else address
            if str(host) not in (LOOPBACK, "::1", "localhost"):
                raise AssertionError(
                    "OUTBOUND REFUSED: an S9-6 test tried to reach %r" % (host,))
            return real_connect(sock, address, *a, **kw)

        socket.socket.connect = guarded
        self.addCleanup(setattr, socket.socket, "connect", real_connect)

    def temp(self, prefix="s96_"):
        path = tempfile.mkdtemp(prefix=prefix)
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def transport(self):
        return run_cells.fixture_transport(self.temp("s96_lease_"))

    def base_run(self, root=None):
        """A real committed-corpus smoke, used as the base run."""
        root = root or self.temp("s96_root_")
        result = run_cells.run(root, clock=lambda: NOW, mode="smoke", enrich=False,
                               bounds=run_cells.RunBounds(12, 5, 1800),
                               source_preflight=())
        return root, result.run_id

    # ------------------------------------------------------------- synthetic
    def synthetic_base(self, urls):
        """A base run whose accepted records point at the URLs a test names.

        Built by taking a REAL smoke and rewriting only the target URLs of its
        full records — so every other byte of the tree is the committed producer's
        own output, and only the thing under test is synthetic. The committed
        fixture corpus is never edited: it is byte-frozen, and its accepted targets
        are all reachable, which is exactly why a broken-link case has to be
        constructed.

        Which cells hold full records is a property of the corpus, so it is
        DISCOVERED rather than assumed — naming a cell here would make the suite
        fail for a reason that has nothing to do with link checking.
        """
        root, run_id = self.base_run()
        rewritten = 0
        for cell_id in runvalidate.configured_cell_ids():
            path = artifacts.cell_artifact_path(root, run_id, cell_id)
            with open(path, encoding="utf-8") as handle:
                document = json.load(handle)
            full = [r for r in document["records"]
                    if r.get("record_type") == "full"]
            if not full:
                continue
            for record in full:
                url = urls[rewritten % len(urls)]
                rewritten += 1
                record["identity_url"] = url
                record["canonical_url"] = url
                record["target_url"] = url
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(artifacts.serialize(document).decode("utf-8"))
        self.assertGreaterEqual(rewritten, len(urls),
                                "the base run must hold at least one full record "
                                "per synthetic URL for the case to be meaningful")
        return root, run_id

    def linkcheck(self, root, base_run_id, **kw):
        kw.setdefault("sample", 5)
        kw.setdefault("transport", self.transport())
        kw.setdefault("clock", lambda: LATER)
        return linkcheck.run(root, base_run_id, **kw)

    def entries(self, root, run_id):
        """Every link_history entry this run appended, by record id."""
        out = {}
        for cell_id in runvalidate.configured_cell_ids():
            path = artifacts.cell_artifact_path(root, run_id, cell_id)
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as handle:
                for record in json.load(handle).get("records") or ():
                    history = record.get("link_history") or []
                    if history:
                        out[record["record_id"]] = history
        return out


# ------------------------------------------------------------- sample bound
class TestSampleBound(Base):
    def test_the_default_is_twenty(self):
        self.assertEqual(linkcheck.DEFAULT_SAMPLE, 20)

    def test_the_ceiling_is_the_committed_target_fetch_bound(self):
        self.assertEqual(linkcheck.MAX_SAMPLE,
                         run_cells.MAX_TARGET_FETCHES_PER_CELL)

    def test_an_excessive_sample_is_refused_not_clamped(self):
        with self.assertRaises(linkcheck.LinkcheckError) as caught:
            linkcheck.validate_sample(linkcheck.MAX_SAMPLE + 1)
        self.assertIn("never widened", str(caught.exception))

    def test_zero_negative_and_non_integer_are_refused(self):
        for bad in (0, -1, 1.5, "5", None, True):
            with self.subTest(bad=bad):
                with self.assertRaises(linkcheck.LinkcheckError):
                    linkcheck.validate_sample(bad)


# --------------------------------------------------------- sample selection
class TestSampleDeterminism(Base):
    def test_selection_is_the_committed_sort_order(self):
        root, run_id = self.base_run()
        cells = linkcheck.read_base_run(root, run_id)
        ordered = linkcheck.accepted_full_records(cells)
        self.assertEqual(ordered, sorted(ordered, key=records_mod.sort_key))

    def test_shuffling_the_base_records_cannot_change_the_sample(self):
        """ANTI-ORDER: the sample is a function of content, never of iteration."""
        root, run_id = self.base_run()
        cells = linkcheck.read_base_run(root, run_id)
        chosen = [r["record_id"]
                  for r in linkcheck.select_sample(
                      linkcheck.accepted_full_records(cells), 3)]
        self.assertTrue(chosen)
        rnd = random.Random(20260730)
        for _ in range(8):
            shuffled = {}
            for cell_id, document in cells.items():
                copied = copy.deepcopy(document)
                rnd.shuffle(copied["records"])
                shuffled[cell_id] = copied
            again = [r["record_id"]
                     for r in linkcheck.select_sample(
                         linkcheck.accepted_full_records(shuffled), 3)]
            self.assertEqual(again, chosen)

    def test_only_full_records_are_ever_selected(self):
        root, run_id = self.base_run()
        cells = linkcheck.read_base_run(root, run_id)
        for record in linkcheck.accepted_full_records(cells):
            self.assertEqual(record.get("record_type"), "full")

    def test_a_base_run_with_no_accepted_record_is_refused(self):
        root, run_id = self.base_run()
        for cell_id in runvalidate.configured_cell_ids():
            path = artifacts.cell_artifact_path(root, run_id, cell_id)
            with open(path, encoding="utf-8") as handle:
                document = json.load(handle)
            document["records"] = []
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(artifacts.serialize(document).decode("utf-8"))
        with self.assertRaises(linkcheck.LinkcheckError) as caught:
            self.linkcheck(root, run_id)
        self.assertIn("nothing to link-check", str(caught.exception))

    def test_a_missing_base_run_is_refused(self):
        root = self.temp("s96_empty_")
        with self.assertRaises(linkcheck.LinkcheckError):
            self.linkcheck(root, "20260730T120000Z-1")


# --------------------------------------------------------------- the output
class TestPublishedRun(Base):
    def setUp(self):
        super().setUp()
        self.root, self.base_id = self.base_run()
        self.result = self.linkcheck(self.root, self.base_id)
        self.run_id = self.result["run_id"]
        self.manifest = self.result["manifest"]

    def test_it_publishes_the_eighteen_selected_documents(self):
        written = [p for p in self.result["paths"] if p.endswith(".json")]
        self.assertEqual(len(written), runvalidate.SELECTED_RUN_JSON)

    def test_the_run_validates_at_forty_three_paths(self):
        report = runvalidate.validate_run(self.root, self.run_id)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["json_documents_checked"], runvalidate.TOTAL_JSON)
        self.assertEqual(report["paths_checked"], runvalidate.TOTAL_PATHS)

    def test_the_mode_and_eligibility_are_derived_not_asserted(self):
        self.assertEqual(self.manifest["mode"], "linkcheck")
        self.assertIs(self.manifest["publication_eligible"], False)

    def test_the_lineage_is_recorded_and_checkable(self):
        self.assertEqual(self.manifest["base_run_id"], self.base_id)
        self.assertNotEqual(self.manifest["base_run_id"],
                            self.manifest["harvest_run_id"])
        self.assertTrue(os.path.isdir(artifacts.run_dir(self.root, self.base_id)))

    def test_enrichment_is_true_and_the_sample_bound_is_reported(self):
        self.assertIs(self.manifest["config"]["enrich"], True)
        self.assertEqual(self.manifest["config"]["bounds"]["sample"], 5)

    def test_the_source_preflight_is_empty(self):
        """A linkcheck contacts sampled TARGET pages only; it probes no source."""
        self.assertEqual(self.manifest["source_preflight"], [])

    def test_cell_status_is_ok_where_checked_and_not_run_elsewhere(self):
        checked = {cid for cid, _ in self.entries(self.root, self.run_id).items()}
        by_cell = {}
        for cell_id in runvalidate.configured_cell_ids():
            path = artifacts.cell_artifact_path(self.root, self.run_id, cell_id)
            with open(path, encoding="utf-8") as handle:
                ids = {r["record_id"] for r in json.load(handle).get("records") or ()}
            by_cell[cell_id] = bool(ids & checked)
        for row in self.manifest["cells"]:
            with self.subTest(row["cell_id"]):
                expected = "ok" if by_cell[row["cell_id"]] else "not_run"
                self.assertEqual(row["status"], expected)
        self.assertTrue(any(r["status"] == "ok" for r in self.manifest["cells"]))

    def test_the_c2_sighting_tuple_is_absent(self):
        """A linkcheck performs no discovery, so it measures no sightings."""
        for row in self.manifest["cells"]:
            for name in run_cells.SIGHTING_FIELDS:
                with self.subTest(cell=row["cell_id"], field=name):
                    self.assertNotIn(name, row)

    def test_the_pointer_names_the_linkcheck_run(self):
        self.assertEqual(artifacts.read_latest_run_id(self.root), self.run_id)

    def test_one_fetch_per_canonical_identity(self):
        accounting = self.manifest["request_accounting"]
        self.assertEqual(accounting["target_fetch_owners"],
                         self.result["identities_fetched"])
        self.assertLessEqual(self.result["identities_fetched"],
                             self.result["checked"])


# ------------------------------------------------------- base immutability
class TestBaseRunImmutability(Base):
    def test_the_base_run_directory_is_byte_identical_afterwards(self):
        root, base_id = self.base_run()
        base_dir = artifacts.run_dir(root, base_id)
        before = tree_hash(base_dir)
        self.linkcheck(root, base_id)
        self.assertEqual(tree_hash(base_dir), before,
                         "the linkcheck modified the run it was measuring")

    def test_no_record_is_deleted_and_history_only_grows(self):
        root, base_id = self.base_run()
        result = self.linkcheck(root, base_id)
        for cell_id in runvalidate.configured_cell_ids():
            with open(artifacts.cell_artifact_path(root, base_id, cell_id),
                      encoding="utf-8") as handle:
                before = json.load(handle)["records"]
            with open(artifacts.cell_artifact_path(root, result["run_id"], cell_id),
                      encoding="utf-8") as handle:
                after = json.load(handle)["records"]
            with self.subTest(cell_id):
                self.assertEqual(len(after), len(before))
                self.assertEqual([r["record_id"] for r in after],
                                 [r["record_id"] for r in before])
                for old, new in zip(before, after):
                    old_history = old.get("link_history") or []
                    new_history = new.get("link_history") or []
                    self.assertGreaterEqual(len(new_history), len(old_history))
                    self.assertEqual(new_history[:len(old_history)], old_history)

    def test_a_second_linkcheck_appends_rather_than_replaces(self):
        root, base_id = self.base_run()
        first = self.linkcheck(root, base_id)
        second = self.linkcheck(root, first["run_id"],
                                clock=lambda: LATER + datetime.timedelta(hours=1))
        lengths = []
        for history in self.entries(root, second["run_id"]).values():
            lengths.append(len(history))
        self.assertTrue(lengths)
        self.assertTrue(any(n >= 2 for n in lengths),
                        "a re-check must append a SECOND entry, not overwrite one")


# ------------------------------------------------------------ anti-vacuity
class TestOutcomesAreReal(Base):
    def test_broken_targets_produce_non_ok_access_statuses(self):
        """ANTI-VACUITY: at least one 404 / 410 / redirect is actually observed."""
        root, base_id = self.synthetic_base(
            [NOT_FOUND_URL, GONE_URL, REDIRECT_URL, OK_URL])
        result = self.linkcheck(root, base_id)
        seen = {entry["access_status"]
                for history in self.entries(root, result["run_id"]).values()
                for entry in history}
        self.assertTrue(
            seen & {targetfetch_mod.NOT_FOUND, targetfetch_mod.GONE,
                    targetfetch_mod.REDIRECTED},
            "no broken or redirected target was observed; the check is vacuous "
            "(saw %r)" % (sorted(seen),))

    def test_an_all_ok_stub_fails_the_anti_vacuity_assertion(self):
        """The guard above must be capable of failing, or it proves nothing."""
        real = targetfetch_mod.fetch_target

        def always_ok(url, **kw):
            return targetfetch_mod.TargetFetchOutcome(
                requested_url=url, access_status=targetfetch_mod.OK,
                verification_status=targetfetch_mod.FETCHED,
                verification_evidence="stub", last_checked_at=STAMP_LATER)

        import src.harvest.linkcheck as module
        module.targetfetch_mod.fetch_target = always_ok
        self.addCleanup(setattr, module.targetfetch_mod, "fetch_target", real)

        root, base_id = self.synthetic_base(
            [NOT_FOUND_URL, GONE_URL, REDIRECT_URL, OK_URL])
        result = self.linkcheck(root, base_id)
        seen = {entry["access_status"]
                for history in self.entries(root, result["run_id"]).values()
                for entry in history}
        self.assertEqual(seen, {targetfetch_mod.OK})
        self.assertFalse(
            seen & {targetfetch_mod.NOT_FOUND, targetfetch_mod.GONE,
                    targetfetch_mod.REDIRECTED},
            "the stub must defeat the anti-vacuity guard, proving it can fail")

    def test_a_broken_link_does_not_delete_or_downgrade_the_record(self):
        root, base_id = self.synthetic_base([NOT_FOUND_URL])
        result = self.linkcheck(root, base_id)
        for cell_id in runvalidate.configured_cell_ids():
            with open(artifacts.cell_artifact_path(root, base_id, cell_id),
                      encoding="utf-8") as handle:
                before = json.load(handle)["records"]
            with open(artifacts.cell_artifact_path(root, result["run_id"], cell_id),
                      encoding="utf-8") as handle:
                after = json.load(handle)["records"]
            self.assertEqual(len(after), len(before), cell_id)

    def test_every_entry_carries_the_two_required_fields(self):
        root, base_id = self.synthetic_base([NOT_FOUND_URL, OK_URL])
        result = self.linkcheck(root, base_id)
        history = self.entries(root, result["run_id"])
        self.assertTrue(history)
        for entries in history.values():
            for entry in entries:
                self.assertIn("checked_at", entry)
                self.assertIn("access_status", entry)
                self.assertEqual(entry["checked_at"], STAMP_LATER)


# ------------------------------------------------------------- determinism
class TestDeterminism(Base):
    def test_equal_inputs_and_equal_clocks_give_byte_identical_output(self):
        pinned = "20260730T130000Z-777"
        digests = []
        for _ in range(2):
            root, base_id = self.base_run()
            result = self.linkcheck(root, base_id, run_id_value=pinned)
            digests.append(tree_hash(artifacts.run_dir(root, result["run_id"])))
        self.assertEqual(digests[0], digests[1])

    def test_the_run_refuses_to_overwrite_its_own_base(self):
        root, base_id = self.base_run()
        with self.assertRaises(linkcheck.LinkcheckError) as caught:
            self.linkcheck(root, base_id, run_id_value=base_id)
        self.assertIn("may never overwrite", str(caught.exception))

    def test_a_transport_is_required_rather_than_defaulted(self):
        """There is no default transport: reaching the network is cli.py's call."""
        root, base_id = self.base_run()
        with self.assertRaises(linkcheck.LinkcheckError) as caught:
            linkcheck.run(root, base_id, sample=2, transport=None,
                          clock=lambda: LATER)
        self.assertIn("explicit transport", str(caught.exception))


# --------------------------------------------------------------- boundaries
class TestBoundary(Base):
    def module_source(self):
        with open(os.path.join(ROOT, "src", "harvest", "linkcheck.py"),
                  encoding="utf-8") as handle:
            return handle.read()

    def test_the_module_reaches_no_network_of_its_own(self):
        """Scanned through the AST, not as a substring.

        A raw text scan is permanently red on the very prose that records the
        guarantee — this module's docstring says "cost one request", and
        `RequestBudget` contains the word. The committed `code_only` lesson: read
        what a module DOES. Here that means the names it actually references.
        """
        tree = ast.parse(self.module_source())
        referenced = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                referenced.add(node.attr)
                if isinstance(node.value, ast.Name):
                    referenced.add(node.value.id)
            elif isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    referenced.add(alias.name.split(".")[-1])
        for forbidden in ("default_opener", "urlopen", "socket", "requests",
                          "urllib", "fixture_transport", "live_transport",
                          "Transport"):
            with self.subTest(forbidden):
                self.assertNotIn(forbidden, referenced)

    def test_it_constructs_no_transport_and_takes_one_instead(self):
        """The transport is a PARAMETER; building one is cli.py's decision."""
        import inspect
        self.assertIn("transport", inspect.signature(linkcheck.run).parameters)

    def test_the_frozen_owners_are_byte_unchanged(self):
        for path in ("src/harvest/records.py", "src/harvest/targetfetch.py",
                     "src/harvest/artifacts.py", "src/harvest/run_cells.py",
                     "src/harvest/pool.py", "src/harvest/dedupe.py",
                     "src/harvest/extract.py"):
            with self.subTest(path):
                rc = subprocess.call(["git", "diff", "--exit-code", "--quiet",
                                      "HEAD", "--", path], cwd=ROOT)
                self.assertEqual(rc, 0, path)

    def test_the_fixture_corpus_was_not_modified(self):
        rc = subprocess.call(["git", "diff", "--exit-code", "--quiet", "HEAD",
                              "--", "tests/fixtures/harvest"], cwd=ROOT)
        self.assertEqual(rc, 0)

    def test_the_schema_tree_is_clean_relative_to_HEAD(self):
        """S9-6A. The predecessor was a SPENT checkpoint census, retired here.

        It asserted `git diff --name-only HEAD -- schemas/harvest` equalled
        `["schemas/harvest/run_manifest.v1.json"]`, which held only while S9-6 was
        written and not yet committed. Once S9-6 was committed the diff is
        correctly EMPTY, so the assertion became impossible to satisfy at any
        clean tip — it failed precisely because the checkpoint succeeded. That is
        E9-9's spent-guard problem, and the historical fact that exactly one
        schema moved belongs to the S9-6 COMMIT, not to a permanent working-tree
        assertion.

        Retirement AND replacement, not deletion. This is a different and
        deliberately weaker contract — "no schema is uncommitted" rather than
        "exactly this schema moved" — but it is the boundary this class can still
        establish at any tip, and it is the one nothing else covers: the siblings
        above hold the `src/harvest` owners and the fixture corpus, and the
        schema's own SHAPE (`base_run_id` optional at the root, conditionally
        required for `mode: "linkcheck"`) is owned by
        `test_manifest.py::TestBaseRunLineage`. Driving a linkcheck must leave the
        schema tree exactly as it found it.
        """
        rc = subprocess.call(["git", "diff", "--exit-code", "--quiet", "HEAD",
                              "--", "schemas/harvest"], cwd=ROOT)
        self.assertEqual(rc, 0)

    def test_the_outbound_guard_is_genuinely_installed(self):
        with self.assertRaises(AssertionError) as caught:
            socket.socket().connect(("example.invalid", 80))
        self.assertIn("OUTBOUND REFUSED", str(caught.exception))

    def test_no_repository_runtime_path_was_created(self):
        for leaked in ("state/taxonomy_harvest", "data/harvested", "runs",
                       "LATEST_RUN_ID"):
            with self.subTest(leaked):
                self.assertFalse(os.path.exists(os.path.join(ROOT, leaked)))

    def test_the_command_is_registered_and_nothing_stays_planned(self):
        self.assertIn("linkcheck", cli.COMMANDS)
        self.assertIs(cli.COMMANDS["linkcheck"], cli.cmd_linkcheck)
        self.assertEqual(cli.PLANNED_COMMANDS, {})

    def test_the_validator_accepts_a_linkcheck_manifest_shape(self):
        self.assertIn("linkcheck", runvalidate.VALIDATABLE_MODES)
        self.assertEqual(runvalidate.MAX_LINKCHECK_SAMPLE, linkcheck.MAX_SAMPLE)


# ------------------------------------------------------- validator refusals
class TestValidatorRefusals(Base):
    def rewrite(self, root, run_id, mutate):
        path = artifacts.run_manifest_path(root, run_id)
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        mutate(document)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)

    def prepared(self):
        root, base_id = self.base_run()
        result = self.linkcheck(root, base_id)
        return root, result["run_id"]

    def test_a_missing_base_run_id_is_invalid(self):
        root, run_id = self.prepared()
        self.rewrite(root, run_id, lambda d: d.pop("base_run_id"))
        report = runvalidate.validate_run(root, run_id)
        self.assertFalse(report["valid"])

    def test_a_self_naming_lineage_is_invalid(self):
        root, run_id = self.prepared()
        self.rewrite(root, run_id, lambda d: d.__setitem__("base_run_id", run_id))
        report = runvalidate.validate_run(root, run_id)
        self.assertTrue(any("may never name itself" in e for e in report["errors"]),
                        report["errors"])

    def test_a_lineage_naming_no_run_directory_is_invalid(self):
        root, run_id = self.prepared()
        self.rewrite(root, run_id,
                     lambda d: d.__setitem__("base_run_id", "20200101T000000Z-9"))
        report = runvalidate.validate_run(root, run_id)
        self.assertTrue(any("no run directory" in e for e in report["errors"]),
                        report["errors"])

    def test_a_non_empty_source_preflight_is_invalid(self):
        root, run_id = self.prepared()
        self.rewrite(root, run_id, lambda d: d.__setitem__(
            "source_preflight", [{"source_id": "openai-news", "result": "ok"}]))
        report = runvalidate.validate_run(root, run_id)
        self.assertTrue(any("probes no source" in e for e in report["errors"]),
                        report["errors"])

    def test_an_out_of_range_sample_is_invalid(self):
        root, run_id = self.prepared()
        self.rewrite(root, run_id, lambda d: d["config"]["bounds"].__setitem__(
            "sample", linkcheck.MAX_SAMPLE + 1))
        report = runvalidate.validate_run(root, run_id)
        self.assertTrue(any("bounds.sample" in e for e in report["errors"]),
                        report["errors"])

    def test_enrich_false_is_invalid_for_a_linkcheck(self):
        root, run_id = self.prepared()
        self.rewrite(root, run_id,
                     lambda d: d["config"].__setitem__("enrich", False))
        report = runvalidate.validate_run(root, run_id)
        self.assertTrue(any("expected true" in e for e in report["errors"]),
                        report["errors"])

    def test_an_all_not_run_linkcheck_is_invalid(self):
        root, run_id = self.prepared()

        def blank(document):
            for row in document["cells"]:
                row["status"] = "not_run"
        self.rewrite(root, run_id, blank)
        report = runvalidate.validate_run(root, run_id)
        self.assertTrue(any("checked nothing" in e for e in report["errors"]),
                        report["errors"])

    def test_a_forbidden_cell_status_is_invalid(self):
        root, run_id = self.prepared()

        def spoil(document):
            document["cells"][0]["status"] = "zero_result"
        self.rewrite(root, run_id, spoil)
        report = runvalidate.validate_run(root, run_id)
        self.assertTrue(any("never sets a cell status" in e
                            for e in report["errors"]), report["errors"])

    def test_harvest_mode_is_still_refused(self):
        root, run_id = self.prepared()
        self.rewrite(root, run_id, lambda d: d.__setitem__("mode", "harvest"))
        report = runvalidate.validate_run(root, run_id)
        self.assertFalse(report["valid"])
        self.assertTrue(any("expected one of" in e for e in report["errors"]),
                        report["errors"])

    def test_the_schema_requires_lineage_only_for_linkcheck(self):
        document = artifacts.build_run_manifest(
            harvest_run_id="20260730T120000Z-1", started_at="2026-07-30T12:00:00Z",
            finished_at="2026-07-30T12:00:00Z", mode="linkcheck")
        self.assertNotEqual(
            schema_mod.validate(document, "run_manifest.v1.json"), [])
        document["base_run_id"] = "20260730T110000Z-1"
        self.assertEqual(schema_mod.validate(document, "run_manifest.v1.json"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
