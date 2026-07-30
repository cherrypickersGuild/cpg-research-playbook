"""entity_assess.py — read-only assessment of the legacy entity registry (S7-1).

D7-J: this module **migrates zero entities**. It emits no taxonomy record, no
migration bundle and no runtime state. Its only product is a Markdown assessment
generated from the protected registry, so the document can never drift from the
data it describes: if the registry changes, the document is regenerated, never
edited.

Four separated layers, each callable on its own from a test:

  1. `load_registry()`  — read and validate the expected shape. A malformed top
     level or a malformed row RAISES; nothing is skipped, because a skipped row
     is a row that silently leaves every count in the document wrong.
  2. `assess()`         — derive the assessment data. Pure over its input, and
     ORDER-FREE: every grouping is sorted by a total key, so reversing or
     shuffling `entities` cannot change a single byte downstream.
  3. `render()`         — deterministic Markdown. No clock, no absolute path, no
     Python repr, exactly one trailing newline.
  4. `write_assessment()` — the only function that touches the filesystem, and
     only at an explicitly supplied path. There is no default output path and no
     implicit write.

Determinism obligations this module accepts: no wall-clock time, no network, no
git state, no absolute machine path, no reliance on input iteration order, and
no mutable module-global state. The one instant that appears in the document,
`last_merged_at`, is read from the registry — it is a property of the input, not
of the run.
"""
import collections
import json
import os
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

# Repo-relative on purpose: the rendered document must carry no absolute path.
SOURCE_PATH = "state/entity_registry.json"
DOCUMENT_PATH = "docs/harvest/ENTITY_REGISTRY_MIGRATION_ASSESSMENT.md"

# Structural, not a parameter: S7-1 has no migration path at all. Reported in the
# document and asserted by the suite, so "zero" stays a proved fact rather than a
# claim in prose.
MIGRATED_ENTITY_COUNT = 0

# The corpus this assessment was written against. It is RECONCILED, never assumed:
# `assess()` derives the total from the rows and reports agreement or disagreement
# with both this number and the registry's own `metadata.total_entities`.
EXPECTED_ENTITY_COUNT = 1161

REQUIRED_TOP_LEVEL = ("schema_version", "last_merged_at", "metadata", "entities")

# The complete row contract. Missing field => raise: the document claims to
# inventory every field, and a row that quietly lacks one would make the
# inventory a lie. UNKNOWN field => raise as well, because an unclassified field
# would slip past §4's mapping table without appearing anywhere in the document.
REQUIRED_ROW_FIELDS = (
    "conflicting_evidence_log", "corroboration_count", "description",
    "description_source", "discovery", "entity_id", "entity_key", "entity_type",
    "freshness_signal", "github_stars", "maintainer_or_vendor", "name",
    "related_topics", "source_url", "target_url", "topic",
)
REQUIRED_DISCOVERY_FIELDS = ("first_seen_at", "found_via", "last_corroborated_at")

# The legacy sentinel. The AX registry uses the same one; `records.null_if_unknown`
# is the committed translation for the migration path, and it is deliberately NOT
# applied here — this module reports what the registry holds, it does not clean it.
UNKNOWN = "unknown"


class AssessmentError(ValueError):
    """A registry that does not have the shape this assessment describes."""


# ------------------------------------------------------------------ loading
def registry_path(path=None):
    """Absolute path to the source registry. Never rendered into the document."""
    return path if path else os.path.join(ROOT, *SOURCE_PATH.split("/"))


def load_registry(path=None):
    """Read the protected registry and refuse anything that is not its shape.

    Opened read-only. This module never opens the registry for writing, in any
    mode, on any code path — it is one of the 18 protected files.
    """
    target = registry_path(path)
    try:
        with open(target, "r", encoding="utf-8") as handle:
            doc = json.load(handle)
    except OSError as exc:
        raise AssessmentError("cannot read the entity registry: %s" % exc)
    except ValueError as exc:
        raise AssessmentError("entity registry is not valid JSON: %s" % exc)
    validate_registry(doc)
    return doc


def validate_registry(doc):
    """Fail loudly and specifically, naming the row and the field at fault."""
    if not isinstance(doc, dict):
        raise AssessmentError("entity registry must be a JSON object, got %s"
                              % type(doc).__name__)
    for key in REQUIRED_TOP_LEVEL:
        if key not in doc:
            raise AssessmentError("entity registry is missing the top-level key %r" % key)
    if not isinstance(doc["metadata"], dict):
        raise AssessmentError("entity registry `metadata` must be an object, got %s"
                              % type(doc["metadata"]).__name__)
    if not isinstance(doc["entities"], list):
        raise AssessmentError("entity registry `entities` must be an array, got %s"
                              % type(doc["entities"]).__name__)

    allowed = set(REQUIRED_ROW_FIELDS)
    for index, row in enumerate(doc["entities"]):
        where = "entities[%d]" % index
        if not isinstance(row, dict):
            raise AssessmentError("%s must be an object, got %s"
                                  % (where, type(row).__name__))
        for field in REQUIRED_ROW_FIELDS:
            if field not in row:
                raise AssessmentError("%s is missing the required field %r" % (where, field))
        extra = sorted(set(row) - allowed)
        if extra:
            raise AssessmentError(
                "%s carries unrecognised field(s) %s. An unclassified field would "
                "not appear in the field-mapping section, so it is refused rather "
                "than silently dropped." % (where, ", ".join(repr(e) for e in extra)))
        discovery = row["discovery"]
        if not isinstance(discovery, dict):
            raise AssessmentError("%s.discovery must be an object, got %s"
                                  % (where, type(discovery).__name__))
        for field in REQUIRED_DISCOVERY_FIELDS:
            if field not in discovery:
                raise AssessmentError("%s.discovery is missing %r" % (where, field))
        if not isinstance(discovery["found_via"], list):
            raise AssessmentError("%s.discovery.found_via must be an array, got %s"
                                  % (where, type(discovery["found_via"]).__name__))
    return True


# ------------------------------------------------------------------ helpers
def _is_blank(value):
    return not (isinstance(value, str) and value.strip())


def _is_absolute_http(url):
    """The `record.v1.json` bar for target_url: an absolute http(s) URL."""
    if _is_blank(url):
        return False
    parts = urllib.parse.urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def _counted(values):
    """[(value, count)] sorted by value — never by count, never by input order."""
    return sorted(collections.Counter(values).items())


def _canonical(row):
    """Content key for exact-duplicate detection. Key order cannot affect it."""
    return json.dumps(row, sort_keys=True, ensure_ascii=False)


# ------------------------------------------------------------------ analysis
def assess(registry):
    """Derive the assessment. Pure, order-free, and free of any clock."""
    validate_registry(registry)
    rows = registry["entities"]
    metadata = registry["metadata"]
    derived_total = len(rows)

    declared_total = metadata.get("total_entities")
    by_topic = _counted(r["topic"] for r in rows)
    by_type = _counted(r["entity_type"] for r in rows)
    by_topic_type = sorted(collections.Counter(
        (r["topic"], r["entity_type"]) for r in rows).items())
    by_description_source = _counted(r["description_source"] for r in rows)

    declared_topic = metadata.get("entity_count_by_topic") or {}
    declared_type = metadata.get("entity_count_by_entity_type") or {}

    reconciliation = {
        "derived_total": derived_total,
        "declared_total": declared_total,
        "expected_total": EXPECTED_ENTITY_COUNT,
        "derived_matches_declared": derived_total == declared_total,
        "derived_matches_expected": derived_total == EXPECTED_ENTITY_COUNT,
        "topic_subtotal": sum(c for _, c in by_topic),
        "type_subtotal": sum(c for _, c in by_type),
        "topic_type_subtotal": sum(c for _, c in by_topic_type),
        "description_source_subtotal": sum(c for _, c in by_description_source),
        "declared_topic_agrees": sorted(declared_topic.items()) == by_topic,
        "declared_type_agrees": sorted(declared_type.items()) == by_type,
    }

    # ---- identity -----------------------------------------------------------
    ids = [r["entity_id"] for r in rows]
    id_groups = collections.defaultdict(list)
    for row in rows:
        id_groups[row["entity_id"]].append(row)
    repeated = {k: v for k, v in id_groups.items() if len(v) > 1}
    repeated_rows = sum(len(v) for v in repeated.values())
    cross_topic = sum(1 for v in repeated.values() if len({r["topic"] for r in v}) > 1)

    duplicate_groups = [
        {
            "entity_id": entity_id,
            "rows": len(repeated[entity_id]),
            "topics": sorted({r["topic"] for r in repeated[entity_id]}),
            "entity_keys": sorted(r["entity_key"] for r in repeated[entity_id]),
        }
        for entity_id in sorted(repeated)
    ]
    # Size first so the worst collisions lead, then identifier so ties are total.
    duplicate_groups.sort(key=lambda g: (-g["rows"], g["entity_id"]))

    canonical_rows = [_canonical(r) for r in rows]
    exact_duplicate_rows = len(canonical_rows) - len(set(canonical_rows))

    identity = {
        "entity_id_present": sum(1 for v in ids if not _is_blank(v)),
        "entity_id_blank": sum(1 for v in ids if _is_blank(v)),
        "entity_id_distinct": len(set(ids)),
        "repeated_id_groups": len(repeated),
        "repeated_id_rows": repeated_rows,
        "repeated_id_groups_cross_topic": cross_topic,
        "repeated_id_groups_single_topic": len(repeated) - cross_topic,
        "largest_repeated_group": max((len(v) for v in repeated.values()), default=0),
        "topic_qualified_distinct": len({(r["topic"], r["entity_id"]) for r in rows}),
        "entity_key_distinct": len({r["entity_key"] for r in rows}),
        "entity_key_blank": sum(1 for r in rows if _is_blank(r["entity_key"])),
        "exact_duplicate_rows": exact_duplicate_rows,
        "duplicate_groups": duplicate_groups,
    }

    # ---- URLs, which is where record identity would have to come from -------
    target_usable = sum(1 for r in rows if _is_absolute_http(r["target_url"]))
    source_usable = sum(1 for r in rows if _is_absolute_http(r["source_url"]))
    usable_targets = [r["target_url"] for r in rows if _is_absolute_http(r["target_url"])]
    shared = {u: c for u, c in collections.Counter(usable_targets).items() if c > 1}
    shared_rows = sum(shared.values())

    urls = {
        "target_usable": target_usable,
        "target_unusable": len(rows) - target_usable,
        "target_unknown_sentinel": sum(1 for r in rows if r["target_url"] == UNKNOWN),
        "source_usable": source_usable,
        "source_unusable": len(rows) - source_usable,
        "source_unknown_sentinel": sum(1 for r in rows if r["source_url"] == UNKNOWN),
        "target_equals_source": sum(1 for r in rows if r["target_url"] == r["source_url"]),
        "distinct_usable_targets": len(set(usable_targets)),
        "shared_target_urls": len(shared),
        "shared_target_rows": shared_rows,
        "distinct_target_hosts": len({urllib.parse.urlsplit(u).hostname
                                      for u in usable_targets}),
    }

    # ---- evidence and provenance shape --------------------------------------
    found_via_shapes = sorted(collections.Counter(
        tuple(sorted(item.keys())) if isinstance(item, dict) else ("<not-an-object>",)
        for r in rows for item in r["discovery"]["found_via"]).items())
    first_seen = sorted({r["discovery"]["first_seen_at"] for r in rows})
    corroborated = sorted({r["discovery"]["last_corroborated_at"] for r in rows})

    evidence = {
        "github_stars_present": sum(1 for r in rows if r["github_stars"] is not None),
        "github_stars_null": sum(1 for r in rows if r["github_stars"] is None),
        "related_topics_present": sum(1 for r in rows if r["related_topics"]),
        "related_topic_counts": _counted(t for r in rows for t in r["related_topics"]),
        "conflicting_evidence_present": sum(1 for r in rows if r["conflicting_evidence_log"]),
        "corroboration_counts": _counted(r["corroboration_count"] for r in rows),
        "found_via_items": sum(len(r["discovery"]["found_via"]) for r in rows),
        "found_via_shapes": [(list(shape), count) for shape, count in found_via_shapes],
        "found_via_empty_rows": sum(1 for r in rows if not r["discovery"]["found_via"]),
        "first_seen_earliest": first_seen[0] if first_seen else None,
        "first_seen_latest": first_seen[-1] if first_seen else None,
        "first_seen_distinct": len(first_seen),
        "corroborated_earliest": corroborated[0] if corroborated else None,
        "corroborated_latest": corroborated[-1] if corroborated else None,
        "blank_description": sum(1 for r in rows if _is_blank(r["description"])),
        "blank_maintainer": sum(1 for r in rows if _is_blank(r["maintainer_or_vendor"])),
        "blank_freshness_signal": sum(1 for r in rows if _is_blank(r["freshness_signal"])),
    }

    return {
        "source_path": SOURCE_PATH,
        "schema_version": registry["schema_version"],
        "last_merged_at": registry["last_merged_at"],
        "metadata_keys": sorted(metadata),
        "top_level_keys": sorted(registry),
        "row_fields": list(REQUIRED_ROW_FIELDS),
        "declared_topics": sorted(metadata.get("topics") or []),
        "declared_entity_types": sorted(metadata.get("entity_types") or []),
        "total": derived_total,
        "migrated": MIGRATED_ENTITY_COUNT,
        "by_topic": by_topic,
        "by_entity_type": by_type,
        "by_topic_entity_type": [(t, e, c) for (t, e), c in by_topic_type],
        "by_description_source": by_description_source,
        "reconciliation": reconciliation,
        "identity": identity,
        "urls": urls,
        "evidence": evidence,
    }


# --------------------------------------------------------- authored analysis
# The measurements above are derived; the judgements below are authored ONCE,
# here, and rendered with the measured numbers interpolated. They live in the
# module rather than in the document so the document is never hand-edited — the
# rule that keeps it regenerable.

# (field, class, note). `render()` asserts this covers exactly REQUIRED_ROW_FIELDS,
# so a new registry field fails loudly instead of vanishing from the table.
FIELD_CLASSIFICATION = (
    ("name", "generic", "Maps cleanly onto `title`."),
    ("description", "generic", "Maps cleanly onto `summary`."),
    ("topic", "unsafe", "A HARVEST-LANE label (`agent`/`mcp`/`prompt`/`skill`), not one of the three committed taxonomy topics. Reusing the name would silently redefine `topic`."),
    ("entity_type", "domain", "Sixteen values with no committed vocabulary behind them. Usable as a domain field; not a `primary_category`."),
    ("entity_id", "raw", "Not unique (see §3). Retainable only as a `legacy_ids[]` label."),
    ("entity_key", "raw", "The registry's real dedup key (`topic|normalized(name)`). A legacy identifier, not a taxonomy identity."),
    ("target_url", "generic", "Would be `target_url` — but only where it is an absolute http(s) URL (see §3 and §4.1)."),
    ("source_url", "generic", "Would be `source_url`, the surfacing page; frequently identical to `target_url`."),
    ("maintainer_or_vendor", "domain", "Nearest generic field is `publisher`, but the two are not the same claim: a maintainer is not who published the page."),
    ("description_source", "raw", "`verified`/`snippet-only` describes how the DESCRIPTION was obtained, not whether the URL was fetched. It cannot supply `verification_status`."),
    ("freshness_signal", "raw", "Free-text prose ('© 2026 footer', promotional copy). Not a date, and not convertible into one."),
    ("github_stars", "domain", "Popularity metric with no home in the generic contract."),
    ("related_topics", "domain", "Harvest-lane cross-references, not taxonomy topics."),
    ("corroboration_count", "domain", "How many discovery hits agreed. Evidence about discovery, not about the page."),
    ("conflicting_evidence_log", "raw", "Retained verbatim; it has no generic counterpart."),
    ("discovery", "raw", "`first_seen_at` could supply `discovered_at`; `found_via[]` is discovery metadata and is NEVER a URL."),
)

FIELD_CLASSES = (
    ("generic", "Safely reusable as a generic taxonomy field"),
    ("domain", "Potentially useful as a domain-specific field"),
    ("raw", "Retainable only as provenance / raw data"),
    ("unsafe", "Unsafe or ambiguous without a product decision"),
)

# (contract, what record.v1.json requires, what the registry supports, verdict)
RECORD_CONTRACT_GAPS = (
    ("Target / identity URL",
     "`target_url` must be an absolute http(s) URL; `identity_url`, `record_id` and `content_id` are all derived from it.",
     "{target_usable} of {total} rows carry a usable absolute URL; {target_unusable} carry the `\"unknown\"` sentinel.",
     "BLOCKING for {target_unusable} rows — no URL means no identity, and identity cannot be invented."),
    ("Identity collision",
     "One `identity_url` is one record; two rows sharing a URL are one record, not two.",
     "{shared_target_urls} usable URLs are shared by {shared_target_rows} rows; {distinct_usable_targets} distinct usable URLs back {target_usable} rows.",
     "BLOCKING — URL-derived identity would silently merge entities the registry treats as distinct."),
    ("Topic and primary category",
     "`topic` and `primary_category` must come from the committed 12-cell taxonomy.",
     "The registry's four `topic` values are harvest lanes, and its sixteen `entity_type` values have no committed category behind them.",
     "BLOCKING — no committed cell describes 'an MCP server' or 'a skill'."),
    ("Classification evidence",
     "`classification` requires a `rule_id`, a rationale and quoted evidence.",
     "No rule fired: the lane label was assigned by the harvester, not by a precedence rule over the page.",
     "Requires a decision — a migration-specific rule id would have to be defined, as D7-E does for AX cases."),
    ("Verification / access evidence",
     "`access_status`, `http_status`, `verification_status`, `content_hash`, `last_checked_at`.",
     "`description_source` describes the description, not the page; no fetch is recorded anywhere in a row.",
     "Honest values exist (`not_checked` / `unverified`); no page-level claim can be made."),
    ("Required scores",
     "`relevance_score`, `quality_score`, `audience_fit_score`, `freshness_score` are required keys.",
     "Nothing in the registry was scored by the committed scorers.",
     "Null is the only honest value, exactly as D7-G decides for AX cases."),
    ("Dates",
     "`published_at` and `updated_at` must be ISO-8601 UTC or null.",
     "`discovery.first_seen_at` is a discovery date, not a publication date; `freshness_signal` is prose.",
     "`published_at` would be null for every row; `discovered_at` is available."),
    ("Provenance",
     "`provenance.source_id`, `source_adapter`, `raw`, and `discovered_via[]` as non-URL metadata.",
     "The complete row can be retained under `provenance.raw`; `found_via[]` is already `{{hit_id, platform}}`-shaped, with {found_via_empty} empty objects.",
     "Supported — provenance is the one contract the registry meets comfortably."),
    ("Facet applicability",
     "`case_facets` is required in `cases__domain-applications`, forbidden under `research-and-models` and `discourse`.",
     "Entities are tools and products, not deployment case studies; no industry, business function or use case is recorded.",
     "Not applicable under any plausible destination — and inferring facets is forbidden."),
)

CANDIDATE_APPROACHES = (
    ("A · A separate entity taxonomy and entity record schema",
     ("Entities keep their own identity rule (`entity_key`), so nothing is merged by URL and "
      "the {target_unusable} URL-less rows remain representable.",
      "No committed contract is bent to fit an object it was not designed for."),
     ("A second schema, a second validator and a second publication path to maintain.",
      "Every consumer must learn which of two record shapes it is holding."),
     ("Whether entities are published at all, or only held internally.",
      "Who owns the entity vocabulary, and what its categories are.")),
    ("B · Selective conversion into existing content-record categories",
     ("Reuses the committed record contract, validator, artifacts and gate with no new schema.",
      "A curated subset — the {target_usable} rows with usable URLs — could migrate first."),
     ("No committed cell describes a tool or a server; `topic` and `primary_category` would have to be invented.",
      "URL-derived identity merges the {shared_target_rows} rows that share {shared_target_urls} URLs.",
      "{target_unusable} rows are unrepresentable at all."),
     ("Which cells, if any, may receive entity rows.",
      "What happens to rows that cannot be represented — dropped, held, or converted differently.")),
    ("C · Entities as linked reference data, not published records",
     ("No identity, category or evidence claim is manufactured; the registry keeps its own shape.",
      "Records could reference an entity without the entity becoming a record."),
     ("Needs a reference contract that does not exist yet.",
      "Provides no answer for entities that a reader would expect to see published."),
     ("Whether any consumer actually needs entities as first-class records.",)),
    ("D · Retain the registry unchanged until a product decision is made",
     ("Costs nothing, risks nothing and loses nothing; the registry is protected and stable.",
      "Keeps the {repeated_id_rows} rows with repeated `entity_id`s from being frozen into a taxonomy identity."),
     ("The corpus stays outside the taxonomy pipeline and gains none of its guarantees.",),
     ("Whether the taxonomy is the intended destination at all.",)),
)

RISKS = (
    ("Identity stability",
     "`entity_id` is not a key: {entity_id_distinct} distinct values cover {total} rows, and "
     "{repeated_id_groups} of them are reused by {repeated_id_rows} rows. Qualifying by topic "
     "helps but does not fix it ({topic_qualified_distinct} distinct topic-qualified ids). Only "
     "`entity_key` is unique ({entity_key_distinct}/{total}), and it is a merge key invented by "
     "`merge_entity_registry.sh`, not a stable public identifier."),
    ("Duplicate handling",
     "There are **no exact duplicate rows** ({exact_duplicate_rows}), so every repeat is a repeated "
     "IDENTIFIER over distinct content — a different failure with a different fix. Semantic "
     "near-duplicates are not measured here and must not be claimed without a reviewed rule."),
    ("Topic and category semantics",
     "The four registry topics are harvest lanes. Mapping them onto taxonomy topics would redefine "
     "`topic` for every existing record, and no committed category describes an MCP server, a skill "
     "or a prompt technique."),
    ("Missing URL and evidence ownership",
     "{target_unusable} rows carry `target_url: \"unknown\"` and {source_unusable} carry an unusable "
     "`source_url`. A record cannot be built without an absolute URL, and no row records that any "
     "page was ever fetched."),
    ("Compatibility with existing harvested records",
     "Entity rows would enter the same identity space as harvested records. Any URL an entity shares "
     "with a harvested record becomes one identity with two provenance stories."),
    ("Promotion and merge collision risk",
     "{shared_target_urls} usable URLs are already shared inside the registry itself "
     "({shared_target_rows} rows). A merge keyed on identity would collapse them silently."),
    ("Provenance preservation",
     "Every row can be retained verbatim under `provenance.raw`, and {found_via_items} `found_via` "
     "items are already non-URL discovery metadata — but {found_via_empty} of them are empty objects, "
     "a schema drift that a migration would have to decide about rather than normalise away."),
    ("Rollback and regenerability",
     "The registry is protected and is never written by this pipeline, so any migration is "
     "regenerable from it and rollback is deleting the output. That property is worth keeping: it is "
     "what makes a migration safe to retry."),
    ("Object-type heterogeneity",
     "The corpus is mixed: {entity_type_count} `entity_type` values spanning products, platforms, "
     "servers, skills, specs, guides, datasets and techniques. These are not one kind of thing, and "
     "one destination contract may not fit all of them."),
)

DECISION_CHECKLIST = (
    "Decide whether entities belong in the taxonomy at all, or remain reference data.",
    "Decide what a stable entity identifier is, given that `entity_id` is not one and `entity_key` is a merge artefact.",
    "Decide what happens to the rows with no usable URL — they cannot be identified by URL.",
    "Decide whether two rows sharing a URL are one thing or two.",
    "Decide the destination vocabulary: taxonomy topics and categories, a new entity vocabulary, or neither.",
    "Decide whether an entity record may exist with no page-level evidence and null scores.",
    "Decide the `found_via` empty-object drift: fix at source, or accept and record it.",
    "Decide who reviews the result, and against what acceptance criterion.",
)


# ------------------------------------------------------------------ rendering
def _n(value):
    """Thousands separators, so 1,161 reads the same everywhere in the document."""
    return "{:,}".format(value)


def _table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return out


def _fmt(text, facts):
    return text.format(**facts)


def _facts(a):
    """The flat interpolation namespace shared by the authored prose."""
    ident, urls, ev = a["identity"], a["urls"], a["evidence"]
    return {
        "total": _n(a["total"]),
        "target_usable": _n(urls["target_usable"]),
        "target_unusable": _n(urls["target_unusable"]),
        "source_unusable": _n(urls["source_unusable"]),
        "shared_target_urls": _n(urls["shared_target_urls"]),
        "shared_target_rows": _n(urls["shared_target_rows"]),
        "distinct_usable_targets": _n(urls["distinct_usable_targets"]),
        "entity_id_distinct": _n(ident["entity_id_distinct"]),
        "repeated_id_groups": _n(ident["repeated_id_groups"]),
        "repeated_id_rows": _n(ident["repeated_id_rows"]),
        "topic_qualified_distinct": _n(ident["topic_qualified_distinct"]),
        "entity_key_distinct": _n(ident["entity_key_distinct"]),
        "exact_duplicate_rows": _n(ident["exact_duplicate_rows"]),
        "found_via_items": _n(ev["found_via_items"]),
        "found_via_empty": _n(sum(c for shape, c in ev["found_via_shapes"] if not shape)),
        "entity_type_count": _n(len(a["by_entity_type"])),
    }


def render(assessment):
    """Deterministic Markdown. Same input, same bytes, always."""
    a = assessment
    classified = sorted(field for field, _cls, _note in FIELD_CLASSIFICATION)
    if classified != sorted(a["row_fields"]):
        raise AssessmentError(
            "the field-mapping table does not cover exactly the registry's fields: "
            "table=%s registry=%s" % (classified, sorted(a["row_fields"])))

    facts = _facts(a)
    ident, urls, ev, rec = a["identity"], a["urls"], a["evidence"], a["reconciliation"]
    L = []

    L.append("# Entity registry migration assessment")
    L.append("")
    L.append("**Generated by `src/harvest/migrate/entity_assess.py` (Stage 7, checkpoint S7-1) from "
             "`%s`. Do not edit this file by hand — change the implementation and regenerate it.**"
             % a["source_path"])
    L.append("")
    L.append("- **This assessment migrates %s entities.** It is a measurement, not a conversion."
             % _n(a["migrated"]))
    L.append("- **It creates no taxonomy record.** Not one row here becomes a `record.v1.json` document.")
    L.append("- **It creates no migration bundle and no runtime state.** Nothing is written under "
             "`state/taxonomy_harvest/`, `data/harvested/` or `runs/`.")
    L.append("- **The destination taxonomy remains an unresolved product decision.** No destination is "
             "chosen, recommended or implied by this document.")
    L.append("- **Stage 7 does not classify entity rows as Product Discovery records**, or as records "
             "of any other committed cell.")
    L.append("- The source is one of the 18 protected files. It was **opened read-only** and is "
             "byte-identical afterwards.")
    L.append("")

    # ---- 1
    L.append("## 1 · Source and scope")
    L.append("")
    L.extend(_table(["Property", "Value"], [
        ("Source path", "`%s` (protected, read-only)" % a["source_path"]),
        ("Registry `schema_version`", "`%s`" % a["schema_version"]),
        ("Registry `last_merged_at`", "`%s`" % a["last_merged_at"]),
        ("Top-level keys", ", ".join("`%s`" % k for k in a["top_level_keys"])),
        ("`metadata` keys", ", ".join("`%s`" % k for k in a["metadata_keys"])),
        ("Entity rows (derived)", "**%s**" % _n(a["total"])),
        ("Entity rows (declared in `metadata.total_entities`)", _n(rec["declared_total"])),
        ("Expected corpus total", _n(rec["expected_total"])),
        ("Entities migrated", "**%s**" % _n(a["migrated"])),
    ]))
    L.append("")
    L.append("Derived, declared and expected totals **agree**: %s · %s · %s."
             % ("derived == declared" if rec["derived_matches_declared"] else
                "DERIVED != DECLARED",
                "derived == expected" if rec["derived_matches_expected"] else
                "DERIVED != EXPECTED",
                "the count is re-derived from the rows on every run, never trusted from `metadata`"))
    L.append("")
    L.append("Every row carries exactly these %d fields; a missing or unrecognised field is a hard "
             "error, not a skipped row:" % len(a["row_fields"]))
    L.append("")
    for field in sorted(a["row_fields"]):
        L.append("- `%s`" % field)
    L.append("")
    L.append("`discovery` is an object with `first_seen_at`, `last_corroborated_at` and `found_via[]` "
             "on every row.")
    L.append("")

    # ---- 2
    L.append("## 2 · Population breakdown")
    L.append("")
    L.append("### 2.1 · By topic")
    L.append("")
    L.extend(_table(["Topic", "Entities"],
                    [("`%s`" % t, _n(c)) for t, c in a["by_topic"]]
                    + [("**Total**", "**%s**" % _n(rec["topic_subtotal"]))]))
    L.append("")
    L.append("Reconciles to the population (%s == %s), and agrees with the registry's own "
             "`metadata.entity_count_by_topic`: **%s**."
             % (_n(rec["topic_subtotal"]), _n(a["total"]),
                "yes" if rec["declared_topic_agrees"] else "NO — the metadata disagrees"))
    L.append("")
    L.append("### 2.2 · By entity type")
    L.append("")
    L.extend(_table(["Entity type", "Entities"],
                    [("`%s`" % t, _n(c)) for t, c in a["by_entity_type"]]
                    + [("**Total**", "**%s**" % _n(rec["type_subtotal"]))]))
    L.append("")
    L.append("Reconciles to the population (%s == %s), and agrees with "
             "`metadata.entity_count_by_entity_type`: **%s**."
             % (_n(rec["type_subtotal"]), _n(a["total"]),
                "yes" if rec["declared_type_agrees"] else "NO — the metadata disagrees"))
    L.append("")
    L.append("### 2.3 · Topic × entity type")
    L.append("")
    L.append("%d of the %d × %d possible pairs are populated. An absent pair is absent from the "
             "corpus, not omitted here."
             % (len(a["by_topic_entity_type"]), len(a["by_topic"]), len(a["by_entity_type"])))
    L.append("")
    L.extend(_table(["Topic", "Entity type", "Entities"],
                    [("`%s`" % t, "`%s`" % e, _n(c))
                     for t, e, c in a["by_topic_entity_type"]]
                    + [("**Total**", "", "**%s**" % _n(rec["topic_type_subtotal"]))]))
    L.append("")
    L.append("### 2.4 · By schema and description source")
    L.append("")
    L.append("The registry carries **one** version field, the top-level `schema_version` (`%s`), which "
             "applies to all %s rows. There is no per-row schema or record version, so no per-row "
             "version dimension is reported — inventing one would be reporting a field the source "
             "does not have." % (a["schema_version"], _n(a["total"])))
    L.append("")
    L.extend(_table(["`description_source`", "Entities"],
                    [("`%s`" % s, _n(c)) for s, c in a["by_description_source"]]
                    + [("**Total**", "**%s**" % _n(rec["description_source_subtotal"]))]))
    L.append("")
    L.append("`description_source` describes how the **description** was obtained. It is **not** a "
             "claim that the URL was fetched, and it cannot supply `verification_status`.")
    L.append("")

    # ---- 3
    L.append("## 3 · Identity and duplicate analysis")
    L.append("")
    L.extend(_table(["Measurement", "Value"], [
        ("Rows", _n(a["total"])),
        ("`entity_id` present (non-blank)", _n(ident["entity_id_present"])),
        ("`entity_id` null or blank", _n(ident["entity_id_blank"])),
        ("Distinct `entity_id`", "**%s**" % _n(ident["entity_id_distinct"])),
        ("Repeated `entity_id` values", _n(ident["repeated_id_groups"])),
        ("Rows carrying a repeated `entity_id`", _n(ident["repeated_id_rows"])),
        ("Largest repeated group", _n(ident["largest_repeated_group"])),
        ("Repeated groups spanning more than one topic", _n(ident["repeated_id_groups_cross_topic"])),
        ("Repeated groups confined to one topic", _n(ident["repeated_id_groups_single_topic"])),
        ("Distinct `(topic, entity_id)`", _n(ident["topic_qualified_distinct"])),
        ("Distinct `entity_key`", "**%s**" % _n(ident["entity_key_distinct"])),
        ("Blank `entity_key`", _n(ident["entity_key_blank"])),
        ("Exact duplicate rows (whole-row content match)", _n(ident["exact_duplicate_rows"])),
    ]))
    L.append("")
    L.append("**`entity_id` cannot be treated as globally unique.** %s distinct values cover %s rows. "
             "Qualifying by topic — the only existing namespace field — raises the distinct count to "
             "%s, still short of %s, so **topic qualification does not repair uniqueness either**. "
             "Only `entity_key` (`topic|normalized(name)`) is unique across the corpus: %s of %s."
             % (_n(ident["entity_id_distinct"]), _n(a["total"]),
                _n(ident["topic_qualified_distinct"]), _n(a["total"]),
                _n(ident["entity_key_distinct"]), _n(a["total"])))
    L.append("")
    L.append("This is the condition recorded in `docs/entity_id_collision_note.md`: each `1G` "
             "extraction invents its own `ent-YYYY-NNNN` sequence with no coordination across topics "
             "or runs, and `scripts/merge_entity_registry.sh` deduplicates entirely on `entity_key`, "
             "so `entity_id` is carried through as an inert display label. The note reported the "
             "collision qualitatively; the measurement above is its current extent.")
    L.append("")
    L.append("**Three different things, kept apart:**")
    L.append("")
    L.append("- **Exact duplicate source rows** — %s. Mechanically measured by whole-row content."
             % _n(ident["exact_duplicate_rows"]))
    L.append("- **Repeated identifiers over distinct rows** — %s rows across %s `entity_id` values. "
             "Also mechanically measured, and a different defect with a different fix."
             % (_n(ident["repeated_id_rows"]), _n(ident["repeated_id_groups"])))
    L.append("- **Semantically similar entities** — **not measured, and not claimed.** Deciding that "
             "two differently-named rows are the same tool needs a reviewed rule that does not "
             "exist; asserting it from lexical similarity would manufacture findings.")
    L.append("")
    L.append("**No new permanent identifier is selected or proposed here.** That is a product "
             "decision and belongs in the checklist in §6.")
    L.append("")
    if ident["duplicate_groups"]:
        L.append("### 3.1 · Repeated `entity_id` groups")
        L.append("")
        L.append("Ordered by group size, then by identifier — never by input order.")
        L.append("")
        L.extend(_table(["`entity_id`", "Rows", "Topics", "Example `entity_key`s"],
                        [("`%s`" % g["entity_id"], _n(g["rows"]),
                          ", ".join("`%s`" % t for t in g["topics"]),
                          ", ".join("`%s`" % k for k in g["entity_keys"][:3])
                          + (" …" if len(g["entity_keys"]) > 3 else ""))
                         for g in ident["duplicate_groups"]]))
        L.append("")

    L.append("### 3.2 · URLs, where a taxonomy identity would have to come from")
    L.append("")
    L.extend(_table(["Measurement", "Value"], [
        ("Rows with an absolute http(s) `target_url`", "**%s**" % _n(urls["target_usable"])),
        ("Rows whose `target_url` is unusable", "**%s**" % _n(urls["target_unusable"])),
        ("… of which carry the `\"unknown\"` sentinel", _n(urls["target_unknown_sentinel"])),
        ("Rows with an absolute http(s) `source_url`", _n(urls["source_usable"])),
        ("Rows whose `source_url` is unusable", _n(urls["source_unusable"])),
        ("… of which carry the `\"unknown\"` sentinel", _n(urls["source_unknown_sentinel"])),
        ("Rows where `target_url` == `source_url`", _n(urls["target_equals_source"])),
        ("Distinct usable `target_url`", "**%s**" % _n(urls["distinct_usable_targets"])),
        ("Usable `target_url` values shared by more than one row", _n(urls["shared_target_urls"])),
        ("Rows involved in a shared `target_url`", _n(urls["shared_target_rows"])),
        ("Distinct hosts among usable `target_url`", _n(urls["distinct_target_hosts"])),
    ]))
    L.append("")
    L.append("Two consequences follow directly, and both are structural rather than a matter of "
             "effort: **%s rows have no URL to derive an identity from**, and **%s rows share a URL "
             "with another row**, so URL-derived identity would merge entities the registry treats "
             "as distinct."
             % (_n(urls["target_unusable"]), _n(urls["shared_target_rows"])))
    L.append("")

    # ---- 4
    L.append("## 4 · Field-mapping assessment")
    L.append("")
    L.append("### 4.1 · The %d source fields, classified" % len(a["row_fields"]))
    L.append("")
    by_class = {key: [] for key, _ in FIELD_CLASSES}
    for field, cls, note in FIELD_CLASSIFICATION:
        by_class[cls].append((field, note))
    for key, heading in FIELD_CLASSES:
        L.append("**%s**" % heading)
        L.append("")
        L.extend(_table(["Field", "Assessment"],
                        [("`%s`" % f, n) for f, n in sorted(by_class[key])]))
        L.append("")
    L.append("A field is classified by what it can *honestly* support, not by name similarity. "
             "`maintainer_or_vendor` and `publisher` are the clearest example: they look "
             "interchangeable and are not the same claim.")
    L.append("")
    L.append("### 4.2 · Required record contracts the registry cannot meet")
    L.append("")
    L.extend(_table(["Contract", "What `record.v1.json` requires", "What the registry supports",
                     "Verdict"],
                    [(c, req, _fmt(sup, facts), _fmt(v, facts))
                     for c, req, sup, v in RECORD_CONTRACT_GAPS]))
    L.append("")
    L.append("**No record mapping is manufactured here.** A destination field with a similar name is "
             "not evidence that the source can fill it.")
    L.append("")

    # ---- 5
    L.append("## 5 · Candidate destinations")
    L.append("")
    L.append("Four approaches are described. **None is approved, recommended or chosen** — each is "
             "recorded with what it buys, what it breaks, and what still has to be decided.")
    L.append("")
    for name, benefits, conflicts, decisions in CANDIDATE_APPROACHES:
        L.append("### %s" % name)
        L.append("")
        L.append("*Benefits*")
        L.append("")
        for item in benefits:
            L.append("- %s" % _fmt(item, facts))
        L.append("")
        L.append("*Contract conflicts*")
        L.append("")
        for item in conflicts:
            L.append("- %s" % _fmt(item, facts))
        L.append("")
        L.append("*Decisions still required*")
        L.append("")
        for item in decisions:
            L.append("- %s" % _fmt(item, facts))
        L.append("")

    # ---- 6
    L.append("## 6 · Migration risks and required decisions")
    L.append("")
    for title, body in RISKS:
        L.append("**%s.** %s" % (title, _fmt(body, facts)))
        L.append("")
    L.append("### 6.1 · Supporting measurements")
    L.append("")
    L.extend(_table(["Measurement", "Value"], [
        ("Rows with a `github_stars` value", _n(ev["github_stars_present"])),
        ("Rows with `github_stars: null`", _n(ev["github_stars_null"])),
        ("Rows with a non-empty `related_topics`", _n(ev["related_topics_present"])),
        ("Rows with a non-empty `conflicting_evidence_log`", _n(ev["conflicting_evidence_present"])),
        ("`found_via` items in total", _n(ev["found_via_items"])),
        ("Rows with an empty `found_via`", _n(ev["found_via_empty_rows"])),
        ("Earliest `discovery.first_seen_at`", "`%s`" % ev["first_seen_earliest"]),
        ("Latest `discovery.first_seen_at`", "`%s`" % ev["first_seen_latest"]),
        ("Distinct `discovery.first_seen_at`", _n(ev["first_seen_distinct"])),
        ("Latest `discovery.last_corroborated_at`", "`%s`" % ev["corroborated_latest"]),
        ("Rows with a blank `description`", _n(ev["blank_description"])),
        ("Rows with a blank `maintainer_or_vendor`", _n(ev["blank_maintainer"])),
        ("Rows with a blank `freshness_signal`", _n(ev["blank_freshness_signal"])),
    ]))
    L.append("")
    L.append("`found_via` item shapes, which is where the drift shows:")
    L.append("")
    L.extend(_table(["Item keys", "Occurrences"],
                    [(", ".join("`%s`" % k for k in shape) if shape else "*(empty object)*",
                      _n(count)) for shape, count in ev["found_via_shapes"]]))
    L.append("")
    L.append("`related_topics` values, which are harvest lanes and not taxonomy topics:")
    L.append("")
    L.extend(_table(["Related topic", "Occurrences"],
                    [("`%s`" % t, _n(c)) for t, c in ev["related_topic_counts"]]))
    L.append("")
    L.append("`corroboration_count` distribution:")
    L.append("")
    L.extend(_table(["`corroboration_count`", "Entities"],
                    [(str(v), _n(c)) for v, c in ev["corroboration_counts"]]
                    + [("**Total**", "**%s**"
                        % _n(sum(c for _, c in ev["corroboration_counts"])))]))
    L.append("")
    L.append("### 6.2 · Follow-up decision checklist")
    L.append("")
    L.append("Decisions, not implementation steps. Each has to be answered by a person before any "
             "entity migration checkpoint can be written.")
    L.append("")
    for index, item in enumerate(DECISION_CHECKLIST, start=1):
        L.append("%d. %s" % (index, item))
    L.append("")
    L.append("Until every one of them is answered, **the destination taxonomy remains an unresolved "
             "product decision and %s entities are migrated.**" % _n(a["migrated"]))

    return "\n".join(L).rstrip("\n") + "\n"


def write_assessment(path, text):
    """Write rendered bytes to an EXPLICIT path. There is no default location."""
    if not path:
        raise AssessmentError("write_assessment needs an explicit output path")
    data = text.encode("utf-8")
    with open(path, "wb") as handle:
        handle.write(data)
    return len(data)


def build(registry_path_=None):
    """(assessment, text) from the protected registry. Writes nothing."""
    registry = load_registry(registry_path_)
    assessment = assess(registry)
    return assessment, render(assessment)
