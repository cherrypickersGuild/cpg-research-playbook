#!/usr/bin/env python3
"""feed.py — RSS 2.0 and Atom, stdlib only. 22 of the 25 configured sources.

`xml.etree.ElementTree`, not feedparser: `requirements.txt` pins `jsonschema`
alone, and a feed parser is not worth a dependency when the two formats differ
in about thirty lines.

Namespaces are handled structurally — every tag is compared on its local name
after stripping `{uri}` — so Atom, RSS, Dublin Core and content:encoded all work
without a single per-source branch. There are no source-ID conditionals in this
file; a test asserts that.
"""
import urllib.parse
import xml.etree.ElementTree as ET

from .base import Adapter, AdapterError, RawCandidate, decode

# Atom rel values, in preference order. `alternate` is the human-readable page,
# which is what a candidate is; `enclosure` and `via` are not.
_ATOM_LINK_PREFERENCE = ("alternate", "")


def _local(tag):
    """`{http://www.w3.org/2005/Atom}entry` -> `entry`."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1] if tag.startswith("{") else tag


def _find_all(parent, *names):
    wanted = {n.lower() for n in names}
    return [c for c in parent if _local(c.tag).lower() in wanted]


def _first_text(parent, *names):
    for child in _find_all(parent, *names):
        text = "".join(child.itertext()).strip()
        if text:
            return text
    return None


class FeedAdapter(Adapter):
    name = "feed"
    expect_content_types = ("xml",)
    parse_error_reason = "feed_parse_error"
    empty_reason = "no_items_in_window"

    def parse(self, body, source, base_url):
        text = decode(body or b"")
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise AdapterError("feed is not well-formed XML: %s" % exc,
                               "feed_parse_error") from exc

        entries = self._entries(root)
        out = []
        for entry in entries:
            target = self._target_url(entry, base_url)
            if not target:
                # No target identity means nothing downstream can dedup, fetch
                # or publish it. Skipped, not an error: one malformed item does
                # not invalidate the feed.
                continue
            out.append(RawCandidate(
                target_url=target,
                title=_first_text(entry, "title"),
                published_at=_first_text(entry, "published", "updated",
                                         "pubDate", "date"),
                summary=_first_text(entry, "summary", "description", "encoded",
                                    "content"),
                publisher=self._publisher(entry, root),
            ))
        return out

    # ------------------------------------------------------------- internals
    @staticmethod
    def _entries(root):
        """RSS items live under <channel>; Atom entries hang off the root."""
        items = []
        for channel in _find_all(root, "channel"):
            items.extend(_find_all(channel, "item"))
        items.extend(_find_all(root, "item", "entry"))
        return items

    @staticmethod
    def _target_url(entry, base_url):
        """RSS <link>text</link>; Atom <link href=… rel=alternate/>."""
        candidates = []
        for link in _find_all(entry, "link"):
            href = link.get("href")
            if href:
                rel = (link.get("rel") or "").strip().lower()
                if rel in _ATOM_LINK_PREFERENCE:
                    candidates.append((_ATOM_LINK_PREFERENCE.index(rel), href))
                continue
            text = (link.text or "").strip()
            if text:
                candidates.append((0, text))
        if not candidates:
            # Fall back to a GUID that is itself a permalink, which several RSS
            # feeds use in place of <link>.
            guid = _first_text(entry, "guid", "id")
            if guid and guid.startswith(("http://", "https://")):
                candidates.append((0, guid))
        if not candidates:
            return None
        candidates.sort(key=lambda pair: pair[0])
        href = candidates[0][1].strip()
        # Relative references resolve against the document base, per the URL
        # contract. Canonicalization for dedup stays the pool's job.
        return urllib.parse.urljoin(base_url, href) if base_url else href

    @staticmethod
    def _publisher(entry, root):
        for parent in (entry, root):
            for name in ("author", "creator", "source"):
                for node in _find_all(parent, name):
                    named = _first_text(node, "name")
                    if named:
                        return named
                    text = "".join(node.itertext()).strip()
                    if text:
                        return text
        for channel in _find_all(root, "channel"):
            title = _first_text(channel, "title")
            if title:
                return title
        return _first_text(root, "title")
