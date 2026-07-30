#!/usr/bin/env python3
"""test_target_determinism.py — determinism, failure modes and partial runs (S6-7).

Stage 6 added the first thing in this pipeline that reads a page. This suite asks
the only questions that matter once it does: does the run still produce the same
bytes, does it still fail safely, and is what it says about itself still true?

Five failures are worth catching here, and none of them is visible from a green
healthy-path run:

  * BYTES THAT MOVE ON THEIR OWN. Two equivalent runs must be byte-identical, and
    two runs at different instants must differ at an ENUMERATED set of leaves —
    never a normalized-away one. A normalizer hides whatever it was not told
    about; enumeration turns a new moving field into a failure.
  * ORDER LEAKING INTO OUTPUT. If which cell, which source or which candidate went
    first can change a byte, the artifacts are a function of scheduling rather
    than of content, and every hash in the tree becomes meaningless.
  * A FAILURE MODE THAT CORRUPTS THE RUN AROUND IT. A 404, a 410, a 403, a
    terminal 500, an empty body, a non-HTML body, a redirect and a contradictory
    canonical must each produce a complete, valid, honest record — not a crash,
    not a hole in an artifact, and not a silently dropped record.
  * A HALF-WRITTEN TREE. An interruption during the fetch phase must publish
    nothing at all, and the retry must be an ordinary fresh run rather than a
    resume — there is no resume, deliberately (plan §7.3).
  * A CLAIM THE RUN CANNOT SUPPORT. Accounting must count one identity once and a
    skipped target as zero; eligibility must survive observed failures and must
    not survive a target nobody checked.

WHAT THIS SUITE DELIBERATELY DOES NOT DO:

  * It does not simulate transport. Timeout sequencing, a `500 → 200` retry
    transition and an over-cap body belong to the committed `HttpClient` and are
    tested there (plan §5.0, §14 E15). No fixture here carries a transport
    directive, and no retry count is asserted — only the accounting identity that
    holds whatever the client did.
  * It does not compose a run-level `robots_denied`. All four accepted targets in
    the committed corpus live on `github.com`, and so does the source feed that
    surfaces them, so denying that host stops discovery before any record exists —
    the case would prove nothing about a denied *record*. `RobotsDenied →
    robots_denied` stays owned by `tests/harvest/test_target_fetch.py`, where it is
    asserted directly, and by fixture #20, whose contract is that it is never even
    opened.
  * It edits no committed fixture, no source fixture, no topic configuration and
    no production module. Every scenario is a COPY of the committed corpus with
    target-fixture content substituted in the copy.

Offline throughout: the opener is the committed `FixtureOpener` over a temp tree.
"""
import copy
import datetime
import hashlib
import json
import os
import random
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import aliases as aliases_mod                    # noqa: E402
from src.harvest import artifacts, run_cells, schema              # noqa: E402
from src.harvest import fixtures as fixtures_mod                  # noqa: E402
from src.harvest import httpclient as httpclient_mod              # noqa: E402
from src.harvest import pool as pool_mod                          # noqa: E402
from src.harvest import sourcecache as sourcecache_mod            # noqa: E402
from src.harvest import targetfetch as targetfetch_mod            # noqa: E402
from src.harvest.budget import RequestBudget                      # noqa: E402

FIXTURE_ROOT = os.path.join(ROOT, "tests", "fixtures", "harvest")

# Two instants. A run id is derived from the clock, so two runs are two runs only
# if the clock moved; T2 is also far enough away that freshness visibly decays.
T1 = datetime.datetime(2026, 7, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)
T2 = datetime.datetime(2026, 8, 14, 9, 30, 0, tzinfo=datetime.timezone.utc)
STAMP1 = "2026-07-30T12:00:00Z"

# The one cell the committed corpus accepts records in, and the four accepted
# target identities it produces. Not invented here — they are what
# dedupe → extract → classify → verify yields, and what the Group B fixtures
# were authored against (plan §11, S6-1).
CELL = "research-and-models__benchmark-and-datasets"
ACCEPTED = tuple("https://github.com/posts/lm-eval-harness-releases-%d" % n
                 for n in (1, 2, 3, 4))
ACCEPTED_FIXTURES = tuple("tgt_accepted_%d" % n for n in (1, 2, 3, 4))


# --------------------------------------------------------------------- helpers
def listing(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            out.append(os.path.relpath(os.path.join(dirpath, name), root)
                       .replace("\\", "/"))
    return sorted(out)


def read(root, rel):
    with open(os.path.join(root, rel), "rb") as handle:
        return handle.read()


def load(root, rel):
    return json.loads(read(root, rel).decode("utf-8"))


def tree_hash(root):
    """Every relative path and every byte. Paths included: a tree that moved a
    file is not the same tree."""
    digest = hashlib.sha256()
    for rel in listing(root):
        digest.update(rel.encode("utf-8"))
        digest.update(read(root, rel))
    return digest.hexdigest()


def snapshot(root):
    return {rel: read(root, rel) for rel in listing(root)}


def temps_under(root):
    return sorted(rel for rel in listing(root)
                  if os.path.basename(rel).startswith(artifacts.TEMP_PREFIX))


def schema_for(rel):
    """The committed schema for one artifact path.

    `alias_conflicts.json` is listed explicitly. S6-6 shipped the artifact and
    missed exactly this mapping in a private copy of this helper, so a new
    artifact validated against nothing; naming it here is the cheap half of that
    lesson.
    """
    parts = rel.split("/")
    if parts[-1] == "manifest.json":
        return "run_manifest.v1.json"
    if parts[-1] == "coverage.json":
        return "coverage_report.v1.json"
    if parts[-1] == "alias_conflicts.json":
        return "alias_conflict.v1.json"
    return {"cells": "cell_artifact.v1.json", "topics": "topic_artifact.v1.json",
            "rejections": "rejection.v1.json",
            "ledgers": "ledger.v1.json"}[parts[-2]]


def expected_paths(run_id, cell_ids, topic_slugs):
    """The complete tree one finished run leaves behind — 43 paths today.

    Asserted EXACTLY, so an extra file fails as loudly as a missing one.
    """
    paths = ["LATEST_RUN_ID",
             "runs/%s/alias_conflicts.json" % run_id,
             "runs/%s/coverage.json" % run_id,
             "runs/%s/manifest.json" % run_id]
    for cell_id in cell_ids:
        paths.append("runs/%s/cells/%s.json" % (run_id, cell_id))
        paths.append("rejections/%s.json" % cell_id)
        paths.append("ledgers/%s.json" % cell_id)
    for topic_slug in topic_slugs:
        paths.append("runs/%s/topics/%s.json" % (run_id, topic_slug))
    return sorted(paths)


def configured_ids():
    return [cell["cell_id"] for cell in run_cells.configured_cells()]


def configured_topics():
    return sorted({cell["topic_slug"] for cell in run_cells.configured_cells()})


def diff_paths(left, right, path=""):
    """Every JSON path at which two documents disagree.

    Enumeration rather than normalization: a normalizer silently forgives every
    field it was not told about, so the day a sixth field starts moving it passes.
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
    return {p.rsplit("/", 1)[-1] for p in paths}


# ------------------------------------------------------------- corpus composer
def committed_target(fixture_id):
    """One committed target fixture, read but never written."""
    with open(os.path.join(FIXTURE_ROOT, "targets", "%s.json" % fixture_id),
              encoding="utf-8") as handle:
        return json.load(handle)


def body_of(fixture_id):
    """The status, headers and body of a committed Group A fixture, to be lifted
    onto an accepted URL in a COPY of the corpus."""
    fixture = committed_target(fixture_id)
    part = {"status": fixture["status"], "headers": dict(fixture["headers"])}
    if "body_b64" in fixture:
        part["body_b64"] = fixture["body_b64"]
    else:
        part["body"] = fixture["body"]
    return part


HTML = ('<!doctype html>\n<html lang="en">\n <head>\n  <meta charset="utf-8">\n'
        '  <title>%s</title>\n%s </head>\n <body>\n  <h1>%s</h1>\n </body>\n'
        '</html>\n')


def html_with_canonical(title, href):
    tag = '  <link rel="canonical" href="%s">\n' % href if href else ""
    return HTML % (title, tag, title)


def compose(substitutions):
    """A temp copy of the committed corpus with target CONTENT substituted.

    Only `status`, `headers` and the body of a target fixture are replaced, and
    only in the copy: `fixture_id`, the filename and the URL stay exactly as
    committed, because the loader keys the corpus by filename and indexes it by
    URL, and because an accepted record's identity must not move (that is what
    makes these scenarios comparable to the clean run).

    The copied `MANIFEST.json` is deliberately left as committed and therefore no
    longer describes the substituted bytes. That is correct: the manifest pins the
    REPOSITORY corpus and is checked by `check_fixtures.py` against the repository,
    never by the loader, which validates shape rather than provenance.

    No committed file is opened for writing. Nothing here can touch
    `tests/fixtures/harvest`.
    """
    base = tempfile.mkdtemp(prefix="s6_7_fx_")
    target_root = os.path.join(base, "harvest")
    shutil.copytree(FIXTURE_ROOT, target_root)
    for fixture_id, part in substitutions.items():
        path = os.path.join(target_root, "targets", "%s.json" % fixture_id)
        with open(path, encoding="utf-8") as handle:
            fixture = json.load(handle)
        fixture.pop("body", None)
        fixture.pop("body_b64", None)
        fixture.update(copy.deepcopy(part))
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(fixture, handle, indent=1, sort_keys=True)
            handle.write("\n")
    return base, target_root


# ------------------------------------------------------------------ cached runs
_RUNS = {}
_TEMPS = []


def temp_root(prefix="s6_7_"):
    root = tempfile.mkdtemp(prefix=prefix)
    _TEMPS.append(root)
    return root


def harvest(key, *, clock=T1, fixtures_dir=None, cells=None, root=None):
    """One completed run, cached by key.

    A run costs ~1.4s; this suite needs a dozen distinct ones, and re-running an
    identical harvest per assertion would make the suite slow enough to stop being
    run. Every cache key names a DISTINCT input — a different clock, a different
    corpus, a different cell order — so nothing is shared between two runs that
    were supposed to differ, and the ordering and recovery cases below deliberately
    take their own uncached roots.
    """
    if key not in _RUNS:
        target = root or temp_root("s6_7_%s_" % key)
        result = run_cells.run(target, clock=lambda: clock,
                               fixtures_dir=fixtures_dir, cells=cells)
        _RUNS[key] = (target, result)
    return _RUNS[key]


_SCENARIOS = {}


def scenario(key, substitutions):
    """A composed corpus, built once and shared by the runs that need it."""
    if key not in _SCENARIOS:
        base, target_root = compose(substitutions)
        _TEMPS.append(base)
        _SCENARIOS[key] = target_root
    return _SCENARIOS[key]


# The four composed corpora. Each one puts a different family of Stage 6 target
# outcomes onto the four accepted slots; families that cannot coexist in four
# slots get their own scenario rather than being forced into one impossible run.
def failures_corpus():
    return scenario("failures", {
        "tgt_accepted_1": body_of("tgt_not_found"),      # 404 -> not_found
        "tgt_accepted_2": body_of("tgt_gone"),           # 410 -> gone
        "tgt_accepted_3": body_of("tgt_forbidden"),      # 403 -> auth_required
        "tgt_accepted_4": body_of("tgt_server_error"),   # terminal 500
    })


def bodies_corpus():
    return scenario("bodies", {
        "tgt_accepted_1": body_of("tgt_empty_body"),     # EmptyResponse
        "tgt_accepted_2": body_of("tgt_non_html_pdf"),   # non-HTML, hashed
        # A permanent-only chain: one 301 hop onto a committed 200 terminus, so
        # `permanent_redirect` is true and an alias is adopted.
        "tgt_accepted_3": {
            "status": 301,
            "headers": {"content-type": "text/html; charset=utf-8",
                        "location": "https://tgt.harvest.test/redirect-permanent-c"},
            "body": HTML % ("Composed Permanent Redirect", "",
                            "Composed Permanent Redirect")},
        # One 302 hop: any temporary hop must prevent alias adoption.
        "tgt_accepted_4": {
            "status": 302,
            "headers": {"content-type": "text/html; charset=utf-8",
                        "location": "https://tgt.harvest.test/redirect-temporary-c"},
            "body": HTML % ("Composed Temporary Redirect", "",
                            "Composed Temporary Redirect")},
    })


def canonical_corpus():
    return scenario("canonical", {
        # Cross registrable domain, no migration rule -> conflict, no alias.
        "tgt_accepted_1": body_of("tgt_canonical_cross_host"),
        # Same registrable domain, but robots evidence is unwired (S6-4/S6-5 pass
        # canonical_robots_allowed=None) -> conflict, no alias.
        "tgt_accepted_2": {
            "status": 200,
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": html_with_canonical(
                "Composed Same Host Canonical",
                "https://github.com/posts/lm-eval-harness-canonical")},
        # Two different canonicals on one page -> conflict, no alias.
        "tgt_accepted_3": body_of("tgt_canonical_conflicting"),
        # Self-canonical: a no-op, neither alias nor conflict.
        "tgt_accepted_4": {
            "status": 200,
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": html_with_canonical("Composed Self Canonical", ACCEPTED[3])},
    })


def tearDownModule():
    for path in _TEMPS:
        shutil.rmtree(path, ignore_errors=True)


# ------------------------------------------------------------------ assertions
class TreeCase(unittest.TestCase):

    def assertEveryArtifactValidates(self, root):
        checked = 0
        for rel in listing(root):
            if rel == artifacts.LATEST_RUN_ID_NAME:
                continue
            checked += 1
            self.assertEqual(schema.validate(load(root, rel), schema_for(rel)), [],
                             "%s is not a complete valid artifact" % rel)
        self.assertGreater(checked, 0, "nothing was validated")

    def assertCompleteTree(self, root, result):
        self.assertEqual(listing(root),
                         expected_paths(result.run_id, configured_ids(),
                                        configured_topics()))
        self.assertEqual(temps_under(root), [])


# ---------------------------------------------- 1 · same-clock byte determinism
class TestSameClockWholeTreeDeterminism(TreeCase):
    """Two equivalent runs, one pinned clock, two roots: the same 43 files and
    the same bytes in every one of them."""

    @classmethod
    def setUpClass(cls):
        cls.root_a, cls.result_a = harvest("clean_t1")
        cls.root_b, cls.result_b = harvest("clean_t1_again")

    def test_the_tree_is_exactly_the_43_expected_paths(self):
        self.assertEqual(len(expected_paths(self.result_a.run_id, configured_ids(),
                                            configured_topics())), 43)
        self.assertCompleteTree(self.root_a, self.result_a)

    def test_both_runs_produced_the_same_run_id(self):
        """Equivalent means equivalent: one clock, one run id, one set of paths."""
        self.assertEqual(self.result_a.run_id, self.result_b.run_id)

    def test_the_whole_tree_hashes_identically(self):
        self.assertEqual(tree_hash(self.root_b), tree_hash(self.root_a))

    def test_every_file_matches_byte_for_byte(self):
        """The hash above would pass on two empty trees; this names each file."""
        left, right = snapshot(self.root_a), snapshot(self.root_b)
        self.assertEqual(sorted(left), sorted(right))
        for rel in sorted(left):
            with self.subTest(rel):
                self.assertEqual(right[rel], left[rel])

    def test_each_artifact_family_is_covered_by_that_comparison(self):
        """Anti-vacuity for the file-by-file test: every family is really there."""
        rels = listing(self.root_a)
        self.assertIn("LATEST_RUN_ID", rels)
        self.assertIn("runs/%s/manifest.json" % self.result_a.run_id, rels)
        self.assertIn("runs/%s/coverage.json" % self.result_a.run_id, rels)
        self.assertIn("runs/%s/alias_conflicts.json" % self.result_a.run_id, rels)
        self.assertEqual(len([r for r in rels if "/cells/" in r]), 12)
        self.assertEqual(len([r for r in rels if "/topics/" in r]), 3)
        self.assertEqual(len([r for r in rels if r.startswith("rejections/")]), 12)
        self.assertEqual(len([r for r in rels if r.startswith("ledgers/")]), 12)

    def test_every_artifact_validates(self):
        self.assertEveryArtifactValidates(self.root_a)

    def test_the_pointer_names_this_run_and_verifies(self):
        self.assertEqual(read(self.root_a, "LATEST_RUN_ID").decode("utf-8"),
                         "%s\n" % self.result_a.run_id)
        self.assertEqual(artifacts.verify_latest_run_id(self.root_a),
                         self.result_a.run_id)


# ------------------------------------------------- 2 · ordering independence
class TestCellOrderIndependence(TreeCase):

    def test_a_shuffled_cell_order_yields_an_identical_tree(self):
        base_root, _ = harvest("clean_t1")
        ids = configured_ids()
        shuffled = list(ids)
        random.Random(20260807).shuffle(shuffled)
        self.assertNotEqual(shuffled, ids, "the shuffle must actually shuffle")
        root, _ = harvest("shuffled_cells", cells=shuffled)
        self.assertEqual(tree_hash(root), tree_hash(base_root))


def one_cell(cell, *, fixtures_root=None, clock=T1):
    """Drive a single cell through the committed pipeline, as `run` does.

    The source and candidate shuffles need a boundary `run()` does not expose:
    `run()` takes cell IDs and reads the sources from the committed configuration,
    so the only way to reorder them without editing that configuration is to hand
    `_run_one_cell` a cell whose `sources` list is in a different order. The
    construction below mirrors `run()`'s exactly — the same committed opener, the
    same client, the same pool, cache and budget — so what is being measured is
    the pipeline and not a different wiring of it.
    """
    stamp = clock.strftime(run_cells.STAMP_FORMAT)
    fixture_root = fixtures_root or FIXTURE_ROOT
    opener = fixtures_mod.FixtureOpener(
        sources=fixtures_mod.load_source_fixtures(
            os.path.join(fixture_root, "sources")),
        robots=fixtures_mod.load_robots_fixtures(
            os.path.join(fixture_root, "robots")),
        targets=fixtures_mod.load_target_fixtures(
            os.path.join(fixture_root, "targets")))
    lease_root = tempfile.mkdtemp(prefix="s6_7_lease_")
    try:
        with open(run_cells.POLICY_PATH, encoding="utf-8") as handle:
            policy = json.load(handle)
        client = httpclient_mod.HttpClient(policy, lease_root=lease_root,
                                           opener=opener, sleep=lambda s: None)
        pool = pool_mod.CandidatePool("s6-7-probe")
        cache = sourcecache_mod.SourceFetchCache(pool, clock=lambda: stamp)
        return run_cells._run_one_cell(
            cell, cache=cache, client=client, budget=RequestBudget(),
            policy=policy, clock=lambda: stamp, pool=pool, outcomes={},
            canon_policy=aliases_mod.load_canonicalization())
    finally:
        shutil.rmtree(lease_root, ignore_errors=True)


def cell_config(cell_id):
    for cell in run_cells.configured_cells():
        if cell["cell_id"] == cell_id:
            return copy.deepcopy(cell)
    raise AssertionError("no such configured cell: %s" % cell_id)


def cell_bytes(run):
    """The cell artifact one CellRun would produce, serialized."""
    records = []
    for candidate in run.accepted:
        key = candidate.candidate_key
        records.append(run_cells._full_record(
            candidate, run.classifications[key], run.verdicts[key],
            run.assignments[key],
            source_map={source["source_id"]: source
                        for source in run.cell["sources"]},
            harvest_run_id="20260730T120000Z-1", discovered_at=STAMP1,
            outcome=run.fetch_outcomes.get(key),
            adjudication=run.adjudications.get(key)))
    artifact = artifacts.build_cell_artifact(
        records, topic=run.cell["topic"], topic_slug=run.cell["topic_slug"],
        category=run.cell["category"], category_slug=run.cell["category_slug"],
        cell_id=run.cell_id, harvest_run_id="20260730T120000Z-1",
        generated_at=STAMP1,
        metadata={"sources": run.sources, "rejected": len(run.rejected)})
    return artifacts.serialize(artifact)


class TestSourceOrderIndependence(unittest.TestCase):
    """Which source in a cell is read first must not change a byte."""

    @classmethod
    def setUpClass(cls):
        cls.cell = cell_config(CELL)
        cls.shuffled = copy.deepcopy(cls.cell)
        random.Random(20260808).shuffle(cls.shuffled["sources"])
        cls.forward = one_cell(cls.cell)
        cls.reordered = one_cell(cls.shuffled)

    def test_the_shuffle_really_reordered_the_sources(self):
        self.assertGreater(len(self.cell["sources"]), 1,
                           "a one-source cell cannot prove order independence")
        self.assertNotEqual([s["source_id"] for s in self.shuffled["sources"]],
                            [s["source_id"] for s in self.cell["sources"]])

    def test_the_cell_artifact_bytes_are_identical(self):
        self.assertEqual(cell_bytes(self.reordered), cell_bytes(self.forward))

    def test_the_same_candidates_were_extracted_in_the_same_order(self):
        self.assertEqual([c.candidate_key for c in self.reordered.extracted],
                         [c.candidate_key for c in self.forward.extracted])

    def test_the_source_rows_are_sorted_by_source_id_either_way(self):
        ids = [row["source_id"] for row in self.reordered.sources]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(self.reordered.sources, self.forward.sources)

    def test_the_same_targets_were_fetched(self):
        self.assertEqual(sorted(o.requested_url
                                for o in self.reordered.fetch_outcomes.values()),
                         sorted(o.requested_url
                                for o in self.forward.fetch_outcomes.values()))


class TestCandidateOrderIndependence(unittest.TestCase):
    """Which accepted candidate is fetched first must not change a byte either.

    Shuffled at the fetch-phase boundary over REAL candidates from a real cell
    run, then re-driven with a fresh pool and outcome map, so the second pass is
    an honest repeat rather than a reuse of the first pass's decisions.
    """

    @classmethod
    def setUpClass(cls):
        cls.forward = one_cell(cell_config(CELL))
        cls.reordered = one_cell(cell_config(CELL))
        cls.order = [c.candidate_key for c in cls.reordered.extracted]
        shuffled = list(cls.reordered.extracted)
        random.Random(20260809).shuffle(shuffled)
        cls.shuffled_order = [c.candidate_key for c in shuffled]
        cls.reordered.extracted = tuple(shuffled)
        cls.reordered.fetch_outcomes = {}
        cls.reordered.adjudications = {}
        cls.calls = []
        pool = pool_mod.CandidatePool("s6-7-reorder")
        run_cells._fetch_targets(
            cls.reordered, client=_RecordingClient(cls.calls),
            budget=RequestBudget(), pool=pool, outcomes={},
            clock=lambda: STAMP1,
            canon_policy=aliases_mod.load_canonicalization())

    def test_the_shuffle_really_reordered_the_candidates(self):
        self.assertGreater(len(self.order), 1)
        self.assertNotEqual(self.shuffled_order, self.order)

    def test_the_fetch_order_is_the_committed_candidate_key_order(self):
        self.assertEqual(self.calls, sorted(self.calls))

    def test_every_candidate_reached_the_same_outcome(self):
        for key, outcome in self.forward.fetch_outcomes.items():
            with self.subTest(key):
                other = self.reordered.fetch_outcomes[key]
                self.assertEqual(other.access_status, outcome.access_status)
                self.assertEqual(other.content_hash, outcome.content_hash)
                self.assertEqual(other.http_status, outcome.http_status)

    def test_the_adjudications_are_unchanged(self):
        for key, adjudication in self.forward.adjudications.items():
            with self.subTest(key):
                canonical, aliases, conflicts = adjudication
                other_canonical, other_aliases, other_conflicts = \
                    self.reordered.adjudications[key]
                self.assertEqual(other_canonical, canonical)
                self.assertEqual(other_aliases, aliases)
                self.assertEqual(other_conflicts, conflicts)


class _RecordingClient:
    """The committed fixture path, with the requested URLs written down."""

    def __init__(self, calls):
        self.calls = calls
        opener = fixtures_mod.FixtureOpener(
            sources=fixtures_mod.load_source_fixtures(
                os.path.join(FIXTURE_ROOT, "sources")),
            robots=fixtures_mod.load_robots_fixtures(
                os.path.join(FIXTURE_ROOT, "robots")),
            targets=fixtures_mod.load_target_fixtures(
                os.path.join(FIXTURE_ROOT, "targets")))
        self._lease_root = tempfile.mkdtemp(prefix="s6_7_lease_")
        _TEMPS.append(self._lease_root)
        with open(run_cells.POLICY_PATH, encoding="utf-8") as handle:
            policy = json.load(handle)
        self._client = httpclient_mod.HttpClient(
            policy, lease_root=self._lease_root, opener=opener,
            sleep=lambda s: None)

    def get(self, url, budget=None, **kwargs):
        self.calls.append(url)
        return self._client.get(url, budget=budget, **kwargs)


# ------------------------------------------------- 3 · cross-clock enumeration
# The leaves a second run at a different instant is allowed to move, on the
# UNCHANGED COMMITTED CORPUS. Plan §10's five, unchanged by S6-7.
#
# `observed_at` and `detected_at` are deliberately ABSENT: the committed corpus
# adopts no alias and records no conflict, so neither leaf exists in its output.
# They appear only in the composed scenarios below, which is exactly why those are
# compared same-clock instead of being folded into this set.
CLOCK_DERIVED = {"harvest_run_id", "generated_at", "discovered_at",
                 "freshness_score", "last_checked_at"}

# Two artifact families carry additional instants that are STRUCTURAL rather than
# record-derived, and each is enumerated exactly rather than excused:
#
#   the manifest    `started_at` / `finished_at` — the run's own clock, echoed
#                   into the document that describes the run;
#   a rejection log `rejected_at` — when this run rejected the candidate;
#   a ledger        `updated_at` / `first_seen_at` / `last_seen_at` — a CROSS-RUN
#                   store whose entire job is recording when a URL was seen, so
#                   these moving is the feature, not a determinism defect.
MANIFEST_EXTRA = {"started_at", "finished_at"}
# `freshness` is the SAME clock-derived quantity as the record's `freshness_score`
# under the name `rejection.v1.json` gives it: that schema's `scores` block is
# `{relevance, quality, audience_fit, freshness}` while `record.v1.json` uses
# `*_score`. Enumerated under both names rather than normalized to one, because
# the leaf that actually moved is the one the document actually has.
REJECTION_EXTRA = {"rejected_at", "freshness"}
LEDGER_LEAVES = {"updated_at", "first_seen_at", "last_seen_at", "last_checked_at"}


class TestCrossClockEnumeration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root_1, cls.first = harvest("clean_t1")
        cls.root_2, cls.second = harvest("clean_t2", clock=T2)

    def differing(self, rel_1, rel_2=None):
        return diff_paths(load(self.root_1, rel_1),
                          load(self.root_2, rel_2 or rel_1))

    def run_rel(self, tail, run_id):
        return "runs/%s/%s" % (run_id, tail)

    def both(self, tail):
        return (self.run_rel(tail, self.first.run_id),
                self.run_rel(tail, self.second.run_id))

    def test_the_two_runs_are_genuinely_two_runs(self):
        self.assertNotEqual(self.first.run_id, self.second.run_id)

    def test_the_record_bearing_artifacts_differ_in_exactly_the_five(self):
        """Cells and topics: the plan §10 contract, over every one of them."""
        names = set()
        for cell_id in configured_ids():
            names |= leaf_names(self.differing(*self.both("cells/%s.json" % cell_id)))
        for topic_slug in configured_topics():
            names |= leaf_names(self.differing(*self.both("topics/%s.json" % topic_slug)))
        self.assertEqual(names, CLOCK_DERIVED)

    def test_the_coverage_report_differs_in_a_subset_of_the_five(self):
        names = leaf_names(self.differing(*self.both("coverage.json")))
        self.assertTrue(names)
        self.assertLessEqual(names, CLOCK_DERIVED)

    def test_the_alias_conflict_artifact_differs_in_a_subset_of_the_five(self):
        names = leaf_names(self.differing(*self.both("alias_conflicts.json")))
        self.assertTrue(names)
        self.assertLessEqual(names, CLOCK_DERIVED)
        # The committed corpus records no conflict, which is why `detected_at`
        # cannot appear above. Asserted so the reason stays visible.
        self.assertEqual(load(self.root_1,
                              self.run_rel("alias_conflicts.json",
                                           self.first.run_id))["conflicts"], [])

    def test_the_manifest_differs_in_the_five_plus_its_own_two_instants(self):
        names = leaf_names(self.differing(*self.both("manifest.json")))
        self.assertEqual(names, (CLOCK_DERIVED | MANIFEST_EXTRA) & names)
        self.assertLessEqual(names, CLOCK_DERIVED | MANIFEST_EXTRA)
        self.assertTrue(MANIFEST_EXTRA <= names)

    def test_a_rejection_log_differs_in_the_five_plus_rejected_at(self):
        names = set()
        for cell_id in configured_ids():
            names |= leaf_names(self.differing("rejections/%s.json" % cell_id))
        self.assertLessEqual(names, CLOCK_DERIVED | REJECTION_EXTRA)
        self.assertTrue(REJECTION_EXTRA <= names)

    def test_a_ledger_differs_only_in_when_it_saw_things(self):
        names = set()
        for cell_id in configured_ids():
            names |= leaf_names(self.differing("ledgers/%s.json" % cell_id))
        self.assertLessEqual(names, LEDGER_LEAVES)
        self.assertTrue(names)

    def test_no_other_file_moved_at_all(self):
        """Every JSON path in the tree is accounted for by a test above."""
        covered = set()
        for cell_id in configured_ids():
            covered |= {self.run_rel("cells/%s.json" % cell_id, self.first.run_id),
                        "rejections/%s.json" % cell_id,
                        "ledgers/%s.json" % cell_id}
        for topic_slug in configured_topics():
            covered.add(self.run_rel("topics/%s.json" % topic_slug, self.first.run_id))
        for tail in ("manifest.json", "coverage.json", "alias_conflicts.json"):
            covered.add(self.run_rel(tail, self.first.run_id))
        self.assertEqual(set(listing(self.root_1)) - covered, {"LATEST_RUN_ID"})

    def test_the_request_accounting_is_identical(self):
        """Time moved; what the run cost did not. Includes the S6-6A target
        counters, whose whole claim is that they are observed rather than
        estimated — an estimate would have no reason to survive a clock change."""
        first = load(self.root_1,
                     self.run_rel("manifest.json", self.first.run_id))
        second = load(self.root_2,
                      self.run_rel("manifest.json", self.second.run_id))
        self.assertEqual(second["request_accounting"], first["request_accounting"])
        for key in ("target_http_attempts", "target_retries",
                    "target_redirect_hops", "http_attempts",
                    "source_fetch_owners", "target_fetch_owners"):
            with self.subTest(key):
                self.assertIn(key, first["request_accounting"])

    def test_freshness_decayed_rather_than_froze(self):
        """Anti-vacuity for `freshness_score`: it is in the set because it moves."""
        def scores(root, run_id):
            return {r["record_id"]: r["freshness_score"]
                    for r in load(root, self.run_rel("cells/%s.json" % CELL,
                                                     run_id))["records"]
                    if r["record_type"] == "full"
                    and r.get("freshness_score") is not None}
        early = scores(self.root_1, self.first.run_id)
        late = scores(self.root_2, self.second.run_id)
        self.assertTrue(early)
        for record_id, value in early.items():
            with self.subTest(record_id):
                self.assertLess(late[record_id], value)

    def test_nothing_was_re_judged(self):
        first = {r["record_id"]: r for r in
                 load(self.root_1, self.run_rel("cells/%s.json" % CELL,
                                                self.first.run_id))["records"]}
        second = {r["record_id"]: r for r in
                  load(self.root_2, self.run_rel("cells/%s.json" % CELL,
                                                 self.second.run_id))["records"]}
        self.assertEqual(sorted(first), sorted(second))
        for record_id, record in first.items():
            other = second[record_id]
            for field in ("content_id", "identity_url", "canonical_url", "cell_id",
                          "relevance_score", "quality_score", "audience_fit_score",
                          "classification", "case_facets", "access_status",
                          "http_status", "content_hash", "url_aliases"):
                with self.subTest(record_id=record_id, field=field):
                    self.assertEqual(other.get(field), record.get(field))


# ------------------------------------------------- 4 · composed target corpora
class ComposedScenario:
    """Shared setup and the two assertions every composed scenario owes.

    A MIXIN rather than a TestCase subclass on purpose: a shared base that
    inherits from TestCase is collected and run in its own right, with no corpus
    to build. Skipping it would work and would also leave a permanent skip in the
    suite's output, which is a worse thing for a reader to have to interpret.
    """

    KEY = None
    CORPUS = None

    @classmethod
    def setUpClass(cls):
        cls.root, cls.result = harvest(cls.KEY, fixtures_dir=cls.CORPUS())
        cls.manifest = load(cls.root, "runs/%s/manifest.json" % cls.result.run_id)
        cls.records = {
            record["identity_url"]: record
            for record in load(cls.root, "runs/%s/cells/%s.json"
                               % (cls.result.run_id, CELL))["records"]
            if record["record_type"] == "full"}

    def statuses(self):
        return {url: self.records[url]["access_status"] for url in ACCEPTED}

    def test_all_four_accepted_records_are_present(self):
        self.assertEqual(sorted(self.records), sorted(ACCEPTED))

    def test_the_tree_is_complete_and_every_artifact_validates(self):
        self.assertCompleteTree(self.root, self.result)
        self.assertEveryArtifactValidates(self.root)


class TestComposedTerminalFailures(ComposedScenario, TreeCase):
    """404, 410, 403 and a terminal 500 in one run — every record still complete.

    No retry sequence is asserted. What the committed client does between the
    first 500 and the raise is its own tested contract (plan §5.0).
    """

    KEY = "composed_failures"
    CORPUS = staticmethod(failures_corpus)

    def test_each_failure_maps_to_its_committed_access_status(self):
        self.assertEqual(self.statuses(), {
            ACCEPTED[0]: "not_found",
            ACCEPTED[1]: "gone",
            ACCEPTED[2]: "auth_required",
            ACCEPTED[3]: "server_error"})

    def test_no_failed_record_claims_to_have_been_fetched(self):
        for url in ACCEPTED:
            with self.subTest(url):
                self.assertEqual(self.records[url]["verification_status"],
                                 "unverified")
                self.assertIsNone(self.records[url]["content_hash"])

    def test_the_failure_class_survives_in_the_evidence(self):
        self.assertIn("ClientError", self.records[ACCEPTED[0]]["verification_evidence"])
        self.assertIn("ServerError", self.records[ACCEPTED[3]]["verification_evidence"])

    def test_the_identities_did_not_move(self):
        for url in ACCEPTED:
            with self.subTest(url):
                self.assertEqual(self.records[url]["canonical_url"], url)
                self.assertEqual(self.records[url]["url_aliases"], [])

    def test_an_observed_failure_does_not_make_the_run_ineligible(self):
        """§8: a 404 or a robots denial is CHECKED — it has a real observed status.
        Only a target nobody looked at keeps a run from being publishable."""
        self.assertTrue(self.manifest["publication_eligible"])
        self.assertIsNone(self.manifest["publication_ineligible_reason"])

    def test_no_record_was_dropped_by_a_failure(self):
        row = [c for c in self.manifest["cells"] if c["cell_id"] == CELL][0]
        self.assertEqual(row["accepted"], 4)
        self.assertEqual(row["status"], "ok")

    def test_the_accounting_identity_still_holds_with_retries_in_play(self):
        """A terminal 500 costs the committed number of attempts, whatever that
        is; this asserts the DV-8 identity rather than the retry count."""
        acct = self.manifest["request_accounting"]
        self.assertEqual(acct["target_http_attempts"],
                         acct["target_fetch_owners"] + acct["target_retries"]
                         + acct["target_redirect_hops"])
        self.assertGreater(acct["target_retries"], 0,
                           "the terminal 500 must have been retried by the client")


class TestComposedBodiesAndRedirects(ComposedScenario, TreeCase):
    """An empty body, a non-HTML body, a permanent chain and a temporary one."""

    KEY = "composed_bodies"
    CORPUS = staticmethod(bodies_corpus)

    def test_each_body_and_redirect_maps_as_committed(self):
        self.assertEqual(self.statuses(), {
            ACCEPTED[0]: "unreachable",     # EmptyResponse (CF-16)
            ACCEPTED[1]: "ok",              # application/pdf, hashed not parsed
            ACCEPTED[2]: "redirected",      # every hop permanent
            ACCEPTED[3]: "ok"})             # a 302 in the chain is not a redirect
                                            # worth rewriting identity for

    def test_the_empty_body_names_its_exact_class(self):
        self.assertIn("EmptyResponse",
                      self.records[ACCEPTED[0]]["verification_evidence"])

    def test_the_non_html_body_was_hashed_and_not_parsed(self):
        record = self.records[ACCEPTED[1]]
        self.assertTrue(record["content_hash"])
        self.assertEqual(record["url_aliases"], [])
        self.assertEqual(record["canonical_url"], ACCEPTED[1])

    def test_a_permanent_chain_adopts_an_alias_and_moves_canonical_only(self):
        record = self.records[ACCEPTED[2]]
        self.assertEqual([a["kind"] for a in record["url_aliases"]],
                         ["permanent_redirect"])
        self.assertEqual(record["canonical_url"],
                         "https://tgt.harvest.test/redirect-permanent-c")
        # Identity is not a redirect's to move.
        self.assertEqual(record["identity_url"], ACCEPTED[2])
        self.assertEqual(record["target_url"], ACCEPTED[2])

    def test_a_temporary_hop_adopts_nothing(self):
        record = self.records[ACCEPTED[3]]
        self.assertEqual(record["url_aliases"], [])
        self.assertEqual(record["canonical_url"], ACCEPTED[3])

    def test_the_alias_carries_the_run_instant_it_was_observed_at(self):
        """The sixth clock-derived leaf, and the reason this corpus is compared
        same-clock rather than against the committed five."""
        alias = self.records[ACCEPTED[2]]["url_aliases"][0]
        self.assertEqual(alias["observed_at"], STAMP1)

    def test_the_composed_corpus_is_byte_deterministic(self):
        again, result = harvest("composed_bodies_again", fixtures_dir=self.CORPUS())
        self.assertEqual(result.run_id, self.result.run_id)
        self.assertEqual(tree_hash(again), tree_hash(self.root))


class TestComposedCanonicalAdjudication(ComposedScenario, TreeCase):
    """Three contradictory canonicals and one self-canonical, in one run."""

    KEY = "composed_canonical"
    CORPUS = staticmethod(canonical_corpus)

    def setUp(self):
        self.artifact = load(self.root, "runs/%s/alias_conflicts.json"
                             % self.result.run_id)

    def test_no_canonical_moved_a_records_url(self):
        for url in ACCEPTED:
            with self.subTest(url):
                self.assertEqual(self.records[url]["canonical_url"], url)
                self.assertEqual(self.records[url]["url_aliases"], [])

    def test_every_record_was_still_fetched_successfully(self):
        self.assertEqual(set(self.statuses().values()), {"ok"})

    def test_the_three_conflicts_were_recorded_with_their_committed_reasons(self):
        self.assertEqual(
            sorted(row["reason"] for row in self.artifact["conflicts"]),
            sorted([aliases_mod.CONFLICT_CROSS_DOMAIN_UNAUTHORIZED,
                    aliases_mod.CONFLICT_MULTIPLE_CANONICALS,
                    aliases_mod.CONFLICT_ROBOTS_UNVERIFIED]))

    def test_the_self_canonical_produced_neither_alias_nor_conflict(self):
        """A page naming itself is a no-op, not contradictory evidence."""
        named = {row["identity_url"] for row in self.artifact["conflicts"]}
        self.assertNotIn(ACCEPTED[3], named)

    def test_the_manifest_count_agrees_with_the_artifact(self):
        self.assertEqual(self.manifest["alias_conflicts_count"],
                         len(self.artifact["conflicts"]))
        self.assertEqual(self.artifact["alias_conflicts_count"],
                         len(self.artifact["conflicts"]))

    def test_a_conflict_does_not_make_the_run_ineligible(self):
        """Recording refused evidence is not a defect in the run."""
        self.assertTrue(self.manifest["publication_eligible"])

    def test_the_conflicts_carry_the_run_instant(self):
        """`detected_at` is the seventh clock-derived leaf, and it exists only
        here — never in the committed corpus, whose conflict set is empty."""
        for row in self.artifact["conflicts"]:
            with self.subTest(row["conflict_id"]):
                self.assertEqual(row["detected_at"], STAMP1)

    def test_the_composed_corpus_is_byte_deterministic(self):
        again, result = harvest("composed_canonical_again",
                                fixtures_dir=self.CORPUS())
        self.assertEqual(result.run_id, self.result.run_id)
        self.assertEqual(tree_hash(again), tree_hash(self.root))


# ------------------------------------------------- 5 · accounting & eligibility
class TestBudgetSkipMakesARunIneligible(TreeCase):
    """The one thing that must keep a run unpublishable: a target nobody checked.

    Produced by lowering the per-cell fetch cap for the duration of one run — a
    test-local patch of the committed module constant, not a config or production
    edit, and the same technique `test_target_ownership.py` uses to reach the cap.
    """

    @classmethod
    def setUpClass(cls):
        cls.root = temp_root("s6_7_budget_")
        original = run_cells.MAX_TARGET_FETCHES_PER_CELL
        run_cells.MAX_TARGET_FETCHES_PER_CELL = 2
        try:
            cls.result = run_cells.run(cls.root, clock=lambda: T1)
        finally:
            run_cells.MAX_TARGET_FETCHES_PER_CELL = original
        cls.manifest = load(cls.root, "runs/%s/manifest.json" % cls.result.run_id)
        cls.records = {
            record["identity_url"]: record
            for record in load(cls.root, "runs/%s/cells/%s.json"
                               % (cls.result.run_id, CELL))["records"]
            if record["record_type"] == "full"}

    def test_exactly_two_targets_were_checked(self):
        checked = [url for url, record in self.records.items()
                   if record["access_status"] != "not_checked"]
        skipped = [url for url, record in self.records.items()
                   if record["access_status"] == "not_checked"]
        self.assertEqual(len(checked), 2)
        self.assertEqual(len(skipped), 2)

    def test_the_cap_was_applied_in_the_committed_candidate_order(self):
        """Which two were skipped is a function of content, not of iteration."""
        skipped = sorted(url for url, record in self.records.items()
                         if record["access_status"] == "not_checked")
        again_root = temp_root("s6_7_budget_again_")
        original = run_cells.MAX_TARGET_FETCHES_PER_CELL
        run_cells.MAX_TARGET_FETCHES_PER_CELL = 2
        try:
            again = run_cells.run(again_root, clock=lambda: T1)
        finally:
            run_cells.MAX_TARGET_FETCHES_PER_CELL = original
        repeat = sorted(
            record["identity_url"]
            for record in load(again_root, "runs/%s/cells/%s.json"
                               % (again.run_id, CELL))["records"]
            if record["record_type"] == "full"
            and record["access_status"] == "not_checked")
        self.assertEqual(repeat, skipped)
        self.assertEqual(tree_hash(again_root), tree_hash(self.root))

    def test_a_skipped_record_claims_nothing_about_the_page(self):
        for url, record in self.records.items():
            if record["access_status"] != "not_checked":
                continue
            with self.subTest(url):
                self.assertIsNone(record["http_status"])
                self.assertIsNone(record["content_hash"])
                self.assertEqual(record["verification_status"], "unverified")

    def test_the_run_is_ineligible_and_says_why(self):
        self.assertFalse(self.manifest["publication_eligible"])
        self.assertIn("no target evidence",
                      self.manifest["publication_ineligible_reason"])

    def test_the_skipped_targets_cost_nothing(self):
        """Genuine zeros: two owners made no request at all, so the run's attempts
        account for the two fetches only."""
        acct = self.manifest["request_accounting"]
        self.assertEqual(acct["target_fetch_owners"], 4)
        self.assertEqual(acct["target_http_attempts"], 2)
        self.assertEqual(acct["target_retries"], 0)
        self.assertEqual(acct["target_redirect_hops"], 0)

    def test_the_source_accounting_is_untouched_by_the_cap(self):
        base_root, base = harvest("clean_t1")
        base_manifest = load(base_root, "runs/%s/manifest.json" % base.run_id)
        for key in ("source_fetch_owners", "http_attempts", "retries",
                    "redirect_hops", "conditional_revalidations"):
            with self.subTest(key):
                self.assertEqual(self.manifest["request_accounting"][key],
                                 base_manifest["request_accounting"][key])

    def test_every_artifact_still_validates(self):
        self.assertEveryArtifactValidates(self.root)


class TestAccountingAcrossRuns(unittest.TestCase):

    def manifest(self, key, **kw):
        root, result = harvest(key, **kw)
        return load(root, "runs/%s/manifest.json" % result.run_id)

    def test_equivalent_fresh_runs_report_identical_accounting(self):
        self.assertEqual(self.manifest("clean_t1_again")["request_accounting"],
                         self.manifest("clean_t1")["request_accounting"])

    def test_one_identity_is_one_attempt_on_the_committed_corpus(self):
        acct = self.manifest("clean_t1")["request_accounting"]
        self.assertEqual(acct["target_fetch_owners"], 4)
        self.assertEqual(acct["target_http_attempts"], 4)

    def test_a_shared_identity_is_counted_once_across_two_topics(self):
        """Proved with test-local synthetic candidates, because a shared identity
        is a property of what the feeds surfaced and the committed corpus has
        none (plan §14 E15)."""
        shared = "https://tgt.harvest.test/ok-plain"
        pool = pool_mod.CandidatePool("s6-7-shared")
        outcomes = {}
        calls = []
        client = _RecordingClient(calls)
        for cell_id in ("cases__case-studies", "discourse__market-and-investment"):
            topic, category = cell_id.split("__", 1)
            run = run_cells.CellRun({"cell_id": cell_id, "topic_slug": topic,
                                     "category_slug": category, "sources": []})
            run.extracted = (_Candidate(shared),)
            run.verdicts = {"k-%s" % cell_id: _Accepted()}
            run.verdicts = {run.extracted[0].candidate_key: _Accepted()}
            run_cells._fetch_targets(
                run, client=client, budget=RequestBudget(), pool=pool,
                outcomes=outcomes, clock=lambda: STAMP1,
                canon_policy=aliases_mod.load_canonicalization())
        self.assertEqual(len(calls), 1)
        self.assertEqual(pool.accounting()["target_fetch_owners"], 1)
        totals = artifacts.target_request_accounting(list(outcomes.values()))
        self.assertEqual(totals["target_http_attempts"], 1)

    def test_the_two_key_spaces_are_never_summed(self):
        acct = self.manifest("clean_t1")["request_accounting"]
        for combined in ("total_http_attempts", "total_attempts",
                         "http_attempts_including_targets"):
            with self.subTest(combined):
                self.assertNotIn(combined, acct)
        self.assertNotEqual(acct["http_attempts"],
                            25 + acct["target_http_attempts"])


class _Candidate:
    def __init__(self, url):
        self.candidate_key = "k-%s" % url
        self.target_url = url
        self.identity_url = url
        self.canonical_url = url


class _Accepted:
    accepted = True


# --------------------------------------------------- 6 · recovery and refusal
class TestInterruptedFetchPhasePublishesNothing(unittest.TestCase):
    """All target fetching completes before the first artifact byte (plan §7.3),
    so an interruption there must leave the root exactly as it found it — and the
    retry is an ordinary fresh run, because there is no resume."""

    @classmethod
    def setUpClass(cls):
        cls.root = temp_root("s6_7_interrupt_")
        real = targetfetch_mod.fetch_target
        state = {"n": 0}

        def interrupt(url, **kw):
            state["n"] += 1
            if state["n"] > 2:
                raise KeyboardInterrupt("simulated interruption mid fetch phase")
            return real(url, **kw)

        run_cells.targetfetch_mod.fetch_target = interrupt
        try:
            run_cells.run(cls.root, clock=lambda: T1)
        except KeyboardInterrupt:
            cls.interrupted = True
        else:
            cls.interrupted = False
        finally:
            run_cells.targetfetch_mod.fetch_target = real
        cls.fetched_before_dying = state["n"]

        # CAPTURED HERE, not re-observed per test. The retry below deliberately
        # writes into this same root, and a test that read the directory again
        # would then be asserting whatever ran before it — which is how the first
        # draft of this class passed or failed on alphabetical method order. A
        # suite about determinism does not get to be order-dependent itself.
        cls.after_interruption = listing(cls.root)
        cls.temps_after_interruption = temps_under(cls.root)
        cls.pointer_after_interruption = artifacts.read_latest_run_id(cls.root)
        cls.verified_after_interruption = artifacts.verify_latest_run_id(cls.root)

    def test_the_run_really_was_interrupted(self):
        self.assertTrue(self.interrupted)

    def test_the_interruption_really_was_part_way_through(self):
        """Two targets were fetched before it died, so the phase was genuinely
        in flight rather than never started."""
        self.assertGreater(self.fetched_before_dying, 2)

    def test_the_root_is_completely_empty(self):
        self.assertEqual(self.after_interruption, [])

    def test_no_run_artifact_was_published(self):
        self.assertEqual([rel for rel in self.after_interruption
                          if rel.startswith("runs/")], [])

    def test_no_cross_run_cell_file_was_written(self):
        for name in ("ledgers/", "rejections/"):
            with self.subTest(name):
                self.assertEqual([rel for rel in self.after_interruption
                                  if rel.startswith(name)], [])

    def test_no_pointer_was_written(self):
        self.assertIsNone(self.pointer_after_interruption)
        self.assertIsNone(self.verified_after_interruption)

    def test_no_temp_debris_survives(self):
        self.assertEqual(self.temps_after_interruption, [])

    def test_the_retry_is_an_ordinary_fresh_run_with_identical_output(self):
        """No resume, and none needed: the same clock in the same root produces
        exactly the tree a clean run produces elsewhere."""
        result = run_cells.run(self.root, clock=lambda: T1)
        base_root, base = harvest("clean_t1")
        self.assertEqual(result.run_id, base.run_id)
        self.assertEqual(tree_hash(self.root), tree_hash(base_root))


class TestFinishedRunIsRefusedBeforeAnyRequest(unittest.TestCase):
    """A repeat costs nothing at all — not a byte, and not a request."""

    @classmethod
    def setUpClass(cls):
        cls.root = temp_root("s6_7_repeat_")
        run_cells.run(cls.root, clock=lambda: T1)
        cls.before = snapshot(cls.root)
        cls.opener_calls = []
        cls.loads = []
        real_loader = fixtures_mod.load_target_fixtures
        real_call = fixtures_mod.FixtureOpener.__call__

        def counting_loader(*a, **kw):
            cls.loads.append(a)
            return real_loader(*a, **kw)

        def counting_call(self, req, timeout=20):
            cls.opener_calls.append(getattr(req, "full_url", req))
            return real_call(self, req, timeout=timeout)

        fixtures_mod.load_target_fixtures = counting_loader
        fixtures_mod.FixtureOpener.__call__ = counting_call
        cls.error = None
        try:
            run_cells.run(cls.root, clock=lambda: T1)
        except run_cells.RunCellsError as exc:
            cls.error = str(exc)
        finally:
            fixtures_mod.load_target_fixtures = real_loader
            fixtures_mod.FixtureOpener.__call__ = real_call

    def test_the_repeat_was_refused(self):
        self.assertIsNotNone(self.error, "the repeated run was not refused at all")
        self.assertIn("already finished", self.error)

    def test_not_one_request_was_issued(self):
        self.assertEqual(self.opener_calls, [])

    def test_the_fixture_corpus_was_never_even_loaded(self):
        """The refusal precedes the opener's construction, not merely its use."""
        self.assertEqual(self.loads, [])

    def test_the_tree_is_hash_identical_after_the_refusal(self):
        self.assertEqual(snapshot(self.root), self.before)

    def test_the_counters_would_have_caught_a_request(self):
        """Anti-vacuity: the same instrumentation sees a real run's traffic."""
        calls, loads = [], []
        real_loader = fixtures_mod.load_target_fixtures
        real_call = fixtures_mod.FixtureOpener.__call__

        def counting_loader(*a, **kw):
            loads.append(a)
            return real_loader(*a, **kw)

        def counting_call(inner_self, req, timeout=20):
            calls.append(getattr(req, "full_url", req))
            return real_call(inner_self, req, timeout=timeout)

        fixtures_mod.load_target_fixtures = counting_loader
        fixtures_mod.FixtureOpener.__call__ = counting_call
        fresh = temp_root("s6_7_probe_")
        try:
            run_cells.run(fresh, cells=[CELL], clock=lambda: T2)
        finally:
            fixtures_mod.load_target_fixtures = real_loader
            fixtures_mod.FixtureOpener.__call__ = real_call
        self.assertGreater(len(calls), 0)
        self.assertGreater(len(loads), 0)


class TestPointerRemainsCheckable(unittest.TestCase):

    def test_verify_latest_run_id_names_the_finished_run(self):
        root, result = harvest("clean_t1")
        self.assertEqual(artifacts.verify_latest_run_id(root), result.run_id)

    def test_an_empty_root_names_nothing_rather_than_raising(self):
        self.assertIsNone(artifacts.verify_latest_run_id(temp_root("s6_7_empty_")))

    def test_a_pointer_naming_a_missing_manifest_raises(self):
        """The predicate is only useful if it can fail."""
        root = temp_root("s6_7_broken_")
        artifacts.write_latest_run_id(root, "20260730T120000Z-9")
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.verify_latest_run_id(root)


# ------------------------------------------------------------------ boundary
class TestBoundary(unittest.TestCase):

    def test_the_committed_fixture_corpus_was_not_modified(self):
        """Every scenario is a copy. Asserted against the repository itself, since
        a composer bug would otherwise edit the corpus every other suite reads."""
        import subprocess
        rc = subprocess.call(["git", "diff", "--exit-code", "--quiet", "HEAD",
                              "--", "tests/fixtures/harvest"], cwd=ROOT)
        self.assertEqual(rc, 0)

    def test_no_repository_runtime_path_was_created(self):
        for leaked in ("state/taxonomy_harvest", "data/harvested", "runs",
                       "LATEST_RUN_ID"):
            with self.subTest(leaked):
                self.assertFalse(os.path.exists(os.path.join(ROOT, leaked)))

    def test_every_composed_fixture_still_loads_as_a_committed_one_would(self):
        """The composer substitutes CONTENT; the loader's shape contract is
        untouched, and a fixture it would refuse to serve is not a scenario."""
        for corpus in (failures_corpus(), bodies_corpus(), canonical_corpus()):
            loaded = fixtures_mod.load_target_fixtures(
                os.path.join(corpus, "targets"))
            with self.subTest(corpus):
                self.assertEqual(len(loaded), 24)
                for fixture_id in ACCEPTED_FIXTURES:
                    self.assertEqual(loaded[fixture_id]["fixture_id"], fixture_id)

    def test_the_composed_corpora_kept_the_accepted_urls(self):
        """If a substitution moved a URL the scenarios would not be comparable to
        the clean run at all."""
        for corpus in (failures_corpus(), bodies_corpus(), canonical_corpus()):
            loaded = fixtures_mod.load_target_fixtures(
                os.path.join(corpus, "targets"))
            with self.subTest(corpus):
                self.assertEqual(
                    sorted(loaded[f]["url"] for f in ACCEPTED_FIXTURES),
                    sorted(ACCEPTED))

    def test_no_composed_fixture_carries_a_transport_directive(self):
        """Stage 6 owns no transport simulation, in a temp tree either."""
        for corpus in (failures_corpus(), bodies_corpus(), canonical_corpus()):
            for name in sorted(os.listdir(os.path.join(corpus, "targets"))):
                with open(os.path.join(corpus, "targets", name),
                          encoding="utf-8") as handle:
                    fixture = json.load(handle)
                for key in fixtures_mod.FORBIDDEN_TARGET_KEYS:
                    with self.subTest(name=name, key=key):
                        self.assertNotIn(key, fixture)


if __name__ == "__main__":
    unittest.main(verbosity=2)
