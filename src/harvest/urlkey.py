#!/usr/bin/env python3
"""urlkey.py — conservative URL canonicalization and stable record identity.

Two separate jobs, deliberately kept apart:

  canonicalize_string(url)   Pure string normalization. Performs ONLY operations
                             that RFC 3986 (or an explicit versioned config rule)
                             guarantees preserve the identity of the resource.
  content_id / record_id     Stable hashes over the IMMUTABLE identity_url.

The governing principle is: **prefer a false negative over a destructive
false-positive merge.** Keeping two records that turn out to be the same thing
is recoverable — an alias joins them later. Collapsing two records that were
actually different destroys information that no later step can recover.

So the things people usually "just normalize" are NOT done here:

  http: -> https:        Not guaranteed equivalent. Becomes an alias only on an
                         observed 301/308, a verified rel=canonical, or an
                         explicit per-domain rule. A 302/307 never rewrites
                         identity — a temporary redirect is temporary.
  strip "www."           Same class of assumption. Alias-only.
  strip trailing slash   "/a" and "/a/" are distinct resources in RFC 3986.
                         Alias-only.
  sort query parameters  Parameter order is content-significant on some sites,
                         and repeated keys (?tag=x&tag=y) carry order. Sorting
                         happens only under a per-domain rule.
  strip fragments        Preserved by default; a fragment can be the whole
                         resource identifier in a hash-routed application.

What IS done is listed in canonicalize_string()'s docstring.
"""
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, quote, unquote

# --------------------------------------------------------------------------- config defaults
# Tracking parameters removed unconditionally. This is an explicit allowlist of
# things to STRIP, never a heuristic. Parameters that merely look like tracking
# are left alone -- see NEVER_STRIP below for why that matters.
DEFAULT_TRACKING_PARAMS = frozenset([
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_source_platform", "utm_creative_format", "utm_marketing_tactic",
    "gclid", "gclsrc", "dclid", "gbraid", "wbraid",
    "fbclid", "msclkid", "twclid", "igshid", "ttclid", "yclid",
    "mc_cid", "mc_eid", "_hsenc", "_hsmi",
    "vero_id", "vero_conv", "oly_anon_id", "oly_enc_id",
    "s_cid", "ck_subscriber_id",
])

# Documented non-strip list. These are frequently assumed to be tracking and are
# not: "?ref=" selects a content variant on some sites, "?source=" is part of the
# path identity on others, and the rest are ordinary content selectors. Recorded
# here so a future reader does not "helpfully" add them to the strip list.
NEVER_STRIP = frozenset(["ref", "source", "id", "p", "q", "v", "page", "t", "si"])

DEFAULT_PORTS = {"http": "80", "https": "443"}

# RFC 3986 unreserved set: these may be percent-decoded without changing meaning.
_UNRESERVED = re.compile(r"%(2[DdEe]|3[0-9]|[46][1-9A-Fa-f]|[57][0-9Aa]|5[Ff]|7[Ee])")

_PCT = re.compile(r"%[0-9A-Fa-f]{2}")


class UrlError(ValueError):
    """A URL that cannot be canonicalized into a usable identity."""


# --------------------------------------------------------------------------- helpers
def _normalize_percent_encoding(s):
    """Uppercase percent-encoding hex digits and decode unreserved octets.

    RFC 3986 6.2.2.1/6.2.2.2: percent-encodings are case-insensitive, and
    unreserved characters are equivalent whether encoded or not. Both are safe.
    """
    def up(m):
        return m.group(0).upper()
    s = _PCT.sub(up, s)

    # Decode only unreserved characters; anything else keeps its encoding,
    # because decoding a reserved character (e.g. %2F -> /) would change the
    # structure of the URL.
    def dec(m):
        return unquote(m.group(0))
    return _UNRESERVED.sub(dec, s)


def _remove_dot_segments(path):
    """RFC 3986 5.2.4 — resolve "." and ".." without touching anything else."""
    if not path:
        return path
    leading = path.startswith("/")
    trailing = path.endswith("/") and len(path) > 1
    out = []
    for seg in path.split("/"):
        if seg == ".":
            continue
        if seg == "..":
            if out:
                out.pop()
            continue
        if seg == "" :
            continue
        out.append(seg)
    result = "/".join(out)
    if leading:
        result = "/" + result
    if trailing and not result.endswith("/"):
        result += "/"
    return result or ("/" if leading else "")


def registrable_host(host):
    """Best-effort registrable domain, used only for same-domain trust checks.

    Deliberately simple: the last two labels. There is no public-suffix list in
    this repo and adding a network-fetched one would be a new dependency, so
    this is intentionally conservative in the direction that matters -- it may
    treat "a.co.uk" and "b.co.uk" as the same registrable domain, which makes
    the SAME-domain canonical-tag path slightly more permissive than ideal.
    That path still requires a syntactic + robots check, and the cross-domain
    path (the one with real risk) is unaffected.
    """
    host = (host or "").lower().strip(".")
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    return ".".join(parts[-2:])


def is_hash_route(fragment):
    """True when the fragment is structurally a route rather than an anchor.

    Only the unambiguous forms: hashbang ("#!"), router path ("#/") and a
    query-bearing fragment ("#?"). Everything else is treated as UNKNOWN, not as
    an anchor -- see should_strip_fragment().
    """
    if not fragment:
        return False
    return fragment.startswith("!") or fragment.startswith("/") or fragment.startswith("?")


def should_strip_fragment(fragment, host, domain_rules=None, anchor_evidence=None):
    """Decide whether a fragment may be dropped. Default: NO.

    A fragment is stripped only when one of these holds:

      1. a versioned per-domain rule declares ordinary-anchor stripping safe for
         this host (`strip_ordinary_anchors: true`); or
      2. fetched-document evidence confirms the fragment names an ordinary
         in-document anchor -- an element with that id/name exists in the body --
         AND the host is not configured for hash routing.

    Structure alone is never sufficient: "#dashboard" is not an anchor merely
    because it lacks a leading "/" or "!".
    """
    if not fragment:
        return False

    rules = (domain_rules or {}).get(registrable_host(host), {})

    # A hash-routed application encodes the resource in the fragment; nothing
    # may strip it.
    if rules.get("hash_routing"):
        return False
    if is_hash_route(fragment):
        return False

    if rules.get("strip_ordinary_anchors"):
        return True

    if anchor_evidence is not None and fragment in anchor_evidence:
        return True

    return False


# --------------------------------------------------------------------------- canonicalization
def canonicalize_string(url, tracking_params=None, domain_rules=None,
                        anchor_evidence=None):
    """Return the canonical string form of a URL.

    Operations performed (each provably identity-preserving):
      1. trim surrounding whitespace;
      2. lowercase the scheme and host ONLY (RFC 3986 6.2.2.1) -- path, query
         and fragment keep their case;
      3. drop the default port for the scheme;
      4. normalize percent-encoding (uppercase hex, decode unreserved);
      5. resolve dot-segments in the path (RFC 3986 5.2.4);
      6. remove ONLY the configured tracking parameters, preserving the original
         order and multiplicity of everything else;
      7. drop the fragment only when should_strip_fragment() authorizes it.

    Optionally, under an explicit per-domain rule, sort the remaining query
    parameters (`query_sort: true`).

    Raises UrlError for anything without a usable scheme and host, so a relative
    or malformed URL can never become an identity.
    """
    if not isinstance(url, str):
        raise UrlError("url must be a string, got %r" % type(url).__name__)
    raw = url.strip()
    if not raw:
        raise UrlError("empty url")

    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise UrlError("unparseable url %r: %s" % (url, exc))

    scheme = (parts.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise UrlError("unsupported scheme %r in %r (only http/https)" % (scheme, url))

    host = (parts.hostname or "").lower()
    if not host:
        raise UrlError("url %r has no host" % (url,))

    # Userinfo is dropped: credentials are never part of a public resource
    # identity, and keeping them would leak them into artifacts and filenames.
    port = parts.port
    netloc = host
    if port is not None and str(port) != DEFAULT_PORTS.get(scheme):
        netloc = "%s:%d" % (host, port)

    path = _normalize_percent_encoding(parts.path or "")
    path = _remove_dot_segments(path)
    if path == "":
        path = "/"

    strip = DEFAULT_TRACKING_PARAMS if tracking_params is None else frozenset(tracking_params)
    rules = (domain_rules or {}).get(registrable_host(host), {})

    query = ""
    if parts.query:
        # keep_blank_values: "?a=" is not the same request as "?a" absent.
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        kept = [(k, v) for k, v in pairs if k not in strip]
        if rules.get("query_sort"):
            kept.sort(key=lambda kv: (kv[0], kv[1]))
        query = urlencode(kept, doseq=False, quote_via=quote, safe="")
        query = _normalize_percent_encoding(query)

    fragment = parts.fragment or ""
    if should_strip_fragment(fragment, host, domain_rules, anchor_evidence):
        fragment = ""
    else:
        fragment = _normalize_percent_encoding(fragment)

    return urlunsplit((scheme, netloc, path, query, fragment))


# --------------------------------------------------------------------------- identity
def content_id(identity_url):
    """Global, cross-topic content identity.

    The same URL appearing under two topics is the same piece of content; this
    is the join key that links them.
    """
    if not isinstance(identity_url, str) or not identity_url:
        raise UrlError("identity_url must be a non-empty string")
    return hashlib.sha256(identity_url.encode("utf-8")).hexdigest()[:16]


def record_id(topic_slug, identity_url):
    """Per-topic persistent primary key.

    Topic artifacts are the publishing unit, so each needs its own addressable,
    diffable key. Derived from the IMMUTABLE identity_url and the topic only --
    never from primary_category, which is a mutable classification property, and
    never from canonical_url, which changes when a redirect or canonical tag is
    later observed.
    """
    if not isinstance(topic_slug, str) or not topic_slug:
        raise UrlError("topic_slug must be a non-empty string")
    if not isinstance(identity_url, str) or not identity_url:
        raise UrlError("identity_url must be a non-empty string")
    key = "%s|%s" % (topic_slug, identity_url)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def content_hash(body_bytes):
    """SHA-256 of a fetched response body, for material-change detection."""
    if body_bytes is None:
        return None
    if isinstance(body_bytes, str):
        body_bytes = body_bytes.encode("utf-8")
    return hashlib.sha256(body_bytes).hexdigest()
