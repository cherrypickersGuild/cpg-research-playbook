"""base.py — the suspicious-URL guard (Stage 7, checkpoint S7-2).

D7-H. One legacy URL goes in; either it is refused with the exact rule that
refused it, or it is not. **The guard never rewrites a URL** — it has no output
channel for a replacement, by construction: `GuardMatch` carries a rule id and a
detail and nothing else.

**Structure, never substrings** (erratum E24). Read as substring matching, the
master plan's wording rejects five legitimate pages in the protected AX corpus:
four `cloud.google.com` vendor-blog posts caught by the fragment `google.`, and
one LinkedIn engineering article whose path merely contains a `/search/` segment.
So every predicate here is host EQUALITY or a whole path SEGMENT, and the query
is parsed into keys rather than searched as text.

`urlkey.registrable_host` is deliberately NOT used. It is the committed authority
on registrable domains and stays that way — but the registrable domain of
`cloud.google.com` is `google.com`, so using it here would reintroduce exactly
the defect E24 records. Full-host equality is the contract D7-H fixed.

Pure: no filesystem, no registry, no record, no schema, no clock, no environment,
no subprocess, no network, no CLI, no serialization, no module-global mutable
state. Importing this module does nothing but define constants and functions.
"""
import dataclasses
import urllib.parse

# The four committed override rule ids, in committed precedence order. This is
# the ONE place the vocabulary is written down: `migration_overrides.v1.json`
# names the same four and is never edited to add a synonym.
SUSPICIOUS_RULE_IDS = ("search_engine_host", "search_query_path",
                       "feed_path", "index_page")

# Full hosts, never fragments and never registrable domains — see the module
# docstring. `cloud.google.com` is not in this set and must never match it.
SEARCH_ENGINE_HOSTS = frozenset({
    "google.com", "www.google.com",
    "bing.com", "www.bing.com",
    "duckduckgo.com", "www.duckduckgo.com",
    "baidu.com", "www.baidu.com",
    "yandex.com", "www.yandex.com", "yandex.ru", "www.yandex.ru",
})

# A host whose FIRST label is exactly this is a search endpoint (`search.foo.com`).
# First label, not a substring: `research.foo.com` is not a search endpoint.
SEARCH_HOST_LABEL = "search"

# Query parameter NAMES that carry a search term. Matched exactly against parsed
# keys — never against a key that merely contains one, and never against a value.
SEARCH_QUERY_KEYS = ("q", "query", "s")

# Whole last path segments meaning "this is a feed, not an article".
FEED_SEGMENTS = frozenset({"feed", "rss", "atom"})

# Index/list structural markers.
README_HOST = "raw.githubusercontent.com"
README_BASENAME = "readme.md"
AWESOME_SEGMENT_PREFIX = "awesome-"
INDEX_SEGMENTS = ("category", "tag")
PAGINATION_SEGMENT = "page"


class MigrationInputError(ValueError):
    """Input that is not a legacy URL this guard can examine at all.

    Deliberately NOT one of the four suspicious verdicts: "this is not a URL" and
    "this is a search page" are different findings, and collapsing them would
    file a malformed row under a rule that never looked at it.
    """


@dataclasses.dataclass(frozen=True)
class GuardMatch:
    """Why a URL was refused. Frozen, value-comparable, and carries no URL.

    There is no `suggested_url`, no `rewritten_url` and no `canonical_url` field:
    the guard refuses, and a type that cannot express a replacement cannot leak
    one.
    """
    rule_id: str
    detail: str


def _parts(url):
    """Split a raw legacy URL, or refuse it. Nothing is repaired or coerced."""
    if not isinstance(url, str) or not url.strip():
        raise MigrationInputError(
            "a legacy URL must be a non-empty string, got %r" % (url,))
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError as exc:
        raise MigrationInputError("%r is not a parseable URL: %s" % (url, exc))
    if parts.scheme not in ("http", "https"):
        raise MigrationInputError(
            "%r is not an absolute http(s) URL (scheme %r). The guard refuses to "
            "prepend a scheme or otherwise repair it." % (url, parts.scheme))
    if not parts.hostname:
        raise MigrationInputError("%r has no host" % (url,))
    return parts


def _segments(path):
    """The non-empty path segments, in order. `/a/b/` -> ['a', 'b']."""
    return [segment for segment in path.split("/") if segment]


def _query_keys(query):
    """Parsed query parameter NAMES. Values are never examined."""
    return [key for key, _value in
            urllib.parse.parse_qsl(query, keep_blank_values=True)]


# ------------------------------------------------------------- the four rules
def _search_engine_host(parts, segments):
    host = parts.hostname.lower()          # host case is not significant in URLs
    if host in SEARCH_ENGINE_HOSTS:
        return "host %r is a committed search-engine host" % host
    labels = host.split(".")
    if labels and labels[0] == SEARCH_HOST_LABEL and len(labels) > 1:
        return "host %r begins with the label %r" % (host, SEARCH_HOST_LABEL + ".")
    return None


def _search_query_path(parts, segments):
    if segments and segments[-1].lower() == "search":
        return "the last path segment is 'search'"
    keys = _query_keys(parts.query)
    for name in SEARCH_QUERY_KEYS:         # committed order, so ties are stable
        if name in keys:
            return "the query carries the search parameter %r" % name
    return None


def _feed_path(parts, segments):
    if segments and segments[-1].lower() in FEED_SEGMENTS:
        return "the last path segment is %r, which names a feed" % segments[-1].lower()
    return None


def _index_page(parts, segments):
    if parts.hostname.lower() == README_HOST and segments \
            and segments[-1].lower() == README_BASENAME:
        return "a %s path ending in %r is a repository index, not an item page" \
            % (README_HOST, segments[-1])
    for segment in segments:
        if segment.lower().startswith(AWESOME_SEGMENT_PREFIX):
            return "the path segment %r begins with %r" % (segment, AWESOME_SEGMENT_PREFIX)
    for segment in segments:
        if segment.lower() in INDEX_SEGMENTS:
            return "the path carries the index segment %r" % segment.lower()
    if len(segments) >= 2 and segments[-2].lower() == PAGINATION_SEGMENT \
            and segments[-1].isdigit():
        return "the path ends with the pagination segments '/%s/%s'" \
            % (PAGINATION_SEGMENT, segments[-1])
    return None


# Rule id -> predicate, in committed precedence order. A URL that satisfies more
# than one rule is reported under the FIRST one here, so the same URL always
# produces the same rule id and the same detail.
_RULES = (
    (SUSPICIOUS_RULE_IDS[0], _search_engine_host),
    (SUSPICIOUS_RULE_IDS[1], _search_query_path),
    (SUSPICIOUS_RULE_IDS[2], _feed_path),
    (SUSPICIOUS_RULE_IDS[3], _index_page),
)


# ---------------------------------------------------------------- public API
def suspicious_url_match(url):
    """The complete match, or None. Never a replacement URL.

    Raises `MigrationInputError` for anything that is not an absolute http(s)
    URL: that is a malformed input, not a suspicious one.
    """
    parts = _parts(url)
    segments = _segments(parts.path)
    for rule_id, predicate in _RULES:
        detail = predicate(parts, segments)
        if detail is not None:
            return GuardMatch(rule_id=rule_id, detail=detail)
    return None


def looks_like_index_or_search(url):
    """Boolean convenience over `suspicious_url_match`. Same refusals."""
    return suspicious_url_match(url) is not None
