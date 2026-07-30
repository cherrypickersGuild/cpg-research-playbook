#!/usr/bin/env python3
"""artifacts.py — deterministic, atomic artifact writing (S5-1).

Stage 4 built records in memory and wrote nothing. This module is the one place
that puts bytes on disk, and it exists so that every artifact in Stage 5 gets the
same three guarantees rather than each writer inventing its own:

  * ONE SERIALIZATION. Identical logical input yields identical bytes. Key order
    comes from `sort_keys`, not from dict insertion order, so a document built by
    two different code paths still hashes the same. The explicit `newline="\\n"`
    matters: this repository is checked out on Windows, and text mode would
    otherwise turn every artifact into CRLF and break byte-comparison against a
    POSIX run.
  * NOTHING PARTIAL IS EVER READABLE. Writes go to a uniquely named temp file in
    the DESTINATION directory, are fsynced, and are then moved into place with
    `os.replace`. A reader sees the previous complete artifact or the new
    complete artifact — never a half-written one. The temp name is unique per
    write (`uuid4`), never a fixed `<file>.tmp`, because a fixed name is a shared
    name and two writers would interleave through it.
  * NOTHING INVALID REACHES DISK. `write_document` validates against the
    committed schema BEFORE serializing. A document that does not validate raises
    and writes no file at all, so the artifact tree can be trusted without
    re-reading it.

A temp file never outlives its write: failure and interruption both clean up, so
an interrupted run leaves the previous artifact intact and no debris behind.

S5-2 adds the first two artifact shapes — cell and topic — on top of that base.
They derive every count from the records they were handed, so a metadata block
can never disagree with the records beside it, and they refuse a record the
record schema rejects rather than burying it in an artifact.

S5-3 added the ledger and rejection-log PATHS here, beside the other two, so the
committed layout has one home. Their MEANING — merge semantics, outcome
transitions, what counts as a rejection — lives in `ledger.py`.

S5-7 added the recovery primitives beside them: a `WriteJournal` that sweeps the
temp files ONE run created (and provably nothing else), `run_is_finished` so a
driver can refuse a repeat before it writes rather than after, and
`verify_latest_run_id`, which turns the pointer's promise into something a
caller can check after an interruption instead of assume.

Not here: cell execution (S5-6 drives this module, not the reverse), target
fetching, locking, concurrency, or the network.
"""
import contextlib
import copy
import datetime
import json
import os
import uuid

from . import coverage as coverage_mod
from . import records as records_mod
from . import schema
from . import scheduler
from . import verify as verify_mod

# `YYYYMMDDTHHMMSSZ-<pid>`, the run identifier format fixed by
# IMPLEMENTATION_PLAN.md §10.
RUN_ID_FORMAT = "%Y%m%dT%H%M%SZ"

# Every in-flight write is `<dir>/.tmp_<uuid4hex>_<basename>`. The prefix is
# matched by the committed `state/.tmp_*` ignore rule and is what a sweeper
# looks for; no code path ever READS a file with this prefix.
TEMP_PREFIX = ".tmp_"

# The pointer file. Written LAST, after a manifest is safely on disk, so it can
# never name a run that did not finish.
LATEST_RUN_ID_NAME = "LATEST_RUN_ID"

# Stage 5's only mode. The other five values in the schema's enum belong to the
# stages that introduce them: smoke, smoke_model, refresh, linkcheck, migration.
MODE_HARVEST = "harvest"

# A configured cell that was never reached is `not_run` — recorded, never omitted.
STATUS_NOT_RUN = "not_run"
CELL_ERROR_STATUSES = ("adapter_error", "infrastructure_error")

# The committed `record.v1.json` access_status value meaning "no check occurred".
# Named from the schema's own vocabulary rather than imported from a Stage 6
# module, so this Stage 5 file gains no dependency on a later stage for one string.
NOT_CHECKED = "not_checked"


class ArtifactError(Exception):
    """A contract violation this module refuses to paper over."""


# --------------------------------------------------------------- serialization
def serialize(doc):
    """The one serialization. Deterministic bytes, UTF-8, LF, trailing newline.

    `sort_keys` makes byte output a function of content rather than of how the
    dict happened to be built. `ensure_ascii=False` keeps non-ASCII titles
    readable instead of escaping them into `\\uXXXX`.
    """
    text = json.dumps(doc, sort_keys=True, ensure_ascii=False, indent=2,
                      separators=(",", ": ")) + "\n"
    return text.encode("utf-8")


# ----------------------------------------------------------------- atomic write
def _temp_path(directory, name):
    return os.path.join(directory, "%s%s_%s" % (TEMP_PREFIX, uuid.uuid4().hex, name))


def _fsync_dir(directory):
    """Make the rename itself durable, where the platform allows it.

    Opening a directory read-only is a POSIX facility; Windows refuses it. That
    is a durability nicety, not a correctness requirement — `os.replace` has
    already made the swap atomic — so failure here is ignored rather than
    surfaced as an artifact failure.
    """
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


# ---------------------------------------------------------------- write journal
class WriteJournal:
    """Every temp file one run created, so its own debris can be swept (S5-7).

    `write_atomic` already removes its temp file on failure and on interruption.
    This exists for the case where that cleanup ITSELF cannot complete: the
    unlink is best-effort by necessity — a file can be held open, a directory can
    turn read-only — and a swallowed failure there is exactly how a `.tmp_*` file
    outlives the write that made it.

    OWNERSHIP IS PROVED, NEVER GUESSED. The journal does not glob for `.tmp_*`;
    it removes only paths it watched being created. A temp file belonging to
    anything else is left strictly alone, which matters because a glob-and-delete
    sweeper would destroy another writer's in-flight file. A finished artifact is
    untouched by construction — it never carries the temp prefix — and the unlink
    re-checks that prefix anyway, so the sweeper cannot be talked into removing a
    real artifact by a bad entry.
    """

    def __init__(self, owner=None):
        self.owner = owner            # the run_id, for diagnosis only
        self._outstanding = []
        self.swept = []

    def note(self, path):
        """Record a temp file that is about to exist."""
        self._outstanding.append(path)

    def done(self, path):
        """Forget a temp file that has been renamed into place or removed."""
        try:
            self._outstanding.remove(path)
        except ValueError:
            pass

    @property
    def outstanding(self):
        return tuple(self._outstanding)

    def sweep(self):
        """Remove what this run created and left behind. Never raises.

        Called from a `finally`, so raising here would mask the interruption that
        made the sweep necessary. A path that cannot be removed stays outstanding
        and is reported rather than retried.
        """
        remaining = []
        for path in self._outstanding:
            if not os.path.basename(path).startswith(TEMP_PREFIX):
                # Refused, not swept: the journal may only ever remove temp
                # files, whatever it was told.
                continue
            if not os.path.exists(path):
                continue
            try:
                os.unlink(path)
            except OSError:
                remaining.append(path)
                continue
            self.swept.append(path)
        self._outstanding = remaining
        return list(self.swept)


# The journal in force for the current run, or None. A module-level handle
# rather than a parameter because every writer in the process — including
# `ledger.py`'s two — funnels through `write_atomic`, and threading an argument
# through each of them would leave whichever one was forgotten unswept.
# Sequential by contract: `write_journal` REFUSES to nest, so two overlapping
# runs in one process cannot cross-attribute their temp files (see plan §9.1).
_ACTIVE_JOURNAL = None


@contextlib.contextmanager
def write_journal(owner=None):
    """Install a journal for the duration of one run, and sweep on the way out."""
    global _ACTIVE_JOURNAL
    if _ACTIVE_JOURNAL is not None:
        raise ArtifactError(
            "a write journal is already active (owner %r); refusing to nest, "
            "because two journals cannot both own the same temp file"
            % (_ACTIVE_JOURNAL.owner,))
    journal = WriteJournal(owner)
    _ACTIVE_JOURNAL = journal
    try:
        yield journal
    finally:
        _ACTIVE_JOURNAL = None
        journal.sweep()


def write_atomic(path, data):
    """Write `data` to `path` so that no partial file is ever observable.

    The temp file is created in the DESTINATION directory, not a system temp
    dir, because `os.replace` is only atomic within one filesystem. Missing
    parent directories are created — the artifact layout is nested, and having
    every caller repeat that is how a caller eventually forgets.
    """
    if not isinstance(data, bytes):
        raise ArtifactError("write_atomic needs bytes, got %s" % type(data).__name__)

    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    tmp = _temp_path(directory, os.path.basename(path))
    journal = _ACTIVE_JOURNAL
    if journal is not None:
        # Noted BEFORE the file exists: a crash between creation and the note
        # would otherwise leave debris the journal has never heard of.
        journal.note(tmp)
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        # BaseException, not Exception: KeyboardInterrupt is exactly the
        # interruption this cleanup exists for. The temp file must not outlive
        # the write that created it. If the unlink cannot complete, the entry
        # stays outstanding and the journal sweeps it at the end of the run.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    if journal is not None:
        journal.done(tmp)             # renamed into place; nothing left to sweep
    _fsync_dir(directory)
    return path


def write_document(path, doc, schema_name):
    """Validate against the committed schema, then serialize, then write.

    Validation comes first so an invalid document leaves the filesystem exactly
    as it was — no truncated file, no stale temp, no "write it and check later".
    """
    errors = schema.validate(doc, schema_name)
    if errors:
        raise ArtifactError("document does not validate against %s (%d problem(s)): %s"
                            % (schema_name, len(errors), "; ".join(errors[:3])))
    return write_atomic(path, serialize(doc))


# ------------------------------------------------------------------- run paths
def run_id(clock=None, pid=None):
    """`YYYYMMDDTHHMMSSZ-<pid>`. Both parts injectable so runs are reproducible."""
    now = clock() if clock is not None else datetime.datetime.now(datetime.timezone.utc)
    return "%s-%d" % (now.strftime(RUN_ID_FORMAT),
                      os.getpid() if pid is None else pid)


def run_dir(root, run_id_value):
    """The per-run directory under an injected root. Creates nothing."""
    if not run_id_value:
        raise ArtifactError("run_dir needs a run_id")
    return os.path.join(root, "runs", run_id_value)


def cell_artifact_path(root, run_id_value, cell_id):
    """`<root>/runs/<run_id>/cells/<cell_id>.json` — the committed layout."""
    return os.path.join(run_dir(root, run_id_value), "cells", "%s.json" % cell_id)


def topic_artifact_path(root, run_id_value, topic_slug):
    """`<root>/runs/<run_id>/topics/<topic_slug>.json` — the committed layout."""
    return os.path.join(run_dir(root, run_id_value), "topics", "%s.json" % topic_slug)


# The next two are NOT under `runs/<run_id>/`: a cell's ledger and rejection log
# are cross-run and cell-owned, per §2.1. That is the whole point of the ledger —
# it is what one run knows that the next one should not have to rediscover.
def ledger_path(root, cell_id):
    """`<root>/ledgers/<cell_id>.json` — cross-run, cell-owned."""
    return os.path.join(root, "ledgers", "%s.json" % cell_id)


def rejection_log_path(root, cell_id):
    """`<root>/rejections/<cell_id>.json` — cross-run, cell-owned."""
    return os.path.join(root, "rejections", "%s.json" % cell_id)


def coverage_report_path(root, run_id_value):
    """`<root>/runs/<run_id>/coverage.json` — per-run, like the artifacts."""
    return os.path.join(run_dir(root, run_id_value), "coverage.json")


def alias_conflicts_path(root, run_id_value):
    """`<root>/runs/<run_id>/alias_conflicts.json` — per-run, like coverage."""
    return os.path.join(run_dir(root, run_id_value), "alias_conflicts.json")


def run_manifest_path(root, run_id_value):
    """`<root>/runs/<run_id>/manifest.json` — per-run."""
    return os.path.join(run_dir(root, run_id_value), "manifest.json")


def latest_run_id_path(root):
    """`<root>/LATEST_RUN_ID` — the pointer to the newest COMPLETE run."""
    return os.path.join(root, LATEST_RUN_ID_NAME)


# ------------------------------------------------------------------- records
# The two schema-admitted keys of a record's classification evidence. This is
# D2: `classify.Evidence` also carries `field`, but `record.v1.json` closes
# `classification.evidence` items to {signal, matched}. The projection lives
# HERE, once, so no caller re-derives it and drifts.
CLASSIFICATION_EVIDENCE_KEYS = ("signal", "matched")


def project_classification_evidence(evidence):
    """Narrow classify's evidence to what a record may carry (D2).

    Accepts `classify.Evidence` objects or plain dicts and returns plain dicts.
    Forwarding the dataclass wholesale is refused by the schema, which is the
    point: the narrowing is a contract, not a formatting preference.
    """
    projected = []
    for item in evidence or ():
        if isinstance(item, dict):
            get = item.get
        else:
            get = lambda key, _item=item: getattr(_item, key, None)  # noqa: E731
        projected.append({key: get(key) for key in CLASSIFICATION_EVIDENCE_KEYS})
    return projected


def _validated_records(records):
    """Sort by the committed key, refusing anything the record schema rejects.

    Validation happens before assembly so a bad record surfaces as itself rather
    than as an opaque failure of the artifact that swallowed it.
    """
    ordered = records_mod.sort_records(list(records))
    for record in ordered:
        errors = schema.validate(record, "record.v1.json")
        if errors:
            raise ArtifactError(
                "record %r does not validate against record.v1.json: %s"
                % (record.get("record_id"), "; ".join(errors[:2])))
    return ordered


def _counts(ordered):
    """total = full + cross_reference. A pointer is not independent content."""
    full = sum(1 for r in ordered if r.get("record_type") == "full")
    cross = sum(1 for r in ordered if r.get("record_type") == "cross_reference")
    return {"total_records": len(ordered), "full_records": full,
            "cross_references": cross}


def _metadata(base, derived):
    """Merge caller metadata with derived counts, refusing a second source of truth."""
    merged = dict(base or {})
    clash = sorted(set(merged) & set(derived))
    if clash:
        raise ArtifactError(
            "metadata may not set derived count(s) %s — they are computed from "
            "the records so the two can never disagree" % ", ".join(clash))
    merged.update(derived)
    return merged


# --------------------------------------------------------- cell/topic artifacts
def build_cell_artifact(records, *, topic, topic_slug, category, category_slug,
                        cell_id, harvest_run_id, generated_at, metadata=None):
    """One cell's artifact. Records sorted by the committed key, counts derived.

    `metadata` carries only what cannot be derived from the records — `sources`
    (per-source outcome, which lives on the AdapterResults) and an optional
    `rejected` count. The three record counts are computed here.
    """
    ordered = _validated_records(records)
    return {
        "schema_version": records_mod.SCHEMA_VERSION,
        "artifact_type": "cell",
        "topic": topic,
        "topic_slug": topic_slug,
        "category": category,
        "category_slug": category_slug,
        "cell_id": cell_id,
        "generated_at": generated_at,
        "harvest_run_id": harvest_run_id,
        "metadata": _metadata(metadata or {"sources": []}, _counts(ordered)),
        "records": copy.deepcopy(ordered),
    }


def build_topic_artifact(cell_artifacts, *, topic, topic_slug, harvest_run_id,
                         generated_at, metadata=None):
    """The deterministic fold of one topic's cells.

    At most one record per `record_id` survives: `record_id` is derived from
    (topic, identity_url), so within a topic a duplicate `record_id` IS the same
    URL appearing in two categories. The winner is the first in committed sort
    order, which makes the choice a function of content rather than of the order
    cells happened to finish in.
    """
    merged = []
    for artifact in cell_artifacts:
        merged.extend(artifact.get("records", ()))

    # Sort BEFORE deduplicating. Deduplicating first would keep whichever copy
    # the cell iteration happened to reach first, making the survivor a function
    # of cell order; sorting first makes it a function of content.
    ordered, seen = [], set()
    for record in _validated_records(merged):
        key = record.get("record_id")
        if key in seen:
            continue
        seen.add(key)
        ordered.append(record)

    by_category = {}
    for record in ordered:
        # Full records only: a cross_reference is a pointer, not coverage.
        if record.get("record_type") == "full":
            slug = record.get("primary_category")
            by_category[slug] = by_category.get(slug, 0) + 1

    cells = [{"cell_id": a.get("cell_id"), "present": True,
              "records": len(a.get("records", ()))}
             for a in cell_artifacts]
    cells.sort(key=lambda row: row["cell_id"] or "")

    derived = dict(_counts(ordered), by_category=by_category, cells=cells)
    return {
        "schema_version": records_mod.SCHEMA_VERSION,
        "artifact_type": "topic",
        "topic": topic,
        "topic_slug": topic_slug,
        "generated_at": generated_at,
        "harvest_run_id": harvest_run_id,
        "metadata": _metadata(metadata, derived),
        "records": copy.deepcopy(ordered),
    }


# ------------------------------------------------------------ coverage report
def build_coverage_report(records, *, harvest_run_id, generated_at,
                          thresholds_constant=None, facets_dir=None,
                          config_dir=None, include_records=True):
    """Wiring, not new coverage logic.

    The committed `coverage.build_coverage_report` does all the counting and stays
    byte-unchanged. Two things are added here, both about persistence:

      * ORDER. The delegate sorts `by_category`, but builds its per-record
        projection in INPUT order — so the record set is sorted by the committed
        `records.sort_key` first. That is what makes two runs over the same set
        byte-identical, and it belongs here rather than in `coverage.py`.
      * REFUSAL. Records are validated against `record.v1.json` before they are
        counted, so a malformed record is named rather than silently tallied.

    Nothing is recalibrated: `thresholds_constant` is *reported* from the caller's
    observation of the run, never derived or reinterpreted here.
    """
    ordered = _validated_records(records)
    return coverage_mod.build_coverage_report(
        ordered, harvest_run_id, generated_at,
        thresholds_constant=thresholds_constant,
        facets_dir=facets_dir, config_dir=config_dir,
        include_records=include_records)


def write_coverage_report(path, report):
    return write_document(path, report, "coverage_report.v1.json")


# ------------------------------------------------------- alias conflicts (S6-6)
def conflict_id(reason, identity_url, proposed_alias):
    """A content-derived id, so the same contradiction is the same id every run.

    Deliberately not a counter or a uuid: either would make the id depend on
    iteration order, and two runs over one input would then differ in a field
    nobody could explain.
    """
    import hashlib
    material = "\x1f".join([reason or "", identity_url or "",
                            proposed_alias or ""])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def build_alias_conflicts(conflicts, *, harvest_run_id, generated_at):
    """One alias_conflicts.v1.json document. The count is DERIVED.

    Takes the `AliasConflict` rows S6-3 produced (or their payload dicts) and
    shapes them; it adjudicates nothing and resolves nothing. `resolution` is
    always "unresolved" — a resolved conflict is not a conflict, and nothing in
    Stage 6 resolves one.

    An EMPTY conflict set is a real answer and still produces the artifact: a run
    that found no contradictory evidence says so, rather than omitting a file and
    leaving a reader unable to tell "none" from "never looked".

    Rows are sorted by `(reason, identity_url, proposed_alias)` so bytes follow
    content rather than the order cells happened to run in.
    """
    rows = []
    for index, conflict in enumerate(conflicts or ()):
        payload = (conflict.payload() if hasattr(conflict, "payload")
                   else dict(conflict))
        reason = payload.get("reason")
        identity_url = payload.get("identity_url")
        if not reason or not identity_url:
            raise ArtifactError(
                "alias conflict %d names no reason or no identity_url: %r"
                % (index, payload))
        proposed = payload.get("proposed_alias")
        rows.append({
            "conflict_id": conflict_id(reason, identity_url, proposed),
            "reason": reason,
            "identity_url": identity_url,
            "proposed_alias": proposed,
            # A conflict with no explanation is not reportable: the whole point
            # of the row is telling an operator what to look at.
            "detail": payload.get("detail") or reason,
            "resolution": "unresolved",
            "detected_at": generated_at,
        })
    rows.sort(key=lambda row: (row["reason"], row["identity_url"],
                               row["proposed_alias"] or ""))

    document = {
        "schema_version": 1,
        "artifact_type": "alias_conflicts",
        "harvest_run_id": harvest_run_id,
        "generated_at": generated_at,
        # Derived from the rows beside it, exactly like every S5-2 count: a caller
        # may not supply it, so the number can never disagree with the list.
        "alias_conflicts_count": len(rows),
        "conflicts": rows,
    }
    if document["alias_conflicts_count"] != len(document["conflicts"]):
        raise ArtifactError("alias_conflicts_count disagrees with its own rows")
    return document


def write_alias_conflicts(path, document):
    return write_document(path, document, "alias_conflict.v1.json")


def alias_conflicts_count(document):
    """The count read back from a VALIDATED artifact document.

    The manifest reports this rather than a number the driver carried alongside,
    so the two can never drift: the artifact is the single source of truth about
    how many conflicts a run found.
    """
    if not isinstance(document, dict):
        raise ArtifactError("alias conflicts document must be an object")
    rows = document.get("conflicts")
    if not isinstance(rows, list):
        raise ArtifactError("alias conflicts document carries no conflicts list")
    declared = document.get("alias_conflicts_count")
    if declared != len(rows):
        raise ArtifactError(
            "alias_conflicts_count %r disagrees with %d rows" % (declared, len(rows)))
    return len(rows)


# ------------------------------------------------------------- run manifest
def configured_cell_rows():
    """One `not_run` row per configured cell, keyed by `cell_id`.

    The baseline the manifest starts from: a cell that was never reached is
    reported as `not_run` rather than omitted, so "12 configured cells" and "12
    rows" always agree and a silently skipped cell cannot hide.
    """
    rows = {}
    for lane in scheduler.configured_cells():
        cell_id = lane[len("cell__"):] if lane.startswith("cell__") else lane
        topic_slug, _, category_slug = cell_id.partition("__")
        rows[cell_id] = {"cell_id": cell_id, "topic_slug": topic_slug,
                         "category_slug": category_slug, "status": STATUS_NOT_RUN}
    return rows


def policy_thresholds(policy=None):
    """The three acceptance thresholds as committed policy states them.

    Read from `policy.v1.json` rather than typed here, so the manifest records
    what verify actually applied. Recorded for Stage 9 to compare against; this
    function neither changes nor reinterprets the provisional S4-4 numbers.
    """
    scoring = (policy or verify_mod.load_policy()).get("scoring") or {}
    limits = scoring.get("thresholds") or {}
    return {key: limits[key] for key in
            ("min_relevance", "min_quality", "accept_composite") if key in limits}


def environment_block():
    """The interpreter and validator this run actually used.

    Passed through from `schema.check_environment()` rather than re-listed key by
    key: that function is the single source of truth for what was checked, its
    keys already match the schema's `environment` block exactly, and a copy here
    could only drift from it.
    """
    return dict(schema.check_environment())


def unchecked_full_records(records):
    """(unchecked, total) over FULL accepted records only.

    A `cross_reference` is a pointer at a full record in another cell; it carries
    no `access_status` because it was never a page anyone could fetch. Counting one
    as unchecked would invent a missing-evidence finding out of the cross-topic
    policy, so only full records are counted — on both sides of the ratio.
    """
    total = unchecked = 0
    for record in records or ():
        if record.get("record_type") != "full":
            continue
        total += 1
        if record.get("access_status") == NOT_CHECKED:
            unchecked += 1
    return unchecked, total


def target_request_accounting(outcomes):
    """Exact target-fetch counters, summed from what the client already froze.

    One `TargetFetchOutcome` per OWNED CANONICAL IDENTITY is the input contract, and
    it is the whole reason this is a sum rather than an estimate. S6-4 fetches each
    identity once per run and hands the same outcome object to every record owning
    it, so summing the run-scoped map counts a URL accepted in two cells — or under
    two topics — exactly once. Summing per record would count it twice and would
    quietly contradict the ownership guarantee it is supposed to describe.

    Every number here was incremented by the committed HTTP client at the moment
    the event occurred, frozen onto the response or the typed error, and copied onto
    the outcome by S6-2 (this module names no transport type and constructs none —
    it reads three integers off objects it is handed). Nothing is estimated,
    nothing is derived from a formula, and no
    `client.stats` delta is taken: that dict is a client-lifetime aggregate shared by
    every call, and diffing it around one fetch attributes other work to this one.

    THREE KEYS, AND THE ONES DELIBERATELY MISSING. Source and target accounting are
    two key spaces with different owners (plan §2), so the target counters are named
    apart and `http_attempts` / `retries` / `redirect_hops` keep their source-only
    meaning. There is no `total_http_attempts`: a sum across the two would erase the
    boundary this separation exists to hold. `request_charges` is available on every
    outcome but is not projected here — the block has no `budget_charged` counterpart
    on the source side either. Conditional revalidations are not reported because the
    target path has no revalidation to count, and robots retrievals never enter
    `attempts` by DV-8's own contract.
    """
    totals = {"target_http_attempts": 0, "target_retries": 0,
              "target_redirect_hops": 0}
    for outcome in outcomes or ():
        accounting = getattr(outcome, "accounting", None)
        if accounting is None:
            continue
        totals["target_http_attempts"] += accounting.attempts
        totals["target_retries"] += accounting.retries
        totals["target_redirect_hops"] += accounting.redirect_hops
    return totals


def derive_publication_eligibility(mode, cells, *, target_fetch_owners=0,
                                   records=()):
    """Derived from facts the manifest already records — never asserted.

    Stage 5 fetched no target page, so every record carried access_status
    "not_checked" and verification_status "unverified", and a run that verified
    nothing is honestly ineligible.

    `target_fetch_owners > 0` is NECESSARY BUT NEVER SUFFICIENT. The guard below
    was brought forward from S6-6 to S6-4, because S6-4 is what first makes the
    owner count non-zero: without it, acquiring one target-fetch owner would flip a
    run to eligible while every record still said nobody had checked it. A run is
    eligible when, and only when, it is a `harvest` run, no cell failed, at least
    one target fetch was owned, AND every full accepted record was actually
    checked. A budget-skipped target is `not_checked`, so it keeps the run
    ineligible — which is the point: partial enrichment is not publishable.

    Every input is a fact about the run. The condition and its reason are computed
    here; a caller cannot supply either.
    """
    if mode != MODE_HARVEST:
        return False, "%s runs are infrastructure tests, not publishable output" % mode
    if not target_fetch_owners:
        return False, ("no target page was fetched, so every record is unverified "
                       "(target fetching arrives in Stage 6)")
    broken = sorted(c.get("cell_id") for c in cells
                    if c.get("status") in CELL_ERROR_STATUSES)
    if broken:
        return False, "cell(s) failed: %s" % ", ".join(broken)
    unchecked, total = unchecked_full_records(records)
    if unchecked:
        return False, ("%d of %d accepted records carry no target evidence "
                       "(access_status not_checked)" % (unchecked, total))
    return True, None


def build_run_manifest(*, harvest_run_id, started_at, finished_at, cells=(),
                       mode=MODE_HARVEST, config=None, source_preflight=(),
                       classification_decisions=(), coverage=None, rounds=None,
                       request_accounting=None, target_fetch_owners=0,
                       target_outcomes=None,
                       records=(), alias_conflicts=None, environment=None,
                       policy=None):
    """One manifest per run. Counts and eligibility are derived, not asserted.

    `cells` supplies outcomes for the cells that ran; every other configured cell
    appears as `not_run`. Rows are keyed and sorted by `cell_id`, so a cell can
    appear exactly once and artifact order never depends on completion order.
    """
    rows = configured_cell_rows()
    for outcome in cells:
        cell_id = outcome.get("cell_id")
        if cell_id not in rows:
            raise ArtifactError("cell %r is not one of the %d configured cells"
                                % (cell_id, len(rows)))
        row = dict(rows[cell_id])
        row.update(outcome)
        row["topic_slug"] = rows[cell_id]["topic_slug"]
        row["category_slug"] = rows[cell_id]["category_slug"]
        rows[cell_id] = row
    ordered_cells = [rows[key] for key in sorted(rows)]

    # `records` is read ONLY to derive eligibility; it is not persisted here and
    # does not enter the manifest. The records themselves live in the cell
    # artifacts, which remain their single home.
    eligible, ineligible_reason = derive_publication_eligibility(
        mode, ordered_cells, target_fetch_owners=target_fetch_owners,
        records=records)

    doc = {
        "schema_version": 1,
        "harvest_run_id": harvest_run_id,
        "mode": mode,
        "started_at": started_at,
        "finished_at": finished_at,
        "environment": environment or environment_block(),
        "config": dict(config or {}),
        "cells": ordered_cells,
        "source_preflight": sorted(source_preflight,
                                   key=lambda s: s.get("source_id") or ""),
        "classification_decisions": sorted(classification_decisions,
                                           key=lambda d: d.get("content_id") or ""),
        "publication_eligible": eligible,
        "publication_ineligible_reason": ineligible_reason,
    }
    if coverage is not None:
        doc["coverage"] = coverage
    if request_accounting is not None:
        doc["request_accounting"] = request_accounting
    # Target counters are DERIVED here from the outcomes themselves, never carried
    # in beside them, so the reported number and the fetches that produced it cannot
    # drift — the same rule `alias_conflicts_count` follows.
    #
    # The None sentinel is load-bearing and is why this is not a defaulted empty
    # tuple: OMITTED means the caller is not reporting target accounting, and every
    # committed pre-S6-6A caller stays byte-identical; SUPPLIED-BUT-EMPTY means this
    # run owned no target fetch, which is a fact, and all three keys appear at zero.
    # An absent key and a zero must not be the same statement.
    #
    # The merge builds a NEW dict rather than updating the one the caller passed:
    # a builder that mutated its argument would edit `pool.accounting()`'s result
    # under a caller still holding it.
    if target_outcomes is not None:
        merged = dict(doc.get("request_accounting") or {})
        merged.update(target_request_accounting(target_outcomes))
        doc["request_accounting"] = merged
    # Read back from the VALIDATED alias-conflicts artifact, never carried
    # alongside it, so the manifest's count and the artifact's rows cannot drift.
    # Reported even when zero: "this run found none" is a fact worth stating, and
    # omitting it would be indistinguishable from "nobody looked".
    if alias_conflicts is not None:
        doc["alias_conflicts_count"] = alias_conflicts_count(alias_conflicts)
    # A run that never scheduled a second round omits `rounds` rather than
    # writing an empty claim; when present, round 1 records the thresholds in
    # force so it is provable they never moved.
    if rounds is not None:
        doc["rounds"] = list(rounds)
    return doc


def write_run_manifest(path, manifest):
    return write_document(path, manifest, "run_manifest.v1.json")


# ------------------------------------------------------------ LATEST_RUN_ID
def read_latest_run_id(root):
    """The newest complete run, or None when no run has finished here."""
    path = latest_run_id_path(root)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8").strip() or None


def write_latest_run_id(root, run_id_value):
    """A single line with a trailing newline, written atomically."""
    if not run_id_value:
        raise ArtifactError("refusing to write an empty LATEST_RUN_ID")
    return write_atomic(latest_run_id_path(root),
                        ("%s\n" % run_id_value).encode("utf-8"))


def publish_run(root, run_id_value, manifest):
    """Persist the manifest, then advance the pointer — in that order only.

    Three refusals, each protecting the pointer's one promise (it names a run
    whose manifest exists and validates):

      * an unfinished run (`finished_at` is null) is never published;
      * a manifest whose `harvest_run_id` disagrees with the path is refused;
      * a run that already has a manifest is refused rather than overwritten.

    If the manifest write fails — invalid document, full disk, interruption —
    `write_document` raises before any byte lands and the pointer is never
    touched, so the previous complete run stays the newest one.
    """
    if manifest.get("finished_at") is None:
        raise ArtifactError("refusing to publish run %s: finished_at is null, so "
                            "the run did not finish" % run_id_value)
    if manifest.get("harvest_run_id") != run_id_value:
        raise ArtifactError("manifest names run %r but is being published as %r"
                            % (manifest.get("harvest_run_id"), run_id_value))
    path = run_manifest_path(root, run_id_value)
    if os.path.exists(path):
        raise ArtifactError("run %s already has a manifest; refusing to overwrite "
                            "a finished run" % run_id_value)
    write_run_manifest(path, manifest)
    write_latest_run_id(root, run_id_value)      # LAST, and only now
    return path


# ------------------------------------------------------------------ recovery
def run_is_finished(root, run_id_value):
    """True when this run already has a manifest — that is what "finished" means.

    `publish_run` enforces the same fact at the END of a run. This exposes it so
    a driver can refuse a repeat BEFORE it writes anything: discovering it only
    at publication time would mean the cross-run ledger had already counted every
    candidate a second time, and the cell's rejection log had already been
    replaced, for a run that was never going to be published.
    """
    return os.path.exists(run_manifest_path(root, run_id_value))


def verify_latest_run_id(root):
    """The pointer's one promise, as a checkable predicate rather than a hope.

    Returns the run_id `LATEST_RUN_ID` names, or None when no run has finished in
    this root. Raises when the pointer names a run whose manifest is missing,
    unreadable, invalid, or names a different run — the four states the write
    order in `publish_run` exists to make impossible. Written to be run AFTER an
    interruption, when "is this tree still consistent?" is the only question that
    matters.
    """
    named = read_latest_run_id(root)
    if named is None:
        return None
    path = run_manifest_path(root, named)
    if not os.path.exists(path):
        raise ArtifactError(
            "LATEST_RUN_ID names run %s but %s does not exist; the pointer moved "
            "before the manifest was safely on disk" % (named, path))
    try:
        with open(path, "rb") as handle:
            doc = json.loads(handle.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ArtifactError("LATEST_RUN_ID names run %s but its manifest is "
                            "unreadable (%s)" % (named, exc)) from exc
    errors = schema.validate(doc, "run_manifest.v1.json")
    if errors:
        raise ArtifactError(
            "LATEST_RUN_ID names run %s but its manifest does not validate "
            "(%d problem(s)): %s" % (named, len(errors), "; ".join(errors[:2])))
    if doc.get("harvest_run_id") != named:
        raise ArtifactError("LATEST_RUN_ID names run %s but that manifest names %r"
                            % (named, doc.get("harvest_run_id")))
    return named


def write_cell_artifact(path, artifact):
    return write_document(path, artifact, "cell_artifact.v1.json")


def write_topic_artifact(path, artifact):
    return write_document(path, artifact, "topic_artifact.v1.json")
