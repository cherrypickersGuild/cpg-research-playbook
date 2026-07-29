#!/usr/bin/env python3
"""seed.py — bounded index reader. 1 configured source (anthropic-customers).

This is the adapter most at risk of quietly becoming a crawler, so the property
that stops it is structural rather than configured:

    _SEED_DEPTH = 1     module constant, not a parameter, not config-reachable

There is no queue, no recursion and no second pass over a child. The adapter
reads ONE index body, emits the qualifying `<a href>` targets as candidates, and
stops. It never fetches a child body — a child that is itself an index is simply
a candidate, not something to expand — and it assigns no target-fetch or
extraction ownership. Those are Stage 4's.

`path_prefix_allowlist` FAILS CLOSED: an empty or missing list qualifies
nothing, so a config typo yields an honest zero result instead of the whole
site.
"""
import urllib.parse
from html.parser import HTMLParser

from .base import Adapter, AdapterError, RawCandidate, decode

# Structural, not configurable. Changing this to anything else makes this a
# crawler and requires its own approved contract.
_SEED_DEPTH = 1


class _AnchorCollector(HTMLParser):
    """Collect `<a href>` in document order, with their link text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        self._flush()
        for key, value in attrs:
            if key.lower() == "href" and value:
                self._href = value.strip()
                self._text = []
                return

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a":
            self._flush()

    def _flush(self):
        if self._href is not None:
            self.anchors.append((self._href, "".join(self._text).strip() or None))
            self._href, self._text = None, []

    def close(self):
        super().close()
        self._flush()


class SeedAdapter(Adapter):
    name = "seed"
    expect_content_types = ("html",)
    parse_error_reason = "index_parse_failed"
    empty_reason = "no_links_matched_allowlist"

    def parse(self, body, source, base_url):
        assert _SEED_DEPTH == 1, "seed depth is structural and must remain 1"
        config = source.get("seed") or {}
        allowlist = tuple(config.get("path_prefix_allowlist") or ())
        same_host_only = config.get("same_host_only", True)
        max_children = config.get("max_children")

        parser = _AnchorCollector()
        try:
            parser.feed(decode(body or b""))
            parser.close()
        except Exception as exc:                      # noqa: BLE001
            # html.parser is lenient by design, so this is rare — but malformed
            # markup must never become an unbounded anything.
            raise AdapterError("index could not be parsed: %s" % exc,
                               "index_parse_failed") from exc

        index_host = urllib.parse.urlsplit(base_url).hostname if base_url else None
        seen, out = set(), []
        for href, text in parser.anchors:
            resolved = urllib.parse.urljoin(base_url, href) if base_url else href
            parts = urllib.parse.urlsplit(resolved)
            if parts.scheme not in ("http", "https"):
                continue                              # mailto:, javascript:, …
            if same_host_only and index_host and parts.hostname != index_host:
                continue
            if not allowlist or not parts.path.startswith(allowlist):
                continue                              # fails closed on an empty list
            # In-page duplicates collapse; the first occurrence wins, so output
            # order stays document order.
            if resolved in seen:
                continue
            seen.add(resolved)
            out.append(RawCandidate(target_url=resolved, title=text))

        # max_children is the seed's own bound, applied before the shared
        # max_candidates cap; both drop in document order.
        if max_children is not None:
            out = out[:int(max_children)]
        return out
