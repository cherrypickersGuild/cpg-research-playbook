#!/usr/bin/env python3
"""jsonapi.py — configuration-driven JSON extraction. 2 configured sources.

Everything source-specific lives in `config/harvest/topics/*.json` under the
source's `jsonapi` object — `items_path` and a dotted `field_map`. There is no
per-API parser here and there must never be one: the Federal Register and HN
Algolia sources differ only by configuration, which is what makes adding a third
API a config edit rather than a code change.

Dotted paths address nested objects and list indices alike, so
`agencies.0.name` reads the first agency's name. A path that does not resolve
yields None for an optional field, and is an explicit skip for the one field
that is not optional: `target_url`.
"""
import json

from .base import Adapter, AdapterError, RawCandidate, decode

_MISSING = object()


def resolve_path(node, dotted):
    """Walk a dotted path through dicts and lists. Returns _MISSING if absent.

    Numeric segments index lists; everything else keys dicts. A numeric segment
    against a dict is tried as a key first, so an API with literal "0" keys is
    still addressable.
    """
    current = node
    for segment in dotted.split("."):
        if isinstance(current, dict):
            if segment in current:
                current = current[segment]
                continue
            return _MISSING
        if isinstance(current, list):
            if not segment.lstrip("-").isdigit():
                return _MISSING
            index = int(segment)
            if -len(current) <= index < len(current):
                current = current[index]
                continue
            return _MISSING
        return _MISSING
    return current


def _scalar(value):
    """JSON values that can stand in for a text field; others are dropped."""
    if value is _MISSING or value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return None          # a flag is not a title
    if isinstance(value, (int, float)):
        return str(value)
    return None              # dict/list is a mapping error, not a text value


class JsonApiAdapter(Adapter):
    name = "jsonapi"
    expect_content_types = ("json",)
    parse_error_reason = "schema_mapping_failed"
    empty_reason = "no_items_in_window"

    def parse(self, body, source, base_url):
        config = source.get("jsonapi") or {}
        items_path = config.get("items_path")
        field_map = config.get("field_map") or {}
        if not items_path or "target_url" not in field_map:
            raise AdapterError(
                "source %r lacks items_path or a target_url field mapping"
                % source.get("source_id"), "schema_mapping_failed")

        try:
            document = json.loads(decode(body or b""))
        except ValueError as exc:
            raise AdapterError("response is not valid JSON: %s" % exc,
                               "schema_mapping_failed") from exc

        items = resolve_path(document, items_path)
        if items is _MISSING:
            raise AdapterError("items_path %r not present in the response"
                               % items_path, "schema_mapping_failed")
        if not isinstance(items, list):
            raise AdapterError(
                "items_path %r resolved to %s, expected a list"
                % (items_path, type(items).__name__), "schema_mapping_failed")

        out = []
        for item in items:
            if not isinstance(item, (dict, list)):
                # A scalar where an object was expected is a mapping failure,
                # not an empty window: the shape contract is broken.
                raise AdapterError(
                    "items_path %r contains %s, expected objects"
                    % (items_path, type(item).__name__), "schema_mapping_failed")
            target = _scalar(resolve_path(item, field_map["target_url"]))
            if not target or not target.startswith(("http://", "https://")):
                # Missing or non-absolute target: skipped deterministically.
                continue
            out.append(RawCandidate(
                target_url=target,
                title=_scalar(resolve_path(item, field_map["title"]))
                if "title" in field_map else None,
                published_at=_scalar(resolve_path(item, field_map["published_at"]))
                if "published_at" in field_map else None,
                summary=_scalar(resolve_path(item, field_map["summary"]))
                if "summary" in field_map else None,
                publisher=_scalar(resolve_path(item, field_map["publisher"]))
                if "publisher" in field_map else None,
            ))
        return out
