#!/usr/bin/env python3
"""scheduler.py — bounded adaptive rounds over coverage gaps.

The one thing this module must never do is change what is accepted. Coverage
targets are HINTS about where to look; `min_relevance`, `min_quality` and
`accept_composite` are read ONCE per run from policy.v1.json, recorded on every
round, and never touched again. An unmet target is reported as an unmet target —
never met by lowering a threshold, and never met by inventing a weak facet.

Round 1 is always the configured cells, exactly as today. Later rounds rank gaps
over seven factors and open bounded lanes only where a credible source exists;
where none does, `no_credible_source` is recorded and the gap is reported
honestly rather than papered over.

Deterministic and offline. Round results are INJECTED through a callable and the
clock is injectable, which is what lets the adaptive behaviour be proved by
fixture before any Stage 3 adapter exists.
"""
import glob
import json
import os

from . import coverage, facets

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POLICY_PATH = os.path.join(ROOT, "config", "harvest", "policy.v1.json")
TOPICS_DIR = os.path.join(ROOT, "config", "harvest", "topics")

STOP_REASONS = ("max_rounds", "no_progress", "duplicate_rate", "budget_exhausted",
                "all_targets_met", "no_credible_source")


class SchedulerError(Exception):
    """A scheduling contract that cannot be honoured."""


def load_thresholds(policy_path=None):
    """The acceptance thresholds. Read once per run; never written by anything here."""
    with open(policy_path or POLICY_PATH, "r", encoding="utf-8") as f:
        pol = json.load(f)
    t = pol["scoring"]["thresholds"]
    return {"min_relevance": t["min_relevance"],
            "min_quality": t["min_quality"],
            "accept_composite": t["accept_composite"]}


def configured_cells(topics_dir=None):
    """The round-1 lanes: one per configured cell, in a stable order.

    Read from the topic configs, not invented here. Facets create no cells, and
    scripts/harvest/check_config.py remains the sole authority on whether the
    configured set is the approved 12.
    """
    out = []
    for path in sorted(glob.glob(os.path.join(topics_dir or TOPICS_DIR, "*.v1.json"))):
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        for cat in doc.get("categories", []):
            out.append("cell__%s__%s" % (doc["topic_slug"], cat["category_slug"]))
    return sorted(out)


class Scheduler:
    """Bounded adaptive coverage scheduling.

    round_fn(round_no, lane_ids) -> {"records": [...], "new_accepted": int,
                                     "duplicate_rate": float|None,
                                     "budget_exhausted": bool (optional)}
    """

    def __init__(self, config_dir=None, facets_dir=None, topics_dir=None,
                 policy_path=None, clock=None):
        self.config_dir = config_dir
        self.facets_dir = facets_dir
        self.topics_dir = topics_dir
        # Read once. Every round records these, so "thresholds never moved" is
        # checkable rather than merely asserted.
        self.thresholds = load_thresholds(policy_path)
        self.targets = facets.load_coverage_targets(config_dir)
        self._clock = clock or (lambda: 0.0)

        sched = self.targets.get("scheduler", {})
        self.max_rounds = int(sched.get("max_rounds", 3))
        self.no_progress_min = int(sched.get("no_progress_min", 1))
        self.duplicate_rate_stop = float(sched.get("duplicate_rate_stop", 0.8))
        self.never_gap = set(sched.get("never_schedule_gap_lane_for", []))

        self.records = []
        self.rounds = []

    # ------------------------------------------------------------------ gaps
    def open_gaps(self, lane_stats=None, credible_sources=None,
                  remaining_budget_frac=1.0):
        """Ranked, still-unmet gaps. cross-industry and the sentinel are excluded."""
        rows = coverage.axis_targets(self.records, self.facets_dir, self.config_dir)
        ranked = coverage.rank_gaps(rows, lane_stats=lane_stats,
                                    remaining_budget_frac=remaining_budget_frac,
                                    credible_sources=credible_sources,
                                    facets_dir=self.facets_dir,
                                    config_dir=self.config_dir)
        return [r for r in ranked if r["slug"] not in self.never_gap]

    def plan_round(self, round_no, lane_stats=None, credible_sources=None,
                   remaining_budget_frac=1.0, max_lanes=2):
        """Lanes for one round.

        Round 1 is the configured cells and nothing else — the mandatory smoke
        stays an infrastructure test, never a coverage experiment.
        """
        if round_no == 1:
            return [{"lane_id": lid, "kind": "configured_cell"}
                    for lid in configured_cells(self.topics_dir)], []

        opened, skipped = [], []
        for row in self.open_gaps(lane_stats, credible_sources, remaining_budget_frac):
            if row.get("not_opened_reason") == "no_credible_source":
                skipped.append({"lane_id": row["lane_id"], "axis": row["axis"],
                                "slug": row["slug"], "gap": row["gap"],
                                "not_opened_reason": "no_credible_source"})
                continue
            if len(opened) >= max_lanes:
                break
            opened.append({"lane_id": row["lane_id"], "kind": "gap",
                           "axis": row["axis"], "slug": row["slug"],
                           "opened_because": {"gap": row["gap"],
                                              "rank_score": row["rank_score"],
                                              "factors": row["factors"]}})
        return opened, skipped

    # ------------------------------------------------------------------- run
    def run(self, round_fn, lane_stats=None, credible_sources=None,
            budget_frac_fn=None, max_lanes=2):
        """Drive rounds until a stop condition fires. Returns the rounds[] list."""
        budget_frac_fn = budget_frac_fn or (lambda r: 1.0)
        stop = None

        for round_no in range(1, self.max_rounds + 1):
            frac = budget_frac_fn(round_no)
            lanes, skipped = self.plan_round(round_no, lane_stats, credible_sources,
                                             frac, max_lanes)

            if round_no > 1 and not lanes:
                # Distinguish "nothing left to seek" from "nowhere to look".
                stop = "no_credible_source" if skipped else "all_targets_met"
                self._record(round_no, [], skipped, 0, None, stop)
                break

            result = round_fn(round_no, [l["lane_id"] for l in lanes]) or {}
            self.records.extend(result.get("records", []))
            new_accepted = int(result.get("new_accepted", 0))
            dup = result.get("duplicate_rate")

            if result.get("budget_exhausted"):
                stop = "budget_exhausted"
            elif frac <= 0.0:
                stop = "budget_exhausted"
            elif dup is not None and dup > self.duplicate_rate_stop:
                stop = "duplicate_rate"
            elif round_no > 1 and new_accepted < self.no_progress_min:
                stop = "no_progress"
            elif not self.open_gaps(lane_stats, credible_sources, frac):
                stop = "all_targets_met"
            elif round_no == self.max_rounds:
                stop = "max_rounds"

            self._record(round_no, lanes, skipped, new_accepted, dup, stop)
            if stop:
                break

        return self.rounds

    def _record(self, round_no, lanes, skipped, new_accepted, dup, stop):
        self.rounds.append({
            "round": round_no,
            "lanes": [l["lane_id"] for l in lanes],
            "new_accepted": new_accepted,
            "duplicate_rate": dup,
            "stop_reason": stop,
            # The same object every round, by construction.
            "thresholds": dict(self.thresholds),
            "_skipped": skipped,
            "_at": self._clock(),
        })

    def manifest_rounds(self):
        """rounds[] as run_manifest.v1.json expects (internal keys dropped)."""
        return [{k: v for k, v in r.items() if not k.startswith("_")}
                for r in self.rounds]
