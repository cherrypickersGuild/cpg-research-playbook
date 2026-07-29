#!/usr/bin/env python3
"""ledger.py — the per-cell rejection log and URL ledger (S5-3).

Two artifacts, one job between them: make "this cell returned nothing" always
explainable, and make "we have already seen this URL" durable across runs.

  * A REJECTION IS A FINDING, NOT A DELETION. The rejection log records every
    candidate that was considered and not accepted, with the reason and the
    numbers behind it, so a threshold change can be evaluated against what it
    would have admitted. Reasons come from `Verdict.rejection_reason` and are
    never re-derived here — this module has no opinion about what should be
    rejected.
  * THE LEDGER IS KEYED BY IDENTITY, NOT BY THE RAW STRING. `identity_url` is the
    canonicalized, immutable identity, which is the deliberate difference from
    the legacy `state/visited_url_ledger.json`: that file keys raw source URLs and
    so treats http/https/www/utm variants as distinct rows.
  * A REJECTED URL STAYS REJECTED. `outcome: "rejected"` is retained on purpose.
    Drop it and every run re-fetches and re-rejects the same URL.
  * FIRST SEEN IS WRITTEN ONCE. Re-merging an observation advances `last_seen_at`
    and `seen_count` and touches nothing else. An outcome, once terminal, is
    final; a second observation claiming a DIFFERENT terminal outcome is a
    contradiction and raises rather than being quietly dropped.
  * LOSING A LEDGER IS EXPENSIVE. An existing ledger that cannot be read or does
    not validate raises. Silently starting from empty would re-harvest the whole
    corpus and look like success.

Not here: coverage reporting, manifests, `LATEST_RUN_ID` (S5-4, S5-5), cell
execution (S5-6), recovery orchestration (S5-7), locking, concurrency, the
network. Bytes reach disk only through the shared S5-1 writer.
"""
import json
import os

from . import artifacts
from . import schema

# The terminal outcomes. `pending` is the only non-terminal one: a candidate that
# has been seen but whose verdict is not yet known.
PENDING = "pending"
TERMINAL_OUTCOMES = ("accepted", "rejected", "duplicate")
OUTCOMES = (PENDING,) + TERMINAL_OUTCOMES

# Entry fields a caller may supply. `first_seen_at`, `last_seen_at` and
# `seen_count` are owned by the merge and are never accepted from an observation.
OBSERVATION_FIELDS = ("identity_url", "content_id", "source_id", "outcome",
                      "rejection_reason", "record_id", "http_status",
                      "content_hash", "last_checked_at")
MERGE_OWNED_FIELDS = ("first_seen_at", "last_seen_at", "seen_count")


class LedgerError(Exception):
    """A contract violation this module refuses to paper over."""


# -------------------------------------------------------------- rejection log
def _rejection_entry(extracted, verdict, rejected_at):
    scores = getattr(verdict, "scores", None)
    source_ids = tuple(getattr(extracted, "source_ids", ()) or ())
    if not source_ids:
        raise LedgerError("candidate %r has no source_id; a rejection must name "
                          "the source that offered it"
                          % getattr(extracted, "candidate_key", None))
    entry = {
        "identity_url": extracted.identity_url,
        "target_url": getattr(extracted, "target_url", None),
        # The first source in committed dedupe order. A candidate offered by
        # several sources is still one rejection, attributed to one of them.
        "source_id": source_ids[0],
        "title": getattr(extracted, "title", None),
        "rejection_reason": verdict.rejection_reason,
        "detail": getattr(verdict, "detail", None) or None,
        "rejected_at": rejected_at,
    }
    if scores is not None:
        entry["scores"] = {
            "relevance": getattr(scores, "relevance", None),
            "quality": getattr(scores, "quality", None),
            "audience_fit": getattr(scores, "audience_fit", None),
            "freshness": getattr(scores, "freshness", None),
        }
    return entry


def build_rejection_log(verdicts, *, cell_id, harvest_run_id, generated_at):
    """One cell's rejection log.

    `verdicts` is an iterable of `(extracted, verdict)` pairs: a `Verdict` names
    the reason and the scores but carries no identity, so the candidate has to
    come with it. Accepted verdicts are skipped — this is a log of refusals.
    """
    rejections = []
    for extracted, verdict in verdicts:
        if getattr(verdict, "accepted", False):
            continue
        if not verdict.rejection_reason:
            raise LedgerError("candidate %r was not accepted but names no "
                              "rejection_reason" % extracted.identity_url)
        rejections.append(_rejection_entry(extracted, verdict, generated_at))

    # (reason, identity_url): grouped by reason, and a function of content rather
    # than of the order candidates happened to be scored in.
    rejections.sort(key=lambda r: (r["rejection_reason"], r["identity_url"]))
    return {
        "schema_version": 1,
        "cell_id": cell_id,
        "harvest_run_id": harvest_run_id,
        "generated_at": generated_at,
        "rejections": rejections,
    }


def write_rejection_log(root, cell_id, doc):
    return artifacts.write_document(artifacts.rejection_log_path(root, cell_id),
                                    doc, "rejection.v1.json")


# --------------------------------------------------------------------- ledger
def empty_ledger(cell_id, updated_at):
    return {"schema_version": 1, "cell_id": cell_id, "updated_at": updated_at,
            "entries": []}


def load_ledger(root, cell_id):
    """The existing ledger, or None when this cell has never run.

    A missing file is a first run, not a fault. A file that exists but cannot be
    parsed or does not validate raises: treating it as empty would silently
    re-harvest everything this cell has ever seen.
    """
    path = artifacts.ledger_path(root, cell_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as handle:
            doc = json.loads(handle.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise LedgerError("ledger %s is unreadable (%s). Refusing to continue: "
                          "starting from empty would re-harvest the whole cell."
                          % (path, exc)) from exc
    errors = schema.validate(doc, "ledger.v1.json")
    if errors:
        raise LedgerError("ledger %s does not validate (%d problem(s)): %s. "
                          "Refusing to continue: starting from empty would "
                          "re-harvest the whole cell."
                          % (path, len(errors), "; ".join(errors[:2])))
    if doc.get("cell_id") != cell_id:
        raise LedgerError("ledger %s belongs to cell %r, not %r"
                          % (path, doc.get("cell_id"), cell_id))
    return doc


def _check_observation(observation):
    identity = observation.get("identity_url")
    if not identity:
        raise LedgerError("every observation needs an identity_url")
    owned = sorted(set(observation) & set(MERGE_OWNED_FIELDS))
    if owned:
        raise LedgerError("observation for %s may not set %s — the merge owns "
                          "those fields" % (identity, ", ".join(owned)))
    unknown = sorted(set(observation) - set(OBSERVATION_FIELDS))
    if unknown:
        raise LedgerError("observation for %s carries unknown field(s) %s"
                          % (identity, ", ".join(unknown)))
    outcome = observation.get("outcome", PENDING)
    if outcome not in OUTCOMES:
        raise LedgerError("observation for %s has outcome %r, not one of %s"
                          % (identity, outcome, ", ".join(OUTCOMES)))
    return identity, outcome


def _resolve_outcome(identity, existing, incoming):
    """`pending -> terminal` once. A different terminal is a contradiction."""
    if existing == incoming:
        return existing
    if existing == PENDING:
        return incoming
    if incoming == PENDING:
        # A later, less informative sighting never un-decides a decided URL.
        return existing
    raise LedgerError("ledger outcome for %s is already %r; refusing to change "
                      "it to %r — a terminal outcome is final"
                      % (identity, existing, incoming))


def merge_ledger(existing, observations, *, now, cell_id=None):
    """Fold observations into a ledger. Idempotent apart from the seen counters.

    Re-applying the same observations advances `last_seen_at` and `seen_count`
    and changes nothing else: not `first_seen_at`, not `outcome`, not the number
    of entries.
    """
    if existing is None:
        if not cell_id:
            raise LedgerError("merging into a new ledger needs a cell_id")
        existing = empty_ledger(cell_id, now)
    target_cell = cell_id or existing.get("cell_id")

    entries = {}
    for entry in existing.get("entries", ()):
        entries[entry["identity_url"]] = dict(entry)

    for observation in observations:
        identity, incoming = _check_observation(observation)
        entry = entries.get(identity)
        if entry is None:
            entry = {"identity_url": identity, "first_seen_at": now,
                     "last_seen_at": now, "seen_count": 1, "outcome": incoming}
            for field in OBSERVATION_FIELDS:
                if field in ("identity_url", "outcome"):
                    continue
                if field in observation:
                    entry[field] = observation[field]
            entries[identity] = entry
            continue

        entry["outcome"] = _resolve_outcome(identity, entry.get("outcome", PENDING),
                                            incoming)
        entry["last_seen_at"] = now
        entry["seen_count"] = int(entry.get("seen_count", 1)) + 1
        # first_seen_at is deliberately absent from this loop.
        for field in OBSERVATION_FIELDS:
            if field in ("identity_url", "outcome"):
                continue
            if observation.get(field) is not None:
                entry[field] = observation[field]

    return {
        "schema_version": 1,
        "cell_id": target_cell,
        "updated_at": now,
        "entries": [entries[key] for key in sorted(entries)],
    }


def write_ledger(root, cell_id, doc):
    return artifacts.write_document(artifacts.ledger_path(root, cell_id),
                                    doc, "ledger.v1.json")
