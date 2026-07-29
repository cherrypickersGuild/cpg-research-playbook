#!/usr/bin/env python3
"""facetassign.py — deterministic `case_facets` assignment (S4-5A).

The three vocabularies under `config/harvest/facets/` are the authority, and
`facets.py` owns every contract built on them. This module only *applies* them:
it never restates a slug, never invents a term, and never recomputes a state
`facets.py` already decides.

Five rules run through everything, each of them a committed contract rather than
a preference:

  * A FACET IS A FINDING, NOT AN IMPRESSION. A value is asserted only with a term
    quoted from the document. `facets.evidence_supports` is called as the final
    gate on every asserted value, so an ungrounded slug cannot survive.
  * THE PUBLISHER IS NOT THE CUSTOMER. `INDUSTRY_FORBIDDEN_EVIDENCE_FIELDS`
    keeps `publisher` out of industry evidence — a vendor-published customer
    story takes the CUSTOMER's industry — and
    `TECHNOLOGY_SOFTWARE_FORBIDDEN_EVIDENCE_FIELDS` additionally keeps
    `target_url` out of `technology-software`, so a slug cannot be earned by the
    domain the page happens to live on.
  * AMBIGUITY IS RECORDED, NOT BROKEN BY A TIE-BREAK. Two industries matching
    equally well is a genuine ambiguity, so the axis resolves to the committed
    `other-unclear` sentinel with the competing values named in `unresolved[]`.
    Picking the alphabetically smaller one would manufacture a finding.
  * APPLICABILITY IS THE SCHEMA'S, NOT OURS. `research-and-models` and
    `discourse` full records may not carry facets at all, so those return an
    explicit not-applicable result — never an empty payload dressed up as an
    attempted classification, which `reporting_state` would then count as
    `unresolved` instead of `not_enriched`.
  * ONE MATCHER. Vocabulary terms go through classify's committed whole-token
    matcher (S4-3A), the same one verify uses. `ide` does not match `guide` here
    either.

Not here: record construction (S4-5B), scoring, verification, classification,
the pool, and any form of I/O beyond reading the committed vocabularies.
"""
import dataclasses

from . import classify as cl
from . import facets

# The evidence fields available to Stage 4, in a fixed order. `body` and
# `legacy_field` are legal in the schema but need a fetch or a migration, so they
# never appear here.
EVIDENCE_FIELDS = ("title", "summary", "publisher", "target_url")

# Confidence shape. NOT committed config — `facets.py` fixes which values are
# legal and when evidence is required, but not how confident an assignment is.
# Distinct supporting terms, saturating: one mention is a hint, three is a theme.
CONFIDENCE_SATURATION = 3
PRECISION = 4

# Quote window around a match, in characters. The schema requires 3..400.
QUOTE_WINDOW = 120
QUOTE_MIN, QUOTE_MAX = 3, 400

# Schema caps, restated only so a violation raises here rather than at S4-5B.
MAX_MULTI_VALUES = 4
MAX_SECONDARY = 2


class FacetAssignError(Exception):
    """A contract violation this module refuses to paper over."""


# ------------------------------------------------------------------- outputs
@dataclasses.dataclass(frozen=True, slots=True)
class FacetAssignment:
    """One candidate's facet outcome.

    `case_facets` is None in exactly two situations, and they mean different
    things: the topic forbids facets (`applicable` False), or the cell permits
    them but nothing could be grounded. Only the first is not-applicable.
    """
    candidate_key: str
    applicable: bool
    case_facets: dict = None
    reason: str = ""
    gated: bool = False
    report_only: bool = False

    @property
    def classification_state(self):
        if not isinstance(self.case_facets, dict):
            return None
        return self.case_facets.get("classification_state")


# ------------------------------------------------------------------ matching
def _quote(text, start, end):
    """A bounded quote around the match, from the ORIGINAL text."""
    left = max(0, start - QUOTE_WINDOW // 2)
    right = min(len(text), end + QUOTE_WINDOW // 2)
    snippet = text[left:right].strip()
    if len(snippet) < QUOTE_MIN:
        snippet = text.strip()
    return snippet[:QUOTE_MAX]


def _allowed_fields(axis, slug):
    """Which fields may ground this value. The committed prohibitions, applied."""
    forbidden = set()
    if axis == "industry":
        forbidden |= facets.INDUSTRY_FORBIDDEN_EVIDENCE_FIELDS
        if slug == "technology-software":
            forbidden |= facets.TECHNOLOGY_SOFTWARE_FORBIDDEN_EVIDENCE_FIELDS
    return tuple(f for f in EVIDENCE_FIELDS if f not in forbidden)


def _terms(axis, slug, facets_dir=None):
    """positive_terms + synonyms, in committed config order."""
    entry = facets.entry(axis, slug, facets_dir)
    if entry is None:
        return ()
    return tuple(list(entry.get("positive_terms") or []) +
                 list(entry.get("synonyms") or []))


def _evidence_for(extracted, axis, slug, facets_dir=None):
    """Every distinct supporting term found, quoted. Config order, so stable."""
    fields = _allowed_fields(axis, slug)
    out = []
    for term in _terms(axis, slug, facets_dir):
        if len(term) < 2:
            continue                      # matched_term has minLength 2
        for field in fields:
            text = getattr(extracted, field, None)
            if not isinstance(text, str) or len(text) < QUOTE_MIN:
                continue
            tokens = cl._tokenize(text)
            span = cl._find_term(term, tokens)
            if span is None:
                continue
            first, last = span
            start, end = tokens[first][1], tokens[last][2]
            out.append({"field": field, "matched_term": term,
                        "quote": _quote(text, start, end), "offset": start})
            break
    return out


def _confidence(hits):
    return round(min(hits, CONFIDENCE_SATURATION) / float(CONFIDENCE_SATURATION),
                 PRECISION)


def _candidates_for_axis(extracted, axis, facets_dir=None):
    """(slug, evidence) for every vocabulary value this document supports.

    Ordered by strength then slug, both derived from content, so two runs rank
    identically. `evidence_supports` is the final gate: a value on
    LEXICAL_SUPPORT_REQUIRED that nothing in the document mentions is dropped
    even if it somehow got this far.
    """
    found = []
    for slug in sorted(facets.active_slugs(axis, facets_dir)):
        if slug == facets.SENTINEL:
            continue                      # the sentinel is a state, not a match
        evidence = _evidence_for(extracted, axis, slug, facets_dir)
        if not evidence:
            continue
        if not facets.evidence_supports(axis, slug, evidence, facets_dir):
            continue
        found.append((slug, evidence))
    return sorted(found, key=lambda pair: (-len(pair[1]), pair[0]))


# --------------------------------------------------------------------- axes
def _industry_axis(extracted, facets_dir=None):
    """The single-value axis. A tie is an ambiguity, not a coin toss."""
    ranked = _candidates_for_axis(extracted, "industry", facets_dir)
    unresolved = []
    if not ranked:
        unresolved.append({
            "axis": "industry", "state": "insufficient_evidence", "term": None,
            "detail": "no industry vocabulary term is grounded in the document"})
        return {"primary": None, "secondary": [], "confidence": None,
                "evidence": []}, unresolved

    best = len(ranked[0][1])
    tied = [slug for slug, evidence in ranked if len(evidence) == best]
    if len(tied) > 1:
        unresolved.append({
            "axis": "industry", "state": facets.SENTINEL, "term": None,
            "detail": "%d industries are equally supported: %s"
                      % (len(tied), ", ".join(tied))})
        return {"primary": facets.SENTINEL, "secondary": [],
                "confidence": _confidence(best),
                "evidence": ranked[0][1]}, unresolved

    slug, evidence = ranked[0]
    # `secondary` means DEPLOYMENT CONTEXT, never corporate portfolio — a
    # judgement lexical evidence cannot make. Left empty deliberately rather
    # than filled with the runners-up. See CF-11.
    return {"primary": slug, "secondary": [],
            "confidence": _confidence(len(evidence)),
            "evidence": evidence}, unresolved


def _multi_axis(extracted, axis, facets_dir=None):
    """A multi-value axis, capped by the schema and ordered deterministically."""
    ranked = _candidates_for_axis(extracted, axis, facets_dir)
    unresolved = []
    if not ranked:
        unresolved.append({
            "axis": axis, "state": "insufficient_evidence", "term": None,
            "detail": "no %s vocabulary term is grounded in the document" % axis})
        return [], unresolved
    kept = ranked[:MAX_MULTI_VALUES]
    if len(ranked) > MAX_MULTI_VALUES:
        unresolved.append({
            "axis": axis, "state": facets.SENTINEL, "term": None,
            "detail": "%d values matched; the schema admits %d, dropped: %s"
                      % (len(ranked), MAX_MULTI_VALUES,
                         ", ".join(slug for slug, _ in ranked[MAX_MULTI_VALUES:]))})
    return [{"slug": slug, "confidence": _confidence(len(evidence)),
             "evidence": evidence} for slug, evidence in kept], unresolved


# --------------------------------------------------------------------- entry
def applicability(classification):
    """(applicable, gated, report_only) for a classified cell. Schema's rules."""
    cell = (classification.topic_slug, classification.category_slug)
    if classification.topic_slug in facets.FACET_FORBIDDEN_TOPICS:
        return False, False, False
    return True, cell in facets.FACET_GATED_CELLS, cell in facets.FACET_REPORT_ONLY_CELLS


def assign(extracted, classification, *, facets_dir=None):
    """Assign `case_facets` for one classified candidate, or say it does not apply.

    Never fetches, never builds a record, never touches the classification or any
    score. A lane id, a request key and an ownership designation are not evidence
    and are not read.
    """
    key = getattr(extracted, "candidate_key", "")
    applicable, gated, report_only = applicability(classification)
    if not applicable:
        # record.v1.json requires case_facets to be null for these topics. An
        # empty payload here would be counted as `unresolved` rather than
        # `not_enriched`, which is a different and wrong reviewer signal.
        return FacetAssignment(
            candidate_key=key, applicable=False, case_facets=None,
            reason="topic %r may not carry case_facets" % classification.topic_slug)

    industry, unresolved = _industry_axis(extracted, facets_dir)
    functions, more = _multi_axis(extracted, "business_function", facets_dir)
    unresolved += more
    use_cases, more = _multi_axis(extracted, "use_case_type", facets_dir)
    unresolved += more

    payload = {
        "facets_version": facets.FACETS_VERSION,
        "vocabulary_versions": facets.vocabulary_versions(facets_dir),
        "classification_state": "unresolved",
        "industry": industry,
        "business_functions": functions,
        "use_case_types": use_cases,
    }
    # Never computed locally: facets.py owns what "resolved" means, and it needs
    # BOTH a supported non-sentinel industry AND one supported function or use
    # case. Recomputing that rule here would let the two drift.
    payload["classification_state"] = facets.decide_classification_state(
        payload, facets_dir)
    if unresolved:
        payload["unresolved"] = sorted(
            unresolved, key=lambda u: (u["axis"], u["state"], u["detail"]))

    return FacetAssignment(
        candidate_key=key, applicable=True, case_facets=payload,
        reason="assigned from the committed vocabularies",
        gated=gated, report_only=report_only)


def assign_all(extraction, classifications, *, facets_dir=None):
    """Assign for a whole batch. Sorted by candidate_key; input order irrelevant."""
    by_key = {c.candidate_key: c for c in classifications}
    out = []
    for candidate in getattr(extraction, "candidates", ()) or ():
        classification = by_key.get(candidate.candidate_key)
        if classification is None:
            raise FacetAssignError("candidate %s has no classification"
                                   % candidate.candidate_key)
        out.append(assign(candidate, classification, facets_dir=facets_dir))
    return tuple(sorted(out, key=lambda a: a.candidate_key))
