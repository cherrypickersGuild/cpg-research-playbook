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
import argparse
import copy
import dataclasses
import json
import os
import re
import sys
import uuid

from .. import artifacts as artifacts_mod
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


# =========================================================== S7-4 · CLI layer
# Everything below is orchestration: loading files, parsing the reviewed
# overrides, deriving the dry-run report and dispatching argv. The mapping above
# stays callable without any of it, and none of it can write a migration bundle
# — `--apply` is refused, because apply is S7-5 and is neither implemented nor
# authorized here.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

DEFAULT_REGISTRY = "state/ax_case_harvest_registry.json"
DEFAULT_OVERRIDES = "config/harvest/migration_overrides.v1.json"
DEFAULT_EXPECT_COUNT = 231

# The report's own contract, versioned separately from any artifact schema: this
# document goes to stdout and never to disk, so it is deliberately NOT a
# committed artifact type.
#
# E29: the S7-4 value was `ax_cases_dry_run`, which named one MODE. The report
# already carries `operation` and a `dry_run` boolean, so the family label was
# simply false on an apply result. `report_type` names the family; `dry_run` is
# the sole discriminator. No second type, no alias, no version bump — the shape
# never changed.
REPORT_TYPE = "ax_cases"
REPORT_VERSION = 1

DEFAULT_STATE_ROOT = "state/taxonomy_harvest"

# Cell identity for the one cell a migration produces, in display and slug form.
TOPIC_DISPLAY = "Cases"
CATEGORY_DISPLAY = "Case Studies"

# The committed override row shape (`_reviewed_unmappable_shape` in
# migration_overrides.v1.json). Every key is required, and an unrecognised key
# is refused rather than ignored: a key that changes what a review MEANS must
# not slip past unread.
REVIEW_ROW_FIELDS = ("case_id", "legacy_source_url", "matched_rule", "reviewer",
                     "reviewed_at", "decision", "note")


def _repo_path(path):
    """Resolve a possibly relative path against the repository root."""
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def load_json_document(path, label):
    """Read one UTF-8 JSON document, or fail loudly naming the LOGICAL input."""
    try:
        with open(_repo_path(path), "r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise AxMigrationError("cannot read the %s: %s" % (label, exc.strerror))
    except ValueError as exc:
        raise AxMigrationError("the %s is not valid JSON: %s" % (label, exc))


def parse_overrides(document):
    """The committed override document -> the in-memory review form S7-3 takes.

    The committed file is never modified, normalized or written. An empty
    `reviewed_unmappable` is valid and is what the current corpus carries.
    """
    _require(isinstance(document, dict),
             "the reviewed-overrides document must be a JSON object")
    _require(document.get("config_version") == 1,
             "the reviewed-overrides document declares config_version %r; this "
             "checkpoint reads version 1" % (document.get("config_version"),))
    block = document.get("ax_cases")
    _require(isinstance(block, dict),
             "the reviewed-overrides document has no `ax_cases` object")
    rows = block.get("reviewed_unmappable")
    _require(isinstance(rows, list),
             "`ax_cases.reviewed_unmappable` must be an array, got %s"
             % type(rows).__name__)

    reviews = []
    seen = set()
    for index, row in enumerate(rows):
        where = "ax_cases.reviewed_unmappable[%d]" % index
        _require(isinstance(row, dict), "%s must be an object" % where)
        missing = [f for f in REVIEW_ROW_FIELDS if f not in row]
        _require(not missing,
                 "%s is missing %s" % (where, ", ".join(repr(f) for f in missing)))
        extra = sorted(set(row) - set(REVIEW_ROW_FIELDS))
        _require(not extra,
                 "%s carries unrecognised key(s) %s; a key that changes what a "
                 "review means may not pass unread"
                 % (where, ", ".join(repr(k) for k in extra)))
        _require(row["decision"] in REVIEW_DECISIONS,
                 "%s decision %r is not one of %s"
                 % (where, row["decision"], ", ".join(REVIEW_DECISIONS)))
        _require(row["matched_rule"] in base.SUSPICIOUS_RULE_IDS,
                 "%s matched_rule %r is not one of the four committed guard rule "
                 "ids" % (where, row["matched_rule"]))
        for field in ("case_id", "legacy_source_url", "reviewer", "note"):
            _require(isinstance(row[field], str) and row[field].strip(),
                     "%s.%s must be a non-empty string" % (where, field))
        _require(isinstance(row["reviewed_at"], str)
                 and _UTC_SECOND.match(row["reviewed_at"]),
                 "%s.reviewed_at must be UTC ISO-8601 at second precision, got %r"
                 % (where, row["reviewed_at"]))
        key = (row["case_id"], row["legacy_source_url"])
        _require(key not in seen,
                 "%s repeats the review of %r; one case, one decision"
                 % (where, row["case_id"]))
        seen.add(key)
        reviews.append({"case_id": row["case_id"],
                        "legacy_source_url": row["legacy_source_url"],
                        "decision": row["decision"],
                        "note": row["note"]})
    return tuple(reviews), tuple(rows)


def _check_matched_rules(declared_rows, cases):
    """A review must name the rule that actually fires on that case's URL."""
    by_id = {case["case_id"]: case for case in cases}
    for index, row in enumerate(declared_rows):
        case = by_id.get(row["case_id"])
        if case is None:
            continue                    # the mapper refuses an unknown case by name
        match = base.suspicious_url_match(case["source_url"])
        _require(match is not None,
                 "ax_cases.reviewed_unmappable[%d] reviews %r, whose URL the guard "
                 "does not refuse at all" % (index, row["case_id"]))
        _require(match.rule_id == row["matched_rule"],
                 "ax_cases.reviewed_unmappable[%d] declares matched_rule %r but the "
                 "guard refuses %r under %r"
                 % (index, row["matched_rule"], row["case_id"], match.rule_id))


def build_report(document, reviews, result, *, expected_count, allow_unmappable,
                 harvest_run_id, migrated_at, dry_run=True):
    """The complete facts. No paths, no environment, no accepted payloads.

    One shape for both modes (E29): `dry_run` is the discriminator, and an apply
    result is the same sixteen fields with it set false.
    """
    decisions = {row["case_id"]: row["decision"] for row in reviews}
    suspicious = [case["case_id"] for case in document["cases"]
                  if base.suspicious_url_match(case["source_url"]) is not None]
    admitted = sorted(c for c in suspicious if decisions.get(c) == "admit")
    rejected_reviewed = sorted(c for c in suspicious if decisions.get(c) == "reject")
    unresolved = sorted(c for c in suspicious if c not in decisions)
    return {
        "report_type": REPORT_TYPE,
        "report_version": REPORT_VERSION,
        "operation": "ax-cases",
        "dry_run": bool(dry_run),
        "harvest_run_id": harvest_run_id,
        "migrated_at": migrated_at,
        "expected_count": expected_count,
        "source_count": len(document["cases"]),
        "accepted_count": len(result.accepted),
        "rejected_count": len(result.rejected),
        "reviewed_admit_count": len(admitted),
        "reviewed_reject_count": len(rejected_reviewed),
        "unresolved_rejection_count": len(unresolved),
        "unresolved_case_ids": unresolved,
        "allow_unmappable": bool(allow_unmappable),
        "rejections": list(result.rejected),
    }


def render_report(report):
    """One rendering, the committed one: sorted keys, UTF-8, LF, one newline."""
    return artifacts_mod.serialize(report).decode("utf-8")


def load_and_map(*, registry_path, overrides_path, facets_dir, expected_count,
                 harvest_run_id, migrated_at):
    """(document, reviews, result). The shared read-and-map both modes use.

    The mapping always runs with `allow_unmappable=True` so the report is
    COMPLETE; whether the command succeeded is decided separately, from the
    unresolved count. A rejected case is never reinterpreted as accepted.
    """
    document = load_json_document(registry_path, "AX case registry")
    overrides = load_json_document(overrides_path, "reviewed-overrides document")
    reviews, declared = parse_overrides(overrides)

    _require(isinstance(document, dict) and isinstance(document.get("cases"), list),
             "the AX case registry has no `cases` array")
    actual = len(document["cases"])
    _require(actual == expected_count,
             "the AX case registry holds %d cases; --expect-count is %d. The count "
             "is asserted, never assumed: rerun with --expect-count %d if the corpus "
             "really changed." % (actual, expected_count, actual))
    _check_matched_rules(declared, document["cases"])

    result = map_registry(document, harvest_run_id=harvest_run_id,
                          migrated_at=migrated_at, reviewed=list(reviews),
                          allow_unmappable=True, facets_dir=facets_dir)
    return document, reviews, result


def dry_run(*, registry_path=DEFAULT_REGISTRY, overrides_path=DEFAULT_OVERRIDES,
            facets_dir=None, expected_count=DEFAULT_EXPECT_COUNT,
            allow_unmappable=False, harvest_run_id, migrated_at):
    """Map the whole registry in memory and derive the report. Writes nothing."""
    document, reviews, result = load_and_map(
        registry_path=registry_path, overrides_path=overrides_path,
        facets_dir=facets_dir, expected_count=expected_count,
        harvest_run_id=harvest_run_id, migrated_at=migrated_at)
    return build_report(document, reviews, result, expected_count=expected_count,
                        allow_unmappable=allow_unmappable,
                        harvest_run_id=harvest_run_id, migrated_at=migrated_at,
                        dry_run=True)


# ====================================================== S7-5 · atomic publication
# Three documents are built and validated COMPLETELY in memory, then written into
# a uniquely named sibling staging directory, then published by ONE
# same-filesystem directory rename. A reader sees the whole bundle or no bundle.
# There is no resume, no pointer, nothing under `runs/`, and no promotion.
def build_candidate_artifact(result, *, harvest_run_id, migrated_at, source_count):
    """`cell_artifact.v1.json` through the committed builder — counts derived."""
    metadata = {"sources": [{"source_id": SOURCE_ID,
                             "adapter": SOURCE_ADAPTER,
                             "result": "ok",
                             "candidates": source_count,
                             "accepted": len(result.accepted),
                             "requests_made": 0}],
                "rejected": len(result.rejected)}
    return artifacts_mod.build_cell_artifact(
        list(result.accepted), topic=TOPIC_DISPLAY, topic_slug=TOPIC_SLUG,
        category=CATEGORY_DISPLAY, category_slug=CATEGORY_SLUG, cell_id=CELL_ID,
        harvest_run_id=harvest_run_id, generated_at=migrated_at, metadata=metadata)


def build_rejection_artifact(result, *, harvest_run_id, migrated_at):
    """`rejection.v1.json`. The S7-3 rows verbatim — no second representation.

    An empty list is still written: "this migration refused nothing" is a fact,
    and omitting the file would make it indistinguishable from "nobody looked".
    """
    return {"schema_version": 1,
            "cell_id": CELL_ID,
            "harvest_run_id": harvest_run_id,
            "generated_at": migrated_at,
            "rejections": [dict(row) for row in result.rejected]}


def derive_publication_ineligibility(records):
    """(False, reason). Derived from the records, never asserted by a caller.

    `artifacts.build_run_manifest` is deliberately not used: it expands to the
    twelve configured cells and refuses any other cell id, which is a harvest
    contract, not this one. The eligibility FACT is still derived here, from the
    committed unchecked-record owner.
    """
    unchecked, total = artifacts_mod.unchecked_full_records(records)
    _require(unchecked == total,
             "%d of %d accepted migrated records claim checked access. Migration "
             "issues no request, so a checked record cannot have come from here; "
             "the bundle is refused rather than published with a false claim."
             % (total - unchecked, total))
    if not total:
        return False, ("the migration produced no accepted records, so there is "
                       "nothing to publish")
    return False, ("all %d of %d accepted records carry no target evidence "
                   "(access_status not_checked): a migration fetches nothing"
                   % (unchecked, total))


def build_migration_manifest(result, *, harvest_run_id, migrated_at, expected_count,
                             source_count):
    """`run_manifest.v1.json` with exactly one migration cell row."""
    eligible, reason = derive_publication_ineligibility(list(result.accepted))
    return {
        "schema_version": 1,
        "harvest_run_id": harvest_run_id,
        "mode": "migration",
        "started_at": migrated_at,
        "finished_at": migrated_at,
        "environment": artifacts_mod.environment_block(),
        "config": {"topics": [TOPIC_SLUG], "enrich": False,
                   "bounds": {"expected_source_count": expected_count}},
        "cells": [{"cell_id": CELL_ID,
                   "topic_slug": TOPIC_SLUG,
                   "category_slug": CATEGORY_SLUG,
                   "status": "ok",
                   "candidates": source_count,
                   "accepted": len(result.accepted),
                   "rejected": len(result.rejected),
                   "requests_made": 0,
                   "adapters_used": [SOURCE_ADAPTER]}],
        "source_preflight": [],
        "classification_decisions": [],
        "publication_eligible": eligible,
        "publication_ineligible_reason": reason,
    }


def build_bundle_documents(result, *, harvest_run_id, migrated_at, expected_count,
                           source_count):
    """The complete bundle as ((relative path, document, schema name), …).

    Every document is built before any directory exists, and all three are
    validated before the first staging write.
    """
    documents = (
        (base.BUNDLE_RELATIVE_PATHS[0],
         build_candidate_artifact(result, harvest_run_id=harvest_run_id,
                                  migrated_at=migrated_at,
                                  source_count=source_count),
         "cell_artifact.v1.json"),
        (base.BUNDLE_RELATIVE_PATHS[1],
         build_migration_manifest(result, harvest_run_id=harvest_run_id,
                                  migrated_at=migrated_at,
                                  expected_count=expected_count,
                                  source_count=source_count),
         "run_manifest.v1.json"),
        (base.BUNDLE_RELATIVE_PATHS[2],
         build_rejection_artifact(result, harvest_run_id=harvest_run_id,
                                  migrated_at=migrated_at),
         "rejection.v1.json"),
    )
    for relative, document, schema_name in documents:
        schema_mod.validate_or_raise(document, schema_name,
                                     label="migration bundle %s" % relative)
    # Written content first and the manifest last, mirroring the committed
    # harvest order: nothing observes a partial bundle anyway (the rename is what
    # publishes), but a manifest that describes files already staged beside it
    # keeps the same reading order a reviewer already knows.
    order = {relative: index for index, relative in enumerate(
        (base.BUNDLE_RELATIVE_PATHS[0], base.BUNDLE_RELATIVE_PATHS[2],
         base.BUNDLE_RELATIVE_PATHS[1]))}
    return tuple(sorted(documents, key=lambda row: order[row[0]]))


def _staged_paths(staging):
    found = []
    for base_dir, dirs, files in os.walk(staging):
        dirs.sort()
        for name in sorted(files):
            found.append(os.path.relpath(os.path.join(base_dir, name),
                                         staging).replace(os.sep, "/"))
    return tuple(sorted(found))


def _verify_staged_paths(staging):
    """The staged tree is EXACTLY the three committed paths, or nothing ships."""
    found = _staged_paths(staging)
    _require(found == base.BUNDLE_RELATIVE_PATHS,
             "the staged bundle holds %s; exactly %s was expected"
             % (list(found), list(base.BUNDLE_RELATIVE_PATHS)))
    return found


def _remove_owned_staging(staging, state_root, run_id):
    """Remove ONLY the staging directory this invocation created.

    Ownership is proved twice — the caller hands back the exact path it created,
    and the path must be one this layout would have named under this migrations
    root for this run id. Nothing is globbed, and no other path is ever accepted.
    """
    if not staging or not base.owns_staging(staging, state_root, run_id):
        return False
    if not os.path.isdir(staging):
        return False
    for base_dir, dirs, files in os.walk(staging, topdown=False):
        for name in files:
            os.unlink(os.path.join(base_dir, name))
        for name in dirs:
            os.rmdir(os.path.join(base_dir, name))
    os.rmdir(staging)
    return True


def apply_bundle(result, *, state_root, harvest_run_id, migrated_at, expected_count,
                 source_count):
    """Publish the bundle atomically, or leave the state root as it was found.

    Order is the whole contract: build and validate everything, stage beside the
    destination, verify the staged path set, recheck the destination, then ONE
    `os.replace` of the directory. An interruption anywhere before that rename
    publishes nothing and leaves no debris.
    """
    final = base.bundle_path(state_root, harvest_run_id)
    _require(not os.path.lexists(final),
             "the bundle %s already exists. A finished run id is never "
             "overwritten, merged or resumed; rerun with a new run id."
             % base.bundle_dirname(harvest_run_id))

    documents = build_bundle_documents(result, harvest_run_id=harvest_run_id,
                                       migrated_at=migrated_at,
                                       expected_count=expected_count,
                                       source_count=source_count)

    root = base.migrations_root(state_root)
    created_root = not os.path.isdir(root)
    staging = os.path.join(root, base.staging_name(harvest_run_id, uuid.uuid4().hex))
    try:
        os.makedirs(staging)                     # creates `migrations/` if needed
        for relative, document, schema_name in documents:
            target = os.path.join(staging, *relative.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            artifacts_mod.write_document(target, document, schema_name)
        _verify_staged_paths(staging)
        _require(not os.path.lexists(final),
                 "%s appeared while this bundle was being staged; publication is "
                 "refused rather than overwriting it." % base.bundle_dirname(
                     harvest_run_id))
        os.replace(staging, final)
    except BaseException:
        # Cleanup catches BaseException so an interrupt leaves no debris either.
        _remove_owned_staging(staging, state_root, harvest_run_id)
        if created_root and os.path.isdir(root) and not os.listdir(root):
            os.rmdir(root)
        raise
    return final


def apply_migration(*, state_root, registry_path=DEFAULT_REGISTRY,
                    overrides_path=DEFAULT_OVERRIDES, facets_dir=None,
                    expected_count=DEFAULT_EXPECT_COUNT, allow_unmappable=False,
                    harvest_run_id, migrated_at):
    """(report, bundle path or None). Nothing is written unless it publishes."""
    final = base.bundle_path(state_root, harvest_run_id)
    _require(not os.path.lexists(final),
             "the bundle %s already exists. A finished run id is never "
             "overwritten, merged or resumed; rerun with a new run id."
             % base.bundle_dirname(harvest_run_id))

    document, reviews, result = load_and_map(
        registry_path=registry_path, overrides_path=overrides_path,
        facets_dir=facets_dir, expected_count=expected_count,
        harvest_run_id=harvest_run_id, migrated_at=migrated_at)
    report = build_report(document, reviews, result, expected_count=expected_count,
                          allow_unmappable=allow_unmappable,
                          harvest_run_id=harvest_run_id, migrated_at=migrated_at,
                          dry_run=False)
    if report["unresolved_rejection_count"] and not allow_unmappable:
        return report, None                      # reported, and nothing written
    published = apply_bundle(result, state_root=state_root,
                             harvest_run_id=harvest_run_id,
                             migrated_at=migrated_at,
                             expected_count=expected_count,
                             source_count=len(document["cases"]))
    return report, published


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("%r is not an integer" % (value,))
    if number < 0:
        raise argparse.ArgumentTypeError("%r must not be negative" % (value,))
    return number


def build_parser():
    parser = argparse.ArgumentParser(
        prog="migrate.sh ax-cases",
        description="Map the protected AX case registry in memory and report. "
                    "Dry-run only: this command writes nothing.")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--overrides", default=DEFAULT_OVERRIDES)
    parser.add_argument("--facets-dir", default=None)
    parser.add_argument("--expect-count", type=_positive_int,
                        default=DEFAULT_EXPECT_COUNT)
    parser.add_argument("--allow-unmappable", action="store_true")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--migrated-at", default=None)
    parser.add_argument("--apply", action="store_true",
                        help="publish one migration bundle under --state-root")
    parser.add_argument("--state-root", default=None,
                        help="root holding migrations/; defaults to %s"
                             % DEFAULT_STATE_ROOT)
    return parser


def main(argv=None, stdout=None, stderr=None):
    """Dry-run entry point. Returns an exit status; never writes a file.

    `stdout` is a BINARY stream. The report's bytes are its contract, and a text
    stream on Windows would rewrite every LF into CRLF on the way out.
    """
    out = stdout if stdout is not None else sys.stdout.buffer
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)

    if args.state_root is not None and not args.apply:
        err.write("migrate.sh ax-cases: --state-root is only meaningful with "
                  "--apply. A dry-run writes nothing, so it has no state root; "
                  "the option is refused rather than silently ignored.\n")
        return 1

    harvest_run_id = args.run_id or artifacts_mod.run_id()
    migrated_at = args.migrated_at or records_mod.utcnow()
    state_root = args.state_root or DEFAULT_STATE_ROOT
    try:
        if args.apply:
            report, published = apply_migration(
                state_root=state_root,
                registry_path=args.registry,
                overrides_path=args.overrides,
                facets_dir=args.facets_dir,
                expected_count=args.expect_count,
                allow_unmappable=args.allow_unmappable,
                harvest_run_id=harvest_run_id,
                migrated_at=migrated_at)
        else:
            report, published = dry_run(
                registry_path=args.registry,
                overrides_path=args.overrides,
                facets_dir=args.facets_dir,
                expected_count=args.expect_count,
                allow_unmappable=args.allow_unmappable,
                harvest_run_id=harvest_run_id,
                migrated_at=migrated_at), None
    except (AxMigrationError, base.MigrationInputError, base.MigrationPathError,
            schema_mod.SchemaError, artifacts_mod.ArtifactError, OSError) as exc:
        err.write("migrate.sh ax-cases: %s\n" % exc)
        return 1

    # The report is rendered LAST on an apply: it is printed only once the final
    # rename has already put the complete bundle in place, so a success report
    # can never describe a publication that did not happen.
    out.write(render_report(report).encode("utf-8"))
    if report["unresolved_rejection_count"] and not args.allow_unmappable:
        err.write("migrate.sh ax-cases: %d legacy URL(s) tripped the suspicious-URL "
                  "guard with no reviewed decision: %s. Review each one in "
                  "%s, or rerun with --allow-unmappable to complete with the "
                  "rejections intact. Nothing was written.\n"
                  % (report["unresolved_rejection_count"],
                     ", ".join(report["unresolved_case_ids"]), DEFAULT_OVERRIDES))
        return 1
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    sys.exit(main())
