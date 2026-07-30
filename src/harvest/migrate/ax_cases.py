"""ax_cases.py — the in-memory AX case mapping (Stage 7, checkpoint S7-3).

One already-loaded AX registry document goes in; accepted `record.v1.json`
records and rejection rows come out. **Nothing is read from disk except the
committed CONFIGURATION the committed owners already read** (the canonicalization
policy and the facet vocabularies), and **nothing is written at all** — no path,
no bundle, no manifest, no serialization. Those belong to S7-4 and S7-5.

The plan's §5 mapping table is implemented literally, and the things it refuses
to do are refused here structurally rather than by intention:

  * **No clock.** `harvest_run_id` and `migrated_at` are required keyword inputs,
    and `discovered_at` is always passed explicitly, so `make_full_record` can
    never fall back to `records.utcnow()`. A test asserts this module names no
    clock at all.
  * **No re-judging.** `classify.py` and `verify.py` are not imported. The
    classification is the one fixed migration object D7-E approves, and all four
    scores are null because nothing was scored.
  * **No evidence that was never observed.** D7-D: `access_status` is
    `not_checked`, `http_status`, `content_hash` and `last_checked_at` are null,
    `canonical_url == identity_url`, `url_aliases` is empty, and the legacy word
    `verified` NEVER becomes `fetched` — it survives verbatim in
    `provenance.raw`.
  * **No invented identity.** Identity is URL-derived through the committed
    `urlkey` helpers only. `case_id` is not unique in this corpus (126 distinct
    over 231) and is retained as a label, never as a key.
  * **No mutation of the source.** Every retained mutable value is deep-copied,
    in both directions: mapping cannot change the registry, and changing the
    registry afterwards cannot change a finished record.

The one thing this module does own that the table does not spell out is the
composition of `summary` and `curation_reason` from the legacy fields. Both use
one fixed template — labelled parts joined by `" | "`, a part omitted entirely
when its source is blank or `"unknown"`, no conditional punctuation, and `None`
when every part is missing.
"""
import copy
import dataclasses
import re

from .. import records as records_mod
from .. import schema as schema_mod
from .. import urlkey
from .. import facets as facets_mod
from .. import aliases as aliases_mod
from . import base

# The committed AX registry contract this mapping was written against.
AX_SCHEMA_VERSION = 1

# Named once, and it is the protected registry.
SOURCE_ID = "ax_case_harvest_registry"
SOURCE_ADAPTER = "migration"
MIGRATION_ADAPTER = "ax_cases"

# D7-E: the destination is fixed by the source, not by discovery classification.
TOPIC_SLUG = "cases"
CATEGORY_SLUG = "case-studies"
CELL_ID = "cases__case-studies"

CLASSIFICATION_RULE_ID = "migration.ax_case_registry.case_study"
CLASSIFICATION_RATIONALE = (
    "Assigned by migration: the protected AX case registry is an already-curated "
    "case-study corpus, so the destination cell is fixed by the source, not by "
    "discovery classification.")
CLASSIFICATION_EVIDENCE_SIGNAL = "legacy_registry"

# D7-G: honest constants for what the legacy schema simply does not record.
CONTENT_TYPE = "other"
ACCESS_STATUS = "not_checked"
VERIFICATION_SNIPPET = "snippet_only"
VERIFICATION_UNVERIFIED = "unverified"

REJECTION_REASON = "ambiguous_legacy_url"

# The 12 legacy fields surfaced as `domain_fields`, in committed order. Every one
# is carried even when it is null, blank or empty: this block is a declared VIEW
# of the legacy row, and a field vanishing when it is empty would make the view's
# shape depend on the data.
DOMAIN_FIELDS = ("company", "industry", "workflow_before", "workflow_after",
                 "ai_system_or_tool", "measurable_kpi", "kpi_value",
                 "evidence_quote", "transformation_date", "confidence",
                 "corroboration_count", "conflicting_evidence_log")

# Every field the mapping reads, and therefore every field a row must carry.
REQUIRED_CASE_FIELDS = tuple(sorted(set(DOMAIN_FIELDS) | {
    "case_id", "case_key", "source_url", "source_title", "source_domain",
    "publication_date", "verification_status", "discovery"}))
REQUIRED_DISCOVERY_FIELDS = ("first_seen_at", "found_via")

# Deterministic templates. A part whose source is blank or "unknown" is OMITTED —
# never rendered as the word "unknown", which would state something false.
SUMMARY_PARTS = (("workflow_before", "Before"),
                 ("workflow_after", "After"),
                 ("ai_system_or_tool", "AI system"))
CURATION_PARTS = (("measurable_kpi", "KPI"),
                  ("kpi_value", "Reported"),
                  ("evidence_quote", "Evidence"))
TEMPLATE_JOIN = " | "

# D7-H review decisions, supplied in memory by the caller. S7-3 reads no file.
REVIEW_DECISIONS = ("admit", "reject")

_UTC_SECOND = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class AxMigrationError(ValueError):
    """A registry, row or review decision this mapping refuses to paper over."""


@dataclasses.dataclass(frozen=True)
class MappingResult:
    """Exactly what one mapping produced. Immutable at the boundary."""
    accepted: tuple
    rejected: tuple


# ----------------------------------------------------------------- validation
def _require(condition, message):
    if not condition:
        raise AxMigrationError(message)


def _text(value):
    """A trimmed legacy string, or None for blank / missing / "unknown"."""
    cleaned = records_mod.null_if_unknown(value)
    if not isinstance(cleaned, str):
        return None
    cleaned = cleaned.strip()
    return cleaned or None


def validate_registry(document):
    """Refuse anything that is not the committed AX registry shape, by name."""
    _require(isinstance(document, dict),
             "the AX registry must be a JSON object, got %s" % type(document).__name__)
    _require("schema_version" in document,
             "the AX registry is missing the top-level key 'schema_version'")
    _require(document["schema_version"] == AX_SCHEMA_VERSION,
             "the AX registry declares schema_version %r; this mapping is written "
             "against %r and refuses to guess at the difference"
             % (document["schema_version"], AX_SCHEMA_VERSION))
    _require("cases" in document, "the AX registry is missing the top-level key 'cases'")
    _require(isinstance(document["cases"], list),
             "the AX registry `cases` must be an array, got %s"
             % type(document["cases"]).__name__)

    for index, case in enumerate(document["cases"]):
        where = "cases[%d]" % index
        _require(isinstance(case, dict),
                 "%s must be an object, got %s" % (where, type(case).__name__))
        for field in REQUIRED_CASE_FIELDS:
            _require(field in case, "%s is missing the required field %r" % (where, field))
        _require(isinstance(case["conflicting_evidence_log"], list),
                 "%s.conflicting_evidence_log must be an array" % where)
        for field in ("case_id", "case_key", "source_url"):
            _require(isinstance(case[field], str) and case[field].strip(),
                     "%s.%s must be a non-empty string" % (where, field))
        discovery = case["discovery"]
        _require(isinstance(discovery, dict),
                 "%s.discovery must be an object, got %s"
                 % (where, type(discovery).__name__))
        for field in REQUIRED_DISCOVERY_FIELDS:
            _require(field in discovery, "%s.discovery is missing %r" % (where, field))
        _require(records_mod.to_iso8601_utc(discovery["first_seen_at"]) is not None,
                 "%s.discovery.first_seen_at %r is not a parseable date; a record "
                 "cannot be given an invented discovery instant"
                 % (where, discovery["first_seen_at"]))
        _require(isinstance(discovery["found_via"], list),
                 "%s.discovery.found_via must be an array" % where)
        for position, item in enumerate(discovery["found_via"]):
            _require(isinstance(item, dict),
                     "%s.discovery.found_via[%d] must be an object, got %s"
                     % (where, position, type(item).__name__))
            extra = sorted(set(item) - {"hit_id", "platform"})
            _require(not extra,
                     "%s.discovery.found_via[%d] carries unrecognised key(s) %s — "
                     "structural drift that would make the approved mapping ambiguous"
                     % (where, position, ", ".join(repr(k) for k in extra)))
        # The guard needs an absolute URL to examine; a missing one is malformed
        # input, not a suspicious URL.
        try:
            base.suspicious_url_match(case["source_url"])
        except base.MigrationInputError as exc:
            raise AxMigrationError("%s.source_url is unusable: %s" % (where, exc))
    return True


def _validate_clock(harvest_run_id, migrated_at):
    _require(isinstance(harvest_run_id, str) and harvest_run_id.strip(),
             "harvest_run_id is required and must be a non-empty string; this "
             "mapping never reads a clock or invents a run id")
    _require(isinstance(migrated_at, str) and _UTC_SECOND.match(migrated_at or ""),
             "migrated_at must be UTC ISO-8601 at second precision "
             "(YYYY-MM-DDTHH:MM:SSZ), got %r" % (migrated_at,))


def _validate_reviews(reviews, cases):
    """Normalize the in-memory review decisions, refusing anything ambiguous."""
    if reviews is None:
        return {}
    _require(isinstance(reviews, (list, tuple)),
             "reviewed decisions must be a list, got %s" % type(reviews).__name__)
    by_case = {case["case_id"]: case for case in cases}
    normalized = {}
    for index, row in enumerate(reviews):
        where = "reviewed[%d]" % index
        _require(isinstance(row, dict), "%s must be an object" % where)
        extra = sorted(set(row) - {"case_id", "legacy_source_url", "decision", "note"})
        _require(not extra, "%s carries unrecognised key(s) %s"
                 % (where, ", ".join(repr(k) for k in extra)))
        for field in ("case_id", "legacy_source_url", "decision"):
            _require(field in row, "%s is missing %r" % (where, field))
        case_id = row["case_id"]
        _require(case_id in by_case,
                 "%s reviews %r, which is not a case in this registry" % (where, case_id))
        _require(case_id not in normalized,
                 "%s is a second decision for %r; one case, one decision"
                 % (where, case_id))
        _require(row["decision"] in REVIEW_DECISIONS,
                 "%s decision %r is not one of %s"
                 % (where, row["decision"], ", ".join(REVIEW_DECISIONS)))
        _require(row["legacy_source_url"] == by_case[case_id]["source_url"],
                 "%s names a URL that is not %r's own source_url; a review is "
                 "against an exact raw URL, never a similar one" % (where, case_id))
        normalized[case_id] = row["decision"]
    return normalized


# ------------------------------------------------------------- text templates
def _compose(case, parts):
    rendered = []
    for field, label in parts:
        value = _text(case.get(field))
        if value is not None:
            rendered.append("%s: %s" % (label, value))
    return TEMPLATE_JOIN.join(rendered) if rendered else None


# ------------------------------------------------------------------- facets
def _unresolved(axis, state, term, detail):
    return {"axis": axis, "state": state, "term": term, "detail": detail}


def _axis_insufficient(axis, what):
    return _unresolved(
        axis, "insufficient_evidence", None,
        "The AX registry records no %s. Migration does not infer one from workflow "
        "text, tool names, KPI text or the company." % what)


def build_case_facets(case, facets_dir=None):
    """D7-F. Only the committed vocabularies and the reviewed legacy map."""
    legacy = _text(case.get("industry"))
    unresolved = []
    primary = None
    confidence = None
    evidence = []

    if legacy is None:
        unresolved.append(_unresolved(
            "industry", "insufficient_evidence", None,
            "The legacy row carries no industry value, so there is nothing to map. "
            "This is not an unmapped value: no value exists."))
    else:
        slug = facets_mod.lookup_legacy_industry(legacy, facets_dir)
        if slug is None:
            unresolved.append(_unresolved(
                "industry", "unmapped_legacy_value", legacy,
                "The legacy industry %r has no reviewed mapping in "
                "legacy_industry_map.v1.json. It is reported for review rather than "
                "guessed at." % legacy))
        else:
            candidate = [{"field": "legacy_field", "matched_term": legacy, "quote": legacy}]
            # The gate is applied EXACTLY where the committed contract applies it.
            # `facets.LEXICAL_SUPPORT_REQUIRED` names the slugs that slip in
            # without grounding (technology-software, cross-industry); for every
            # other slug the REVIEWED map is the authority, and demanding lexical
            # support as well would be stricter than the committed rule and would
            # withhold six reviewed mappings check_facets accepts.
            gated = ("industry", slug) in facets_mod.LEXICAL_SUPPORT_REQUIRED
            if not gated or facets_mod.evidence_supports("industry", slug,
                                                         candidate, facets_dir):
                primary = slug
                confidence = 1.0
                evidence = candidate
            else:
                # E27: reviewed, but the committed lexical-support gate refuses this
                # grounding. Asserting anyway would fail check_facets; calling it
                # unmapped would send a reviewer to fix a map that is already right.
                unresolved.append(_unresolved(
                    "industry", "insufficient_evidence", legacy,
                    "The legacy industry %r has the reviewed mapping %r, but the "
                    "committed lexical-support contract refuses that value as "
                    "evidence for %r, so the mapping is recorded here instead of "
                    "asserted." % (legacy, slug, slug)))

    unresolved.append(_axis_insufficient("business_function", "business function"))
    unresolved.append(_axis_insufficient("use_case_type", "use-case type"))

    payload = {
        "facets_version": facets_mod.FACETS_VERSION,
        "vocabulary_versions": facets_mod.vocabulary_versions(facets_dir),
        "classification_state": "unresolved",
        "industry": {"primary": primary, "secondary": [],
                     "confidence": confidence, "evidence": evidence},
        "business_functions": [],
        "use_case_types": [],
        "unresolved": unresolved,
    }
    # The committed owner decides the state; it is stored, never asserted.
    payload["classification_state"] = facets_mod.decide_classification_state(
        payload, facets_dir)
    return payload


# ------------------------------------------------------------------ one case
def _classification():
    return {
        "rule_id": CLASSIFICATION_RULE_ID,
        "rationale": CLASSIFICATION_RATIONALE,
        "evidence": [{"signal": CLASSIFICATION_EVIDENCE_SIGNAL, "matched": SOURCE_ID}],
        "competing_categories": [],
    }


def _assumptions(reviewed_admit):
    lines = [
        "The legacy `source_url` is treated as the case's own target page; the AX "
        "schema has no separate feed, index, search or citing URL.",
        "No HTTP request was made and no current accessibility claim is made: "
        "access_status is not_checked and http_status, content_hash and "
        "last_checked_at are null.",
        "The legacy verification vocabulary is retained verbatim in "
        "provenance.raw and is never promoted to `fetched`.",
        "Classification is the migration-specific assignment "
        "%s, not a discovery classification result." % CLASSIFICATION_RULE_ID,
    ]
    if reviewed_admit:
        lines.append(
            "The suspicious-URL guard refused this URL and a reviewer admitted it "
            "verbatim; the URL was not rewritten or repaired.")
    return lines


def _tags(case):
    values = []
    for field in ("industry", "ai_system_or_tool"):
        value = _text(case.get(field))
        if value is not None:
            values.append(value)
    return values           # make_full_record owns deduplication and ordering


def _canon_kwargs():
    policy = aliases_mod.load_canonicalization()
    return {"tracking_params": policy.get("tracking_params"),
            "domain_rules": policy.get("domain_rules")}


def map_case(case, *, harvest_run_id, migrated_at, reviewed_admit=False,
             facets_dir=None, canon_kwargs=None):
    """One legacy case -> one validated `record.v1.json` full record."""
    kwargs = canon_kwargs if canon_kwargs is not None else _canon_kwargs()
    target_url = case["source_url"]
    identity_url = urlkey.canonicalize_string(target_url, **kwargs)
    quote = _text(case.get("evidence_quote"))

    record = records_mod.make_full_record(
        record_id=urlkey.record_id(TOPIC_SLUG, identity_url),
        content_id=urlkey.content_id(identity_url),
        topic_slug=TOPIC_SLUG,
        category_slug=CATEGORY_SLUG,
        cell_id=CELL_ID,
        identity_url=identity_url,
        target_url=target_url,
        canonical_url=identity_url,
        source_url=None,
        harvest_run_id=harvest_run_id,
        source_id=SOURCE_ID,
        source_adapter=SOURCE_ADAPTER,
        source_tier=None,
        title=case.get("source_title"),
        summary=_compose(case, SUMMARY_PARTS),
        curation_reason=_compose(case, CURATION_PARTS),
        publisher=case.get("source_domain"),
        author=None,
        published_at=records_mod.to_iso8601_utc(case.get("publication_date")),
        updated_at=None,
        discovered_at=records_mod.to_iso8601_utc(case["discovery"]["first_seen_at"]),
        last_checked_at=None,
        content_type=CONTENT_TYPE,
        language=None,
        access_status=ACCESS_STATUS,
        http_status=None,
        verification_status=(VERIFICATION_SNIPPET if quote else VERIFICATION_UNVERIFIED),
        verification_evidence=quote,
        relevance_score=None,
        quality_score=None,
        audience_fit_score=None,
        freshness_score=None,
        duplicate_of=None,
        content_hash=None,
        tags=_tags(case),
        classification=_classification(),
        discovered_via=copy.deepcopy(case["discovery"]["found_via"]),
        raw=copy.deepcopy(case),
        legacy_ids=[{"system": SOURCE_ID, "id": case["case_id"], "key": case["case_key"]}],
        domain_fields={field: copy.deepcopy(case.get(field)) for field in DOMAIN_FIELDS},
        rejection_reason=None,
        case_facets=build_case_facets(case, facets_dir),
        provenance_extra={"migration": {"adapter": MIGRATION_ADAPTER,
                                        "migrated_at": migrated_at,
                                        "assumptions": _assumptions(reviewed_admit)}},
    )

    schema_mod.validate_or_raise(record, "record.v1.json",
                                 label="migrated %s" % case["case_id"])
    declared = record["case_facets"]["classification_state"]
    computed = facets_mod.decide_classification_state(record["case_facets"], facets_dir)
    _require(declared == computed,
             "%s: classification_state %r disagrees with the committed decision %r"
             % (case["case_id"], declared, computed))
    return record


def _rejection(case, match, migrated_at, reviewed, canon_kwargs):
    detail = ("legacy case %s: the suspicious-URL guard rule %s refused this URL — %s"
              % (case["case_id"], match.rule_id, match.detail))
    if reviewed:
        detail += "; a reviewer confirmed the rejection"
    return {
        "identity_url": urlkey.canonicalize_string(case["source_url"], **canon_kwargs),
        "target_url": case["source_url"],
        "source_id": SOURCE_ID,
        "title": _text(case.get("source_title")),
        "rejection_reason": REJECTION_REASON,
        "detail": detail,
        "scores": None,
        "rejected_at": migrated_at,
    }


# ---------------------------------------------------------------- public API
def map_registry(document, *, harvest_run_id, migrated_at, reviewed=None,
                 allow_unmappable=False, facets_dir=None):
    """Map an already-loaded AX registry document. Reads no registry file.

    `reviewed` is the in-memory D7-H decision list; S7-3 never opens
    `migration_overrides.v1.json`. `allow_unmappable` permits completion with
    unresolved rejections — it never admits, repairs or rewrites a URL.
    """
    validate_registry(document)
    _validate_clock(harvest_run_id, migrated_at)
    cases = document["cases"]
    decisions = _validate_reviews(reviewed, cases)
    kwargs = _canon_kwargs()

    accepted = []
    rejected = []
    unresolved_rejections = []
    for case in cases:
        match = base.suspicious_url_match(case["source_url"])
        decision = decisions.get(case["case_id"])
        if match is not None and decision != "admit":
            rejected.append(_rejection(case, match, migrated_at,
                                       decision == "reject", kwargs))
            if decision is None:
                unresolved_rejections.append(case["case_id"])
            continue
        accepted.append(map_case(case, harvest_run_id=harvest_run_id,
                                 migrated_at=migrated_at,
                                 reviewed_admit=(match is not None),
                                 facets_dir=facets_dir, canon_kwargs=kwargs))

    if unresolved_rejections and not allow_unmappable:
        raise AxMigrationError(
            "%d legacy URL(s) tripped the suspicious-URL guard and have no reviewed "
            "decision: %s. Review each in migration_overrides.v1.json or pass "
            "allow_unmappable; the mapping refuses to return a partial accepted set "
            "as though it were clear."
            % (len(unresolved_rejections), ", ".join(sorted(unresolved_rejections))))

    for field in ("identity_url", "content_id", "record_id"):
        seen = {}
        for record in accepted:
            value = record[field]
            _require(value not in seen,
                     "two accepted cases share %s %r (%s and %s). Identity is "
                     "URL-derived, and a collision is a finding about the corpus, "
                     "not something to merge away."
                     % (field, value, seen.get(value), record["legacy_ids"][0]["id"]))
            seen[value] = record["legacy_ids"][0]["id"]

    return MappingResult(
        accepted=tuple(records_mod.sort_records(accepted)),
        rejected=tuple(sorted(rejected, key=lambda row: (row["identity_url"],
                                                         row["detail"]))),
    )
