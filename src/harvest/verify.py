#!/usr/bin/env python3
"""verify.py — the four scores and the accept/reject decision (S4-4).

`policy.v1.json` is the authority for every NUMBER: the four weights, the four
thresholds, the freshness half-life. Nothing here restates one as a Python
constant, so tuning the policy tunes the behaviour.

What the committed configuration does NOT specify is the SHAPE of each score —
how a title and a summary become a relevance number. That shape is defined here,
once, and every constant it needs is named, bounded and documented below. It is
recorded as an S4-4 design decision in docs/harvest/TODO.md rather than buried,
because a future reader must be able to find it and disagree with it.

Four rules run through everything:

  * SCORE ONLY WHAT IS KNOWN. A candidate with no publication date gets
    `freshness_score: null`, not 0.0 — zero would assert the item is old. The
    composite renormalizes over the dimensions that could be scored, so an
    unknown never silently becomes a penalty.
  * ONE MATCHER, NOT TWO. The category relevance lists are term lists exactly
    like the precedence keywords, so they go through classify's committed
    whole-token matcher (S4-3A). A second matching semantics here would drift
    from the first.
  * NOTHING IS FETCHED, SO NOTHING IS CLAIMED. Every verdict carries
    access_status "not_checked", http_status None, verification_status
    "unverified" and content_hash None. Those are the honest no-enrichment
    values; a fetch is Stage 6.
  * A REJECTION IS A FINDING, NOT A DELETION. A rejected candidate keeps its
    scores, its reason and the detail naming the exact rule and number. Nothing
    is written to disk — the per-cell rejection log is a Stage 5 artifact.

Not here: classification (S4-3 decided the cell and this never changes it),
facet assignment, record construction, cross-topic ownership, the pool, and any
form of I/O beyond reading the committed config.
"""
import dataclasses
import datetime
import json
import os

from . import classify as cl

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POLICY_PATH = os.path.join(ROOT, "config", "harvest", "policy.v1.json")
TOPICS_DIR = os.path.join(ROOT, "config", "harvest", "topics")

# The authorized evidence fields, identical to classify's. Scoring sees exactly
# what classification saw — no body, no lane, no ownership.
SCORED_FIELDS = cl.EVIDENCE_FIELDS

# --- score-shape constants (NOT committed config; see the module docstring) ---
# How many distinct matching terms saturate a component. Three is enough to
# separate "mentioned once in passing" from "this is what the piece is about",
# and small enough that a short title can reach it.
SATURATION = 3
# Within relevance, how much the category's own `require_any` vocabulary counts
# against its `boost` vocabulary. Required terms define the category; boost terms
# only sharpen it.
#
# Every constant in this block is deliberately chosen NOT to equal any number in
# policy.v1.json. A shape constant that happened to equal a weight or a threshold
# would be unreadable — nobody could tell whether it was the boost share or
# min_quality restated — and a test asserts no policy number appears here.
REQUIRED_SHARE, BOOST_SHARE = 0.68, 0.32
# Within quality, what each observable piece of evidence is worth. These sum to
# 1.0 and are the only things S4-4 can observe without fetching.
QUALITY_PARTS = (("title", 0.22), ("summary", 0.34),
                 ("publisher", 0.22), ("published_at", 0.22))
# A summary this long or longer counts as a full summary rather than a stub.
SUBSTANTIAL_SUMMARY = 200
# Corroboration: each additional independent source beyond the first adds this
# much quality, capped. Two sources reporting the same page is real evidence.
CORROBORATION_STEP, CORROBORATION_CAP = 0.08, 0.24
# Scores are rounded so two runs cannot differ in float noise.
PRECISION = 4

# Honest no-enrichment values. Stage 4 fetches nothing, so it claims nothing.
NOT_CHECKED = "not_checked"
UNVERIFIED = "unverified"

_CACHE = {}


class VerifyError(Exception):
    """A contract violation this module refuses to paper over."""


# --------------------------------------------------------------------- config
def load_policy(path=None):
    resolved = path or POLICY_PATH
    key = ("policy", resolved)
    if key not in _CACHE:
        try:
            with open(resolved, "r", encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, ValueError) as exc:
            raise VerifyError("cannot read %s (%s)" % (resolved, exc))
        if "scoring" not in document:
            raise VerifyError("%s carries no scoring block" % resolved)
        _CACHE[key] = document
    return _CACHE[key]


def load_categories(topics_dir=None):
    """(topic_slug, category_slug) -> the committed category object."""
    resolved = topics_dir or TOPICS_DIR
    key = ("categories", resolved)
    if key not in _CACHE:
        import glob
        out = {}
        for path in sorted(glob.glob(os.path.join(resolved, "*.json"))):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    document = json.load(handle)
            except (OSError, ValueError) as exc:
                raise VerifyError("cannot read %s (%s)" % (path, exc))
            topic = document.get("topic_slug")
            for category in document.get("categories") or ():
                out[(topic, category.get("category_slug"))] = category
        if not out:
            raise VerifyError("no categories found under %s" % resolved)
        _CACHE[key] = out
    return _CACHE[key]


def clear_caches():
    _CACHE.clear()


def thresholds_for(classification, policy=None):
    """The acceptance thresholds for a candidate's CLASSIFIED cell.

    Selection is by the classified (topic, category), never the discovery cell:
    what a candidate must clear depends on where it actually landed. The
    committed policy declares one set for every cell; a per-cell override under
    `scoring.thresholds_by_cell` is honoured if one is ever added, so introducing
    it needs no code change here.
    """
    document = policy or load_policy()
    scoring = document["scoring"]
    cell = "%s__%s" % (classification.topic_slug, classification.category_slug)
    overrides = scoring.get("thresholds_by_cell") or {}
    return dict(scoring["thresholds"], **(overrides.get(cell) or {}))


# ------------------------------------------------------------------- outputs
@dataclasses.dataclass(frozen=True, slots=True)
class ScoreEvidence:
    """Why a score came out as it did, naming the input that moved it."""
    dimension: str
    signal: str
    matched: str = ""

    @property
    def order_key(self):
        return (self.dimension, self.signal, self.matched)

    def payload(self):
        return {"dimension": self.dimension, "signal": self.signal,
                "matched": self.matched}


@dataclasses.dataclass(frozen=True, slots=True)
class Scores:
    """The four committed scores plus the weighted composite.

    `freshness` is None when no usable date exists. The composite renormalizes
    over the dimensions that could be scored, so an unknown is not a penalty.
    """
    relevance: float = 0.0
    quality: float = 0.0
    audience_fit: float = 0.0
    freshness: float = None
    composite: float = 0.0
    excluded: bool = False
    developer_only: bool = False
    required_hits: int = 0
    evidence: tuple = ()
    # Configured terms that cannot participate in token matching, reported so
    # they are visible rather than silently inert. See _hits() and CF-8.
    unusable_terms: tuple = ()

    def payload(self):
        return {"relevance": self.relevance, "quality": self.quality,
                "audience_fit": self.audience_fit, "freshness": self.freshness,
                "composite": self.composite}


@dataclasses.dataclass(frozen=True, slots=True)
class Verdict:
    """Accepted or not, with the exact rule and number that decided it."""
    candidate_key: str
    accepted: bool
    scores: Scores
    rejection_reason: str = None
    detail: str = ""
    ambiguous: bool = False
    rule_id: str = ""
    topic_slug: str = ""
    category_slug: str = ""
    # Honest no-enrichment state. Nothing was fetched, so nothing is claimed.
    access_status: str = NOT_CHECKED
    http_status: int = None
    verification_status: str = UNVERIFIED
    verification_evidence: str = None
    content_hash: str = None


# ------------------------------------------------------------------ matching
def _matches(term, text):
    """One term against one field, via classify's committed token matcher.

    Deliberately reusing the sibling module's helpers rather than compiling a
    second tokenizer: the category relevance lists are term lists exactly like
    the precedence keywords, and two matchers would drift. Same-package private
    reuse follows the shipped precedent of adapters/base.py calling
    `cache._clock()`.
    """
    if not text:
        return None
    tokens = cl._tokenize(text)
    span = cl._find_term(term, tokens)
    if span is None:
        return None
    first, last = span
    return text[tokens[first][1]:tokens[last][2]]


def _hits(terms, fields, dimension, signal):
    """Distinct matching terms, with one quoted evidence each. Config order.

    A term with no matchable token — `%` and `$` are both configured as boost
    terms — cannot participate in token matching at all. It is skipped
    deterministically and REPORTED on the result rather than dropped in silence
    or allowed to abort the batch. Both are already covered by regex patterns in
    `precedence.v1.json`, so nothing is actually lost. See CF-8.
    """
    found, evidence, unusable = 0, [], []
    for term in terms or ():
        try:
            cl.compile_term(term)
        except cl.ClassifyError:
            unusable.append(term)
            continue
        for name, text in fields:
            matched = _matches(term, text)
            if matched is not None:
                found += 1
                evidence.append(ScoreEvidence(dimension=dimension, signal=signal,
                                              matched=matched))
                break
    return found, evidence, tuple(unusable)


def _fields(extracted):
    return tuple((name, getattr(extracted, name, None) or "")
                 for name in SCORED_FIELDS)


def _round(value):
    return None if value is None else round(float(value), PRECISION)


# -------------------------------------------------------------------- clocks
def _parse(stamp):
    if not stamp:
        return None
    try:
        return datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc)
    except (TypeError, ValueError):
        return None


def _now(clock):
    """The evaluation instant. Injected for tests; HARVEST_CLOCK_UTC otherwise."""
    if clock is not None:
        return _parse(clock() if callable(clock) else clock)
    pinned = os.environ.get("HARVEST_CLOCK_UTC")
    if pinned:
        return _parse(pinned)
    return datetime.datetime.now(datetime.timezone.utc)


# -------------------------------------------------------------------- scoring
def score(extracted, classification, *, policy=None, categories=None, clock=None):
    """The four committed scores for one classified candidate.

    Inputs are the normalized metadata, the classification, the committed
    category vocabulary for the CLASSIFIED cell, and an injected clock. No lane,
    no request key, no ownership, no arrival order.
    """
    document = policy or load_policy()
    scoring = document["scoring"]
    weights = scoring["weights"]
    catalog = categories if categories is not None else load_categories()
    cell = (classification.topic_slug, classification.category_slug)
    category = catalog.get(cell) or {}
    rules = category.get("relevance") or {}
    fields = _fields(extracted)
    evidence = []

    # ---- relevance: the classified category's own vocabulary
    excluded, exclude_evidence, bad_x = _hits(rules.get("exclude"), fields,
                                              "relevance", "category_exclusion")
    required, required_evidence, bad_r = _hits(rules.get("require_any"), fields,
                                               "relevance", "require_any")
    boosted, boost_evidence, bad_b = _hits(rules.get("boost"), fields,
                                           "relevance", "boost")
    unusable = tuple(sorted(set(bad_x + bad_r + bad_b)))
    if excluded:
        relevance = 0.0
        evidence.extend(exclude_evidence)
    elif rules.get("require_any") and not required:
        relevance = 0.0
    else:
        relevance = (REQUIRED_SHARE * min(required, SATURATION) / SATURATION +
                     BOOST_SHARE * min(boosted, SATURATION) / SATURATION)
        # A category with no configured vocabulary cannot discriminate; a
        # candidate there is neither rewarded nor punished for it.
        if not rules.get("require_any") and not rules.get("boost"):
            relevance = REQUIRED_SHARE
        evidence.extend(required_evidence + boost_evidence)

    # ---- quality: observable evidence completeness plus corroboration
    quality = 0.0
    for name, share in QUALITY_PARTS:
        value = getattr(extracted, name, None)
        if not value:
            continue
        if name == "summary" and len(value) < SUBSTANTIAL_SUMMARY:
            quality += share / 2.0          # a stub is evidence, but not much
            evidence.append(ScoreEvidence("quality", "summary_stub",
                                          value[:60]))
            continue
        quality += share
        evidence.append(ScoreEvidence("quality", "has_%s" % name, str(value)[:60]))
    sources = len(getattr(extracted, "source_ids", ()) or ())
    if sources > 1:
        bonus = min((sources - 1) * CORROBORATION_STEP, CORROBORATION_CAP)
        quality += bonus
        evidence.append(ScoreEvidence("quality", "corroborated",
                                      "%d independent sources" % sources))
    quality = min(quality, 1.0)

    # ---- audience_fit: the category's own exclusion, and only that
    developer_only = False
    if excluded:
        fired, _ = cl.signals_for(extracted)
        developer_only = bool(fired.get("is_developer_tool"))
        audience_fit = 0.0
        evidence.append(ScoreEvidence(
            "audience_fit",
            "developer_only" if developer_only else "category_exclusion",
            exclude_evidence[0].matched if exclude_evidence else ""))
    else:
        audience_fit = 1.0

    # ---- freshness: exponential decay over the committed half-life
    published = _parse(getattr(extracted, "published_at", None))
    now = _now(clock)
    freshness = None
    if published is not None and now is not None:
        half_life = float(scoring.get("freshness_half_life_days") or 0) or None
        if half_life:
            age_days = max((now - published).total_seconds() / 86400.0, 0.0)
            freshness = min(max(0.5 ** (age_days / half_life), 0.0), 1.0)
            evidence.append(ScoreEvidence("freshness", "age_days",
                                          "%.4f" % age_days))

    # ---- composite: the committed weights, renormalized over what is known
    parts = [("relevance", relevance), ("quality", quality),
             ("audience_fit", audience_fit)]
    if freshness is not None:
        parts.append(("freshness", freshness))
    total_weight = sum(float(weights[name]) for name, _ in parts)
    if total_weight <= 0:
        raise VerifyError("scoring weights sum to zero; nothing can be scored")
    composite = sum(float(weights[name]) * value for name, value in parts)
    composite /= total_weight

    return Scores(
        relevance=_round(relevance), quality=_round(quality),
        audience_fit=_round(audience_fit), freshness=_round(freshness),
        composite=_round(composite), excluded=bool(excluded),
        developer_only=developer_only, required_hits=required,
        evidence=tuple(sorted(evidence, key=lambda e: e.order_key)),
        unusable_terms=unusable)


# ------------------------------------------------------------------ decision
def decide(extracted, classification, scores, *, policy=None, categories=None):
    """Accept or reject, naming the exact rule and number that decided it.

    Gates run in a fixed order, most specific reason first. The verdict never
    changes the classification, never writes a file, and never claims a fetch.
    """
    document = policy or load_policy()
    limits = thresholds_for(classification, document)
    catalog = categories if categories is not None else load_categories()
    rules = ((catalog.get((classification.topic_slug,
                           classification.category_slug)) or {})
             .get("relevance") or {})
    key = getattr(extracted, "candidate_key", "")

    def verdict(accepted, reason=None, detail=""):
        return Verdict(
            candidate_key=key, accepted=accepted, scores=scores,
            rejection_reason=reason, detail=detail,
            ambiguous=classification.ambiguous, rule_id=classification.rule_id,
            topic_slug=classification.topic_slug,
            category_slug=classification.category_slug)

    if scores.excluded:
        return verdict(
            False,
            "developer_only_audience" if scores.developer_only
            else "category_exclusion_applied",
            "the classified category excludes this candidate")

    if not (extracted.title or extracted.summary):
        # Nothing to judge. Reported as insufficient evidence rather than scored
        # to zero and dressed up as a quality finding.
        return verdict(False, "insufficient_evidence",
                       "neither title nor summary is present")

    if rules.get("require_any") and not scores.required_hits:
        return verdict(False, "off_topic",
                       "no required term for %s__%s matched"
                       % (classification.topic_slug, classification.category_slug))

    if scores.relevance < limits["min_relevance"]:
        return verdict(False, "below_relevance_threshold",
                       "relevance %.4f < min_relevance %.4f"
                       % (scores.relevance, limits["min_relevance"]))

    if scores.quality < limits["min_quality"]:
        return verdict(False, "below_quality_threshold",
                       "quality %.4f < min_quality %.4f"
                       % (scores.quality, limits["min_quality"]))

    if scores.audience_fit < limits["min_audience_fit"]:
        return verdict(False, "insufficient_evidence",
                       "audience_fit %.4f < min_audience_fit %.4f"
                       % (scores.audience_fit, limits["min_audience_fit"]))

    if scores.composite < limits["accept_composite"]:
        # The committed rejection vocabulary has no below_composite_threshold
        # value, so the closest honest one is used and the detail names the
        # actual rule and number. Recorded as CF-7.
        return verdict(False, "insufficient_evidence",
                       "composite %.4f < accept_composite %.4f"
                       % (scores.composite, limits["accept_composite"]))

    return verdict(True, None, "composite %.4f >= accept_composite %.4f"
                   % (scores.composite, limits["accept_composite"]))


def verify(extracted, classification, *, policy=None, categories=None, clock=None):
    """score() then decide(), the ordinary path."""
    scores = score(extracted, classification, policy=policy,
                   categories=categories, clock=clock)
    return decide(extracted, classification, scores, policy=policy,
                  categories=categories)


def verify_all(extraction, classifications, *, policy=None, categories=None,
               clock=None):
    """Verify a whole batch. Sorted by candidate_key; input order is irrelevant."""
    by_key = {c.candidate_key: c for c in classifications}
    out = []
    for candidate in getattr(extraction, "candidates", ()) or ():
        classification = by_key.get(candidate.candidate_key)
        if classification is None:
            raise VerifyError("candidate %s has no classification"
                              % candidate.candidate_key)
        out.append(verify(candidate, classification, policy=policy,
                          categories=categories, clock=clock))
    return tuple(sorted(out, key=lambda v: v.candidate_key))
