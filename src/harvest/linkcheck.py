#!/usr/bin/env python3
"""linkcheck.py - bounded link-health re-checking of a completed run (S9-6).

A linkcheck answers one question about a run that already exists: **are the pages
its accepted records point at still reachable?** It is not a second harvest. It
discovers nothing, classifies nothing, scores nothing and rejects nothing. It
re-fetches a deterministic sample of the base run's accepted full records and
appends one `link_history` entry to each.

Five properties carry this module, and each is the answer to a way link-checking
goes wrong:

  * **THE BASE RUN IS IMMUTABLE.** Every byte this module writes lands under its
    own `runs/<new_run_id>/`. The base run's directory is opened read-only and a
    test hashes it before and after. Link-checking that edited its own input would
    destroy the very evidence it was measuring.
  * **AVAILABILITY IS NOT TRUTH.** A 404 today does not unmake a case that
    existed. `link_history` is append-only and NO record is ever deleted,
    downgraded or re-judged - the committed schema says so outright: *"Link-check
    never deletes a record; it appends here."*
  * **THE SAMPLE IS A FUNCTION OF CONTENT.** The first N accepted full records in
    the committed `records.sort_key` order. No RNG, no clock, no set iteration, no
    directory order. The same base run and the same N select the same records,
    always - which is what lets the suite assert byte-identical output.
  * **ONE FETCH PER CANONICAL IDENTITY.** The committed `pool.acquire_target_fetch`
    gate, reused unchanged. Two records sharing a URL cost one request and both
    see the same outcome object.
  * **THE ORDINARY RUN SHAPE, OR NONE.** A linkcheck publishes the same 43-path
    tree as any other run and validates through the same `validate --run-id`. A
    bespoke tree would need its own schema, its own validator and its own recovery
    semantics; reusing the committed ones is what makes the result checkable.

`mode: "linkcheck"` is a non-`harvest` mode, so `publication_eligible` is `false`
by the committed derivation - this module asserts no eligibility of its own.

Offline by construction in S9-6: the transport is injected, and the suite passes
the committed fixture transport. The live opener can only ever be built by
`cli.py`, which is the single reviewable owner of that decision. Executing a
linkcheck against real hosts is S9-L4, a separate operational checkpoint.
"""
import datetime
import json
import os

from . import aliases as aliases_mod
from . import artifacts
from . import httpclient as httpclient_mod
from . import pool as pool_mod
from . import records as records_mod
from . import run_cells
from . import schema as schema_mod
from . import targetfetch as targetfetch_mod
from .budget import RequestBudget

# The committed hard bound on one cell's target-fetch phase. A linkcheck samples
# across the whole run rather than per cell, so this is the ceiling on `--sample`:
# asking for more than the committed per-cell fetch bound would be asking for a
# run the policy never approved. Read from `run_cells` rather than retyped, so the
# two cannot drift.
MAX_SAMPLE = run_cells.MAX_TARGET_FETCHES_PER_CELL

DEFAULT_SAMPLE = 20

MODE_LINKCHECK = "linkcheck"

STATUS_OK = "ok"

# `build_cell_artifact` DERIVES these from the records it is given and refuses a
# caller that also asserts them. The base run's metadata carries them, so they are
# dropped when it is carried forward - re-asserting a count next to the records it
# is computed from is exactly the disagreement the builder exists to prevent.
DERIVED_METADATA_COUNTS = ("full_records", "cross_references", "total_records")

# The `link_history` fields copied VERBATIM off the committed `TargetFetchOutcome`.
# `checked_at` and `access_status` are REQUIRED by `record.v1.json` and are set
# separately; these three are written only when the outcome actually carries them,
# because a null here is a claim ("we looked and there was none") rather than the
# absence of one. `changed_materially` is DERIVED (see `_entry`) and `note` is
# deliberately never written: this module has no note to add that the
# `access_status` does not already say.
LINK_HISTORY_COPIED = ("http_status", "final_url", "content_hash")


class LinkcheckError(Exception):
    """A contract violation this module refuses to paper over."""


def _default_clock():
    return datetime.datetime.now(datetime.timezone.utc)


def validate_sample(value):
    """The sample bound, validated before anything is read or fetched.

    Refused, never clamped: silently reducing an excessive `--sample` would run
    something other than what was asked for and report success. The same reason
    S9-5C1 refuses a negative monotonic delta instead of clamping it to zero.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise LinkcheckError("--sample must be a positive integer, got %r" % (value,))
    if value < 1:
        raise LinkcheckError("--sample must be >= 1, got %r" % (value,))
    if value > MAX_SAMPLE:
        raise LinkcheckError(
            "--sample %d exceeds the committed target-fetch bound of %d. A bound "
            "may be narrowed, never widened - widening it would make the run "
            "something the policy never approved." % (value, MAX_SAMPLE))
    return value


# ------------------------------------------------------------------ base run
def read_base_run(root, base_run_id):
    """The base run's 12 cell artifacts, read-only. Never writes, never repairs.

    Returns `{cell_id: cell_artifact}`. A missing or unreadable artifact is a
    refusal rather than a partial linkcheck: sampling from an incomplete base run
    would silently change which records the sample contains.
    """
    run_directory = artifacts.run_dir(root, base_run_id)
    if not os.path.isdir(run_directory):
        raise LinkcheckError(
            "base run %s has no run directory under %s; a linkcheck re-checks an "
            "existing run and cannot invent one" % (base_run_id, root))
    out = {}
    for cell in run_cells.configured_cells():
        cell_id = cell["cell_id"]
        path = artifacts.cell_artifact_path(root, base_run_id, cell_id)
        if not os.path.isfile(path):
            raise LinkcheckError(
                "base run %s is missing cells/%s.json; refusing to sample from an "
                "incomplete base run" % (base_run_id, cell_id))
        with open(path, "r", encoding="utf-8") as handle:
            out[cell_id] = json.load(handle)
    return out


def accepted_full_records(cell_artifacts):
    """Every accepted FULL record of the base run, in committed sort order.

    A `cross_reference` is a pointer at a full record in another cell; it carries
    no fetchable page of its own, so checking one would be checking the same URL
    twice under a second name. Ordering is the committed `records.sort_key`, which
    is content-derived - not the order cells finished in and not directory order.
    """
    out = []
    for cell_id in sorted(cell_artifacts):
        for record in cell_artifacts[cell_id].get("records") or ():
            if record.get("record_type") == "full":
                out.append(record)
    return sorted(out, key=records_mod.sort_key)


def select_sample(records, sample):
    """The first `sample` accepted full records. A pure prefix of a total order."""
    return list(records[:sample])


# ------------------------------------------------------------- link history
def _entry(outcome, stamp, previous_hash=None):
    """One `link_history` entry from one committed `TargetFetchOutcome`.

    Copied off the outcome the committed client froze; nothing is re-derived and
    no second judgement is made about what the fetch meant. `checked_at` is the
    run's ONE pinned instant rather than a per-record reading, so two runs over
    equal inputs with an equal injected clock produce equal bytes.

    `changed_materially` is the one DERIVED field, and only when both hashes
    exist: a content hash that moved is the only material change this module can
    honestly observe. Absent either hash it is OMITTED rather than guessed - a
    `false` would claim the page is unchanged when nobody could tell.
    """
    entry = {"checked_at": stamp, "access_status": outcome.access_status}
    for field in LINK_HISTORY_COPIED:
        value = getattr(outcome, field, None)
        if value is not None:
            entry[field] = value
    observed = getattr(outcome, "content_hash", None)
    if observed is not None and previous_hash is not None:
        entry["changed_materially"] = observed != previous_hash
    return entry


def _appended(record, entry):
    """A copy of `record` with one entry APPENDED to its link history.

    Never in place, never a replacement, never a deletion. The prior history is
    preserved ahead of the new entry, so a record checked three times carries
    three entries in the order they were observed.
    """
    updated = dict(record)
    updated["link_history"] = list(record.get("link_history") or ()) + [entry]
    return updated


# -------------------------------------------------------------------- run
def run(root, base_run_id, *, sample=DEFAULT_SAMPLE, transport=None, clock=None,
        run_id_value=None):
    """Re-check a sample of `base_run_id`'s targets and publish a linkcheck run.

    Everything decidable without traffic is decided first - the sample bound, the
    base run's completeness, the emptiness check - so a mistake costs no request.

    Returns a dict describing what was published. Raises rather than publishing a
    partial tree: a linkcheck that half-finished is not evidence of link health.
    """
    sample = validate_sample(sample)
    cell_artifacts = read_base_run(root, base_run_id)
    candidates = accepted_full_records(cell_artifacts)
    if not candidates:
        raise LinkcheckError(
            "base run %s holds no accepted full record, so there is nothing to "
            "link-check. Refused BEFORE publication rather than writing an empty "
            "run that would look like a completed check." % base_run_id)

    selected = select_sample(candidates, sample)
    selected_ids = {record["record_id"] for record in selected}

    # The run's single UTC instant. Every artifact stamp and every new
    # `link_history[].checked_at` is this value, so equal inputs and an equal
    # injected clock give byte-identical trees (the S9-5C1 contract).
    now = clock() if clock is not None else _default_clock()
    stamp = now.strftime(run_cells.STAMP_FORMAT)
    new_run_id = run_id_value or artifacts.run_id(clock=lambda: now)
    if new_run_id == base_run_id:
        raise LinkcheckError(
            "the linkcheck run id equals the base run id (%s); a linkcheck is a "
            "NEW run and may never overwrite the run it measures" % base_run_id)
    if artifacts.run_is_finished(root, new_run_id):
        raise LinkcheckError(
            "run %s already finished in %s; a finished run's artifacts are "
            "immutable" % (new_run_id, root))

    if transport is None:
        raise LinkcheckError(
            "linkcheck.run requires an explicit transport. There is no default: "
            "the decision to reach the network belongs to cli.py, and the suite "
            "passes the committed fixture transport.")

    policy = run_cells._run_policy()
    client = httpclient_mod.HttpClient(policy, lease_root=transport.lease_root,
                                       opener=transport.opener,
                                       sleep=transport.sleep)
    budget = RequestBudget()
    pool = pool_mod.CandidatePool(new_run_id)
    canon_policy = aliases_mod.load_canonicalization()

    # ------------------------------------------------- fetch, once per identity
    outcomes = {}
    by_record = {}
    lane_id = "linkcheck__" + new_run_id
    with budget.scope("linkcheck", policy["budgets"].get("cell_max_requests"),
                      policy["budgets"].get("cell_budget_sec")):
        for record in selected:
            url = record.get("canonical_url") or record.get("identity_url")
            cand, _is_new = pool.add_candidate(url, lane_id)
            key = cand["candidate_key"]
            if pool.acquire_target_fetch(key, lane_id):
                outcomes[key] = targetfetch_mod.fetch_target(
                    url, client=client, budget=budget, clock=lambda: now)
            by_record[record["record_id"]] = outcomes[key]

    # ------------------------------------------------------- rebuild the tree
    paths = []
    checked_cells = set()
    rebuilt = {}
    for cell_id in sorted(cell_artifacts):
        base = cell_artifacts[cell_id]
        out_records = []
        for record in base.get("records") or ():
            outcome = by_record.get(record.get("record_id"))
            if outcome is not None and record.get("record_id") in selected_ids:
                entry = _entry(outcome, stamp, record.get("content_hash"))
                out_records.append(_appended(record, entry))
                checked_cells.add(cell_id)
            else:
                out_records.append(dict(record))
        metadata = {k: v for k, v in (base.get("metadata") or {}).items()
                    if k not in DERIVED_METADATA_COUNTS}
        artifact = artifacts.build_cell_artifact(
            out_records, topic=base["topic"], topic_slug=base["topic_slug"],
            category=base["category"], category_slug=base["category_slug"],
            cell_id=cell_id, harvest_run_id=new_run_id, generated_at=stamp,
            metadata=metadata)
        rebuilt[cell_id] = artifact
        paths.append(artifacts.write_cell_artifact(
            artifacts.cell_artifact_path(root, new_run_id, cell_id), artifact))

    if not checked_cells:
        raise LinkcheckError(
            "no cell received a checked record; an all-not_run linkcheck reports "
            "nothing and must not be published")

    for topic_slug in sorted({c["topic_slug"] for c in cell_artifacts.values()}):
        members = [cid for cid in sorted(rebuilt)
                   if rebuilt[cid]["topic_slug"] == topic_slug]
        artifact = artifacts.build_topic_artifact(
            [rebuilt[cid] for cid in members],
            topic=rebuilt[members[0]]["topic"], topic_slug=topic_slug,
            harvest_run_id=new_run_id, generated_at=stamp)
        paths.append(artifacts.write_topic_artifact(
            artifacts.topic_artifact_path(root, new_run_id, topic_slug), artifact))

    all_records = [r for cid in sorted(rebuilt) for r in rebuilt[cid]["records"]]
    coverage = artifacts.build_coverage_report(
        all_records, harvest_run_id=new_run_id, generated_at=stamp)
    paths.append(artifacts.write_coverage_report(
        artifacts.coverage_report_path(root, new_run_id), coverage))

    conflicts = artifacts.build_alias_conflicts(
        (), harvest_run_id=new_run_id, generated_at=stamp)
    paths.append(artifacts.write_alias_conflicts(
        artifacts.alias_conflicts_path(root, new_run_id), conflicts))

    # ------------------------------------------------------------- manifest
    rows = []
    for cell_id in sorted(rebuilt):
        row = {"cell_id": cell_id}
        if cell_id in checked_cells:
            row["status"] = STATUS_OK
        else:
            # Honest: this cell held no sampled record. A link-health RESULT never
            # sets a cell status - a 404 is a finding about a page, not a failure
            # of the cell that found it.
            row["status"] = artifacts.STATUS_NOT_RUN
        rows.append(row)

    accounting = pool.accounting()
    manifest = artifacts.build_run_manifest(
        harvest_run_id=new_run_id, started_at=stamp, finished_at=stamp,
        cells=rows, mode=MODE_LINKCHECK,
        config={"enrich": True, "bounds": {"sample": sample}},
        # A linkcheck contacts the sampled TARGET pages only. It performs no
        # source discovery, so it probes no source and reports an empty array -
        # which is a fact, not an omission.
        source_preflight=(),
        classification_decisions=(),
        request_accounting=accounting,
        target_fetch_owners=accounting.get("target_fetch_owners", 0),
        target_outcomes=[outcomes[k] for k in sorted(outcomes)],
        records=all_records,
        alias_conflicts=conflicts)
    manifest["base_run_id"] = base_run_id

    errors = schema_mod.validate(manifest, "run_manifest.v1.json")
    if errors:
        raise LinkcheckError(
            "the linkcheck manifest does not validate (%d problem(s)): %s"
            % (len(errors), "; ".join(errors[:3])))

    paths.append(artifacts.publish_run(root, new_run_id, manifest))
    return {"run_id": new_run_id, "base_run_id": base_run_id,
            "sample": sample, "checked": len(selected),
            "identities_fetched": len(outcomes), "paths": paths,
            "manifest": manifest}
