#!/usr/bin/env python3
"""pool.py — shared source snapshots and the shared candidate pool.

This module is the difference between "every lane fetches what it needs" and
"the run fetches each thing once". It owns two contracts:

**Run-scoped immutable source snapshots.** The first logical fetch of a request
key in a run may use ETag/Last-Modified carried over from a PREVIOUS run; a 200
or a 304 establishes the snapshot; every later lane and every later adaptive
round reuses it; and no later round may revalidate or replace it. A changed
source needs a new run, or an explicit refresh/linkcheck. Allowing mid-run
revalidation would make output depend on when a round happened to execute, so
two runs over identical inputs could diverge — which would destroy the
determinism the fixture suite asserts.

**Logical owners versus HTTP attempts.** `fetch_count <= 1` at the HTTP level was
wrong: retries, redirect hops and conditional revalidation are legitimate
multiple attempts of ONE logical fetch. So ownership is asserted (one
source-fetch owner per request key, one target-fetch owner per canonical
candidate, one extraction owner per accepted body) while attempts are merely
observed, and charged to the same Stage 2 RequestBudget as before.

No network, no adapters. Results are INJECTED, which is what lets the suite
prove determinism under shuffled worker and round timing without Stage 3.
"""
import threading

from . import request_key as rk


# Set-like provenance: the append guards already prevent repeats, so these carry
# no multiplicity and their encounter order is a pure artefact of which worker
# happened to run first. Normalized ONLY at serialization — see
# _source_document / _candidate_document.
# Order-carrying data (feed item order, Atom entry order, JSON API item order,
# seed anchor order, repeated query-key value order) is never touched by this
# module.
_LEXICAL_SET_FIELDS = ("contributing_lanes", "source_request_keys")
_NUMERIC_SET_FIELDS = ("reused_in_rounds",)


def _sorted_unique_lexical(values):
    return sorted(set(values or ()), key=str)


def _sorted_unique_numeric(values):
    # Deliberately NOT key=str: round 10 sorts after round 2, not between 1 and 2.
    return sorted(set(values or ()))


def _designate(normalized_lanes):
    """The deterministic administrative designation for a row.

    The lexical minimum of the row's normalized contributing lanes. This is an
    assignment of responsibility, not a claim about which lane won a race or
    performed any I/O — that fact stays in live in-memory state, where control
    flow and accounting need it, and is never serialized.
    """
    return min(normalized_lanes) if normalized_lanes else None


class PoolError(Exception):
    """A contract violation the pool refuses to paper over."""


class SnapshotExists(PoolError):
    """A second fetch was attempted for a key already snapshotted in this run."""


class CandidatePool:
    """One per run. Not thread-safe by design: the cell worker owns it."""

    def __init__(self, harvest_run_id, tracking_params=None, domain_rules=None):
        self.harvest_run_id = harvest_run_id
        self._tracking_params = tracking_params
        self._domain_rules = domain_rules
        # Guards the check-and-insert in record_established_source only, so two
        # threads racing one request key cannot both publish a row. The rest of
        # the pool stays single-writer, owned by the cell worker.
        self._lock = threading.RLock()
        self.sources = {}          # source_request_key -> snapshot dict
        self.candidates = {}       # candidate_key -> candidate dict
        self.lanes = {}            # lane_id -> lane dict

    # ------------------------------------------------------------------ lanes
    def register_lane(self, lane_id, round_=1, kind="configured_cell", **extra):
        lane = self.lanes.setdefault(lane_id, {
            "schema_version": 1, "lane_id": lane_id, "round": round_,
            "kind": kind, "harvest_run_id": self.harvest_run_id,
        })
        lane.update(extra)
        return lane

    # ---------------------------------------------------------------- sources
    def request_key(self, source_id, url, **kw):
        kw.setdefault("tracking_params", self._tracking_params)
        kw.setdefault("domain_rules", self._domain_rules)
        return rk.source_request_key(source_id, url, **kw)

    def has_snapshot(self, key):
        return key in self.sources

    def acquire_source(self, key, lane_id):
        """Claim logical ownership of a request key.

        Returns True for the ONE lane that must perform the fetch, False for
        every later lane, which reuses the snapshot instead. Three lanes sharing
        a feed therefore produce one owner, not three.
        """
        if key in self.sources:
            snap = self.sources[key]
            if lane_id not in snap["contributing_lanes"]:
                snap["contributing_lanes"].append(lane_id)
            return False
        self.sources[key] = {
            "source_request_key": key,
            "source_id": None, "normalized_url": None, "adapter_mode": "default",
            "established_by": None, "established_at": None,
            "etag": None, "last_modified": None, "body_sha256": None,
            "owner_lane_id": lane_id,
            "contributing_lanes": [lane_id],
            "reused_in_rounds": [],
            "http_attempts": {"attempts": 0, "retries": 0, "redirect_hops": 0,
                              "conditional_revalidations": 0, "budget_charged": 0},
        }
        return True

    def establish_snapshot(self, key, *, source_id, normalized_url, established_by,
                           established_at=None, etag=None, last_modified=None,
                           body_sha256=None, adapter_mode="default",
                           canonicalization_version=None,
                           attempts=1, retries=0, redirect_hops=0,
                           conditional_revalidations=0, budget_charged=None):
        """Record the run's single, immutable view of one source.

        A 304 establishes it exactly as a 200 does: the cached body IS the run's
        view. Calling this twice for the same key is refused rather than allowed
        to overwrite — silently replacing a snapshot is the failure mode this
        whole contract exists to prevent.
        """
        if key not in self.sources:
            raise PoolError("no lane owns request key %s — call acquire_source first" % key)
        snap = self.sources[key]
        if snap["established_by"] is not None:
            raise SnapshotExists(
                "request key %s already has an immutable run-scoped snapshot "
                "(established by %s). No later round may revalidate or replace it; a "
                "changed source needs a new run, or an explicit refresh/linkcheck."
                % (key, snap["established_by"]))
        if established_by not in ("200", "304"):
            raise PoolError("a snapshot is established by 200 or 304, not %r" % established_by)

        snap.update({
            "source_id": source_id,
            "normalized_url": normalized_url,
            "adapter_mode": adapter_mode,
            "established_by": established_by,
            "established_at": established_at,
            "etag": etag, "last_modified": last_modified, "body_sha256": body_sha256,
        })
        if canonicalization_version is not None:
            snap["canonicalization_version"] = canonicalization_version
        snap["http_attempts"] = {
            "attempts": attempts, "retries": retries, "redirect_hops": redirect_hops,
            "conditional_revalidations": conditional_revalidations,
            "budget_charged": attempts if budget_charged is None else budget_charged,
        }
        return snap

    def record_established_source(self, key, *, source_id, normalized_url,
                                  established_by, owner_lane_id,
                                  established_at=None, etag=None, last_modified=None,
                                  body_sha256=None, adapter_mode="index",
                                  canonicalization_version=None,
                                  attempts=1, retries=0, redirect_hops=0,
                                  conditional_revalidations=0, budget_charged=None):
        """Claim ownership and establish the snapshot as ONE atomic step.

        The two-step acquire_source() -> establish_snapshot() is retained for
        callers that already use it, but it has a gap this closes: if the second
        call raises, an incomplete row is left behind whose source_id,
        normalized_url and established_by are all null — five schema errors on
        serialization. Here the complete row is built and validated off to the
        side, and only a fully valid row is ever published.

        The ACTUAL owner lane is stored, because control flow, accounting and
        diagnostics need to know who really fetched. The deterministic
        designation published in the artifact is a serialization concern and
        stays in to_document() (DV-7).
        """
        def _require(cond, msg):
            if not cond:
                raise PoolError("record_established_source: %s" % msg)

        _require(isinstance(key, str) and len(key) == 16 and
                 all(c in "0123456789abcdef" for c in key),
                 "key must be a 16-char hex source_request_key, got %r" % (key,))
        _require(isinstance(source_id, str) and source_id, "source_id must be a non-empty string")
        _require(isinstance(normalized_url, str) and
                 normalized_url.startswith(("http://", "https://")),
                 "normalized_url must be absolute http(s), got %r" % (normalized_url,))
        _require(established_by in ("200", "304"),
                 "a snapshot is established by 200 or 304, not %r" % (established_by,))
        _require(isinstance(owner_lane_id, str) and owner_lane_id,
                 "owner_lane_id must be a non-empty string")
        _require(isinstance(adapter_mode, str) and adapter_mode,
                 "adapter_mode must be a non-empty string")
        _require(body_sha256 is None or
                 (isinstance(body_sha256, str) and len(body_sha256) == 64 and
                  all(c in "0123456789abcdef" for c in body_sha256)),
                 "body_sha256 must be 64-char hex or None")
        counters = {"attempts": attempts, "retries": retries,
                    "redirect_hops": redirect_hops,
                    "conditional_revalidations": conditional_revalidations}
        for name, value in counters.items():
            _require(isinstance(value, int) and not isinstance(value, bool) and value >= 0,
                     "%s must be a non-negative int, got %r" % (name, value))
        charged = attempts if budget_charged is None else budget_charged
        _require(isinstance(charged, int) and not isinstance(charged, bool) and charged >= 0,
                 "budget_charged must be a non-negative int, got %r" % (budget_charged,))

        row = {
            "source_request_key": key,
            "source_id": source_id,
            "normalized_url": normalized_url,
            "adapter_mode": adapter_mode,
            "established_by": established_by,
            "established_at": established_at,
            "etag": etag,
            "last_modified": last_modified,
            "body_sha256": body_sha256,
            "owner_lane_id": owner_lane_id,
            "contributing_lanes": [owner_lane_id],
            "reused_in_rounds": [],
            "http_attempts": dict(counters, budget_charged=charged),
        }
        if canonicalization_version is not None:
            row["canonicalization_version"] = canonicalization_version

        with self._lock:
            if key in self.sources:
                raise SnapshotExists(
                    "request key %s already has an immutable run-scoped snapshot. "
                    "No later round may revalidate or replace it; a changed source "
                    "needs a new run, or an explicit refresh/linkcheck." % key)
            self.sources[key] = row       # the first observable state is complete
        return row

    def reuse_snapshot(self, key, lane_id, round_):
        """Read an established snapshot without issuing any request."""
        snap = self.sources.get(key)
        if snap is None or snap["established_by"] is None:
            raise PoolError("no established snapshot for request key %s" % key)
        if lane_id not in snap["contributing_lanes"]:
            snap["contributing_lanes"].append(lane_id)
        if round_ not in snap["reused_in_rounds"]:
            snap["reused_in_rounds"].append(round_)
        return snap

    # ------------------------------------------------------------- candidates
    def add_candidate(self, target_url, lane_id, source_request_key=None):
        """Deduplicate on canonical identity BEFORE extraction.

        Returns (candidate, is_new). Every contributing lane is preserved on the
        survivor: provenance is never collapsed to whichever lane happened to
        arrive first, because that is what the lane-quality metrics are computed
        from.
        """
        key, canonical = rk.candidate_key(target_url,
                                          tracking_params=self._tracking_params,
                                          domain_rules=self._domain_rules)
        cand = self.candidates.get(key)
        if cand is None:
            cand = {
                "candidate_key": key,
                "target_url": target_url,
                "canonical_key": canonical,
                "first_seen_lane_id": lane_id,
                "contributing_lanes": [lane_id],
                "source_request_keys": [source_request_key] if source_request_key else [],
                "target_fetch_owner": None,
                "extraction_owner": None,
                "duplicate_of": None,
                "dropped_reason": None,
            }
            self.candidates[key] = cand
            return cand, True

        if lane_id not in cand["contributing_lanes"]:
            cand["contributing_lanes"].append(lane_id)
        if source_request_key and source_request_key not in cand["source_request_keys"]:
            cand["source_request_keys"].append(source_request_key)
        return cand, False

    def acquire_target_fetch(self, candidate_key, lane_id):
        """One target-fetch owner per canonical candidate per run."""
        cand = self.candidates[candidate_key]
        if cand["target_fetch_owner"] is None:
            cand["target_fetch_owner"] = lane_id
            return True
        return False

    def acquire_extraction(self, candidate_key, lane_id):
        """One extraction owner per accepted response body — no double parsing."""
        cand = self.candidates[candidate_key]
        if cand["extraction_owner"] is None:
            cand["extraction_owner"] = lane_id
            return True
        return False

    # ---------------------------------------------------------------- reports
    def accounting(self):
        """Logical owners (asserted) beside HTTP attempts (observed)."""
        totals = {"source_fetch_owners": len(self.sources),
                  "target_fetch_owners": 0, "extraction_owners": 0,
                  "http_attempts": 0, "retries": 0, "redirect_hops": 0,
                  "conditional_revalidations": 0}
        for snap in self.sources.values():
            a = snap["http_attempts"]
            totals["http_attempts"] += a["attempts"]
            totals["retries"] += a["retries"]
            totals["redirect_hops"] += a["redirect_hops"]
            totals["conditional_revalidations"] += a["conditional_revalidations"]
        for cand in self.candidates.values():
            totals["target_fetch_owners"] += 1 if cand["target_fetch_owner"] else 0
            totals["extraction_owners"] += 1 if cand["extraction_owner"] else 0
        return totals

    def budget_charged(self):
        return sum(s["http_attempts"]["budget_charged"] for s in self.sources.values())

    # ------------------------------------------------------- serialization
    @staticmethod
    def _source_document(snap):
        """One source_snapshot row, normalized. Never mutates `snap`."""
        lanes = _sorted_unique_lexical(snap.get("contributing_lanes"))
        row = {
            "source_request_key": snap["source_request_key"],
            "source_id": snap["source_id"],
            "normalized_url": snap["normalized_url"],
            "adapter_mode": snap["adapter_mode"],
            "established_by": snap["established_by"],
            "established_at": snap["established_at"],
            "etag": snap["etag"],
            "last_modified": snap["last_modified"],
            "body_sha256": snap["body_sha256"],
            # The actual owner (snap["owner_lane_id"]) is deliberately absent:
            # it records who won a race and is therefore not reproducible.
            "designated_owner_lane_id": _designate(lanes),
            "contributing_lanes": lanes,
            "reused_in_rounds": _sorted_unique_numeric(snap.get("reused_in_rounds")),
            "http_attempts": dict(snap["http_attempts"]),
        }
        if "canonicalization_version" in snap:
            row["canonicalization_version"] = snap["canonicalization_version"]
        return row

    @staticmethod
    def _candidate_document(cand):
        """One candidate row, normalized. Never mutates `cand`."""
        lanes = _sorted_unique_lexical(cand.get("contributing_lanes"))
        designation = _designate(lanes)
        return {
            "candidate_key": cand["candidate_key"],
            "target_url": cand["target_url"],
            "canonical_key": cand["canonical_key"],
            # Not "first seen": a designation derived from the whole lane set.
            "primary_discovery_lane_id": designation,
            "contributing_lanes": lanes,
            "source_request_keys": _sorted_unique_lexical(cand.get("source_request_keys")),
            # null keeps its meaning — the operation has not occurred. When it
            # has, the designation names who is ACCOUNTABLE for it, not who ran it.
            "designated_target_fetch_owner_lane_id": (
                designation if cand.get("target_fetch_owner") is not None else None),
            "designated_extraction_owner_lane_id": (
                designation if cand.get("extraction_owner") is not None else None),
            "duplicate_of": cand["duplicate_of"],
            "dropped_reason": cand["dropped_reason"],
        }

    def to_document(self, generated_at):
        """A candidate_pool.v1.json document — byte-identical for equal input.

        Two independent sources of order-dependence are removed here, and only
        here, so live state keeps the encounter order and the true runtime owner
        that control flow, accounting and diagnostics rely on:

          * rows are emitted in sorted key order, and set-like provenance inside
            each row is deduplicated and sorted — lexically for lane IDs and
            request keys, NUMERICALLY for round numbers;
          * the race-determined owner scalars are replaced by deterministic
            administrative designations, because "which worker got there first"
            is an execution detail, not a finding. That exactly one fetch
            occurred is still proved by http_attempts.
        """
        return {
            "schema_version": 1,
            "harvest_run_id": self.harvest_run_id,
            "generated_at": generated_at,
            "sources": [self._source_document(self.sources[k])
                        for k in sorted(self.sources)],
            "candidates": [self._candidate_document(self.candidates[k])
                           for k in sorted(self.candidates)],
        }
