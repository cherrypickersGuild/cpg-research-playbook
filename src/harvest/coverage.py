#!/usr/bin/env python3
"""coverage.py — reporting states, coverage against targets, and gap ranking.

Three properties this module has to keep true:

  * The five reporting states are MUTUALLY EXCLUSIVE and EXHAUSTIVE over
    applicable records, so the counts always sum to the applicable population.
    cross_reference rows are excluded from all of them: a pointer is not an
    independent record, and counting it would double-count the record it points
    at.
  * Coverage targets are scheduler HINTS. Nothing here reads or writes
    min_relevance, min_quality or accept_composite. The scheduler changes WHERE
    it looks, never WHAT is accepted, and an unmet target is reported as an unmet
    target rather than met by lowering a threshold.
  * cross-industry and other-unclear are counted and reported but never close or
    reduce the gap of any concrete value, and never open a gap lane.

reporting_state() is re-exported from facets.py rather than reimplemented — one
state machine, not two that can drift.
"""
from . import facets

# Re-exported so callers can say coverage.reporting_state(...) without importing
# two modules, while the single implementation stays in facets.py.
reporting_state = facets.reporting_state
count_states = facets.count_states
REPORTING_STATES = facets.REPORTING_STATES

# Values that are recorded and reported but never sought. Decision R4 for
# cross-industry; other-unclear because seeking more unclassifiable records is
# meaningless.
NEVER_GAP_LANE = frozenset({"cross-industry", facets.SENTINEL})

GAP_FACTORS = ("remaining_gap", "configured_priority", "acceptance_yield",
               "duplicate_rate", "quality_rejection_rate",
               "credible_source_available", "remaining_budget")

# Penalties: a lane that keeps returning duplicates or low-quality items ranks
# DOWN even when its gap is large. Ranking on remaining gap alone is what makes a
# scheduler chase an unproductive value forever.
_PENALTY_FACTORS = frozenset({"duplicate_rate", "quality_rejection_rate"})

_TIER_WEIGHT = {"priority": 1.0, "standard": 0.5, "record_only": 0.0}


# ------------------------------------------------------------------ per record
def is_publication_eligible(record):
    """Derived, never persisted. See facets.is_publication_eligible."""
    return facets.is_publication_eligible(record)


def withheld_reason(record):
    """The state that caused a gated record to be withheld, or None.

    Withheld is not rejected: the record keeps its record_id, carries no
    rejection_reason, and stays auditable until reviewed.
    """
    if not facets.is_facet_gated(record):
        return None
    state = reporting_state(record)
    return None if state == "facet_complete" else state


# ---------------------------------------------------------------- observed use
def observed_counts(records, facets_dir=None):
    """{axis: {slug: n}} over applicable records.

    Counts a slug once per record. Secondary industries count toward their own
    value: a secondary is a real, evidenced deployment context.
    """
    out = {axis: {} for axis in facets.AXES}
    for rec in records:
        if not facets.is_applicable(rec):
            continue
        cf = rec.get("case_facets")
        if not isinstance(cf, dict):
            continue
        seen = {axis: set() for axis in facets.AXES}

        ind = cf.get("industry") or {}
        if ind.get("primary"):
            seen["industry"].add(ind["primary"])
        for s in ind.get("secondary") or []:
            seen["industry"].add(s)
        for item in cf.get("business_functions") or []:
            if item.get("slug"):
                seen["business_function"].add(item["slug"])
        for item in cf.get("use_case_types") or []:
            if item.get("slug"):
                seen["use_case_type"].add(item["slug"])

        for axis, slugs_ in seen.items():
            for s in slugs_:
                out[axis][s] = out[axis].get(s, 0) + 1
    return out


def axis_targets(records, facets_dir=None, config_dir=None):
    """Target versus observed for every value on every axis."""
    observed = observed_counts(records, facets_dir)
    rows = []
    for axis in facets.AXES:
        for e in facets.entries(axis, facets_dir):
            slug = e["slug"]
            tmin = facets.target_min(axis, slug, facets_dir, config_dir)
            obs = observed[axis].get(slug, 0)
            rows.append({
                "axis": axis,
                "slug": slug,
                "coverage_policy": e["coverage_policy"],
                "target_min": tmin,
                "observed": obs,
                "gap": max(0, tmin - obs),
                # cross-industry can never satisfy or reduce a concrete gap, and
                # never launches a lane of its own.
                "counts_toward_gap": slug not in NEVER_GAP_LANE,
                "unmet_reason": None,
            })
    return rows


# ------------------------------------------------------------- category report
def category_coverage(records, topic_slug, category_slug,
                      facets_dir=None, config_dir=None, with_axis_targets=True):
    """One by_category row. The five counts sum to applicable_full_records."""
    scoped = [r for r in records
              if facets.is_applicable(r)
              and r.get("topic") == topic_slug
              and r.get("primary_category") == category_slug]

    tally = facets.count_states(scoped)
    eligible = sum(1 for r in scoped if is_publication_eligible(r))

    row = {
        "topic_slug": topic_slug,
        "category_slug": category_slug,
        "applicable_full_records": tally["applicable_full_records"],
        "states": dict(tally["counts"]),
        # Case Studies and Product Discovery are report-only in v1: counted and
        # reported, blocking neither migration nor publication.
        "gated": (topic_slug, category_slug) in facets.FACET_GATED_CELLS,
        "publication_eligible_records": eligible,
        "publication_withheld_records": tally["applicable_full_records"] - eligible,
    }
    if with_axis_targets:
        row["axis_targets"] = axis_targets(scoped, facets_dir, config_dir)
    return row


def build_coverage_report(records, harvest_run_id, generated_at,
                          thresholds_constant=None, facets_dir=None, config_dir=None,
                          include_records=True):
    """A coverage_report.v1.json document."""
    pairs = []
    for rec in records:
        if facets.is_applicable(rec):
            key = (rec.get("topic"), rec.get("primary_category"))
            if key not in pairs:
                pairs.append(key)

    doc = {
        "schema_version": 1,
        "harvest_run_id": harvest_run_id,
        "generated_at": generated_at,
        "vocabulary_versions": facets.vocabulary_versions(facets_dir),
        "thresholds_constant": thresholds_constant,
        "by_category": [category_coverage(records, t, c, facets_dir, config_dir)
                        for t, c in sorted(pairs, key=lambda p: (p[0] or "", p[1] or ""))],
    }

    if include_records:
        # Published so a consumer never has to re-derive the state from topic,
        # primary_category, case_facets and legacy provenance — and so neither
        # the state nor the eligibility has to be persisted on the record.
        doc["records"] = []
        for rec in records:
            state = reporting_state(rec)
            if state is None:
                continue
            doc["records"].append({
                "record_id": rec.get("record_id"),
                "topic_slug": rec.get("topic"),
                "category_slug": rec.get("primary_category"),
                "reporting_state": state,
                "publication_eligible": is_publication_eligible(rec),
                "withheld_reason": withheld_reason(rec),
            })
    return doc


# --------------------------------------------------------------- gap ranking
def rank_gaps(rows, lane_stats=None, remaining_budget_frac=1.0,
              credible_sources=None, facets_dir=None, config_dir=None):
    """Rank unmet targets by a weighted score over SEVEN factors.

    Remaining gap alone would make the scheduler chase a value that has already
    proved unproductive, so duplicate rate and quality-rejection rate enter as
    penalties and credible-source availability gates the lane entirely.

    Returns rows sorted best-first, each carrying its factors and score. A value
    in NEVER_GAP_LANE is excluded outright, not merely down-ranked.
    """
    weights = (facets.load_coverage_targets(config_dir)
               .get("scheduler", {}).get("gap_rank_weights", {}))
    lane_stats = lane_stats or {}
    credible_sources = credible_sources or {}

    out = []
    for row in rows:
        slug = row["slug"]
        if slug in NEVER_GAP_LANE or row["gap"] <= 0:
            continue
        if row["coverage_policy"] == "record_only":
            continue

        stats = lane_stats.get(slug, {})
        has_source = bool(credible_sources.get(slug))

        factors = {
            "remaining_gap": min(1.0, row["gap"] / max(1, row["target_min"])),
            "configured_priority": _TIER_WEIGHT[row["coverage_policy"]],
            "acceptance_yield": float(stats.get("acceptance_yield", 0.5)),
            "duplicate_rate": float(stats.get("duplicate_rate", 0.0)),
            "quality_rejection_rate": float(stats.get("quality_rejection_rate", 0.0)),
            "credible_source_available": 1.0 if has_source else 0.0,
            "remaining_budget": float(remaining_budget_frac),
        }
        score = 0.0
        for name in GAP_FACTORS:
            w = float(weights.get(name, 0.0))
            score += -w * factors[name] if name in _PENALTY_FACTORS else w * factors[name]

        entry = dict(row)
        entry["factors"] = factors
        entry["rank_score"] = round(score, 6)
        entry["lane_id"] = "gap__%s__%s" % (row["axis"], slug)
        if not has_source:
            entry["not_opened_reason"] = "no_credible_source"
        out.append(entry)

    out.sort(key=lambda r: (-r["rank_score"], r["axis"], r["slug"]))
    return out
