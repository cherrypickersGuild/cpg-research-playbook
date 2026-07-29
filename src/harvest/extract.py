#!/usr/bin/env python3
"""extract.py — metadata normalization (S4-2). NOT body extraction.

The word "extraction" means two different things in this repository, and
conflating them would be a real defect rather than a naming quibble:

  * `pool.acquire_extraction` and `candidate_pool.v1.json`'s
    `designated_extraction_owner_lane_id` mean parsing a FETCHED TARGET BODY —
    "one extraction owner per accepted response body — no double parsing". That
    is Stage 6, and until it happens the field's committed meaning of null is
    "extraction has not occurred".
  * THIS module normalizes the metadata a source already published about a
    candidate. It reads no body, issues no request and touches no ownership
    field, so it must never set either designation.

What it does: one `CandidateGroup` in, one `ExtractedCandidate` out. Display
values come from S4-1's deterministic authority-then-content ordering; dates go
through the committed `records.to_iso8601_utc`; identity comes from the
canonicalization S4-1 already performed and is never recomputed here.

Three rules inherited from `records.py` and kept literally:

  * Unknown is null, never a guess and never the string "unknown".
  * A field nobody supplied is null, and the fact is REPORTED — a normalization
    issue is surfaced on the result rather than swallowed.
  * A field that was never checked says so by being absent. `ExtractedCandidate`
    has no `access_status`, `http_status`, `content_hash`, `updated_at`,
    `last_checked_at` or `url_aliases`, because every one of them needs a fetch.

Nothing here classifies, scores, verifies, assigns a facet, deduplicates or
builds a record. `canonical_url` equals `identity_url` because no redirect or
canonical tag has been observed — observing one requires Stage 6.
"""
import dataclasses
import re

from . import dedupe as dd
from . import records
from .urlkey import content_id as _content_id

# Single-line display fields where a pretty-printed feed routinely injects
# newlines and indentation inside the element. Collapsing runs of whitespace is
# meaning-preserving for a title or a publisher name; `summary` is deliberately
# excluded, because its internal structure is content.
_WS = re.compile(r"\s+")
_COLLAPSE_FIELDS = ("title", "publisher")

# The committed default from records.make_full_record. Stage 4 does NOT derive a
# more specific content_type: no committed config authorizes a derivation rule,
# and a derived value would be a guess dressed as a finding. A test pins this to
# the builder's own default so the two cannot drift apart.
DEFAULT_CONTENT_TYPE = "article"

# Fields a source can contribute, in the order issues are reported.
NORMALIZED_FIELDS = ("title", "summary", "publisher", "published_at")

# Issue kinds. Every one is reported, never inferred away.
MISSING = "missing"
UNKNOWN_SENTINEL = "unknown_sentinel"
UNPARSEABLE_DATE = "unparseable_date"
CONFLICTING_VALUES = "conflicting_values"


class ExtractError(Exception):
    """A contract violation this module refuses to paper over."""


def _collapse(value):
    return _WS.sub(" ", value).strip() if isinstance(value, str) else value


# ---------------------------------------------------------------------- issue
@dataclasses.dataclass(frozen=True, slots=True)
class NormalizationIssue:
    """Something a reviewer should know. Reported, never silently absorbed."""
    candidate_key: str
    field: str
    kind: str
    detail: str = ""

    @property
    def order_key(self):
        return (self.candidate_key, self.field, self.kind, self.detail)


# ------------------------------------------------------------------ candidate
@dataclasses.dataclass(frozen=True, slots=True)
class ExtractedCandidate:
    """One canonical candidate's normalized metadata.

    Deliberately missing, because each requires a fetch that Stage 4 does not
    perform: `access_status`, `http_status`, `content_hash`, `updated_at`,
    `last_checked_at`, `url_aliases`. Their absence is asserted, so a later stage
    cannot quietly start claiming them here.
    """
    candidate_key: str
    target_url: str                 # the display raw URL, per S4-1's authority order
    identity_url: str               # from S4-1's canonicalization; never recomputed
    canonical_url: str              # == identity_url until Stage 6 observes otherwise
    content_id: str
    title: str = None
    summary: str = None
    publisher: str = None
    published_at: str = None        # ISO-8601 UTC, or None — never invented
    author: str = None              # no adapter supplies one; null, not guessed
    language: str = None            # likewise
    content_type: str = DEFAULT_CONTENT_TYPE
    contexts: tuple = ()            # every discovery (topic_slug, category_slug)
    source_ids: tuple = ()
    lane_ids: tuple = ()
    source_request_keys: tuple = ()
    provenance_raw: dict = None     # S4-1's retention payload, unmodified
    issues: tuple = ()

    @property
    def observation_count(self):
        return len((self.provenance_raw or {}).get("observations", ()))

    def variants(self, field):
        """Every alternative value S4-1 retained. Read-only evidence."""
        raw = (self.provenance_raw or {}).get("field_variants", {})
        return tuple((value, tuple(sources)) for value, sources in raw.get(field, ()))


# --------------------------------------------------------------------- result
@dataclasses.dataclass(frozen=True, slots=True)
class ExtractionResult:
    """The deterministic outcome of normalizing one `DedupeResult`.

    `unusable` is S4-1's own collection, passed through untouched: a candidate
    whose target URL could not be canonicalized never became a group, so it
    never becomes an ExtractedCandidate either — and it stays separately
    visible rather than disappearing between the two stages.
    """
    candidates: tuple                 # sorted by candidate_key
    unusable: tuple = ()
    issues: tuple = ()                # every candidate's issues, flattened+sorted

    @property
    def candidate_count(self):
        return len(self.candidates)

    def by_key(self, candidate_key):
        for candidate in self.candidates:
            if candidate.candidate_key == candidate_key:
                return candidate
        return None

    def issues_for(self, candidate_key):
        return tuple(i for i in self.issues if i.candidate_key == candidate_key)


# ---------------------------------------------------------------------- entry
def normalize(group):
    """Normalize one `CandidateGroup` into one `ExtractedCandidate`.

    The canonicalization parameters the proposed plan carried are gone: S4-1 has
    already canonicalized, and `CandidateGroup.identity_url` IS that result.
    Recomputing it here would be a second identity path that could disagree with
    the first.
    """
    if not isinstance(group, dd.CandidateGroup):
        raise ExtractError(
            "normalize expects a dedupe.CandidateGroup, got %r"
            % type(group).__name__)
    if not group.observations:
        raise ExtractError(
            "candidate %s has no observations; an empty group cannot be "
            "normalized" % group.candidate_key)

    key = group.candidate_key
    issues = []

    def clean(field):
        """Display value -> normalized value, recording what happened to it."""
        raw = group.display(field)
        if raw is None:
            issues.append(NormalizationIssue(key, field, MISSING,
                                             "no source supplied a value"))
            return None
        if isinstance(raw, str) and raw.strip().casefold() == "unknown":
            # The legacy sentinel. records.null_if_unknown maps it to null; it is
            # reported so "we were told nothing" is distinguishable from "we were
            # told the word unknown".
            issues.append(NormalizationIssue(key, field, UNKNOWN_SENTINEL, raw))
            return None
        value = records.null_if_unknown(raw)
        if value is None:
            issues.append(NormalizationIssue(key, field, MISSING,
                                             "value was blank after trimming"))
            return None
        return _collapse(value) if field in _COLLAPSE_FIELDS else value

    title = clean("title")
    summary = clean("summary")
    publisher = clean("publisher")

    raw_date = clean("published_at")
    published_at = records.to_iso8601_utc(raw_date) if raw_date else None
    if raw_date and published_at is None:
        # A date we cannot parse yields null rather than a fabrication: inventing
        # one would make the freshness score a fiction. The original is kept on
        # the issue and remains in provenance.
        issues.append(NormalizationIssue(key, "published_at", UNPARSEABLE_DATE,
                                         raw_date))

    # Conflicts are informational, never resolved here. The complete alternative
    # values stay in the retention payload; this only makes them findable.
    for field in dd.PAYLOAD_FIELDS:
        if group.has_conflict(field):
            issues.append(NormalizationIssue(
                key, field, CONFLICTING_VALUES,
                "%d distinct values" % len(group.variants(field))))

    return ExtractedCandidate(
        candidate_key=key,
        target_url=group.display("target_url"),
        identity_url=group.identity_url,
        # No redirect and no canonical tag has been observed, and observing one
        # needs a fetch. Starting equal to identity is what record.v1.json
        # specifies for a URL nothing has verified yet.
        canonical_url=group.identity_url,
        content_id=_content_id(group.identity_url),
        title=title,
        summary=summary,
        publisher=publisher,
        published_at=published_at,
        author=None,
        language=None,
        content_type=DEFAULT_CONTENT_TYPE,
        contexts=group.contexts(),
        source_ids=group.source_ids(),
        lane_ids=group.lane_ids(),
        source_request_keys=group.source_request_keys(),
        provenance_raw=group.retention_payload(),
        issues=tuple(sorted(issues, key=lambda i: i.order_key)),
    )


def normalize_all(result):
    """Normalize a whole `DedupeResult`. One candidate per valid group.

    Output depends only on content: `DedupeResult.groups` is already sorted by
    candidate_key, and every value inside a candidate is derived from S4-1's
    total order, so presentation order cannot change a byte.
    """
    if not isinstance(result, dd.DedupeResult):
        raise ExtractError(
            "normalize_all expects a dedupe.DedupeResult, got %r"
            % type(result).__name__)

    candidates = tuple(sorted((normalize(g) for g in result.groups),
                              key=lambda c: c.candidate_key))
    issues = tuple(sorted((i for c in candidates for i in c.issues),
                          key=lambda i: i.order_key))
    return ExtractionResult(candidates=candidates,
                            unusable=tuple(result.unusable),
                            issues=issues)
