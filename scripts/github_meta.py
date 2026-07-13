#!/usr/bin/env python3
"""github_meta.py — deterministic, cached, sanitized GitHub repo metadata.

Fetches GitHub repository metadata (stars, canonical URL, status) OUTSIDE the
model so the 1G extractor can read a local sanitized file instead of calling
``api.github.com`` per repository through WebFetch — which exhausts the
unauthenticated 60-req/hour limit and stalls the harvest. Topic-agnostic:
operates purely on GitHub URLs found in the candidate hits.

Security model (do not weaken):
  * The API token is read ONLY from the environment: GITHUB_TOKEN, then GH_TOKEN.
  * It is sent ONLY as an ``Authorization: Bearer <token>`` HTTP header — never in
    a URL, a command-line argument, a log line, the cache, or the output file.
  * The token value is never printed, logged, persisted, or serialized. Error
    output is redacted to a status code + generic message (never response
    headers/body that could echo credentials).
  * The cache and the ``--out`` file contain only sanitized repo metadata plus
    non-sensitive rate-limit numbers (remaining/reset/limit).

Usage:
  python github_meta.py prefetch --hits HITS.json --cache CACHE.json --out OUT.json
        [--max-age-days N] [--max-unauth N] [--timeout S]
  python github_meta.py fetch --repo owner/repo --cache CACHE.json   # single; prints sanitized JSON

prefetch always writes a valid --out (possibly with non-"ok" per-repo statuses)
and exits 0 even when some repos fail or the rate limit is hit, so a metadata
hiccup never aborts the harvest. Exit 1 only on bad arguments or an unwritable
cache/out path.
"""
import argparse
import datetime
import json
import os
import re
import sys
import tempfile
import time

API = "https://api.github.com/repos/{owner}/{repo}"
# repo-root only: https://github.com/<owner>/<repo>  (no gist/org/issues/file paths)
_REPO_RE = re.compile(r"^https?://(?:www\.)?github\.com/([^/#?]+)/([^/#?]+?)(?:\.git)?/?$", re.I)
_UA = "axCaseResearch-harvest-github-meta"


# --------------------------------------------------------------------------- token
def read_token():
    """GITHUB_TOKEN then GH_TOKEN from the environment; else None. Never logged."""
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(name)
        if v and v.strip():
            return v.strip()
    return None


# --------------------------------------------------------------------------- urls
def parse_repo(url):
    """Return (owner, repo) if url is a GitHub repo root, else None. Excludes
    gists, org pages, issues, file paths, and other non-repo GitHub shapes."""
    if not isinstance(url, str):
        return None
    m = _REPO_RE.match(url.strip())
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    if owner.lower() in ("orgs", "sponsors", "settings", "marketplace", "topics", "features"):
        return None
    return owner, repo


def repo_key(owner, repo):
    """Stable, case-insensitive cache key (GitHub owner/repo are case-insensitive)."""
    return owner.lower() + "/" + repo.lower()


# --------------------------------------------------------------------------- errors
class RateLimited(Exception):
    def __init__(self, reset=None):
        super().__init__("rate limited")
        self.reset = reset


class NotFound(Exception):
    pass


class MalformedResponse(Exception):
    pass


class TransientError(Exception):
    pass


class NetworkError(Exception):
    pass


# --------------------------------------------------------------------------- http
def _headers_dict(h):
    try:
        return {k.lower(): v for k, v in dict(h).items()}
    except Exception:
        return {}


def default_opener(req, timeout=15):
    """Perform the request. Returns (status:int, headers:dict, body:bytes).
    Raises NetworkError on connection failure. Never returns/raises the token."""
    import urllib.request
    import urllib.error
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)  # follows 3xx for GET
        return resp.getcode(), _headers_dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read()
        except Exception:
            body = b""
        return e.code, _headers_dict(e.headers), body
    except urllib.error.URLError as e:
        raise NetworkError(str(getattr(e, "reason", "url error")))
    except Exception:
        raise NetworkError("connection failed")


def _build_request(owner, repo, token):
    """Build the API GET request. Auth ONLY via header; token never in the URL."""
    import urllib.request
    url = API.format(owner=owner, repo=repo)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": _UA,
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    return urllib.request.Request(url, headers=headers, method="GET")


def _rate_limit_from_headers(h):
    def _int(name):
        try:
            return int(h.get(name))
        except (TypeError, ValueError):
            return None
    return {"remaining": _int("x-ratelimit-remaining"),
            "reset": _int("x-ratelimit-reset"),
            "limit": _int("x-ratelimit-limit")}


def fetch_one(owner, repo, token, opener=default_opener, timeout=15,
              retries=3, backoff=0.5, sleep=time.sleep, _redirects_left=3):
    """Fetch sanitized metadata for one repo. Returns (meta:dict, rate_limit:dict).
    Raises RateLimited / NotFound / MalformedResponse / TransientError. The token
    is used only inside the request header and never appears in any raised value."""
    attempt = 0
    while True:
        attempt += 1
        req = _build_request(owner, repo, token)
        try:
            status, headers, body = opener(req, timeout)
        except NetworkError:
            if attempt <= retries:
                sleep(backoff * (2 ** (attempt - 1)))
                continue
            raise TransientError("network error after %d attempts" % attempt)

        rl = _rate_limit_from_headers(headers)

        if status == 200:
            try:
                data = json.loads(body.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise MalformedResponse("200 body was not valid JSON")
            if not isinstance(data, dict) or "stargazers_count" not in data \
                    or not isinstance(data.get("stargazers_count"), int):
                raise MalformedResponse("200 body missing integer stargazers_count")
            meta = {
                "status": "ok",
                "stars": int(data["stargazers_count"]),
                "canonical_url": data.get("html_url") or ("https://github.com/%s/%s" % (owner, repo)),
                "full_name": data.get("full_name"),
                "archived": bool(data.get("archived", False)),
                "pushed_at": data.get("pushed_at"),
            }
            return meta, rl

        if status in (301, 302, 307, 308):
            loc = headers.get("location")
            m = parse_repo(loc) if loc else None
            if m and _redirects_left > 0:
                return fetch_one(m[0], m[1], token, opener, timeout, retries,
                                 backoff, sleep, _redirects_left - 1)
            raise MalformedResponse("unfollowable redirect")

        if status == 404:
            raise NotFound()

        if status == 429 or (status == 403 and rl.get("remaining") == 0):
            raise RateLimited(reset=rl.get("reset"))

        if status == 403:
            # secondary/abuse limit or auth problem — transient, retry a bounded number
            if attempt <= retries:
                sleep(backoff * (2 ** (attempt - 1)))
                continue
            raise TransientError("403 after %d attempts" % attempt)

        if 500 <= status < 600:
            if attempt <= retries:
                sleep(backoff * (2 ** (attempt - 1)))
                continue
            raise TransientError("server %d after %d attempts" % (status, attempt))

        raise TransientError("unexpected status %d" % status)


# --------------------------------------------------------------------------- cache
def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_cache(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("repos"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"repos": {}}


def _parse_iso(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except (TypeError, ValueError):
        return None


def is_fresh(entry, max_age_days):
    """Fresh iff a DEFINITIVE status (ok/not_found) fetched within max_age_days.
    Transient failures are never cached, so they are never 'fresh'."""
    if not isinstance(entry, dict) or entry.get("status") not in ("ok", "not_found"):
        return False
    ts = _parse_iso(entry.get("fetched_at"))
    if ts is None:
        return False
    age = datetime.datetime.now(datetime.timezone.utc) - ts
    return age <= datetime.timedelta(days=max_age_days)


def atomic_write_json(path, obj):
    """Write JSON via temp-file + os.replace so an interruption cannot corrupt
    the destination (the old file survives until the atomic rename)."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".gh_meta_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# --------------------------------------------------------------------------- prefetch
def _repos_from_hits(hits_obj):
    seen, out = set(), []
    for h in (hits_obj.get("hits") or []) if isinstance(hits_obj, dict) else []:
        if not isinstance(h, dict):
            continue
        m = parse_repo(h.get("target_url"))
        if not m:
            continue
        k = repo_key(*m)
        if k not in seen:
            seen.add(k)
            out.append((m[0], m[1], k))
    return out


def prefetch(hits_path, cache_path, out_path, max_age_days=7, max_unauth=50,
             timeout=15, opener=default_opener, sleep=time.sleep):
    """Prefetch metadata for GitHub repos referenced by the candidate hits,
    reusing fresh cache entries and refreshing stale/missing ones. Writes a
    sanitized --out for the 1G extractor and updates the cache atomically."""
    try:
        with open(hits_path, "r", encoding="utf-8") as f:
            hits_obj = json.load(f)
    except (OSError, ValueError):
        hits_obj = {"hits": []}

    repos = _repos_from_hits(hits_obj)
    cache = load_cache(cache_path)
    token = read_token()
    mode = "authenticated" if token else "unauthenticated"
    live_budget = (10 ** 9) if token else max(0, int(max_unauth))

    out_repos = {}
    rate_limit = {"remaining": None, "reset": None, "limit": None}
    rate_limited = False
    fetched = failed = from_cache = 0

    for owner, repo, key in repos:
        entry = cache["repos"].get(key)
        if is_fresh(entry, max_age_days):
            out_repos[key] = _sanitize_entry(entry)
            from_cache += 1
            continue
        if rate_limited or live_budget <= 0:
            # No fresh cache and no budget/limit left: expose a stale entry if we
            # have one, else record 'skipped' (never fabricate an ok result).
            out_repos[key] = _sanitize_entry(entry) if isinstance(entry, dict) and entry.get("status") in ("ok", "not_found") else {
                "status": "skipped", "stars": None, "fetched_at": None}
            continue
        live_budget -= 1
        try:
            meta, rl = fetch_one(owner, repo, token, opener=opener, timeout=timeout, sleep=sleep)
            meta["fetched_at"] = _now_iso()
            cache["repos"][key] = meta            # cache only definitive success
            out_repos[key] = _sanitize_entry(meta)
            fetched += 1
            _merge_rl(rate_limit, rl)
        except NotFound:
            nf = {"status": "not_found", "stars": None, "canonical_url": None, "fetched_at": _now_iso()}
            cache["repos"][key] = nf              # 404 is definitive -> cacheable
            out_repos[key] = _sanitize_entry(nf)
            fetched += 1
        except RateLimited as e:
            rate_limited = True
            rate_limit["reset"] = e.reset
            rate_limit["remaining"] = 0
            out_repos[key] = {"status": "skipped", "stars": None, "fetched_at": None}
        except (MalformedResponse, TransientError):
            # NOT cached (so a later run retries); recorded as error for this run.
            failed += 1
            out_repos[key] = {"status": "error", "stars": None, "fetched_at": None}

    out = {
        "generated_at": _now_iso(),
        "mode": mode,
        "rate_limit": rate_limit,
        "rate_limited": rate_limited,
        "repos": out_repos,
    }
    atomic_write_json(out_path, out)
    atomic_write_json(cache_path, cache)

    # sanitized stdout summary — no token, no headers, no raw responses
    print(json.dumps({
        "mode": mode, "repos_seen": len(repos), "fetched": fetched,
        "from_cache": from_cache, "failed": failed, "rate_limited": rate_limited,
        "rate_limit_remaining": rate_limit.get("remaining"),
        "rate_limit_reset": rate_limit.get("reset"),
    }))
    return 0


def _sanitize_entry(entry):
    if not isinstance(entry, dict):
        return {"status": "error", "stars": None, "fetched_at": None}
    return {
        "status": entry.get("status"),
        "stars": entry.get("stars"),
        "canonical_url": entry.get("canonical_url"),
        "archived": entry.get("archived"),
        "pushed_at": entry.get("pushed_at"),
        "fetched_at": entry.get("fetched_at"),
    }


def _merge_rl(dst, rl):
    for k in ("remaining", "reset", "limit"):
        if rl.get(k) is not None:
            dst[k] = rl[k]


# --------------------------------------------------------------------------- cli
def main(argv=None):
    p = argparse.ArgumentParser(description="Deterministic cached GitHub repo metadata (sanitized).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("prefetch")
    pp.add_argument("--hits", required=True)
    pp.add_argument("--cache", required=True)
    pp.add_argument("--out", required=True)
    pp.add_argument("--max-age-days", type=int, default=7)
    pp.add_argument("--max-unauth", type=int, default=50)
    pp.add_argument("--timeout", type=int, default=15)

    pf = sub.add_parser("fetch")
    pf.add_argument("--repo", required=True, help="owner/repo")
    pf.add_argument("--cache", required=True)
    pf.add_argument("--timeout", type=int, default=15)

    args = p.parse_args(argv)

    if args.cmd == "prefetch":
        try:
            return prefetch(args.hits, args.cache, args.out,
                            max_age_days=args.max_age_days, max_unauth=args.max_unauth,
                            timeout=args.timeout)
        except OSError as e:
            sys.stderr.write("github_meta: cannot write cache/out: %s\n" % e.strerror)
            return 1

    if args.cmd == "fetch":
        if "/" not in args.repo:
            sys.stderr.write("github_meta: --repo must be owner/repo\n")
            return 1
        owner, repo = args.repo.split("/", 1)
        token = read_token()
        try:
            meta, rl = fetch_one(owner, repo, token)
            meta["fetched_at"] = _now_iso()
            print(json.dumps({"repo": repo_key(owner, repo), "meta": _sanitize_entry(meta),
                              "mode": "authenticated" if token else "unauthenticated",
                              "rate_limit_remaining": rl.get("remaining")}))
            return 0
        except NotFound:
            print(json.dumps({"repo": repo_key(owner, repo), "meta": {"status": "not_found", "stars": None}}))
            return 0
        except (RateLimited, MalformedResponse, TransientError) as e:
            sys.stderr.write("github_meta: fetch failed (%s)\n" % type(e).__name__)  # redacted: type only
            return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
