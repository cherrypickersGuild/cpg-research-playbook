#!/usr/bin/env python3
"""facets.py — the case-facet vocabulary and the contracts built on it.

Three rules run through everything here:

  * The vocabulary files under config/harvest/facets/ are the SINGLE source of
    truth. schemas/harvest/facets.generated.v1.json is derived from them and is
    never hand-edited; this module never reads the generated file.
  * A facet value is asserted only with evidence quoted from the document. The
    lane that found a record, the publisher that printed it and the vendor whose
    model it used are never, by themselves, grounds for a label.
  * Facets are invisible to identity. Nothing here is read by urlkey.py or
    slug.py, and no function in this module contributes to record_id,
    content_id, identity_url, cell_id or a published filename.
"""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FACETS_DIR = os.path.join(ROOT, "config", "harvest", "facets")
CONFIG_DIR = os.path.join(ROOT, "config", "harvest")

FACETS_VERSION = 1

# Axis names are singular here and in case_facets.unresolved[].axis; the plural
# forms are the keys of case_facets.vocabulary_versions. Keeping both spellings
# in one place is what stops the two drifting apart.
AXES = ("industry", "business_function", "use_case_type")
AXIS_FILE = {
    "industry": "industries.v1.json",
    "business_function": "business-functions.v1.json",
    "use_case_type": "use-case-types.v1.json",
}
AXIS_PLURAL = {
    "industry": "industries",
    "business_function": "business_functions",
    "use_case_type": "use_case_types",
}

# The one slug that legitimately appears on all three axes. Every cross-axis
# disjointness check excludes exactly this value and nothing else.
SENTINEL = "other-unclear"

# Decisions R4 and C6, enforced rather than trusted: these three may be recorded
# when evidenced but are never actively sought, so a coverage override that gave
# them a target above zero would quietly reverse an approved decision.
RECORD_ONLY_INDUSTRIES = frozenset({"technology-software", "cross-industry", SENTINEL})

# Applicability. The 12-cell set is untouched by any of this: facets create no
# cells and change no filename.
FACET_GATED_CELLS = frozenset({("cases", "domain-applications")})
FACET_REPORT_ONLY_CELLS = frozenset({("cases", "case-studies"),
                                     ("cases", "product-discovery")})
FACET_FORBIDDEN_TOPICS = frozenset({"research-and-models", "discourse"})

# §5.1: the industry of the ADOPTING organisation is never inferred from who
# printed the article. A schema enum cannot express this, so it lives here and
# is enforced by check_facets.py.
INDUSTRY_FORBIDDEN_EVIDENCE_FIELDS = frozenset({"publisher"})
TECHNOLOGY_SOFTWARE_FORBIDDEN_EVIDENCE_FIELDS = frozenset({"publisher", "target_url"})

UNRESOLVED_STATES = ("other-unclear", "unmapped_legacy_value",
                     "insufficient_evidence", "not_applicable")

REPORTING_STATES = ("unmapped_legacy_value", "not_enriched",
                    "facet_complete", "facet_partial", "unresolved")


class FacetError(Exception):
    """A vocabulary or facet payload that cannot be used as configured."""


# --------------------------------------------------------------------- loading
_VOCAB_CACHE = {}
_TARGETS_CACHE = {}
_LEGACY_CACHE = {}


def _read_json(path):
    if not os.path.isfile(path):
        raise FacetError("no such file: %s" % path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except ValueError as exc:
        raise FacetError("%s is not valid JSON (%s)" % (path, exc))


def load_vocabulary(axis, facets_dir=None):
    """Load one axis vocabulary. Cached per (axis, directory)."""
    if axis not in AXES:
        raise FacetError("unknown axis %r (expected one of %s)" % (axis, ", ".join(AXES)))
    d = facets_dir or FACETS_DIR
    key = (axis, os.path.abspath(d))
    if key in _VOCAB_CACHE:
        return _VOCAB_CACHE[key]

    doc = _read_json(os.path.join(d, AXIS_FILE[axis]))
    if doc.get("axis") != axis:
        raise FacetError("%s declares axis %r but was loaded as %r"
                         % (AXIS_FILE[axis], doc.get("axis"), axis))
    _VOCAB_CACHE[key] = doc
    return doc


def load_all(facets_dir=None):
    return {axis: load_vocabulary(axis, facets_dir) for axis in AXES}


def entries(axis, facets_dir=None):
    return load_vocabulary(axis, facets_dir).get("entries", [])


def slugs(axis, facets_dir=None):
    """Every slug on an axis, including deprecated ones.

    Deprecated values must keep validating on historical records; only NEW
    assignment is refused (see active_slugs).
    """
    return frozenset(e["slug"] for e in entries(axis, facets_dir))


def active_slugs(axis, facets_dir=None):
    return frozenset(e["slug"] for e in entries(axis, facets_dir)
                     if e.get("status") == "active")


def entry(axis, slug, facets_dir=None):
    for e in entries(axis, facets_dir):
        if e["slug"] == slug:
            return e
    return None


def coverage_policy(axis, slug, facets_dir=None):
    e = entry(axis, slug, facets_dir)
    if e is None:
        raise FacetError("%r is not a %s slug" % (slug, axis))
    return e["coverage_policy"]


def tier_counts(axis, facets_dir=None):
    """{'priority': n, 'standard': n, 'record_only': n} — derived, never hardcoded."""
    out = {"priority": 0, "standard": 0, "record_only": 0}
    for e in entries(axis, facets_dir):
        out[e["coverage_policy"]] += 1
    return out


def vocabulary_versions(facets_dir=None):
    """The dict that must appear verbatim as case_facets.vocabulary_versions."""
    return {AXIS_PLURAL[axis]: load_vocabulary(axis, facets_dir)["vocabulary_version"]
            for axis in AXES}


def load_coverage_targets(config_dir=None):
    d = config_dir or CONFIG_DIR
    key = os.path.abspath(d)
    if key not in _TARGETS_CACHE:
        _TARGETS_CACHE[key] = _read_json(os.path.join(d, "coverage_targets.v1.json"))
    return _TARGETS_CACHE[key]


def target_min(axis, slug, facets_dir=None, config_dir=None):
    """The scheduler's target for one value. A HINT — never an acceptance gate."""
    targets = load_coverage_targets(config_dir)
    override = (targets.get("overrides") or {}).get(slug)
    if override is not None:
        return int(override["target_min"] if isinstance(override, dict) else override)
    tier = coverage_policy(axis, slug, facets_dir)
    return int(targets["tiers"][tier]["target_min"])


def clear_caches():
    """Drop cached config. Only tests that point at a temp directory need this."""
    _VOCAB_CACHE.clear()
    _TARGETS_CACHE.clear()
    _LEGACY_CACHE.clear()


# ---------------------------------------------------------------- legacy values
_WS = re.compile(r"\s+")


def normalize_legacy_value(value):
    """The lookup key for legacy_industry_map.v1.json.

    NFKC, collapse whitespace runs, strip, casefold. Nothing else — no synonym
    folding, no punctuation removal, no token reordering. The normalization must
    not itself be a guess, and the record always keeps the exact original in
    provenance.raw.
    """
    if not isinstance(value, str):
        return ""
    s = unicodedata.normalize("NFKC", value)
    s = _WS.sub(" ", s).strip()
    return s.casefold()


def load_legacy_industry_map(facets_dir=None):
    """{normalized legacy string -> industry slug}. A reviewed SEED, not a table."""
    d = facets_dir or FACETS_DIR
    key = os.path.abspath(d)
    if key not in _LEGACY_CACHE:
        doc = _read_json(os.path.join(d, "legacy_industry_map.v1.json"))
        out = {}
        for row in doc.get("entries", []):
            out[normalize_legacy_value(row["legacy_value"])] = row["industry"]
        _LEGACY_CACHE[key] = out
    return _LEGACY_CACHE[key]


def lookup_legacy_industry(value, facets_dir=None):
    """The reviewed slug for a legacy string, or None.

    None means unmapped, which is a REPORTABLE STATE, not a licence to guess.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    return load_legacy_industry_map(facets_dir).get(normalize_legacy_value(value))


# --------------------------------------------------- lexical evidence support
# Slugs where "the evidence exists" is not enough — it must actually be about
# THIS value. Each of these is a place where a plausible-looking assignment slips
# in without the document supporting it:
#   * a secondary industry absorbing a conglomerate's unrelated business lines;
#   * customer-interaction claimed from a chat interface with no external user;
#   * cross-industry claimed because a tool *could* be used broadly;
#   * technology-software claimed from the publisher or the platform.
LEXICAL_SUPPORT_REQUIRED = {
    ("use_case_type", "customer-interaction"),
    ("industry", "cross-industry"),
    ("industry", "technology-software"),
}


def support_terms(axis, slug, facets_dir=None):
    """The terms that can lexically support a value: positive terms + synonyms."""
    e = entry(axis, slug, facets_dir)
    if e is None:
        return frozenset()
    return frozenset(t.casefold() for t in
                     list(e.get("positive_terms") or []) + list(e.get("synonyms") or []))


def evidence_supports(axis, slug, evidence, facets_dir=None):
    """True when at least one evidence item mentions a term for this value.

    Deliberately lexical and deliberately weak — it cannot prove a value is
    right, only refuse one the document never mentions. Grounding is what makes
    a facet a finding rather than an impression.
    """
    terms = support_terms(axis, slug, facets_dir)
    if not terms:
        return True
    for ev in evidence or []:
        haystack = "%s %s" % (ev.get("matched_term") or "", ev.get("quote") or "")
        haystack = haystack.casefold()
        if any(t in haystack for t in terms):
            return True
    return False


# ------------------------------------------------------- classification contract
def _axis_values(case_facets):
    """(industry primary, [function slugs], [use-case slugs]) from a payload."""
    ind = (case_facets or {}).get("industry") or {}
    primary = ind.get("primary")
    funcs = [x.get("slug") for x in (case_facets or {}).get("business_functions") or []]
    ucs = [x.get("slug") for x in (case_facets or {}).get("use_case_types") or []]
    return primary, funcs, ucs


def any_axis_populated(case_facets):
    primary, funcs, ucs = _axis_values(case_facets)
    return bool(primary) or bool(funcs) or bool(ucs)


def decide_classification_state(case_facets, facets_dir=None):
    """'resolved' or 'unresolved' per the non-trivial requirement (§4).

    Resolved needs BOTH: industry.primary is a supported value that is not the
    other-unclear sentinel (cross-industry counts), AND at least one supported
    business function or use-case type. other-unclear alone never satisfies the
    Domain Applications requirement — that is the whole point of the rule.
    """
    primary, funcs, ucs = _axis_values(case_facets)
    if not primary or primary == SENTINEL:
        return "unresolved"
    if primary not in slugs("industry", facets_dir):
        return "unresolved"

    supported_f = [s for s in funcs if s and s != SENTINEL
                   and s in slugs("business_function", facets_dir)]
    supported_u = [s for s in ucs if s and s != SENTINEL
                   and s in slugs("use_case_type", facets_dir)]
    return "resolved" if (supported_f or supported_u) else "unresolved"


# --------------------------------------------------------- reporting + eligibility
def is_applicable(record):
    """Only `full` records carry a reporting state.

    A cross_reference is a pointer: it cannot carry case_facets, it is never
    published as independent content, and counting it would double-count the
    full record it points at.
    """
    return isinstance(record, dict) and record.get("record_type") == "full"


def reporting_state(record):
    """One of the five states, or None when the record is not applicable.

    Precedence — FIRST MATCH WINS, and the order is total, so a record can never
    be counted in two states:

      0. not applicable  record_type != "full"                    -> None
      1. unmapped_legacy_value   any unresolved[] entry says so
      2. not_enriched            case_facets absent or null
      3. facet_complete          classification_state == "resolved"
      4. facet_partial           unresolved, some axis populated
      5. unresolved              unresolved, nothing populated

    Rule 1 outranks everything, including facet_partial: a record whose
    functions were populated but whose industry came from an unmapped legacy
    string is reported as unmapped_legacy_value, because that is the fact a
    reviewer has to act on. Folding it into `unresolved` would hide it.
    """
    if not is_applicable(record):
        return None

    cf = record.get("case_facets")
    if isinstance(cf, dict):
        for u in cf.get("unresolved") or []:
            if u.get("state") == "unmapped_legacy_value":
                return "unmapped_legacy_value"

    if not isinstance(cf, dict):
        return "not_enriched"

    if cf.get("classification_state") == "resolved":
        return "facet_complete"

    return "facet_partial" if any_axis_populated(cf) else "unresolved"


def is_facet_gated(record):
    """True when facets may withhold this record from publication."""
    return (is_applicable(record)
            and (record.get("topic"), record.get("primary_category")) in FACET_GATED_CELLS)


def is_publication_eligible(record):
    """Derived — never persisted, never a record field.

    True means FACETS do not withhold this record. It is not a claim that the
    record is publishable: rejection_reason, the run-level publication_eligible
    flag and link-check outcomes are separate gates and still apply.

    A cases/domain-applications full record is eligible only in state
    facet_complete; facet_partial, unresolved, not_enriched and
    unmapped_legacy_value are all withheld. Withheld is not rejected — the
    record keeps its record_id, carries no rejection_reason, and stays auditable.

    Case Studies and Product Discovery are report-only in v1: their states are
    counted and reported but never gate anything here.
    """
    if not is_facet_gated(record):
        return True
    return reporting_state(record) == "facet_complete"


def count_states(records):
    """The five counts plus the applicable population they must sum to."""
    counts = {s: 0 for s in REPORTING_STATES}
    applicable = 0
    for rec in records:
        state = reporting_state(rec)
        if state is None:
            continue
        applicable += 1
        counts[state] += 1
    return {"counts": counts, "applicable_full_records": applicable}
