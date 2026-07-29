#!/usr/bin/env python3
"""fixtures.py — an injected opener that serves recorded-shape responses offline.

This is the ONLY thing that differs between an offline run and a live one. It
plugs in at `HttpClient(opener=...)`, which means the real robots cache, the RFC
9309 matcher, the redirect and retry logic, content-type and byte-cap checks,
the domain lease and DV-8 accounting all run unmodified above it. There is no
fixture branch anywhere in `adapters/` or `sourcecache.py`, and a static test
proves it.

Two fixture families, both under `tests/fixtures/harvest/`:

  sources/<fixture_id>.json   one per configured source, keyed by its exact URL
  robots/<host>.json          one per configured host, served at /robots.txt

A request for a URL or host with no fixture raises `FixtureMissing`. It is never
answered with a synthesised 200 or an implicit robots allow: a silent default
would let a test pass while proving nothing about the source it claims to cover.
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
MANIFEST_PATH = os.path.join(FIXTURE_ROOT, "MANIFEST.json")


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

    def __init__(self, sources=None, robots=None, strict=True):
        self.sources = sources if sources is not None else load_source_fixtures()
        self.robots = robots if robots is not None else load_robots_fixtures()
        self.strict = strict
        self.calls = []
        self._by_url = {}
        for fixture in self.sources.values():
            url = fixture.get("url")
            if not url:
                raise FixtureError("fixture %r has no url" % fixture.get("fixture_id"))
            if url in self._by_url:
                raise FixtureError("two fixtures claim the same url %r" % url)
            self._by_url[url] = fixture

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
                "no source fixture for %r. Offline runs answer only configured "
                "sources; nothing here invents a response." % url)
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
