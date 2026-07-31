#!/usr/bin/env python3
"""compare.py — run comparison and publication diff (Stage 9, checkpoint S9-4).

Two questions, one owner:

    compare-runs   are two staged runs of the same corpus IDEMPOTENT where they
                   must be, and merely DIFFERENT where they are allowed to be?
    diff           does a staged run differ from what is published?

Both are read-only. **This module reads. It does not write, fetch, promote,
stage, repair or normalize.** It opens no socket, builds no transport, creates no
directory — not even the publication root it is asked about — and never touches
`LATEST_RUN_ID` or either run tree. `cli.py` parses and renders; every judgement
here.

**Why there is no `--normalize`.** The S9-0 plan sketched one and never settled
what it would fold. A normalizer forgives every field it was not told about, so
the day a sixth field starts moving it passes silently — which is the exact
failure S5-7/S6-7 exist to prevent. E9-14 removes the option: comparison always
enumerates and classifies the actual differing JSON paths, and an unenumerated
moving field FAILS rather than disappearing.

**What is compared, and what deliberately is not.** Only the **18 selected-run
documents** under `runs/<run-id>/` — 12 cell artifacts, 3 topic artifacts,
coverage, alias conflicts, manifest. The **24 shared documents** (12 ledgers,
12 rejection logs) are updated IN PLACE and are not per-run snapshots (E9-11), so
there is no historical A/B pair to compare and this module never pretends
otherwise. It reports the exclusion as a number, not as an empty result.

**Historical runs are first-class here.** `runvalidate.validate_run()` requires
its run to be the one `LATEST_RUN_ID` names, because it answers "is the run this
root points at sound?". Comparison asks a different question, so this module
reads run trees directly and requires no pointer agreement from either side.
`runvalidate` is not weakened, called or consulted for that check.
"""
import json
import os

from . import artifacts
from . import run_cells
from . import runvalidate
from . import schema as schema_mod

# The two halves of E9-11, restated from their committed owner rather than
# retyped as numbers, so a change there cannot leave this module disagreeing.
SELECTED_DOCUMENTS = runvalidate.SELECTED_RUN_JSON       # 18, compared
SHARED_DOCUMENTS = runvalidate.SHARED_JSON               # 24, NOT compared

# ------------------------------------------------------------------- classes
# Class 1 — PERMITTED to move. Clock-derived, enumerated EXACTLY from the S9-4
# contract (plan §6.4) and then restricted to fields that actually occur in the
# 18 selected-run documents. The plan's `rejected_at` and the ledger's four are
# deliberately absent: they live in the 24 shared documents, which this module
# does not compare, so listing them here would permit movement in a document that
# is never read.
PERMITTED_CLOCK_FIELDS = frozenset({
    "harvest_run_id",       # every selected document carries the run's own id
    "generated_at",         # every artifact envelope
    "discovered_at",        # record
    "freshness_score",      # record — the one score that is a clock reading
    "last_checked_at",      # record
    "started_at",           # manifest
    "finished_at",          # manifest
    "observed_at",          # record url_aliases[]
    "detected_at",          # alias_conflicts[]
})

# Class 2 — IDENTITY / IDEMPOTENCY invariants. For a record present in BOTH
# runs, these must be identical; a difference is a failure, not a report.
INVARIANT_FIELDS = frozenset({
    "record_id", "content_id", "identity_url", "cell_id", "canonical_url",
    # every NON-freshness score. `freshness_score` is class 1 above.
    "quality_score", "relevance_score", "audience_fit_score",
})

# The classification and facet payloads are invariant as WHOLE SUBTREES: any path
# beneath them is an invariant, however deeply nested and whatever it is named.
# Naming the leaves instead would let a new nested key move unnoticed.
INVARIANT_SUBTREES = frozenset({"classification", "case_facets"})

# The committed schemas that own the 18 selected-run documents, plus the record
# schema they embed.
SELECTED_SCHEMAS = ("cell_artifact.v1.json", "topic_artifact.v1.json",
                    "coverage_report.v1.json", "alias_conflict.v1.json",
                    "run_manifest.v1.json", "record.v1.json")


def _schema_property_names():
    """Every property name the selected-run schemas declare.

    Read through the committed `schema.load_schema`, never by opening the schema
    directory here — there is one reader for those documents and this is not a
    second one.
    """
    names = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "properties" and isinstance(value, dict):
                    names.update(value.keys())
                    for child in value.values():
                        walk(child)
                else:
                    walk(value)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    for schema_name in SELECTED_SCHEMAS:
        walk(schema_mod.load_schema(schema_name))
    return frozenset(names)


# Class 3 — legitimate CONTENT change. DERIVED, not hand-typed: every field the
# committed schemas declare, minus the two classes above. Hand-listing ~190 names
# would drift from the schemas the moment one changed; deriving it means the
# three classes together cover exactly the committed surface.
#
# The consequence is the point: a field that appears on disk but in NO committed
# schema falls into none of the three classes, and `_classify` calls that
# `unclassified` — an invariant violation. An unenumerated moving field fails
# loudly instead of disappearing.
CONTENT_FIELDS = (_schema_property_names()
                  - PERMITTED_CLOCK_FIELDS
                  - INVARIANT_FIELDS
                  - INVARIANT_SUBTREES)

PERMITTED = "permitted_changes"
CONTENT = "content_changes"
VIOLATION = "invariant_violations"

# Arrays that are keyed by identity rather than by position, so reordering a run's
# records cannot change one byte of this report and an added or removed member is
# reported as such instead of as a shifted index.
ARRAY_KEYS = {
    "records": "record_id",
    "cells": "cell_id",
    "conflicts": "conflict_id",
    "source_preflight": "source_id",
    "url_aliases": "identity_url",
}


class CompareError(Exception):
    """An argument this module refuses. A differing TREE is a report."""


# ------------------------------------------------------------- document sets
def selected_document_names():
    """The 18 selected-run document names, relative to `runs/<run-id>/`.

    Derived from the configured cells and topics — the same source
    `runvalidate` uses — so a configuration change cannot leave the comparator
    reading a set the validator does not recognise.
    """
    names = ["cells/%s.json" % cid for cid in runvalidate.configured_cell_ids()]
    names += ["topics/%s.json" % slug
              for slug in runvalidate.configured_topic_slugs()]
    names += ["alias_conflicts.json", "coverage.json", "manifest.json"]
    return sorted(names)


def read_run(root, run_id):
    """(documents, errors) for one run's 18 selected documents. Reads only.

    A missing or malformed document is an ERROR, collected rather than raised:
    "the first unreadable file" is rarely the most useful thing to learn, and a
    comparison that aborts on it reports nothing about the other 17.
    """
    documents = {}
    errors = []
    run_directory = artifacts.run_dir(root, run_id)
    for name in selected_document_names():
        path = os.path.join(run_directory, name.replace("/", os.sep))
        if not os.path.isfile(path):
            errors.append("%s: missing %s" % (run_id, name))
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                documents[name] = json.load(handle)
        except OSError as exc:
            errors.append("%s: cannot read %s (%s)"
                          % (run_id, name, exc.strerror or exc))
        except ValueError as exc:
            errors.append("%s: %s is not valid JSON (%s)" % (run_id, name, exc))
    return documents, errors


# ------------------------------------------------------------- path walking
def _member_key(array_name, item, index):
    """An identity for one array member, falling back to its position.

    A positional fallback is honest about what it is: `[3]` says the comparison
    could not identify this member, so a reorder WILL be reported. It is never
    silently treated as the same member.
    """
    key_field = ARRAY_KEYS.get(array_name)
    if key_field and isinstance(item, dict):
        value = item.get(key_field)
        if isinstance(value, (str, int)):
            return "%s=%s" % (key_field, value)
    return "[%d]" % index


def _index_array(array_name, items):
    """Ordered mapping of member key -> member. Duplicate keys keep their index."""
    indexed = {}
    for position, item in enumerate(items):
        key = _member_key(array_name, item, position)
        if key in indexed:
            key = "%s#%d" % (key, position)
        indexed[key] = item
    return indexed


def _join(prefix, part):
    return part if not prefix else "%s.%s" % (prefix, part)


def _walk(a, b, path, trail, out):
    """Collect every differing JSON path between two documents.

    `trail` is the tuple of dict keys traversed to reach here, which is what lets
    `_classify` see that a leaf sits beneath `classification` even when its own
    name says nothing.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            child = _join(path, key)
            if key not in a:
                out.append((child, trail + (key,), "added", None, b[key]))
            elif key not in b:
                out.append((child, trail + (key,), "removed", a[key], None))
            else:
                _walk(a[key], b[key], child, trail + (key,), out)
        return

    if isinstance(a, list) and isinstance(b, list):
        array_name = trail[-1] if trail else ""
        left = _index_array(array_name, a)
        right = _index_array(array_name, b)
        for key in sorted(set(left) | set(right)):
            child = "%s[%s]" % (path, key)
            if key not in left:
                out.append((child, trail, "added", None, right[key]))
            elif key not in right:
                out.append((child, trail, "removed", left[key], None))
            else:
                _walk(left[key], right[key], child, trail, out)
        return

    if a != b:
        out.append((path, trail, "changed", a, b))


def _classify(trail, kind):
    """Which of the three sections a difference belongs to. Exactly one."""
    # A whole-subtree invariant wins over any leaf name beneath it.
    for key in trail:
        if key in INVARIANT_SUBTREES:
            return VIOLATION, "invariant_subtree"

    field = trail[-1] if trail else ""

    # An added or removed ARRAY MEMBER is a record appearing or disappearing —
    # legitimate content, since two live runs minutes apart see different feed
    # windows. An added or removed FIELD on a member that exists in both runs is
    # not the same thing and is classified by its name below.
    if kind in ("added", "removed") and not field:
        return CONTENT, "member_%s" % kind

    if field in PERMITTED_CLOCK_FIELDS:
        return PERMITTED, "clock_derived"
    if field in INVARIANT_FIELDS:
        return VIOLATION, "identity_invariant"
    if field in CONTENT_FIELDS:
        return CONTENT, "content_%s" % kind
    return VIOLATION, "unclassified_field"


def _summarize(value):
    """A stable, bounded rendering of one side of a difference.

    A whole added record is a finding, not a payload to inline: the report says
    what kind of thing appeared and how big it is, and the run tree remains the
    place to read it.
    """
    if isinstance(value, dict):
        return {"type": "object", "keys": len(value)}
    if isinstance(value, list):
        return {"type": "array", "length": len(value)}
    return value


# --------------------------------------------------------------- comparison
def _within_run_count_findings(label, documents):
    """Within ONE run, metadata counts must agree with that run's own records.

    E9-16, the resolved half of the plan's metadata-count contradiction. This
    check is INTRA-run and reuses the committed `runvalidate` implementation
    rather than restating it, so "a count agrees with its records" has exactly one
    definition in the tree. The INTER-run half is the opposite: a count that
    changed BETWEEN runs is a content change, classified by `_classify` through
    `CONTENT_FIELDS`, and never an identity violation.
    """
    findings = []
    for name in sorted(documents):
        if not (name.startswith("cells/") or name.startswith("topics/")):
            continue
        errors = []
        runvalidate._check_counts("%s %s" % (label, name), documents[name], errors)
        findings.extend(errors)
    return findings


def compare_runs(root, run_id_a, run_id_b):
    """Compare two runs' selected documents. Returns the report. Writes nothing."""
    if run_id_a == run_id_b:
        raise CompareError(
            "--run-id %s was given twice. Comparing a run with itself proves "
            "nothing about idempotency." % run_id_a)

    documents_a, errors_a = read_run(root, run_id_a)
    documents_b, errors_b = read_run(root, run_id_b)
    errors = sorted(errors_a + errors_b)

    sections = {PERMITTED: [], CONTENT: [], VIOLATION: []}

    for finding in (_within_run_count_findings(run_id_a, documents_a)
                    + _within_run_count_findings(run_id_b, documents_b)):
        sections[VIOLATION].append({
            "document": None, "path": None, "kind": "within_run_count",
            "reason": "metadata_disagrees_with_records", "detail": finding})

    for name in selected_document_names():
        if name not in documents_a or name not in documents_b:
            continue
        differences = []
        _walk(documents_a[name], documents_b[name], "", (), differences)
        for path, trail, kind, left, right in differences:
            section, reason = _classify(trail, kind)
            sections[section].append({
                "document": name,
                "path": path,
                "kind": kind,
                "reason": reason,
                "run_a": _summarize(left),
                "run_b": _summarize(right),
            })

    for section in sections.values():
        section.sort(key=lambda row: (row["document"] or "", row["path"] or "",
                                      row["kind"], row["reason"]))

    documents_compared = len([n for n in selected_document_names()
                              if n in documents_a and n in documents_b])
    return {
        "report_type": "compare_runs",
        "run_a": run_id_a,
        "run_b": run_id_b,
        "documents_compared": documents_compared,
        "documents_expected": SELECTED_DOCUMENTS,
        "shared_documents_excluded": SHARED_DOCUMENTS,
        "shared_documents_note": (
            "the %d shared ledger and rejection documents are updated in place "
            "and are not per-run snapshots; they have no historical A/B form and "
            "were not compared" % SHARED_DOCUMENTS),
        "errors": errors,
        PERMITTED: sections[PERMITTED],
        CONTENT: sections[CONTENT],
        VIOLATION: sections[VIOLATION],
        "idempotent": not sections[VIOLATION] and not errors,
    }


# ------------------------------------------------------- publication diff
# The committed publication layout (ROADMAP §6.3): 12 category files + 3 topic
# aggregates + 1 manifest = 16. Only the LAYOUT is committed. No projection
# exists anywhere in the tree — `promote`, `publication_manifest` and
# `promote_staging` have zero implementations — so this derives the expected
# PATHS and never the bytes that would fill them. Inventing a projection here
# would be writing the promotion this checkpoint is forbidden to write.
PUBLICATION_MANIFEST_NAME = "publication_manifest.json"


def publication_document_names():
    """The 16 expected publication paths, relative to the publication root."""
    names = []
    for cell in run_cells.configured_cells():
        names.append("%s/%s__harvest.json" % (cell["topic_slug"], cell["cell_id"]))
    for slug in runvalidate.configured_topic_slugs():
        names.append("%s/%s__all__harvest.json" % (slug, slug))
    names.append(PUBLICATION_MANIFEST_NAME)
    return sorted(names)


def _listing(root):
    """Every file under `root`, as sorted forward-slash relative paths."""
    found = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            absolute = os.path.join(dirpath, name)
            found.append(os.path.relpath(absolute, root).replace(os.sep, "/"))
    return sorted(found)


def diff_publication(root, run_id, publication_root):
    """Compare one staged run with a publication root. Reads only; creates nothing.

    Four distinguishable states, because "there is nothing published" and "what is
    published matches" are opposite answers that an empty diff would render
    identically:

        absent     the publication root does not exist   -> a real answer, exit 0
        empty      it exists and holds no file
        differs    it exists and the two sides disagree
        identical  it exists and nothing is reported

    The expected Stage 9 answer is `absent`, and this must NOT create the path in
    order to look at it.
    """
    documents, errors = read_run(root, run_id)
    expected = publication_document_names()

    if not os.path.exists(publication_root):
        state, published = "absent", []
    elif not os.path.isdir(publication_root):
        raise CompareError("--publication-root %s exists but is not a directory"
                           % publication_root)
    else:
        published = _listing(publication_root)
        state = "empty" if not published else None

    only_in_run = [name for name in expected if name not in published]
    only_in_publication = [name for name in published if name not in expected]
    # Present on BOTH sides. No committed projection exists, so the publication
    # file is REPORTED, not opened and not diffed against fabricated bytes.
    present_both = [name for name in expected if name in published]

    if state is None:
        state = ("differs" if (only_in_run or only_in_publication)
                 else "identical")

    return {
        "report_type": "publication_diff",
        "run_id": run_id,
        "publication_root": publication_root.replace(os.sep, "/"),
        "publication_root_state": state,
        "run_documents_read": len(documents),
        "expected_publication_documents": expected,
        "published_documents": published,
        "only_in_run": only_in_run,
        "only_in_publication": only_in_publication,
        "present_in_both_not_compared": present_both,
        "projection_available": False,
        "projection_note": (
            "no committed projection from a run to publication bytes exists, so "
            "this reports publication-side paths and never fabricates content "
            "for them. A difference does not authorize or perform publication."),
        "errors": errors,
    }
