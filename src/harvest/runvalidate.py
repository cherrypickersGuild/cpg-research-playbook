#!/usr/bin/env python3
"""runvalidate.py — read-only validation of one completed run (S9-3, E9-8).

The Stage 9 plan assigned `validate --run-id` but named no production owner, so
run-tree reading and cross-document checking would have had to live in the CLI
(which parses and renders) or in `run_cells.py` (which writes). Neither should
also be the thing that judges whether what was written is sound. E9-8 gives that
job to this module, and the division is exact:

    cli.py          parses and renders
    run_cells.py    writes
    runvalidate.py  validates an existing tree

**This module reads. It does not write, fetch, classify, score, rebuild, repair,
normalize or promote.** It opens no socket, constructs no client, creates no
directory, drops no marker, removes no debris, does not touch `LATEST_RUN_ID`,
and never rewrites a document it found invalid. A validator that repairs is a
writer wearing a validator's name, and the next reader cannot tell what was
actually on disk.

It also collects rather than aborts: a malformed tree yields as many independent
errors as can be gathered safely, because "the first missing file" is rarely the
most useful thing to learn about a broken run.

**E9-11 — what "43 paths" means once a root has more than one run.** A fresh
state root holding one complete run has 42 JSON documents and one `LATEST_RUN_ID`
pointer, 43 files in all. Those 42 split into two very different halves:

    18  SELECTED-RUN, under runs/<run-id>/
        12 cell artifacts · 3 topic artifacts · coverage · alias_conflicts · manifest
    24  CROSS-RUN, shared and updated in place, never duplicated per run
        12 ledgers · 12 rejection logs

So a second run does **not** make 84 JSON documents. It adds 18 under its own run
directory and updates the same 24 shared ones. This module therefore enforces the
18 exactly, the 24 exactly, and the pointer — while permitting other complete
historical run directories to exist alongside.

Not here: comparison of two runs (S9-4), the PRODUCTION of link-health
evidence (S9-6 `linkcheck.py`), promotion (M6). This module validates a linkcheck
run's artifact; it never performs one, and imports nothing that could.
"""
import json
import os

from . import artifacts
from . import run_cells
from . import schema as schema_mod

# S9-6. The modes `validate --run-id` answers for. A run is validatable here when
# it publishes the ordinary 43-path tree and is not publishable output: `smoke`
# and `linkcheck` both qualify. `harvest`, `refresh`, `smoke_model` and
# `migration` stay REFUSED - each would need its own semantics, and a validator
# that accepted them without having them would be agreeing rather than checking.
MODE_SMOKE = "smoke"
MODE_LINKCHECK = "linkcheck"
VALIDATABLE_MODES = (MODE_SMOKE, MODE_LINKCHECK)

# The cell status a linkcheck may report beside `not_run`. Spelled here rather
# than imported from the producer: this module validates retained fields and must
# not depend on the module that wrote them.
STATUS_OK = "ok"

# The ceiling on a linkcheck's `config.bounds.sample`, read from the committed
# per-cell target-fetch bound rather than retyped, so the validator's ceiling and
# the producer's cannot drift. `run_cells` is already imported for the configured
# cell and topic sets; `linkcheck` is deliberately NOT imported.
MAX_LINKCHECK_SAMPLE = run_cells.MAX_TARGET_FETCHES_PER_CELL

# The committed schema that owns each document family.
SCHEMA_FOR = {
    "cells": "cell_artifact.v1.json",
    "topics": "topic_artifact.v1.json",
    "coverage": "coverage_report.v1.json",
    "alias_conflicts": "alias_conflict.v1.json",
    "manifest": "run_manifest.v1.json",
    "ledgers": "ledger.v1.json",
    "rejections": "rejection.v1.json",
}

# What one complete 12-cell run must contain. Named so the two halves of E9-11
# stay visibly different things rather than one number nobody can decompose.
SELECTED_RUN_JSON = 18          # 12 cells + 3 topics + coverage + conflicts + manifest
SHARED_JSON = 24                # 12 ledgers + 12 rejections
TOTAL_JSON = SELECTED_RUN_JSON + SHARED_JSON            # 42
TOTAL_PATHS = TOTAL_JSON + 1                            # + LATEST_RUN_ID

TEMP_PREFIX = artifacts.TEMP_PREFIX


class RunValidateError(Exception):
    """An argument this module refuses. A bad TREE is a report, not an exception."""


def validate_run_id(value):
    """The one run-id validator, shared with `smoke --run-id`.

    Delegates to `run_cells.validate_run_id_value`, which reads the pattern from
    the committed manifest schema. There is deliberately no second regex here:
    the two commands must agree, and the document itself is the authority.
    """
    try:
        return run_cells.validate_run_id_value(value)
    except run_cells.RunCellsError as exc:
        raise RunValidateError(str(exc))


def configured_cell_ids():
    return sorted(cell["cell_id"] for cell in run_cells.configured_cells())


def configured_topic_slugs():
    return sorted({cell["topic_slug"] for cell in run_cells.configured_cells()})


def _read_json(path):
    """(document, error). Never raises on a malformed file — that is a finding."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except OSError as exc:
        return None, "%s: cannot read (%s)" % (path, exc.strerror or exc)
    except ValueError as exc:
        return None, "%s: not valid JSON (%s)" % (path, exc)


def _rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def _listing(directory):
    try:
        return sorted(os.listdir(directory))
    except OSError:
        return None


def _check_directory(root, directory, expected, errors, label):
    """Exactly `expected` filenames, no more and no fewer.

    Missing and unexpected are separate findings on purpose: a run that lost a
    cell and a run that grew a stray file are different failures, and reporting
    both as "the set differs" tells a reader nothing about which happened.
    """
    names = _listing(directory)
    if names is None:
        errors.append("%s: directory missing (%s)" % (label, _rel(root, directory)))
        return set()
    present = set(names)
    for missing in sorted(set(expected) - present):
        errors.append("%s: missing %s" % (label, missing))
    for extra in sorted(present - set(expected)):
        errors.append("%s: unexpected file %s" % (label, extra))
    return present & set(expected)


def _scan_temp_debris(root, errors):
    """No `.tmp_*` anywhere under the root.

    The committed writer names every in-flight file `.tmp_<uuid>_<basename>` and
    sweeps its own on the way out. One surviving anywhere means a write was
    interrupted and the tree is not the finished thing it looks like.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        for name in sorted(dirnames) + sorted(filenames):
            if name.startswith(TEMP_PREFIX):
                errors.append("temp debris: %s"
                              % _rel(root, os.path.join(dirpath, name)))


def _count_records(document):
    """(full, cross_reference) actually present in a document's records array."""
    full = cross = 0
    for record in document.get("records", []) or []:
        if record.get("record_type") == "cross_reference":
            cross += 1
        else:
            full += 1
    return full, cross


def _check_counts(label, document, errors):
    """A metadata block must agree with the records beside it."""
    metadata = document.get("metadata") or {}
    full, cross = _count_records(document)
    for key, observed in (("full_records", full), ("cross_references", cross),
                          ("total_records", full + cross)):
        declared = metadata.get(key)
        if declared is not None and declared != observed:
            errors.append("%s: metadata.%s is %r but the records array holds %d"
                          % (label, key, declared, observed))
    declared_total = metadata.get("total_records")
    if declared_total is not None:
        parts = (metadata.get("full_records"), metadata.get("cross_references"))
        if None not in parts and declared_total != sum(parts):
            errors.append("%s: total_records %r != full_records + cross_references"
                          % (label, declared_total))


def _check_sightings(rows, errors):
    """S9-5C2. A measured sighting tuple must add up. Conditional by necessity.

    The same shape as `_check_counts` above and as the topic `by_category` check
    below: an OPTIONAL block, guarded on presence, whose declared numbers must
    agree with each other. A manifest written before S9-5C2 carries none of these
    keys, so it is skipped rather than failed - the fields were never measured,
    and reporting that as an error would call the M2/M3 evidence broken.

    Only the integers already on the row are read. Nothing is recounted: this
    module must not import `dedupe`, and re-deriving the numbers from anything
    would make the validator a second producer that could disagree with the first.

    Presence itself is NOT enforced here. All-or-none is the committed schema's
    `dependentRequired` on `cells[]`, which fires in every mode and at write time;
    that a completed cell must carry the tuple at all is the producer's contract,
    owned by `run_cells._cell_row` and its suite. This check owns the arithmetic
    and only the arithmetic.
    """
    triple = run_cells.SIGHTING_FIELDS[:3]
    for row in rows:
        values = [row.get(name) for name in triple]
        if any(value is None for value in values):
            continue
        if any(not isinstance(value, int) or isinstance(value, bool)
               for value in values):
            continue                  # a type problem; the schema already said so
        observations, unique, repeated = values
        if observations != unique + repeated:
            errors.append(
                "manifest.json: cell %s reports %d candidate_observations but "
                "%d unique_candidate_keys + %d repeated_candidate_observations "
                "= %d; every observation is either the first for its canonical "
                "key or a repeat of one"
                % (row.get("cell_id"), observations, unique, repeated,
                   unique + repeated))


def _check_smoke_manifest(manifest, rows, errors):
    """The smoke-only semantics. Unchanged in meaning by S9-6.

    A smoke runs every configured cell with enrichment OFF, under caps it must
    state, having probed every configured source exactly once.
    """
    for row in rows:
        if row.get("status") == artifacts.STATUS_NOT_RUN:
            errors.append("manifest.json: cell %s is not_run; a full smoke "
                          "runs every configured cell" % row.get("cell_id"))

    config = manifest.get("config") or {}
    if config.get("enrich") is not False:
        errors.append("manifest.json: config.enrich is %r, expected false"
                      % config.get("enrich"))
    bounds = config.get("bounds") or {}
    for key in ("max_candidates_per_cell", "max_accepted_per_cell",
                "smoke_budget_sec"):
        if key not in bounds:
            errors.append("manifest.json: config.bounds is missing %s, so the "
                          "run does not say which smoke cap it enforced" % key)

    preflight = manifest.get("source_preflight") or []
    expected_sources = sorted(
        source["source_id"] for cell in run_cells.configured_cells()
        for source in cell["sources"])
    got = [row.get("source_id") for row in preflight]
    if got != sorted(got):
        errors.append("manifest.json: source_preflight is not sorted by source_id")
    if sorted(got) != expected_sources:
        errors.append("manifest.json: source_preflight covers %d id(s), "
                      "expected the %d configured sources exactly once"
                      % (len(got), len(expected_sources)))


def _check_linkcheck_manifest(root, run_id, manifest, rows, cells, errors):
    """The linkcheck-only semantics (S9-6).

    A linkcheck is DERIVED: it re-checks another run's targets, so it must say
    which run, and that lineage must be checkable rather than merely declared.
    Everything here reads retained fields only - this module imports no
    `linkcheck`, no target-fetch owner, no HTTP or adapter owner and no writer,
    and it re-derives nothing. Whether the fetches were correct is the producer's
    contract; whether the ARTIFACT is coherent is this one's.
    """
    base = manifest.get("base_run_id")
    if base is None:
        errors.append("manifest.json: mode is 'linkcheck' but base_run_id is "
                      "absent; a derived run must name the run it measured")
    else:
        if base == run_id:
            errors.append("manifest.json: base_run_id equals this run (%s); a "
                          "linkcheck is a NEW run and may never name itself"
                          % run_id)
        elif not os.path.isdir(artifacts.run_dir(root, base)):
            errors.append("manifest.json: base_run_id %s has no run directory in "
                          "this state root" % base)
        elif not os.path.isfile(artifacts.run_manifest_path(root, base)):
            errors.append("manifest.json: base_run_id %s has no manifest; the "
                          "lineage names an incomplete run" % base)

    config = manifest.get("config") or {}
    if config.get("enrich") is not True:
        errors.append("manifest.json: config.enrich is %r, expected true; a "
                      "linkcheck exists to fetch target pages"
                      % config.get("enrich"))
    sample = (config.get("bounds") or {}).get("sample")
    if (isinstance(sample, bool) or not isinstance(sample, int)
            or sample < 1 or sample > MAX_LINKCHECK_SAMPLE):
        errors.append("manifest.json: config.bounds.sample is %r; expected an "
                      "integer in 1..%d, so the run states the bound it enforced"
                      % (sample, MAX_LINKCHECK_SAMPLE))

    if manifest.get("source_preflight"):
        errors.append("manifest.json: source_preflight is non-empty on a "
                      "linkcheck; a linkcheck contacts sampled TARGET pages only "
                      "and probes no source")

    # Cell status is about whether this run CHECKED anything there - never about
    # what the check found. A 404 is a finding about a page, not a broken cell.
    ok_cells = set()
    for row in rows:
        status = row.get("status")
        if status == STATUS_OK:
            ok_cells.add(row.get("cell_id"))
        elif status != artifacts.STATUS_NOT_RUN:
            errors.append("manifest.json: cell %s has status %r; a linkcheck cell "
                          "is 'ok' when it checked a record and 'not_run' when it "
                          "held none, and a link-health RESULT never sets a cell "
                          "status" % (row.get("cell_id"), status))
    if not ok_cells:
        errors.append("manifest.json: every cell is not_run; a linkcheck that "
                      "checked nothing reports nothing and is not a check")

    # The history must actually have been written THIS run: an artifact carrying
    # only a previous run's entries would validate while proving nothing.
    stamp = manifest.get("started_at")
    checked_by_cell = {}
    for cell_id, document in cells.items():
        count = 0
        for record in document.get("records") or ():
            for entry in record.get("link_history") or ():
                if entry.get("checked_at") == stamp:
                    count += 1
                    break
        checked_by_cell[cell_id] = count
    if not any(checked_by_cell.values()):
        errors.append("manifest.json: no full record carries a link_history entry "
                      "stamped %r; this run appended no history and cannot be "
                      "reporting a check it performed" % stamp)
    for cell_id, count in sorted(checked_by_cell.items()):
        if cell_id in ok_cells and count == 0:
            errors.append("cells/%s.json: the manifest calls this cell 'ok' but no "
                          "record was checked in this run" % cell_id)
        if cell_id not in ok_cells and count:
            errors.append("cells/%s.json: %d record(s) were checked in this run "
                          "but the manifest calls the cell 'not_run'"
                          % (cell_id, count))


def validate_run(root, run_id):
    """Validate the LATEST complete run in `root`. Returns the report document.

    Pointer consistency is part of this command's contract, so a historical
    non-latest run is reported invalid here even when its own documents are
    perfect — `validate` answers "is the run this root currently points at
    sound?". S9-4 may read a historical run for comparison without treating it as
    current; that is a different question and will have a different owner.
    """
    validate_run_id(run_id)
    errors = []
    checked = 0

    cell_ids = configured_cell_ids()
    topic_slugs = configured_topic_slugs()
    run_dir = artifacts.run_dir(root, run_id)

    if not os.path.isdir(root):
        return _report(run_id, ["state root does not exist or is not a directory: "
                                "%s" % root], 0, None)

    # ------------------------------------------------------- the 18 selected
    _check_directory(root, os.path.join(run_dir, "cells"),
                     ["%s.json" % cid for cid in cell_ids], errors, "cells")
    _check_directory(root, os.path.join(run_dir, "topics"),
                     ["%s.json" % slug for slug in topic_slugs], errors, "topics")
    run_root_names = _listing(run_dir)
    if run_root_names is None:
        errors.append("run directory missing: %s" % _rel(root, run_dir))
    else:
        expected_top = {"cells", "topics", "coverage.json",
                        "alias_conflicts.json", "manifest.json"}
        for missing in sorted(expected_top - set(run_root_names)):
            errors.append("run: missing %s" % missing)
        for extra in sorted(set(run_root_names) - expected_top):
            errors.append("run: unexpected entry %s" % extra)

    # ---------------------------------------------------------- the 24 shared
    _check_directory(root, os.path.join(root, "ledgers"),
                     ["%s.json" % cid for cid in cell_ids], errors, "ledgers")
    _check_directory(root, os.path.join(root, "rejections"),
                     ["%s.json" % cid for cid in cell_ids], errors, "rejections")

    # -------------------------------------------------------------- documents
    def load(path, schema_name, label):
        nonlocal checked
        if not os.path.isfile(path):
            return None
        checked += 1
        document, error = _read_json(path)
        if error is not None:
            errors.append(error)
            return None
        errors.extend(schema_mod.validate(document, schema_name, label=label))
        return document

    cells = {}
    for cell_id in cell_ids:
        document = load(artifacts.cell_artifact_path(root, run_id, cell_id),
                        SCHEMA_FOR["cells"], "cells/%s.json" % cell_id)
        if document is not None:
            cells[cell_id] = document
            _check_counts("cells/%s.json" % cell_id, document, errors)
            if document.get("cell_id") != cell_id:
                errors.append("cells/%s.json: declares cell_id %r"
                              % (cell_id, document.get("cell_id")))

    topics = {}
    for slug in topic_slugs:
        document = load(artifacts.topic_artifact_path(root, run_id, slug),
                        SCHEMA_FOR["topics"], "topics/%s.json" % slug)
        if document is not None:
            topics[slug] = document
            _check_counts("topics/%s.json" % slug, document, errors)
            if document.get("topic_slug") != slug:
                errors.append("topics/%s.json: declares topic_slug %r"
                              % (slug, document.get("topic_slug")))

    coverage = load(artifacts.coverage_report_path(root, run_id),
                    SCHEMA_FOR["coverage"], "coverage.json")
    conflicts = load(artifacts.alias_conflicts_path(root, run_id),
                     SCHEMA_FOR["alias_conflicts"], "alias_conflicts.json")
    manifest = load(artifacts.run_manifest_path(root, run_id),
                    SCHEMA_FOR["manifest"], "manifest.json")

    for cell_id in cell_ids:
        load(artifacts.ledger_path(root, cell_id), SCHEMA_FOR["ledgers"],
             "ledgers/%s.json" % cell_id)
        load(artifacts.rejection_log_path(root, cell_id), SCHEMA_FOR["rejections"],
             "rejections/%s.json" % cell_id)

    # ------------------------------------------------------- run id agreement
    for label, document in ([("cells/%s.json" % k, v) for k, v in cells.items()]
                            + [("topics/%s.json" % k, v) for k, v in topics.items()]
                            + [("coverage.json", coverage),
                               ("alias_conflicts.json", conflicts),
                               ("manifest.json", manifest)]):
        if document is None:
            continue
        declared = document.get("harvest_run_id")
        if declared is not None and declared != run_id:
            errors.append("%s: harvest_run_id is %r but this run is %r"
                          % (label, declared, run_id))

    # ---------------------------------------------------------- topic totals
    for slug, topic in topics.items():
        members = [cid for cid in cell_ids if cid.split("__")[0] == slug]
        available = [cells[cid] for cid in members if cid in cells]
        if len(available) != len(members):
            continue
        expected_full = sum(_count_records(c)[0] for c in available)
        expected_cross = sum(_count_records(c)[1] for c in available)
        metadata = topic.get("metadata") or {}
        # A topic aggregate deduplicates by record_id, so it can hold FEWER rows
        # than its cells sum to, never more. Asserting equality would fail on the
        # very deduplication S5-2 exists to perform.
        for key, ceiling in (("full_records", expected_full),
                             ("cross_references", expected_cross)):
            declared = metadata.get(key)
            if declared is not None and declared > ceiling:
                errors.append("topics/%s.json: metadata.%s is %r, more than its "
                              "%d member cells hold (%d)"
                              % (slug, key, declared, len(members), ceiling))
        by_category = metadata.get("by_category") or {}
        if by_category and metadata.get("full_records") is not None:
            total = sum(by_category.values())
            if total != metadata["full_records"]:
                errors.append("topics/%s.json: by_category sums to %d but "
                              "full_records is %r"
                              % (slug, total, metadata["full_records"]))

    # --------------------------------------------------------------- manifest
    if manifest is not None:
        rows = manifest.get("cells") or []
        if len(rows) != len(cell_ids):
            errors.append("manifest.json: %d cell rows, expected %d"
                          % (len(rows), len(cell_ids)))
        declared_ids = sorted(row.get("cell_id") for row in rows)
        if declared_ids != cell_ids:
            errors.append("manifest.json: cell rows do not match the configured set")
        _check_sightings(rows, errors)

        # ------------------------------------------------- common to every mode
        # `publication_eligible` is false for BOTH validatable modes, and the
        # wording is mode-neutral: a linkcheck is not a smoke, and calling it one
        # in an error message would be the small lie that makes a report
        # untrustworthy.
        if manifest.get("publication_eligible") is not False:
            errors.append("manifest.json: publication_eligible is %r; a %s run is "
                          "infrastructure, not publishable output"
                          % (manifest.get("publication_eligible"),
                             manifest.get("mode")))

        mode = manifest.get("mode")
        if mode not in VALIDATABLE_MODES:
            errors.append("manifest.json: mode is %r, expected one of %s"
                          % (mode, ", ".join(repr(m) for m in VALIDATABLE_MODES)))
        elif mode == MODE_SMOKE:
            _check_smoke_manifest(manifest, rows, errors)
        else:
            _check_linkcheck_manifest(root, run_id, manifest, rows, cells, errors)

        if conflicts is not None:
            declared = manifest.get("alias_conflicts_count")
            actual = len(conflicts.get("conflicts") or [])
            if declared is not None and declared != actual:
                errors.append("manifest.json: alias_conflicts_count is %r but the "
                              "artifact holds %d conflicts" % (declared, actual))
            envelope = conflicts.get("alias_conflicts_count")
            if envelope is not None and envelope != actual:
                errors.append("alias_conflicts.json: alias_conflicts_count is %r "
                              "but the document holds %d conflicts"
                              % (envelope, actual))

    # ---------------------------------------------------------- the pointer
    pointer = None
    pointer_path = artifacts.latest_run_id_path(root)
    if not os.path.isfile(pointer_path):
        errors.append("LATEST_RUN_ID: missing")
    else:
        with open(pointer_path, "rb") as handle:
            raw = handle.read()
        if b"\r" in raw:
            errors.append("LATEST_RUN_ID: contains CR; it is one LF-terminated line")
        text = raw.decode("utf-8", "replace")
        if not text.endswith("\n") or text.count("\n") != 1:
            errors.append("LATEST_RUN_ID: must be exactly one LF-terminated line")
        pointer = text.strip() or None
        if pointer != run_id:
            errors.append("LATEST_RUN_ID names %r, not the requested run %r. "
                          "`validate` checks the run this root currently points "
                          "at." % (pointer, run_id))
        else:
            try:
                verified = artifacts.verify_latest_run_id(root)
                if verified != run_id:
                    errors.append("verify_latest_run_id returned %r, not %r"
                                  % (verified, run_id))
            except artifacts.ArtifactError as exc:
                errors.append("LATEST_RUN_ID: %s" % exc)

    _scan_temp_debris(root, errors)

    return _report(run_id, errors, checked, pointer)


def _report(run_id, errors, checked, pointer):
    """The deterministic, unpersisted report. No timestamp, no environment."""
    return {
        "run_id": run_id,
        "valid": not errors,
        "json_documents_checked": checked,
        "paths_checked": checked + 1,
        "pointer_run_id": pointer,
        "errors": sorted(set(errors)),
    }
