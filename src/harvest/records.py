#!/usr/bin/env python3
"""records.py — construct schema-shaped records with explicit, honest defaults.

Two rules run through everything here:

  * Unknown is null, never a guess and never the string "unknown". The legacy AX
    schema used "unknown" as a sentinel; migration maps it to null and keeps the
    original in provenance.raw, so nothing is invented and nothing is lost.
  * A field that was never checked says so. With enrichment disabled the record
    carries access_status "not_checked" and verification_status "unverified" —
    not "ok"/"fetched", which would be a claim we did not earn.
"""
import datetime
import os

SCHEMA_VERSION = 1


# --------------------------------------------------------------------------- time
def utcnow():
    """UTC ISO-8601, second precision, Z-suffixed.

    HARVEST_CLOCK_UTC pins this for fixture tests, which is what lets the
    fixture suite assert byte-identical output across runs.
    """
    pinned = os.environ.get("HARVEST_CLOCK_UTC")
    if pinned:
        return pinned
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_iso8601_utc(value):
    """Best-effort normalization of a publisher date to the schema's format.

    Returns None rather than guessing. A feed that gives a date we cannot parse
    yields published_at: null, which is honest; inventing a timestamp would make
    the freshness score a fiction.
    """
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        dt = value
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        dt = None
        # RFC 822 / RFC 1123, as used by RSS.
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(s)
        except (TypeError, ValueError, IndexError):
            dt = None
        if dt is None:
            # ISO-8601, as used by Atom and most JSON APIs.
            iso = s.replace("Z", "+00:00")
            try:
                dt = datetime.datetime.fromisoformat(iso)
            except ValueError:
                dt = None
        if dt is None:
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d %B %Y", "%B %d, %Y"):
                try:
                    dt = datetime.datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
        if dt is None:
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def null_if_unknown(value):
    """Map the legacy "unknown" sentinel (and empty strings) to an explicit null."""
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() == "unknown":
            return None
        return s
    return value


# The committed `record.v1.json` alias_kind enum, and the only keys a url_alias
# may carry — that object is `additionalProperties: false`, so anything else must
# be dropped here rather than refused by the schema after the record is assembled.
ALIAS_KINDS = ("permanent_redirect", "canonical_tag", "domain_rule",
               "discovered_variant")
ALIAS_KEYS = ("url", "kind", "evidence", "observed_at")


class RecordError(ValueError):
    """A record input this builder refuses to shape into a record."""


def normalize_url_aliases(aliases):
    """Validate, project, deduplicate and order `url_aliases`. (D6-A)

    Owned here because `make_full_record` is the sole owner of the persistent
    record shape: a caller that assembled this list itself would be a second place
    that knows what a record looks like, and would drift from the schema.

    Refuses rather than repairs, and refuses BEFORE the record exists — a malformed
    alias that reached a written artifact would be a false claim about which URLs
    are the same resource, and that is the one error nothing downstream can undo.

    Ordered and deduplicated by `(kind, url)`, so two runs over one input produce
    one byte sequence.
    """
    if not aliases:
        return []
    if isinstance(aliases, (str, bytes, dict)):
        raise RecordError("url_aliases must be a sequence of alias objects, got %s"
                          % type(aliases).__name__)

    seen, out = set(), []
    for index, alias in enumerate(aliases):
        if not isinstance(alias, dict):
            raise RecordError("url_aliases[%d] is not an object: %r" % (index, alias))
        missing = [key for key in ALIAS_KEYS if not alias.get(key)]
        if missing:
            raise RecordError("url_aliases[%d] is missing %s"
                              % (index, ", ".join(missing)))
        kind = alias["kind"]
        if kind not in ALIAS_KINDS:
            raise RecordError("url_aliases[%d] kind %r is not one of the committed "
                              "alias kinds %s" % (index, kind, ALIAS_KINDS))
        url = alias["url"]
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise RecordError("url_aliases[%d] url %r is not an absolute http(s) URL"
                              % (index, url))
        evidence = alias["evidence"]
        if not isinstance(evidence, dict):
            raise RecordError("url_aliases[%d] evidence must be an object" % index)

        key = (kind, url)
        if key in seen:
            continue          # the same claim twice is one claim, not an error
        seen.add(key)
        # Projected to the admitted keys only: the schema forbids extras, and
        # dropping them here keeps that decision in one place.
        out.append({name: alias[name] for name in ALIAS_KEYS})

    out.sort(key=lambda row: (row["kind"], row["url"]))
    return out


# --------------------------------------------------------------------------- builders
def make_full_record(
    *,
    record_id,
    content_id,
    topic_slug,
    category_slug,
    cell_id,
    identity_url,
    target_url,
    harvest_run_id,
    source_id,
    source_adapter,
    canonical_url=None,
    source_url=None,
    title=None,
    summary=None,
    curation_reason=None,
    publisher=None,
    author=None,
    published_at=None,
    updated_at=None,
    discovered_at=None,
    last_checked_at=None,
    content_type="article",
    language=None,
    access_status="not_checked",
    http_status=None,
    verification_status="unverified",
    verification_evidence=None,
    relevance_score=None,
    quality_score=None,
    audience_fit_score=None,
    freshness_score=None,
    duplicate_of=None,
    content_hash=None,
    tags=None,
    classification=None,
    provenance_extra=None,
    source_tier=None,
    discovered_via=None,
    raw=None,
    legacy_ids=None,
    link_history=None,
    domain_fields=None,
    rejection_reason=None,
    case_facets=None,
    url_aliases=None,
):
    """Build a `full` record. Every schema-required key is always present.

    canonical_url defaults to identity_url: at creation nothing has been verified
    yet, so the latest-known-preferred URL is simply the identity. It diverges
    only when a redirect or canonical tag is later observed and trusted.
    """
    rec = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "full",
        "record_id": record_id,
        "content_id": content_id,

        "topic": topic_slug,
        "primary_category": category_slug,
        "tags": sorted(set(tags or [])),

        "title": null_if_unknown(title),
        "summary": null_if_unknown(summary),
        "curation_reason": null_if_unknown(curation_reason),

        "source_url": source_url,
        "target_url": target_url,
        "identity_url": identity_url,
        "canonical_url": canonical_url or identity_url,
        "url_aliases": normalize_url_aliases(url_aliases),

        "publisher": null_if_unknown(publisher),
        "author": null_if_unknown(author),
        "published_at": published_at,
        "updated_at": updated_at,
        "discovered_at": discovered_at or utcnow(),
        "last_checked_at": last_checked_at,

        "content_type": content_type,
        "language": null_if_unknown(language),

        "access_status": access_status,
        "http_status": http_status,
        "verification_status": verification_status,
        "verification_evidence": null_if_unknown(verification_evidence),

        "relevance_score": relevance_score,
        "quality_score": quality_score,
        "audience_fit_score": audience_fit_score,
        "freshness_score": freshness_score,

        "duplicate_of": duplicate_of,
        "content_hash": content_hash,

        "harvest_run_id": harvest_run_id,
        "cell_id": cell_id,

        "classification": classification or {
            "rule_id": "R10_default_by_category",
            "rationale": "No higher-precedence rule fired; assigned to the discovery cell.",
            "evidence": [],
            "competing_categories": [],
        },
        "provenance": {
            "source_id": source_id,
            "source_adapter": source_adapter,
            "source_tier": source_tier,
            "discovered_via": discovered_via or [],
            "raw": raw,
            "migration": (provenance_extra or {}).get("migration"),
        },
        "rejection_reason": rejection_reason,
    }

    # Optional keys are omitted entirely when empty rather than carried as empty
    # containers, so a record's shape reflects what is actually known about it.
    if legacy_ids:
        rec["legacy_ids"] = legacy_ids
    if link_history:
        rec["link_history"] = link_history
    if domain_fields:
        rec["domain_fields"] = domain_fields
    # Same rule, and it carries meaning here: an ABSENT case_facets means
    # enrichment was never attempted (reporting state "not_enriched"), which is
    # deliberately distinct from a present payload whose axes are empty ("looked,
    # found nothing"). Writing null or {} for the untried case would erase that
    # difference. Facets are never read by urlkey.py, so adding or removing this
    # key changes no id, no cell_id and no filename.
    if case_facets:
        rec["case_facets"] = case_facets
    return rec


def make_cross_reference(
    *,
    record_id,
    content_id,
    identity_url,
    topic_slug,
    category_slug,
    duplicate_of,
    owner_topic,
    reason,
    harvest_run_id,
    discovered_at=None,
    cell_id=None,
):
    """Build a `cross_reference` row — a pointer, not a record.

    Deliberately minimal and schema-closed: it cannot carry title, scores or any
    other full-record field, so it can never be mistaken for publishable content
    or silently counted as an independent duplicate.
    """
    row = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "cross_reference",
        "record_id": record_id,
        "content_id": content_id,
        "identity_url": identity_url,
        "topic": topic_slug,
        "primary_category": category_slug,
        "duplicate_of": duplicate_of,
        "owner_topic": owner_topic,
        "cross_reference_reason": reason,
        "harvest_run_id": harvest_run_id,
        "discovered_at": discovered_at or utcnow(),
    }
    if cell_id:
        row["cell_id"] = cell_id
    return row


# --------------------------------------------------------------------------- ordering
def sort_key(record):
    """Deterministic artifact ordering: (topic, primary_category, record_id).

    Stable across runs and independent of the order cells finished in, which is
    what makes the fixture suite's byte-identical assertion possible.
    """
    return (record.get("topic", ""),
            record.get("primary_category", ""),
            record.get("record_id", ""))


def sort_records(records):
    return sorted(records, key=sort_key)
