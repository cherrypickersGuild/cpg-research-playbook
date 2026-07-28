#!/usr/bin/env python3
"""gen_facet_schema.py — emit schemas/harvest/facets.generated.v1.json.

Why a generated file exists at all. The vocabularies under config/harvest/facets/
are the single source of truth, and record.v1.json deliberately checks only slug
SHAPE, so a shape-only schema would accept an invalid slug. Artifacts are
published to cherryinthehaystack.com and may be validated by consumers who have
no access to this repository, so "clone the repo and run check_facets.py" is not
an answer for them. This file carries the real enums, so a published artifact
validates standalone with any off-the-shelf JSON Schema validator.

The cost of generation is drift, so it is guarded:

  * deterministic output — sorted keys, fixed indent, LF newlines, NO timestamp,
    so regenerating an unchanged vocabulary is a byte-identical no-op;
  * a header recording each source vocabulary's config_version, vocabulary_version
    and SHA-256, so a stale file can be identified without re-reading the configs;
  * `--check` regenerates in memory and diffs, which is what the test suite runs;
  * the write is mkstemp + os.replace INSIDE the destination directory, so
    schemas/harvest/ never contains a half-written file. That matters more than
    usual here: src/harvest/schema.py loads EVERY *.json in that directory into
    one cached registry, so a truncated file would break all seven existing
    suites, not just this one.

  Usage:
    python scripts/harvest/gen_facet_schema.py [--out-dir DIR] [--check] [--quiet]

Exit 0: written, or (with --check) already up to date. Exit 1: drift or error.
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.harvest import facets  # noqa: E402

OUT_NAME = "facets.generated.v1.json"
SCHEMA_ID = "https://cherryinthehaystack.com/schemas/harvest/" + OUT_NAME

NEVER_HAND_EDIT = (
    "GENERATED FILE — DO NOT HAND-EDIT. Produced by scripts/harvest/gen_facet_schema.py "
    "from config/harvest/facets/*.v1.json, which are the single source of truth. "
    "Any manual change is overwritten by the next generation and is reported as drift "
    "by tests/test_taxonomy_facets.sh."
)


def _sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def build(facets_dir=None):
    """The generated document, as a plain dict. Pure — writes nothing."""
    d = facets_dir or facets.FACETS_DIR

    sources = []
    axis_slugs = {}
    for axis in facets.AXES:
        path = os.path.join(d, facets.AXIS_FILE[axis])
        doc = facets.load_vocabulary(axis, d)
        axis_slugs[axis] = sorted(e["slug"] for e in doc["entries"])
        sources.append({
            "file": facets.AXIS_FILE[axis],
            "axis": axis,
            "config_version": doc["config_version"],
            "vocabulary_version": doc["vocabulary_version"],
            "entry_count": len(doc["entries"]),
            "sha256": _sha256_file(path),
        })

    evidence = {
        "type": "object",
        "additionalProperties": False,
        "required": ["field", "matched_term", "quote"],
        "properties": {
            "field": {"enum": ["title", "summary", "body", "publisher",
                               "target_url", "legacy_field"]},
            "matched_term": {"type": "string", "minLength": 2},
            "quote": {"type": "string", "minLength": 3, "maxLength": 400},
            "offset": {"type": ["integer", "null"]},
        },
    }

    def axis_multi(axis):
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["slug", "confidence", "evidence"],
            "properties": {
                "slug": {"enum": axis_slugs[axis]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": "array", "minItems": 1,
                             "$ref": "#/$defs/facet_evidence_array_items"},
            },
        }

    doc = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "Case facets — generated slug constraints (v1)",
        "description": (
            "Standalone, enum-bearing constraints for case_facets. record.v1.json checks slug "
            "SHAPE only; this file checks MEMBERSHIP, so a published artifact validates without "
            "repository access. " + NEVER_HAND_EDIT),

        "_generated": {
            "never_hand_edit": NEVER_HAND_EDIT,
            "generator": "scripts/harvest/gen_facet_schema.py",
            "deterministic": ("sorted keys, indent 2, LF newlines, no timestamp — regenerating "
                              "an unchanged vocabulary is byte-identical"),
            "sources": sources,
        },

        "type": "object",
        "properties": {"case_facets": {"$ref": "#/$defs/case_facets"}},

        "$defs": {
            "industry_slug": {"enum": axis_slugs["industry"]},
            "business_function_slug": {"enum": axis_slugs["business_function"]},
            "use_case_type_slug": {"enum": axis_slugs["use_case_type"]},

            "facet_evidence": evidence,
            "facet_evidence_array_items": {"items": evidence},

            "facet_axis_single_industry": {
                "type": "object",
                "additionalProperties": False,
                "required": ["primary", "secondary", "confidence", "evidence"],
                "properties": {
                    "primary": {"oneOf": [{"$ref": "#/$defs/industry_slug"},
                                          {"type": "null"}]},
                    "secondary": {"type": "array", "maxItems": 2, "uniqueItems": True,
                                  "items": {"$ref": "#/$defs/industry_slug"}},
                    "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                    "evidence": {"type": "array", "items": evidence},
                },
            },
            "facet_axis_multi_business_function": axis_multi("business_function"),
            "facet_axis_multi_use_case_type": axis_multi("use_case_type"),

            "facet_unresolved": {
                "type": "object",
                "additionalProperties": False,
                "required": ["axis", "state", "detail"],
                "properties": {
                    "axis": {"enum": list(facets.AXES)},
                    "state": {"enum": list(facets.UNRESOLVED_STATES)},
                    "term": {"type": ["string", "null"]},
                    "detail": {"type": "string", "minLength": 3},
                },
            },

            "case_facets": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "required": ["facets_version", "vocabulary_versions", "classification_state",
                             "industry", "business_functions", "use_case_types"],
                "properties": {
                    "facets_version": {"type": "integer", "const": facets.FACETS_VERSION},
                    "vocabulary_versions": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["industries", "business_functions", "use_case_types"],
                        "properties": {
                            "industries": {"type": "integer"},
                            "business_functions": {"type": "integer"},
                            "use_case_types": {"type": "integer"},
                        },
                    },
                    "classification_state": {"enum": ["resolved", "unresolved"]},
                    "industry": {"$ref": "#/$defs/facet_axis_single_industry"},
                    "business_functions": {
                        "type": "array", "maxItems": 4,
                        "items": {"$ref": "#/$defs/facet_axis_multi_business_function"}},
                    "use_case_types": {
                        "type": "array", "maxItems": 4,
                        "items": {"$ref": "#/$defs/facet_axis_multi_use_case_type"}},
                    "unresolved": {"type": "array",
                                   "items": {"$ref": "#/$defs/facet_unresolved"}},
                },
            },
        },
    }
    return doc


def render(doc):
    """Deterministic bytes. sort_keys is what makes regeneration a no-op."""
    return (json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_atomic(path, payload):
    """mkstemp + os.replace in the DESTINATION directory — never a partial file."""
    import tempfile
    dest_dir = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=dest_dir, prefix=".facets_gen_", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate the facet constraint schema.")
    p.add_argument("--facets-dir", default=None)
    p.add_argument("--out-dir", default=os.path.join(ROOT, "schemas", "harvest"))
    p.add_argument("--check", action="store_true",
                   help="do not write; exit 1 if the on-disk file differs")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    facets.clear_caches()
    try:
        payload = render(build(args.facets_dir))
    except Exception as exc:                      # noqa: BLE001 — reported, not swallowed
        print("ERROR: cannot build the facet schema: %s" % exc, file=sys.stderr)
        return 1

    out = os.path.join(args.out_dir, OUT_NAME)

    if args.check:
        if not os.path.isfile(out):
            print("ERROR: %s does not exist — run gen_facet_schema.py" % out, file=sys.stderr)
            return 1
        with open(out, "rb") as f:
            current = f.read()
        if current != payload:
            print("ERROR: %s is STALE or hand-edited (%d bytes on disk, %d generated).\n"
                  "       Regenerate: python scripts/harvest/gen_facet_schema.py"
                  % (out, len(current), len(payload)), file=sys.stderr)
            return 1
        if not args.quiet:
            print("[gen_facet_schema] OK — %s matches the vocabularies exactly" % OUT_NAME)
        return 0

    write_atomic(out, payload)
    if not args.quiet:
        print("[gen_facet_schema] wrote %s (%d bytes)" % (out, len(payload)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
