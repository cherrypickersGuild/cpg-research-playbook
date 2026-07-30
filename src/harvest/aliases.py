#!/usr/bin/env python3
"""aliases.py — redirect and rel=canonical adjudication (S6-3).

S6-2 turned one fetch into a fact. This module decides what that fact is allowed
to change about a record's URLs, and it is deliberately the most conservative
piece of Stage 6: the governing principle from `canonicalization.v1.json` is that
a false negative is recoverable and a destructive false-positive merge is not.
Keeping two records that turn out to be one is fixed later by an alias. Collapsing
two records that were actually different destroys information nothing can recover.

THE INVARIANT THIS MODULE EXISTS TO PROTECT: `identity_url` is fixed at first
acceptance and is immutable forever, and `record_id` / `content_id` derive from it.
Nothing here recomputes or returns any of the three. A redirect or a canonical tag
moves `canonical_url` and appends to `url_aliases`; it can never mint, merge or
move an identity. That is why `adjudicate` takes `identity_url` only to compare
against — never to rewrite.

WHAT IT DOES NOT OWN. Redirect following and permanence classification belong to
the committed `HttpClient` and reach here already decided, on the S6-2 outcome's
`permanent_redirect` flag. Permanence is NEVER inferred from a hop count: a chain
of three 301s and a chain of 301→302→200 both have redirects, and only the first
may create an alias. Robots is the committed matcher's decision, supplied as
evidence (see `canonical_robots_allowed`) — this module performs no check, makes
no request and follows nothing. Same-registrable-domain is decided by the
committed `urlkey.registrable_host` and by nothing else: a second hostname
comparison in this repo is how two subsystems eventually disagree about whether
two URLs are one resource.

PURITY. `adjudicate` and `extract_rel_canonical` are pure relative to their
explicit inputs: no network, no socket, no filesystem, no runtime state, no clock
beyond the injected instant, no `HttpClient`, no pool, no record construction and
no eligibility judgement. `load_canonicalization` is the one impure function, sits
outside both, and follows the committed loader idiom of `verify.load_policy` and
`classify.load_precedence`.

A conflict is an ordinary outcome, not a crash: contradictory evidence returns an
`AliasConflict` and leaves every URL alone. `AliasError` is reserved for a caller
mistake or unusable policy data.
"""
import dataclasses
import html.parser
import json
import os

from . import urlkey

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANONICALIZATION_PATH = os.path.join(ROOT, "config", "harvest",
                                     "canonicalization.v1.json")

# How much of a body may be scanned for a canonical link. A `<head>` that has not
# ended within 64 KiB is not a document this pipeline should be mining for
# identity evidence, and an unbounded scan over an 8 MiB body (the committed
# max_response_bytes) would make extraction cost depend on page weight. Owned by
# Stage 6, deliberately not a policy number, and reported rather than hidden.
CANONICAL_SCAN_BYTES = 65536

# The committed `alias_kind` enum from record.v1.json. Referenced by name so a
# typo cannot invent a fifth kind.
KIND_PERMANENT_REDIRECT = "permanent_redirect"
KIND_CANONICAL_TAG = "canonical_tag"
KIND_DOMAIN_RULE = "domain_rule"
KIND_DISCOVERED_VARIANT = "discovered_variant"

# Conflict reasons. Deliberately not the record schema's rejection vocabulary: a
# conflict rejects nothing, it declines to alias and says why.
CONFLICT_MULTIPLE_CANONICALS = "multiple_conflicting_canonical_tags"
CONFLICT_CIRCULAR_CANONICAL = "circular_canonical_evidence"
CONFLICT_MALFORMED_CANONICAL = "malformed_or_unresolvable_canonical"
CONFLICT_CROSS_DOMAIN_UNAUTHORIZED = "cross_registrable_domain_without_rule"
CONFLICT_ROBOTS_UNVERIFIED = "canonical_robots_not_verified"

_HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")

_CACHE = {}


class AliasError(Exception):
    """A caller mistake or unusable policy data — never ordinary conflicting
    evidence, which is what `AliasConflict` is for."""


@dataclasses.dataclass(frozen=True, slots=True)
class AliasConflict:
    """Contradictory evidence, recorded rather than resolved.

    `resolution` is always "unresolved": resolving one needs an explicit operator
    decision or a configured `domain_migrations` rule, and neither is Stage 6's.
    Every field is deterministic — no traceback, no repr, no parser diagnostic.
    """
    reason: str
    identity_url: str
    proposed_alias: str = None
    detail: str = ""
    resolution: str = "unresolved"

    def payload(self):
        """A plain dict, ordered by key so two runs serialize identically."""
        return {
            "reason": self.reason,
            "identity_url": self.identity_url,
            "proposed_alias": self.proposed_alias,
            "detail": self.detail,
            "resolution": self.resolution,
        }


# --------------------------------------------------------------------- policy
def load_canonicalization(path=None):
    """Read and cache the committed canonicalization policy.

    The one impure function here, and it is outside both pure functions on
    purpose: `adjudicate` and `extract_rel_canonical` receive the document as
    data and never open a file. Mirrors `verify.load_policy` and
    `classify.load_precedence` rather than inventing a third loader shape.
    """
    resolved = path or CANONICALIZATION_PATH
    if resolved not in _CACHE:
        try:
            with open(resolved, "r", encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, ValueError) as exc:
            raise AliasError("cannot read %s (%s)" % (resolved, exc)) from exc
        if "canonical_tag_trust" not in document:
            raise AliasError("%s carries no canonical_tag_trust block" % resolved)
        _CACHE[resolved] = document
    return _CACHE[resolved]


def clear_caches():
    _CACHE.clear()


def _migrations(policy):
    rules = policy.get("domain_migrations")
    if rules is None:
        return ()
    if not isinstance(rules, list):
        raise AliasError("domain_migrations must be a list, got %r" % type(rules).__name__)
    return tuple(rules)


def migration_rule_for(from_host, to_host, policy):
    """The authorized cross-domain rule for this pair, or None.

    Matched on `registrable_host` at both ends, so a rule written for
    `old.example` authorizes `www.old.example` too — one host comparison, the
    committed one. Rule identity comes from the config, never from a literal here.
    """
    source = urlkey.registrable_host(from_host)
    destination = urlkey.registrable_host(to_host)
    for index, rule in enumerate(_migrations(policy)):
        if not isinstance(rule, dict):
            raise AliasError("domain_migrations[%d] is not an object" % index)
        if (urlkey.registrable_host(rule.get("from") or "") == source
                and urlkey.registrable_host(rule.get("to") or "") == destination):
            return rule
    return None


# ---------------------------------------------------------------- extraction
class _CanonicalCollector(html.parser.HTMLParser):
    """Collects `<link rel=canonical>` hrefs from `<head>`, in document order.

    Stops at `</head>`, because a canonical link outside the head is not one. Uses
    the stdlib parser rather than a regex over markup: a regex cannot tell an
    attribute from text that looks like one, and getting that wrong here would
    move a record's canonical URL.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []
        self._in_head = False
        self._head_closed = False

    def handle_starttag(self, tag, attrs):
        if self._head_closed:
            return
        if tag == "head":
            self._in_head = True
            return
        if tag != "link" or not self._in_head:
            return
        attributes = dict(attrs)
        rel = (attributes.get("rel") or "").strip().lower()
        if "canonical" not in rel.split():
            return
        # Recorded even when blank, so a malformed tag is visible to adjudication
        # rather than silently absent.
        self.hrefs.append((attributes.get("href") or "").strip())

    def handle_endtag(self, tag):
        if tag == "head":
            self._in_head = False
            self._head_closed = True

    def error(self, message):        # pragma: no cover - stdlib compatibility
        """Never raise on malformed markup: a broken page is ordinary input."""


def extract_rel_canonical(body, *, content_type=None, base_url=None,
                          scan_bytes=CANONICAL_SCAN_BYTES):
    """Every `<link rel=canonical>` href in `<head>`, resolved and in document order.

    Pure: reads only what it is given. The body is never mutated, re-encoded or
    returned — it is sliced to `scan_bytes` FIRST and only that slice is decoded,
    so bytes past the cap are never examined at all.

    Non-HTML content types are not scanned, per §4: a PDF or a JSON document has
    no `<head>`, and looking for one would be guessing. A blank or unresolvable
    href is returned as an empty string so adjudication can call it malformed
    rather than mistake it for absence.

    `base_url` resolves relative hrefs (RFC 3986). Without it a relative href
    cannot become absolute and is reported as unresolvable.
    """
    if body is None:
        return ()
    if not isinstance(body, (bytes, bytearray)):
        raise AliasError("body must be bytes, got %s" % type(body).__name__)
    if scan_bytes is not None and int(scan_bytes) < 0:
        raise AliasError("scan_bytes must not be negative")
    if not _is_html(content_type):
        return ()

    window = bytes(body) if scan_bytes is None else bytes(body[:int(scan_bytes)])
    # errors="replace": slicing at a byte cap can split a multi-byte character,
    # and a truncated tail must not raise on an otherwise usable head.
    text = window.decode(_charset_of(content_type), errors="replace")

    collector = _CanonicalCollector()
    collector.feed(text)
    collector.close()

    out = []
    for href in collector.hrefs:
        out.append(_resolve(href, base_url))
    return tuple(out)


def _is_html(content_type):
    if not content_type:
        return False
    base = content_type.split(";", 1)[0].strip().lower()
    return base in _HTML_CONTENT_TYPES


def _charset_of(content_type):
    """The declared charset, defaulting to UTF-8 — the committed convention."""
    if content_type and "charset=" in content_type:
        charset = content_type.split("charset=", 1)[1].split(";")[0].strip()
        if charset:
            try:
                "".encode(charset)
            except LookupError:
                return "utf-8"
            return charset
    return "utf-8"


def _resolve(href, base_url):
    """An absolute URL, or "" when the href cannot honestly become one."""
    if not href:
        return ""
    import urllib.parse
    candidate = href
    if base_url:
        candidate = urllib.parse.urljoin(base_url, href)
    parts = urllib.parse.urlsplit(candidate)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return ""
    return candidate


# --------------------------------------------------------------- adjudication
def _equivalent(left, right, policy):
    """Same resource under the committed canonicalizer, or not.

    Uses `urlkey.canonicalize_string` — the one normalization in this repo — so
    two URLs differing only by a tracking parameter or a default port are one.
    """
    if not left or not right:
        return False
    try:
        return (urlkey.canonicalize_string(left, **_canon_kwargs(policy))
                == urlkey.canonicalize_string(right, **_canon_kwargs(policy)))
    except urlkey.UrlError:
        return False


def _canon_kwargs(policy):
    return {"tracking_params": policy.get("tracking_params"),
            "domain_rules": policy.get("domain_rules")}


def _host_of(url):
    import urllib.parse
    return urllib.parse.urlsplit(url or "").hostname or ""


def _same_registrable_domain(left, right):
    """The committed authority, and the only host comparison in this module."""
    return (urlkey.registrable_host(_host_of(left))
            == urlkey.registrable_host(_host_of(right)))


def _alias(url, kind, evidence, observed_at):
    return {"url": url, "kind": kind, "evidence": dict(evidence),
            "observed_at": observed_at}


def adjudicate(identity_url, canonical_url, outcome, policy, *,
               canonical_robots_allowed=None, observed_at=None):
    """Apply the committed §4 table to one fetch outcome.

    Returns `(canonical_url, url_aliases, conflicts)`:

      * `canonical_url` — the latest verified preferred URL. Starts as the one
        passed in and moves only on evidence this table trusts.
      * `url_aliases` — evidence-bearing alias rows, sorted and deduplicated by
        `(kind, url)` so two runs over one input serialize identically.
      * `conflicts` — `AliasConflict` rows. Contradictory evidence is recorded,
        never resolved, and never mutates a URL.

    `identity_url` is read for comparison and is NEVER returned or rewritten;
    `record_id` and `content_id` are not this module's concern at all.

    `outcome` is the S6-2 `TargetFetchOutcome`. Permanence comes from its
    `permanent_redirect` flag — the committed client's own classification — and is
    never inferred from a redirect count.

    `canonical_robots_allowed` is the committed matcher's verdict on the extracted
    canonical URL, supplied as evidence because this module performs no check:
    True authorizes the same-domain row, False and None (unknown) both decline to
    alias, the conservative direction. The caller resolves it between
    `extract_rel_canonical` and this call.
    """
    if not identity_url:
        raise AliasError("identity_url is required")
    if policy is None:
        raise AliasError("policy is required; adjudicate does not read config")
    if not observed_at:
        raise AliasError("observed_at is required; an alias records when it was seen")

    current = canonical_url or identity_url
    aliases = []
    conflicts = []

    current, aliases, conflicts = _apply_redirect(
        current, outcome, aliases, conflicts, observed_at)
    current, aliases, conflicts = _apply_canonical(
        identity_url, current, outcome, policy, aliases, conflicts,
        canonical_robots_allowed, observed_at)

    return current, _ordered(aliases), tuple(conflicts)


def _apply_redirect(current, outcome, aliases, conflicts, observed_at):
    """Row 2 and row 3: a permanent-only chain aliases; any temporary hop does not."""
    final_url = getattr(outcome, "final_url", None)
    if not final_url or final_url == current:
        return current, aliases, conflicts
    # NOT `redirects > 0`. permanent_redirect is true only when EVERY hop was
    # 301/308; one 302 or 307 anywhere makes the final location temporary, and a
    # temporary location must never rewrite a preferred URL.
    if not getattr(outcome, "permanent_redirect", False):
        return current, aliases, conflicts
    aliases.append(_alias(
        final_url, KIND_PERMANENT_REDIRECT,
        {"http_status": getattr(outcome, "http_status", None),
         "location": final_url},
        observed_at))
    return final_url, aliases, conflicts


def _apply_canonical(identity_url, current, outcome, policy, aliases, conflicts,
                     robots_allowed, observed_at):
    """Rows 4-7: the canonical tag, under the committed trust tiers."""
    hrefs = extract_rel_canonical(
        getattr(outcome, "body", None),
        content_type=getattr(outcome, "content_type", None),
        base_url=getattr(outcome, "final_url", None)
                 or getattr(outcome, "requested_url", None))
    if not hrefs:
        return current, aliases, conflicts

    # Two identical (or canonically equivalent) tags are one claim, not a
    # conflict. Two DIFFERENT claims are a conflict, because nothing here can
    # choose between them and guessing would move a record's canonical URL.
    distinct = []
    for href in hrefs:
        if not any(_equivalent(href, seen, policy) or href == seen
                   for seen in distinct):
            distinct.append(href)

    if any(href == "" for href in hrefs):
        conflicts.append(AliasConflict(
            reason=CONFLICT_MALFORMED_CANONICAL, identity_url=identity_url,
            detail="a rel=canonical href was blank, relative-unresolvable or "
                   "not an absolute http(s) URL"))
        return current, aliases, conflicts

    if len(distinct) > 1:
        conflicts.append(AliasConflict(
            reason=CONFLICT_MULTIPLE_CANONICALS, identity_url=identity_url,
            detail="%d conflicting rel=canonical hrefs on one page" % len(distinct)))
        return current, aliases, conflicts

    proposed = distinct[0]

    # Self-canonical: already the preferred URL. A no-op, not an alias.
    if _equivalent(proposed, current, policy):
        return current, aliases, conflicts

    # Circular: the tag points back at a URL this very fetch was redirected AWAY
    # from. The pure A->B->A form is undetectable without fetching B, which §1.2
    # forbids, so this is the only circular shape Stage 6 can observe.
    requested = getattr(outcome, "requested_url", None)
    if requested and _equivalent(proposed, requested, policy) and requested != current:
        conflicts.append(AliasConflict(
            reason=CONFLICT_CIRCULAR_CANONICAL, identity_url=identity_url,
            proposed_alias=proposed,
            detail="the canonical names a URL already in this fetch's redirect chain"))
        return current, aliases, conflicts

    if _same_registrable_domain(proposed, current):
        # Same registrable domain: auto-accept AFTER the syntax and robots checks.
        # Robots is the committed matcher's verdict, passed in; unknown declines.
        if robots_allowed is not True:
            conflicts.append(AliasConflict(
                reason=CONFLICT_ROBOTS_UNVERIFIED, identity_url=identity_url,
                proposed_alias=proposed,
                detail="a same-domain canonical is trusted only after the "
                       "committed robots matcher allows it; verdict was %r"
                       % (robots_allowed,)))
            return current, aliases, conflicts
        aliases.append(_alias(proposed, KIND_CANONICAL_TAG,
                              {"rel_canonical": proposed}, observed_at))
        return proposed, aliases, conflicts

    # Different registrable domain: authorized only by a configured migration
    # rule. Rule identity comes from the config; no host or rule id is written
    # into this module.
    rule = migration_rule_for(_host_of(current), _host_of(proposed), policy)
    if rule is not None:
        aliases.append(_alias(
            proposed, KIND_DOMAIN_RULE,
            {"rule_id": rule.get("rule_id") or rule.get("_why"),
             "config": "canonicalization.v1.json",
             "rel_canonical": proposed},
            observed_at))
        return proposed, aliases, conflicts

    conflicts.append(AliasConflict(
        reason=CONFLICT_CROSS_DOMAIN_UNAUTHORIZED, identity_url=identity_url,
        proposed_alias=proposed,
        detail="the canonical is on a different registrable domain with no "
               "domain_migrations rule and no independent 301/308 evidence"))
    return current, aliases, conflicts


def _ordered(aliases):
    """Sorted and deduplicated by (kind, url), so bytes follow content."""
    seen, out = set(), []
    for alias in sorted(aliases, key=lambda a: (a["kind"], a["url"])):
        key = (alias["kind"], alias["url"])
        if key in seen:
            continue
        seen.add(key)
        out.append(alias)
    return tuple(out)
