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
from . import request_key as rk


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

    def to_document(self, generated_at):
        """A candidate_pool.v1.json document.

        Sorted by key so the output is byte-identical regardless of the order
        workers and rounds happened to run in.
        """
        return {
            "schema_version": 1,
            "harvest_run_id": self.harvest_run_id,
            "generated_at": generated_at,
            "sources": [self.sources[k] for k in sorted(self.sources)],
            "candidates": [self.candidates[k] for k in sorted(self.candidates)],
        }
