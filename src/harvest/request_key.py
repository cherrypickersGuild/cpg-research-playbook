#!/usr/bin/env python3
"""request_key.py — the identity of a NORMALIZED REQUEST, not of a source.

"Fetch each source once per round" was the wrong unit. One configured source can
legitimately produce several distinct requests — an API queried by a broad lane
and by gap__industry__healthcare-life-sciences is two requests and two fetches,
correctly — while a feed referenced by three lanes is ONE request and must be
fetched once for the whole run.

  source_request_key = sha256( source_id | normalized_url | method |
                               canonical_query | body_hash |
                               significant_headers | adapter_mode |
                               canonicalization_version )[:16]

Four decisions worth stating, because each is a place this could go wrong:

  * `canonicalization_version` is IN the key. The normalized URL comes from the
    Stage 1 canonicalizer, whose behaviour is driven by canonicalization.v1.json;
    without the version, bumping that config would silently change every key and
    two runs would disagree about what had already been fetched.
  * `significant_headers` is an ALLOWLIST. User-Agent is excluded because it
    varies without changing the resource, and authorization material is excluded
    because a cache key must never carry a secret.
  * `canonical_query` PRESERVES the query-pair sequence by default, for every
    adapter without exception. Normalization is opt-in per logical request and is
    never inferred from adapter class, API-versus-feed classification, URL shape,
    the presence of repeated parameters, or a global default. Reordering merges
    two requests into one logical owner and one immutable snapshot, so a wrong
    guess about insignificance silently loses a response.
  * `adapter_mode` separates seed `index` from seed `record` against the same
    URL — the same bytes read for two different purposes.

Nothing here touches identity_url, record_id or content_id: a request key is
about fetching, not about what a record IS.
"""
import hashlib
import json
import os

from . import urlkey

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANONICALIZATION_PATH = os.path.join(ROOT, "config", "harvest", "canonicalization.v1.json")

# Headers that genuinely change the resource returned. Everything else is noise
# or secret.
SIGNIFICANT_HEADERS = ("accept", "accept-language")

# Query-normalization policies. An explicit input to ONE logical request — never
# derived from adapter class, API-versus-feed classification, URL shape, the
# presence of repeated parameters, or a global default.
#
#   preserve                   the complete query-pair sequence, repeated-key
#                              multiplicity, repeated-key value order and blank
#                              values are all kept exactly as given. THE DEFAULT,
#                              for every adapter and every source.
#
#   sort-distinct-keys-stable  normalizes ordering BETWEEN DISTINCT KEYS only.
#                              The relative order of repeated occurrences of the
#                              same key is preserved, as are multiplicity and
#                              blank values. Deliberately not called "sort" or
#                              "order-insignificant": neither name says that
#                              repeated-key order still matters, and a later
#                              reader could take either as licence to sort on
#                              (key, value), which would merge ordered repeats.
QUERY_ORDER_PRESERVE = "preserve"
QUERY_ORDER_SORT_DISTINCT_KEYS_STABLE = "sort-distinct-keys-stable"
QUERY_ORDER_POLICIES = (QUERY_ORDER_PRESERVE, QUERY_ORDER_SORT_DISTINCT_KEYS_STABLE)

_CANON_CACHE = {}


class RequestKeyError(ValueError):
    """A request that cannot be given a stable key."""


def canonicalization_version(path=None):
    p = path or CANONICALIZATION_PATH
    if p not in _CANON_CACHE:
        try:
            with open(p, "r", encoding="utf-8") as f:
                _CANON_CACHE[p] = int(json.load(f).get("config_version", 1))
        except (OSError, ValueError) as exc:
            raise RequestKeyError("cannot read %s (%s)" % (p, exc))
    return _CANON_CACHE[p]


def _split_for_key(url, query_order_policy):
    """(url without its query, canonical query) — the query handled exactly once.

    The query must NOT also travel inside the URL component. canonicalize_string
    preserves parameter order, so including the full normalized URL alongside a
    separately-normalized canonical_query would let the un-normalized copy leak
    back in and the policy would have no effect. Splitting makes canonical_query
    the single authority on query normalization.

    keep_blank_values is on, so "?a=" is not the same request as "?a" absent, and
    two blank duplicates stay two pairs.
    """
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    if query_order_policy not in QUERY_ORDER_POLICIES:
        raise RequestKeyError(
            "unknown query_order_policy %r (expected one of %s)"
            % (query_order_policy, ", ".join(QUERY_ORDER_POLICIES)))

    parts = urlsplit(url)
    base = urlunsplit((parts.scheme, parts.netloc, parts.path, "", parts.fragment))
    if not parts.query:
        return base, ""

    pairs = parse_qsl(parts.query, keep_blank_values=True)
    if query_order_policy == QUERY_ORDER_SORT_DISTINCT_KEYS_STABLE:
        # Key-only and STABLE. Sorting on (key, value) would reorder repeated
        # occurrences of the same key, merging "?filter=region&filter=date" with
        # "?filter=date&filter=region" — two requests that may return different
        # responses, collapsed into one owner and one immutable snapshot.
        pairs = sorted(pairs, key=lambda pair: pair[0])
    return base, urlencode(pairs, doseq=False)


def _headers_component(headers):
    if not headers:
        return ""
    lowered = {str(k).lower(): str(v) for k, v in headers.items()}
    return ";".join("%s=%s" % (h, lowered[h]) for h in SIGNIFICANT_HEADERS if h in lowered)


def source_request_key(source_id, url, adapter="feed", adapter_mode="default",
                       method="GET", body=None, headers=None,
                       tracking_params=None, domain_rules=None,
                       canonicalization_path=None, *,
                       query_order_policy=QUERY_ORDER_PRESERVE):
    """The 16-hex key identifying one normalized request within a run.

    `adapter` selects nothing about query handling — it is carried only for
    callers that already have it. `query_order_policy` is the sole control, it is
    keyword-only so it can never be passed by accident, and it defaults to
    `preserve` for every adapter and every source.

    Until Stage 3 introduces an approved per-source config field, every real
    caller uses the default; the opt-in policy is exercised by unit tests only.
    """
    if not source_id or not isinstance(source_id, str):
        raise RequestKeyError("source_id must be a non-empty string")

    normalized = urlkey.canonicalize_string(url, tracking_params=tracking_params,
                                            domain_rules=domain_rules)
    base, canonical_query = _split_for_key(normalized, query_order_policy)

    body_hash = ""
    if body is not None:
        raw = body.encode("utf-8") if isinstance(body, str) else body
        body_hash = hashlib.sha256(raw).hexdigest()

    material = "|".join([
        source_id,
        base,
        (method or "GET").upper(),
        canonical_query,
        body_hash,
        _headers_component(headers),
        adapter_mode or "default",
        str(canonicalization_version(canonicalization_path)),
    ])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def candidate_key(target_url, tracking_params=None, domain_rules=None):
    """Pool dedup key for a discovered target page.

    The same canonicalizer as identity, but this is NOT an identity_url claim:
    identity is fixed only at acceptance. Deduplicating here means a page found
    by four lanes is fetched once and parsed once.
    """
    canonical = urlkey.canonicalize_string(target_url, tracking_params=tracking_params,
                                           domain_rules=domain_rules)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16], canonical
