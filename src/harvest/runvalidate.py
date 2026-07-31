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

Not here: comparison of two runs (S9-4), link health (S9-6), promotion (M6).
"""
import json
import os

from . import artifacts
from . import run_cells
from . import schema as schema_mod

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
        for row in rows:
            if row.get("status") == artifacts.STATUS_NOT_RUN:
                errors.append("manifest.json: cell %s is not_run; a full smoke "
                              "runs every configured cell" % row.get("cell_id"))
        _check_sightings(rows, errors)

        if manifest.get("mode") != "smoke":
            errors.append("manifest.json: mode is %r, expected 'smoke'"
                          % manifest.get("mode"))
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
        if manifest.get("publication_eligible") is not False:
            errors.append("manifest.json: publication_eligible is %r; a smoke is "
                          "infrastructure, not publishable output"
                          % manifest.get("publication_eligible"))

        preflight = manifest.get("source_preflight") or []
        expected_sources = sorted(
            source["source_id"] for cell in run_cells.configured_cells()
            for source in cell["sources"])
        got = [row.get("source_id") for row in preflight]
        if got != sorted(got):
            errors.append("manifest.json: source_preflight is not sorted by "
                          "source_id")
        if sorted(got) != expected_sources:
            errors.append("manifest.json: source_preflight covers %d id(s), "
                          "expected the %d configured sources exactly once"
                          % (len(got), len(expected_sources)))

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
