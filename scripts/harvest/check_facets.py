#!/usr/bin/env python3
"""check_facets.py — the semantic gate for case facets.

Deliberately SEPARATE from check_config.py. That file hard-codes APPROVED_CELLS,
the 12-cell taxonomy the topic configuration is validated AGAINST, and its suite
asserts an exact summary line; merging two independent specifications into one
gate would couple a vocabulary edit to the cell check and blur which
specification a failure violated. The expectations below are hard-coded here for
the same reason they are hard-coded there: deriving them from the files being
checked would make the check vacuous.

Config-level checks:
  * the generated schema exists, compiles standalone, and matches a fresh
    regeneration byte for byte;
  * every vocabulary validates against facet_vocabulary.v1.json;
  * slugs are already slugs, unique per axis, and total EXACTLY 18 / 19 / 22
    with tier splits 7-8-3 / 10-8-1 / 10-11-1;
  * the three axes are pairwise disjoint EXCEPT the shared other-unclear
    sentinel, which is named rather than special-cased silently;
  * every named near-miss pair exists and is distinct;
  * there is no bare `operations` slug, and both concrete operations functions
    are priority;
  * technology-software / cross-industry / other-unclear are record_only, and no
    coverage override may raise a record_only value above 0;
  * customer-interaction is priority and conversational-assistant is standard.

Record-level checks (--record):
  * applicability per cell; vocabulary_versions matches the loaded vocabularies;
  * every asserted value is a live slug and carries evidence;
  * industry is never evidenced from the publisher, and technology-software is
    never evidenced from the publisher or the host URL;
  * an unmapped legacy value never appears as classification evidence;
  * a migrated record with an unmapped legacy value may not omit case_facets.

  Usage:
    python scripts/harvest/check_facets.py [--facets-dir D] [--config-dir D]
                                           [--record FILE ...] [--quiet]

Exit 0: everything is consistent. Exit 1: any problem (all are reported).
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import facets                      # noqa: E402
from src.harvest import schema as schema_mod        # noqa: E402
from src.harvest.slug import slugify, SlugError     # noqa: E402

# The specification. Hard-coded on purpose — see the module docstring.
EXPECTED_TOTALS = {"industry": 18, "business_function": 19, "use_case_type": 22}
EXPECTED_TIERS = {
    "industry":          {"priority": 7,  "standard": 8,  "record_only": 3},
    "business_function": {"priority": 10, "standard": 8,  "record_only": 1},
    "use_case_type":     {"priority": 10, "standard": 11, "record_only": 1},
}

# Values whose meaning depends on a sibling on ANOTHER axis. Each pair must exist
# and stay distinct, or the axis blur the vocabulary exists to prevent is back.
NEAR_MISS_PAIRS = [
    (("business_function", "training-enablement"), ("use_case_type", "training-education")),
    (("business_function", "legal-risk-compliance"), ("use_case_type", "risk-fraud-compliance")),
    (("business_function", "data-analytics"), ("use_case_type", "data-analysis-bi")),
    (("business_function", "software-engineering"), ("use_case_type", "code-generation")),
    (("use_case_type", "customer-interaction"), ("use_case_type", "conversational-assistant")),
]

REQUIRED_TIERS = [
    ("business_function", "supply-chain-operations", "priority"),
    ("business_function", "production-operations", "priority"),
    ("business_function", "legal-risk-compliance", "priority"),
    ("business_function", "information-security", "standard"),
    ("use_case_type", "customer-interaction", "priority"),
    ("use_case_type", "conversational-assistant", "standard"),
    ("use_case_type", "content-generation", "standard"),
    ("industry", "technology-software", "record_only"),
    ("industry", "cross-industry", "record_only"),
]

# Decision V3: no third generic operations value in v1.
FORBIDDEN_SLUGS = {"operations", "business-operations", "ops"}

LEGACY_RAW_INDUSTRY_KEYS = ("industry",)


# --------------------------------------------------------------- config checks
def check_generated_schema(problems, facets_dir, out_dir):
    """The generated file must exist, compile alone, and be free of drift."""
    path = os.path.join(out_dir, "facets.generated.v1.json")
    if not os.path.isfile(path):
        problems.append("generated schema missing: %s (run gen_facet_schema.py)" % path)
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except ValueError as exc:
        problems.append("generated schema is not valid JSON (%s). This file lives in "
                        "schemas/harvest/, which src/harvest/schema.py loads WHOLESALE into one "
                        "cached registry, so a malformed file here breaks every suite." % exc)
        return

    try:
        import jsonschema
        jsonschema.Draft202012Validator.check_schema(doc)
    except Exception as exc:                       # noqa: BLE001
        problems.append("generated schema does not compile standalone: %s" % exc)
        return

    sys.path.insert(0, os.path.join(ROOT, "scripts", "harvest"))
    import gen_facet_schema
    fresh = gen_facet_schema.render(gen_facet_schema.build(facets_dir))
    with open(path, "rb") as f:
        current = f.read()
    if current != fresh:
        problems.append("generated schema has DRIFTED from the vocabularies "
                        "(%d bytes on disk vs %d generated) — it was hand-edited or is stale; "
                        "regenerate with gen_facet_schema.py" % (len(current), len(fresh)))


def check_vocabularies(problems, facets_dir):
    seen = {}
    for axis in facets.AXES:
        rel = os.path.join("config", "harvest", "facets", facets.AXIS_FILE[axis])
        path = os.path.join(facets_dir, facets.AXIS_FILE[axis])
        for err in schema_mod.validate_file(path, "facet_vocabulary.v1.json"):
            problems.append(err)

        try:
            vocab = facets.load_vocabulary(axis, facets_dir)
        except facets.FacetError as exc:
            problems.append("%s: %s" % (rel, exc))
            continue

        ents = vocab.get("entries", [])
        if len(ents) != EXPECTED_TOTALS[axis]:
            problems.append("%s: has %d entries, the approved vocabulary has %d"
                            % (rel, len(ents), EXPECTED_TOTALS[axis]))

        local = set()
        for e in ents:
            s = e.get("slug", "")
            try:
                if slugify(s) != s:
                    problems.append("%s: %r is not already a slug (slugify gives %r)"
                                    % (rel, s, slugify(s)))
            except SlugError as exc:
                problems.append("%s: %r is not slug-able (%s)" % (rel, s, exc))
            if s in local:
                problems.append("%s: duplicate slug %r" % (rel, s))
            local.add(s)

            if s in FORBIDDEN_SLUGS:
                problems.append("%s: %r is forbidden — decision V3 creates no bare operations "
                                "value; use supply-chain-operations or production-operations"
                                % (rel, s))

            if e.get("status") == "deprecated" and not e.get("replaced_by"):
                problems.append("%s: %r is deprecated with no replaced_by" % (rel, s))
            if e.get("status") == "active" and e.get("replaced_by"):
                problems.append("%s: %r is active but names a replaced_by" % (rel, s))

        got = facets.tier_counts(axis, facets_dir)
        if got != EXPECTED_TIERS[axis]:
            problems.append("%s: tier split is %s, the approved split is %s"
                            % (rel, got, EXPECTED_TIERS[axis]))

        seen[axis] = local

    # pairwise disjoint EXCEPT the one shared sentinel
    axes = list(facets.AXES)
    for i in range(len(axes)):
        for j in range(i + 1, len(axes)):
            a, b = axes[i], axes[j]
            overlap = (seen.get(a, set()) & seen.get(b, set())) - {facets.SENTINEL}
            if overlap:
                problems.append("axes %s and %s share slug(s) %s — every slug except the "
                                "%r sentinel must belong to exactly one axis"
                                % (a, b, sorted(overlap), facets.SENTINEL))
        if facets.SENTINEL not in seen.get(axes[i], set()):
            problems.append("axis %s is missing the shared %r sentinel"
                            % (axes[i], facets.SENTINEL))

    for (ax_a, sl_a), (ax_b, sl_b) in NEAR_MISS_PAIRS:
        for ax, sl in ((ax_a, sl_a), (ax_b, sl_b)):
            if sl not in seen.get(ax, set()):
                problems.append("near-miss pair member %r is missing from axis %s" % (sl, ax))
        if sl_a == sl_b:
            problems.append("near-miss pair %r/%r collapsed into one slug" % (sl_a, sl_b))

    for axis, slug, tier in REQUIRED_TIERS:
        if slug not in seen.get(axis, set()):
            continue
        try:
            got = facets.coverage_policy(axis, slug, facets_dir)
        except facets.FacetError as exc:
            problems.append(str(exc))
            continue
        if got != tier:
            problems.append("%s/%s must be %s, is %s" % (axis, slug, tier, got))

    for slug in sorted(facets.RECORD_ONLY_INDUSTRIES):
        if slug in seen.get("industry", set()):
            got = facets.coverage_policy("industry", slug, facets_dir)
            if got != "record_only":
                problems.append("industry/%s must be record_only, is %s" % (slug, got))


def check_coverage_targets(problems, facets_dir, config_dir):
    try:
        targets = facets.load_coverage_targets(config_dir)
    except facets.FacetError as exc:
        problems.append(str(exc))
        return

    for tier in ("priority", "standard", "record_only"):
        if tier not in targets.get("tiers", {}):
            problems.append("coverage_targets.v1.json: tier %r has no target_min" % tier)
    if targets.get("tiers", {}).get("record_only", {}).get("target_min") != 0:
        problems.append("coverage_targets.v1.json: record_only target_min must be 0")

    for slug, override in (targets.get("overrides") or {}).items():
        value = override["target_min"] if isinstance(override, dict) else override
        axis = next((a for a in facets.AXES if slug in facets.slugs(a, facets_dir)), None)
        if axis is None:
            problems.append("coverage_targets.v1.json: override for unknown slug %r" % slug)
            continue
        if facets.coverage_policy(axis, slug, facets_dir) == "record_only" and int(value) > 0:
            problems.append(
                "coverage_targets.v1.json: override raises record_only value %r to %s. "
                "Refused: decisions R4 and C6 say cross-industry never closes a concrete gap "
                "and technology-software is never actively sought." % (slug, value))

    never = set(targets.get("scheduler", {}).get("never_schedule_gap_lane_for", []))
    for required in ("cross-industry", facets.SENTINEL):
        if required not in never:
            problems.append("coverage_targets.v1.json: %r must appear in "
                            "scheduler.never_schedule_gap_lane_for" % required)


def check_legacy_map(problems, facets_dir):
    path = os.path.join(facets_dir, "legacy_industry_map.v1.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as exc:
        problems.append("legacy_industry_map.v1.json: cannot read (%s)" % exc)
        return

    industry_slugs = facets.slugs("industry", facets_dir)
    seen = set()
    for row in doc.get("entries", []):
        raw = row.get("legacy_value", "")
        slug = row.get("industry", "")
        norm = facets.normalize_legacy_value(raw)
        if norm != raw:
            problems.append("legacy_industry_map.v1.json: key %r is not in normalized form "
                            "(expected %r) — lookups would silently miss it" % (raw, norm))
        if norm in seen:
            problems.append("legacy_industry_map.v1.json: duplicate key %r" % norm)
        seen.add(norm)
        if slug not in industry_slugs:
            problems.append("legacy_industry_map.v1.json: %r maps to %r, which is not an "
                            "industry slug" % (raw, slug))
        if slug == facets.SENTINEL:
            problems.append("legacy_industry_map.v1.json: %r maps to the sentinel. A reviewed "
                            "mapping must name a real industry; an unreviewable value belongs "
                            "in no entry at all, so it becomes unmapped_legacy_value." % raw)


# --------------------------------------------------------------- record checks
def validate_record_facets(record, facets_dir=None, new_assignment=True):
    """Semantic checks a JSON Schema cannot express. Returns a list of problems."""
    problems = []
    rid = record.get("record_id", "<no record_id>")
    rtype = record.get("record_type")
    topic = record.get("topic")
    category = record.get("primary_category")
    cf = record.get("case_facets")

    if rtype == "cross_reference":
        if cf is not None:
            problems.append("%s: a cross_reference may never carry case_facets" % rid)
        return problems
    if rtype != "full":
        return problems

    if topic in facets.FACET_FORBIDDEN_TOPICS and isinstance(cf, dict):
        problems.append("%s: topic %r may not carry case_facets" % (rid, topic))
        return problems

    if (topic, category) in facets.FACET_GATED_CELLS and not isinstance(cf, dict):
        problems.append("%s: cases/domain-applications requires a case_facets object" % rid)
        return problems

    # the consistency rule: a migrated record may not hide an unmapped legacy value
    prov = record.get("provenance") or {}
    raw = prov.get("raw") or {}
    legacy_value = None
    if prov.get("migration") and isinstance(raw, dict):
        for key in LEGACY_RAW_INDUSTRY_KEYS:
            v = raw.get(key)
            if isinstance(v, str) and v.strip():
                legacy_value = v
                break
    unmapped_legacy = (legacy_value is not None
                       and facets.lookup_legacy_industry(legacy_value, facets_dir) is None)

    if unmapped_legacy:
        entries_ = (cf or {}).get("unresolved") or [] if isinstance(cf, dict) else []
        if not any(u.get("state") == "unmapped_legacy_value" for u in entries_):
            problems.append(
                "%s: provenance.raw carries the unmapped legacy industry %r, so case_facets "
                "must exist and carry an unresolved[] entry with state 'unmapped_legacy_value'. "
                "Omitting it would report the record as not_enriched and hide the value."
                % (rid, legacy_value))

    if not isinstance(cf, dict):
        return problems

    expected_versions = facets.vocabulary_versions(facets_dir)
    if cf.get("vocabulary_versions") != expected_versions:
        problems.append("%s: vocabulary_versions %r does not match the loaded vocabularies %r"
                        % (rid, cf.get("vocabulary_versions"), expected_versions))

    if cf.get("facets_version") != facets.FACETS_VERSION:
        problems.append("%s: facets_version must be %d" % (rid, facets.FACETS_VERSION))

    # every asserted value must be a live slug, and carry evidence
    ind = cf.get("industry") or {}
    asserted = []
    secondary_slugs = set()
    if ind.get("primary"):
        asserted.append(("industry", ind["primary"], ind.get("evidence") or []))
    for s in ind.get("secondary") or []:
        secondary_slugs.add(s)
        asserted.append(("industry", s, ind.get("evidence") or []))
    for item in cf.get("business_functions") or []:
        asserted.append(("business_function", item.get("slug"), item.get("evidence") or []))
    for item in cf.get("use_case_types") or []:
        asserted.append(("use_case_type", item.get("slug"), item.get("evidence") or []))

    for axis, slug, evidence in asserted:
        if slug not in facets.slugs(axis, facets_dir):
            problems.append("%s: %r is not a %s slug" % (rid, slug, axis))
            continue
        if new_assignment and slug not in facets.active_slugs(axis, facets_dir):
            problems.append("%s: %r is deprecated and may not be newly assigned "
                            "(it still validates on historical records)" % (rid, slug))
        if not evidence:
            problems.append("%s: %s value %r is asserted with no evidence" % (rid, axis, slug))

        if axis == "industry":
            for ev in evidence:
                field = ev.get("field")
                if field in facets.INDUSTRY_FORBIDDEN_EVIDENCE_FIELDS:
                    problems.append(
                        "%s: industry %r is evidenced from field %r. The industry is the "
                        "ADOPTING organisation's, never the publisher's — a vendor-published "
                        "customer case takes the customer's industry." % (rid, slug, field))
                if (slug == "technology-software"
                        and field in facets.TECHNOLOGY_SOFTWARE_FORBIDDEN_EVIDENCE_FIELDS):
                    problems.append(
                        "%s: technology-software is evidenced from field %r. It is never "
                        "inferred from the publisher, the AI vendor, the platform provider, or "
                        "the fact that the piece appears on a technology site." % (rid, field))

        # The value must actually be MENTIONED, not merely accompanied by a quote.
        needs_support = ((axis, slug) in facets.LEXICAL_SUPPORT_REQUIRED
                         or (axis == "industry" and slug in secondary_slugs))
        if needs_support and not facets.evidence_supports(axis, slug, evidence, facets_dir):
            if slug in secondary_slugs:
                problems.append(
                    "%s: secondary industry %r is not supported by any quoted evidence. A "
                    "secondary means DEPLOYMENT CONTEXT, not corporate portfolio — a "
                    "conglomerate's unrelated business lines generate no secondary label."
                    % (rid, slug))
            elif slug == "customer-interaction":
                problems.append(
                    "%s: customer-interaction is asserted with no evidence of an EXTERNAL "
                    "audience. A conversational interface alone proves nothing about who is "
                    "on the other end; an internal copilot is conversational-assistant only."
                    % rid)
            elif slug == "cross-industry":
                problems.append(
                    "%s: cross-industry is asserted with no evidence of a genuinely "
                    "horizontal or documented multi-industry deployment. A tool that COULD "
                    "be used broadly is not cross-industry." % rid)
            else:
                problems.append(
                    "%s: %s value %r is not supported by any quoted evidence" % (rid, axis, slug))

    # an unmapped legacy value is a reviewer to-do, never classification evidence
    unmapped_terms = {facets.normalize_legacy_value(u.get("term") or "")
                      for u in cf.get("unresolved") or []
                      if u.get("state") == "unmapped_legacy_value"} - {""}
    if unmapped_terms:
        for _axis, _slug, evidence in asserted:
            for ev in evidence:
                if facets.normalize_legacy_value(ev.get("matched_term") or "") in unmapped_terms:
                    problems.append(
                        "%s: the unmapped legacy value %r is presented as classification "
                        "evidence. An unmapped value is a reviewer to-do, not a fact."
                        % (rid, ev.get("matched_term")))

    declared = cf.get("classification_state")
    computed = facets.decide_classification_state(cf, facets_dir)
    if declared != computed:
        problems.append("%s: classification_state is %r but the record's own values compute "
                        "to %r" % (rid, declared, computed))

    if declared == "unresolved" and not (cf.get("unresolved") or []):
        problems.append("%s: an unresolved record must carry at least one unresolved[] entry "
                        "saying why" % rid)

    return problems


# ---------------------------------------------------------------------- driver
def main(argv=None):
    p = argparse.ArgumentParser(description="Validate the case-facet vocabularies and records.")
    p.add_argument("--facets-dir", default=facets.FACETS_DIR)
    p.add_argument("--config-dir", default=facets.CONFIG_DIR)
    p.add_argument("--schema-dir", default=os.path.join(ROOT, "schemas", "harvest"))
    p.add_argument("--record", action="append", default=[],
                   help="a JSON file holding one record or a list of records")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    facets.clear_caches()
    problems = []

    check_generated_schema(problems, args.facets_dir, args.schema_dir)
    check_vocabularies(problems, args.facets_dir)
    check_coverage_targets(problems, args.facets_dir, args.config_dir)
    check_legacy_map(problems, args.facets_dir)

    n_records = 0
    for path in args.record:
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, ValueError) as exc:
            problems.append("%s: cannot read (%s)" % (path, exc))
            continue
        recs = payload if isinstance(payload, list) else [payload]
        for rec in recs:
            n_records += 1
            problems.extend("%s: %s" % (os.path.basename(path), m)
                            for m in validate_record_facets(rec, args.facets_dir))

    if problems:
        for m in problems:
            print("ERROR: %s" % m, file=sys.stderr)
        print("ERROR: facet check FAILED (%d problem(s))." % len(problems), file=sys.stderr)
        return 1

    if not args.quiet:
        totals = " ".join("%s=%d" % (facets.AXIS_PLURAL[a], EXPECTED_TOTALS[a])
                          for a in facets.AXES)
        print("[facets] OK — %s records=%d (vocabularies, tiers, disjointness, targets, "
              "legacy map and generated schema all consistent)" % (totals, n_records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
