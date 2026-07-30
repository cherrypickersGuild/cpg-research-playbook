#!/usr/bin/env python3
"""fixtures.py — an injected opener that serves recorded-shape responses offline.

This is the ONLY thing that differs between an offline run and a live one. It
plugs in at `HttpClient(opener=...)`, which means the real robots cache, the RFC
9309 matcher, the redirect and retry logic, content-type and byte-cap checks,
the domain lease and DV-8 accounting all run unmodified above it. There is no
fixture branch anywhere in `adapters/` or `sourcecache.py`, and a static test
proves it.

Three fixture families, all under `tests/fixtures/harvest/`:

  sources/<fixture_id>.json   one per configured source, keyed by its exact URL
  robots/<host>.json          one per configured host, served at /robots.txt
  targets/<fixture_id>.json   an item's OWN page, keyed by its exact URL (S6-1)

A request for a URL or host with no fixture raises `FixtureMissing`. It is never
answered with a synthesised 200 or an implicit robots allow: a silent default
would let a test pass while proving nothing about the source it claims to cover.

Sources and targets share ONE exact-URL index. That is deliberate: two indexes
would have to agree about who owns a URL, and the first disagreement would be a
fixture silently shadowing another. A URL claimed by both families raises here
instead.

A target fixture is static bytes with a status and headers, exactly like a source
fixture. It carries no transport-simulation directive — no `raise`, no `responses`
sequence, no `delay`, no generated body — because retries, timeouts and the body
cap belong to `HttpClient`, which is tested on them directly. A fixture that could
time out or answer differently on the second call would make this module a second
HTTP implementation.

Validation is split so that nothing is validated twice: this module checks the
shape of a document it is about to serve, while `scripts/harvest/check_fixtures.py`
owns corpus-level facts — the declared file set, provenance, and the manifest's
byte sizes and hashes.
"""
import base64
import io
import json
import os
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE_ROOT = os.path.join(ROOT, "tests", "fixtures", "harvest")
SOURCES_DIR = os.path.join(FIXTURE_ROOT, "sources")
ROBOTS_DIR = os.path.join(FIXTURE_ROOT, "robots")
TARGETS_DIR = os.path.join(FIXTURE_ROOT, "targets")
MANIFEST_PATH = os.path.join(FIXTURE_ROOT, "MANIFEST.json")

# Keys that would turn a static fixture into a transport simulator. Refused by
# name rather than by shape, so the refusal cannot be sidestepped by a synonym
# that happens to type-check.
FORBIDDEN_TARGET_KEYS = ("raise", "raises", "error", "exception",
                         "responses", "sequence", "then",
                         "delay", "delay_sec", "timeout", "timeout_sec",
                         "generate", "generated_bytes", "body_size",
                         "repeat", "fail_first")


class FixtureError(Exception):
    """A fixture is missing, malformed or dishonestly labelled."""


class FixtureMissing(FixtureError):
    """No fixture covers this URL or host — fail loudly, never synthesise one."""


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except OSError as exc:
        raise FixtureError("cannot read %s (%s)" % (path, exc)) from exc
    except ValueError as exc:
        raise FixtureError("%s is not valid JSON (%s)" % (path, exc)) from exc


def load_manifest(path=None):
    return _read_json(path or MANIFEST_PATH)


def load_source_fixtures(directory=None):
    """fixture_id -> fixture dict, for every file in sources/."""
    directory = directory or SOURCES_DIR
    out = {}
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        fixture = _read_json(os.path.join(directory, name))
        fixture_id = fixture.get("fixture_id")
        if not fixture_id:
            raise FixtureError("%s has no fixture_id" % name)
        if fixture_id in out:
            raise FixtureError("duplicate fixture_id %r" % fixture_id)
        out[fixture_id] = fixture
    return out


def load_robots_fixtures(directory=None):
    """host -> robots fixture dict."""
    directory = directory or ROBOTS_DIR
    out = {}
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        fixture = _read_json(os.path.join(directory, name))
        host = fixture.get("host")
        if not host:
            raise FixtureError("%s has no host" % name)
        if host in out:
            raise FixtureError("duplicate robots host %r" % host)
        out[host] = fixture
    return out


def _validate_target(fixture, name):
    """The shape of one target fixture, checked before it can ever be served.

    Refuses rather than repairs. A malformed fixture that loaded anyway would be
    served as some default, and the test above it would pass while proving nothing
    about the page it claims to cover.

    Provenance is NOT checked here — `check_fixtures.py` owns that for all three
    families in one place, and a second copy could only drift from it.
    """
    if not isinstance(fixture, dict):
        raise FixtureError("%s: a target fixture must be a JSON object" % name)

    fixture_id = fixture.get("fixture_id")
    if not fixture_id or not isinstance(fixture_id, str):
        raise FixtureError("%s: no fixture_id" % name)
    stem = name[:-len(".json")] if name.endswith(".json") else name
    if fixture_id != stem:
        raise FixtureError("%s: fixture_id %r does not match its filename — the "
                           "declared corpus is keyed by filename"
                           % (name, fixture_id))

    url = fixture.get("url")
    if not url or not isinstance(url, str):
        raise FixtureError("%s: no url" % name)
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FixtureError("%s: url %r is not an absolute http(s) URL" % (name, url))

    status = fixture.get("status")
    if not isinstance(status, int) or isinstance(status, bool):
        raise FixtureError("%s: status must be an integer, got %r" % (name, status))

    headers = fixture.get("headers", {})
    if not isinstance(headers, dict):
        raise FixtureError("%s: headers must be an object" % name)

    has_body = "body" in fixture
    has_b64 = "body_b64" in fixture
    if has_body and has_b64:
        raise FixtureError("%s: carries both body and body_b64; exactly one is the "
                           "authority for its bytes" % name)
    if not has_body and not has_b64:
        raise FixtureError("%s: no body or body_b64" % name)
    if has_body and not isinstance(fixture["body"], str):
        raise FixtureError("%s: body must be a string" % name)
    if has_b64:
        try:
            base64.b64decode(fixture["body_b64"], validate=True)
        except (ValueError, TypeError) as exc:
            raise FixtureError("%s: body_b64 is not valid base64 (%s)"
                               % (name, exc)) from exc

    # A target page belongs to no configured source. Letting one claim a source_id
    # would make it look like a discovery fixture and put it in scope for the
    # source-completeness check, which is a different contract entirely.
    if "source_id" in fixture:
        raise FixtureError("%s: a target fixture must not claim a source_id — it is "
                           "an item's own page, not a configured source" % name)

    for key in FORBIDDEN_TARGET_KEYS:
        if key in fixture:
            raise FixtureError(
                "%s: forbidden transport-simulation key %r. A fixture is static "
                "bytes with a status and headers; retries, timeouts and the body "
                "cap belong to HttpClient and are tested there." % (name, key))
    return fixture


def load_target_fixtures(directory=None):
    """fixture_id -> fixture dict, for every file in targets/.

    Every document is validated on the way in, so a caller never holds a target
    fixture this module would refuse to serve.
    """
    directory = directory or TARGETS_DIR
    try:
        names = sorted(os.listdir(directory))
    except OSError as exc:
        raise FixtureError("cannot list target fixtures in %s (%s)"
                           % (directory, exc)) from exc
    out, by_url = {}, {}
    for name in names:
        if not name.endswith(".json"):
            raise FixtureError("%s: unexpected non-JSON file in targets/ — the "
                               "target corpus is a declared set, not a scratch "
                               "directory" % name)
        fixture = _validate_target(_read_json(os.path.join(directory, name)), name)
        fixture_id = fixture["fixture_id"]
        if fixture_id in out:
            raise FixtureError("duplicate target fixture_id %r" % fixture_id)
        url = fixture["url"]
        if url in by_url:
            raise FixtureError("two target fixtures claim the same url %r (%s and %s)"
                               % (url, by_url[url], fixture_id))
        by_url[url] = fixture_id
        out[fixture_id] = fixture
    return out


def body_bytes(fixture):
    """A fixture body, from `body_b64` (binary-safe) or `body` (text)."""
    if "body_b64" in fixture:
        return base64.b64decode(fixture["body_b64"])
    return (fixture.get("body") or "").encode("utf-8")


class FixtureOpener:
    """An `opener(req, timeout)` for HttpClient, backed by fixtures on disk.

    Matches HttpClient's opener contract exactly — returns
    `(status, headers, file-like-or-bytes)` — so nothing above it can tell the
    difference between this and `default_opener`.
    """

    def __init__(self, sources=None, robots=None, targets=None, strict=True):
        self.sources = sources if sources is not None else load_source_fixtures()
        self.robots = robots if robots is not None else load_robots_fixtures()
        # `targets=None` means NO targets, deliberately unlike sources and robots:
        # every existing caller constructs this opener without them, and loading
        # them by default would silently start answering 24 more URLs in suites
        # written when only configured sources were answerable.
        self.targets = targets if targets is not None else {}
        self.strict = strict
        self.calls = []
        # ONE exact-URL index across both families, plus who owns each URL so a
        # collision can name both claimants instead of one shadowing the other.
        self._by_url = {}
        self._family = {}
        for family, group in (("source", self.sources), ("target", self.targets)):
            for fixture in group.values():
                url = fixture.get("url")
                if not url:
                    raise FixtureError("fixture %r has no url"
                                       % fixture.get("fixture_id"))
                if url in self._by_url:
                    raise FixtureError(
                        "two fixtures claim the same url %r: %s %r and %s %r"
                        % (url, self._family[url],
                           self._by_url[url].get("fixture_id"),
                           family, fixture.get("fixture_id")))
                self._by_url[url] = fixture
                self._family[url] = family

    def family_of(self, url):
        """Which family owns `url` — "source", "target", or None. Read-only."""
        return self._family.get(url)

    # ------------------------------------------------------------- opener
    def __call__(self, req, timeout=20):
        url = req.full_url
        self.calls.append(url)
        parts = urllib.parse.urlsplit(url)

        if parts.path == "/robots.txt":
            fixture = self.robots.get(parts.hostname)
            if fixture is None:
                raise FixtureMissing(
                    "no robots fixture for host %r. Add one under "
                    "tests/fixtures/harvest/robots/ — a missing robots policy is "
                    "never treated as permission." % parts.hostname)
            return (int(fixture.get("status", 200)),
                    {k.lower(): v for k, v in (fixture.get("headers") or
                                               {"content-type": "text/plain"}).items()},
                    io.BytesIO(body_bytes(fixture)))

        fixture = self._by_url.get(url)
        if fixture is None:
            raise FixtureMissing(
                "no source or target fixture for %r. Offline runs answer only "
                "declared fixtures; nothing here invents a response." % url)
        return (int(fixture.get("status", 200)),
                {k.lower(): v for k, v in (fixture.get("headers") or {}).items()},
                io.BytesIO(body_bytes(fixture)))

    # -------------------------------------------------------------- lookup
    def fixture_for_source(self, source):
        fixture_id = source.get("fixture_id")
        fixture = self.sources.get(fixture_id)
        if fixture is None:
            raise FixtureMissing("no fixture %r for source %r"
                                 % (fixture_id, source.get("source_id")))
        return fixture
