#!/usr/bin/env python3
"""Offline unit tests for scripts/github_meta.py — all HTTP is mocked; no real
network and no real GitHub rate limit is consumed. Run: python -m unittest -v
tests/test_github_meta.py  (or: python tests/test_github_meta.py)."""
import json
import os
import sys
import tempfile
import unittest
import warnings

warnings.simplefilter("ignore", ResourceWarning)  # test-only short-lived file reads

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import github_meta as gm  # noqa: E402

TOKEN = "ghp_UNITTESTsecretTOKENvalue0000000000"
GHTOK = "gho_secondaryTOKENvalue111111111111111"
NOSLEEP = lambda *a, **k: None  # noqa: E731


def hdr(remaining=None, reset=None, limit=None, location=None):
    h = {}
    if remaining is not None:
        h["x-ratelimit-remaining"] = str(remaining)
    if reset is not None:
        h["x-ratelimit-reset"] = str(reset)
    if limit is not None:
        h["x-ratelimit-limit"] = str(limit)
    if location is not None:
        h["location"] = location
    return h


def body(full_name="o/r", stars=1234, html_url="https://github.com/o/r", **extra):
    d = {"full_name": full_name, "stargazers_count": stars, "html_url": html_url}
    d.update(extra)
    return json.dumps(d).encode("utf-8")


class MockOpener:
    """responses: url -> (status, headers, body_bytes) or a list used as a queue
    (last item repeats). Records every Request object it is called with."""
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, req, timeout=15):
        self.calls.append(req)
        r = self.responses.get(req.full_url, (404, {}, b""))
        if isinstance(r, list):
            r = r.pop(0) if len(r) > 1 else r[0]
        if callable(r):
            return r()
        return r

    @property
    def n(self):
        return len(self.calls)


class _EnvMixin(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("GITHUB_TOKEN", "GH_TOKEN")}
        for k in self._saved:
            os.environ.pop(k, None)
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def p(self, name):
        return os.path.join(self.tmp, name)

    def write(self, name, obj):
        with open(self.p(name), "w", encoding="utf-8") as f:
            json.dump(obj, f)
        return self.p(name)


class TestToken(_EnvMixin):
    def test_precedence_github_over_gh(self):
        os.environ["GITHUB_TOKEN"] = TOKEN
        os.environ["GH_TOKEN"] = GHTOK
        self.assertEqual(gm.read_token(), TOKEN)

    def test_falls_back_to_gh_token(self):
        os.environ["GH_TOKEN"] = GHTOK
        self.assertEqual(gm.read_token(), GHTOK)

    def test_none_when_unset(self):
        self.assertIsNone(gm.read_token())


class TestRequestConstruction(_EnvMixin):
    def test_auth_header_set_token_not_in_url(self):
        op = MockOpener({gm.API.format(owner="o", repo="r"): (200, hdr(remaining=4999), body())})
        meta, rl = gm.fetch_one("o", "r", TOKEN, opener=op, sleep=NOSLEEP)
        req = op.calls[0]
        self.assertEqual(req.get_header("Authorization"), "Bearer " + TOKEN)
        self.assertNotIn(TOKEN, req.full_url)             # never in URL
        self.assertEqual(meta["stars"], 1234)
        self.assertEqual(rl["remaining"], 4999)

    def test_unauthenticated_has_no_auth_header(self):
        op = MockOpener({gm.API.format(owner="o", repo="r"): (200, hdr(remaining=59), body())})
        gm.fetch_one("o", "r", None, opener=op, sleep=NOSLEEP)
        self.assertIsNone(op.calls[0].get_header("Authorization"))


class TestParseRepo(_EnvMixin):
    def test_repo_root_only(self):
        self.assertEqual(gm.parse_repo("https://github.com/Owner/Repo"), ("Owner", "Repo"))
        self.assertEqual(gm.parse_repo("https://github.com/o/r.git"), ("o", "r"))
        for bad in ("https://github.com/o", "https://github.com/o/r/issues/1",
                    "https://gist.github.com/o/r", "https://github.com/orgs/x",
                    "https://example.com/o/r", "unknown"):
            self.assertIsNone(gm.parse_repo(bad), bad)


class TestStatusHandling(_EnvMixin):
    def url(self, o="o", r="r"):
        return gm.API.format(owner=o, repo=r)

    def test_404_not_found(self):
        op = MockOpener({self.url(): (404, hdr(remaining=10), b"")})
        with self.assertRaises(gm.NotFound):
            gm.fetch_one("o", "r", None, opener=op, sleep=NOSLEEP)

    def test_redirect_records_canonical(self):
        op = MockOpener({
            self.url("old", "name"): (301, hdr(location="https://github.com/new/name"), b""),
            self.url("new", "name"): (200, hdr(remaining=4998), body(full_name="new/name",
                                      html_url="https://github.com/new/name", stars=77)),
        })
        meta, _ = gm.fetch_one("old", "name", None, opener=op, sleep=NOSLEEP)
        self.assertEqual(meta["canonical_url"], "https://github.com/new/name")
        self.assertEqual(meta["stars"], 77)

    def test_rate_limited_403_zero_remaining(self):
        op = MockOpener({self.url(): (403, hdr(remaining=0, reset=1783999999), b"")})
        with self.assertRaises(gm.RateLimited) as cm:
            gm.fetch_one("o", "r", None, opener=op, sleep=NOSLEEP)
        self.assertEqual(cm.exception.reset, 1783999999)

    def test_rate_limited_429(self):
        op = MockOpener({self.url(): (429, hdr(reset=1783999999), b"")})
        with self.assertRaises(gm.RateLimited):
            gm.fetch_one("o", "r", None, opener=op, sleep=NOSLEEP)

    def test_transient_500_then_success(self):
        op = MockOpener({self.url(): [(500, {}, b""), (200, hdr(remaining=4000), body(stars=5))]})
        meta, _ = gm.fetch_one("o", "r", None, opener=op, sleep=NOSLEEP)
        self.assertEqual(meta["stars"], 5)
        self.assertEqual(op.n, 2)

    def test_transient_persistent_raises(self):
        op = MockOpener({self.url(): (503, {}, b"")})
        with self.assertRaises(gm.TransientError):
            gm.fetch_one("o", "r", None, opener=op, sleep=NOSLEEP)

    def test_malformed_non_json(self):
        op = MockOpener({self.url(): (200, {}, b"<html>not json</html>")})
        with self.assertRaises(gm.MalformedResponse):
            gm.fetch_one("o", "r", None, opener=op, sleep=NOSLEEP)

    def test_malformed_missing_stars(self):
        op = MockOpener({self.url(): (200, {}, json.dumps({"full_name": "o/r"}).encode())})
        with self.assertRaises(gm.MalformedResponse):
            gm.fetch_one("o", "r", None, opener=op, sleep=NOSLEEP)


class TestCache(_EnvMixin):
    def test_fresh_hit_makes_zero_requests(self):
        cache = self.p("cache.json")
        gm.atomic_write_json(cache, {"repos": {"o/r": {
            "status": "ok", "stars": 42, "canonical_url": "https://github.com/o/r",
            "fetched_at": gm._now_iso()}}})
        hits = self.write("hits.json", {"hits": [{"target_url": "https://github.com/o/r"}]})
        op = MockOpener({})
        gm.prefetch(hits, cache, self.p("out.json"), opener=op, sleep=NOSLEEP)
        self.assertEqual(op.n, 0)  # served entirely from cache
        out = json.load(open(self.p("out.json")))
        self.assertEqual(out["repos"]["o/r"]["stars"], 42)

    def test_stale_entry_refreshes(self):
        cache = self.p("cache.json")
        gm.atomic_write_json(cache, {"repos": {"o/r": {
            "status": "ok", "stars": 1, "fetched_at": "2000-01-01T00:00:00Z"}}})
        hits = self.write("hits.json", {"hits": [{"target_url": "https://github.com/o/r"}]})
        op = MockOpener({gm.API.format(owner="o", repo="r"): (200, hdr(remaining=4990), body(stars=999))})
        gm.prefetch(hits, cache, self.p("out.json"), max_age_days=7, opener=op, sleep=NOSLEEP)
        self.assertEqual(op.n, 1)
        self.assertEqual(json.load(open(cache))["repos"]["o/r"]["stars"], 999)

    def test_atomic_write_survives_interruption(self):
        cache = self.p("cache.json")
        gm.atomic_write_json(cache, {"repos": {"keep": {"status": "ok", "stars": 7}}})
        orig = open(cache).read()
        real_replace = gm.os.replace
        try:
            gm.os.replace = lambda *a, **k: (_ for _ in ()).throw(OSError("boom"))
            with self.assertRaises(OSError):
                gm.atomic_write_json(cache, {"repos": {"lost": {"status": "ok", "stars": 9}}})
        finally:
            gm.os.replace = real_replace
        self.assertEqual(open(cache).read(), orig)  # original intact
        leftover = [f for f in os.listdir(self.tmp) if f.startswith(".gh_meta_")]
        self.assertEqual(leftover, [])              # temp cleaned up

    def test_transient_failure_not_cached(self):
        cache = self.p("cache.json")
        gm.atomic_write_json(cache, {"repos": {}})
        hits = self.write("hits.json", {"hits": [{"target_url": "https://github.com/o/r"}]})
        op = MockOpener({gm.API.format(owner="o", repo="r"): (503, {}, b"")})
        gm.prefetch(hits, cache, self.p("out.json"), opener=op, sleep=NOSLEEP)
        self.assertNotIn("o/r", json.load(open(cache))["repos"])  # failure not persisted
        self.assertEqual(json.load(open(self.p("out.json")))["repos"]["o/r"]["status"], "error")


class TestPrefetchModes(_EnvMixin):
    def test_authenticated_mode_and_no_token_leak(self):
        os.environ["GITHUB_TOKEN"] = TOKEN
        cache, out = self.p("cache.json"), self.p("out.json")
        hits = self.write("hits.json", {"hits": [{"target_url": "https://github.com/o/r"}]})
        op = MockOpener({gm.API.format(owner="o", repo="r"): (200, hdr(remaining=4999, limit=5000), body(stars=3))})
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            gm.prefetch(hits, cache, out, opener=op, sleep=NOSLEEP)
        stdout = buf.getvalue()
        self.assertIn('"mode": "authenticated"', json.dumps(json.load(open(out))))
        # token must appear NOWHERE the caller can see it
        for blob in (open(cache).read(), open(out).read(), stdout):
            self.assertNotIn(TOKEN, blob)

    def test_unauthenticated_bounded_fallback(self):
        cache, out = self.p("cache.json"), self.p("out.json")
        hits = self.write("hits.json", {"hits": [
            {"target_url": "https://github.com/o/r%d" % i} for i in range(5)]})
        responses = {gm.API.format(owner="o", repo="r%d" % i): (200, hdr(remaining=59), body(stars=i))
                     for i in range(5)}
        op = MockOpener(responses)
        gm.prefetch(hits, cache, out, max_unauth=2, opener=op, sleep=NOSLEEP)
        self.assertEqual(op.n, 2)  # strictly bounded to 2 live requests
        outd = json.load(open(out))
        self.assertEqual(outd["mode"], "unauthenticated")
        skipped = [k for k, v in outd["repos"].items() if v["status"] == "skipped"]
        self.assertEqual(len(skipped), 3)

    def test_rate_limit_stops_further_fetches(self):
        cache, out = self.p("cache.json"), self.p("out.json")
        hits = self.write("hits.json", {"hits": [
            {"target_url": "https://github.com/o/a"}, {"target_url": "https://github.com/o/b"}]})
        op = MockOpener({
            gm.API.format(owner="o", repo="a"): (403, hdr(remaining=0, reset=123), b""),
            gm.API.format(owner="o", repo="b"): (200, hdr(remaining=0), body(stars=1)),
        })
        gm.prefetch(hits, cache, out, opener=op, sleep=NOSLEEP)
        self.assertEqual(op.n, 1)  # stopped after the rate-limit hit; did not call repo b
        self.assertTrue(json.load(open(out))["rate_limited"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
