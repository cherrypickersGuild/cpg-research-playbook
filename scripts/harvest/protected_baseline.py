#!/usr/bin/env python3
"""protected_baseline.py — generate and verify the protected-file baseline.

The question this has to answer is narrow and strict:

    Do the exact bytes on disk provably derive from the implementation-start
    commit, and are they still those bytes now?

Hashing the working tree alone cannot answer it (it blesses whatever happens to
be there). Hashing the raw stored blob alone cannot answer it either: this repo
is checked out with core.autocrlf=true and has no .gitattributes, so a text file
on disk is CRLF while the stored blob is LF, and those digests never match.

So the authority is Git's own rendering of the commit. For each protected path
we compute BOTH renderings the repository can legitimately produce:

    filtered = git cat-file --filters --path=<p> <commit>:<p>
               the commit put through the current smudge/EOL rules, i.e. what a
               fresh checkout would write to disk (CRLF here);
    blob     = git cat-file blob <commit>:<p>
               the stored bytes verbatim (LF here).

The working tree must byte-match one of them, and the baseline records WHICH.

Why both are accepted: this working tree is genuinely mixed, and that is a
pre-existing condition, not drift. 10 of the 18 protected files are pure LF on
disk (every *.sh and *.py — written by tooling that emits LF) and 8 are pure
CRLF (merge_entity_registry.sh and the large JSON state files — written by a git
checkout). Demanding the filtered rendering for all of them would report drift on
10 unmodified files; demanding the blob for all would report drift on 8. Both
renderings are Git-produced from the commit, so accepting either still proves
derivation, and pinning the observed one in the baseline is what makes the check
strict afterwards.

That pinning is what catches the case a normalized diff cannot:

    an LF-only rewrite of a file that was CRLF at baseline changes its
    raw_sha256 AND flips its eol_form from "filtered" to "blob" — both are
    recorded, so both fire, even though `git diff` still reports the file clean.

  Usage:
    python scripts/harvest/protected_baseline.py generate [--replace-baseline]
    python scripts/harvest/protected_baseline.py verify [--quiet]

  Env overrides (used by the test harness only):
    PROTECTED_BASE_COMMIT   commit to treat as the implementation start
    PROTECTED_PATHS_FILE    path list
    PROTECTED_BASELINE      baseline file

Exit 0 on success; 1 on drift, tampering, missing commit/path, or a refused
regeneration.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

DEFAULT_BASE_COMMIT = "8865c54e2cc8d879410576f247baac4aea149f34"
DEFAULT_PATHS_FILE = "tests/fixtures/taxonomy/protected_paths.txt"
DEFAULT_BASELINE = "tests/fixtures/taxonomy/protected_sha256.txt"


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def git(args, check=True):
    return subprocess.run(["git"] + args, capture_output=True, check=check)


def read_paths(paths_file):
    out = []
    with open(paths_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line)
    return out


def renderings(commit, path):
    """Both legitimate Git renderings of `path` at `commit`.

    Returns (filtered_bytes, blob_bytes, blob_id) or raises RuntimeError if the
    path does not exist in the commit.
    """
    spec = "%s:%s" % (commit, path)
    try:
        blob_id = git(["rev-parse", spec]).stdout.decode().strip()
    except subprocess.CalledProcessError:
        raise RuntimeError("%s does not exist in commit %s" % (path, commit))
    filtered = git(["cat-file", "--filters", "--path=" + path, spec]).stdout
    blob = git(["cat-file", "blob", spec]).stdout
    return filtered, blob, blob_id


def classify(worktree, filtered, blob):
    """Which Git rendering the on-disk bytes match.

    'identical' means the two renderings are the same (no EOL conversion applies
    to this file), so the distinction is moot and either name would do.
    """
    wt = sha256_bytes(worktree)
    f, b = sha256_bytes(filtered), sha256_bytes(blob)
    if f == b:
        return "identical" if wt == f else None
    if wt == f:
        return "filtered"
    if wt == b:
        return "blob"
    return None


def load_baseline(path):
    rows = {}
    meta = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("#"):
                if ":" in line:
                    k, _, v = line[1:].partition(":")
                    meta[k.strip()] = v.strip()
                continue
            if not line.strip():
                continue
            parts = line.split("  ")
            parts = [p for p in parts if p != ""]
            if len(parts) != 4:
                raise RuntimeError("malformed baseline row: %r" % line)
            raw_sha, eol_form, blob_id, p = parts
            rows[p] = {"raw_sha256": raw_sha, "eol_form": eol_form, "blob_id": blob_id}
    return meta, rows


def cmd_generate(args):
    commit = os.environ.get("PROTECTED_BASE_COMMIT", DEFAULT_BASE_COMMIT)
    paths_file = os.environ.get("PROTECTED_PATHS_FILE", DEFAULT_PATHS_FILE)
    out = os.environ.get("PROTECTED_BASELINE", DEFAULT_BASELINE)

    if os.path.exists(out) and not args.replace_baseline:
        sys.stderr.write(
            "ERROR: %s already exists.\n"
            "       The baseline is generated once, before implementation, and committed.\n"
            "       Regenerating it would let an accidental modification bless itself.\n"
            "       Pass --replace-baseline only if you genuinely intend to move it.\n" % out)
        return 1

    try:
        git(["cat-file", "-e", commit + "^{commit}"])
    except subprocess.CalledProcessError:
        sys.stderr.write("ERROR: implementation-start commit %s not found.\n" % commit)
        return 1

    paths = read_paths(paths_file)
    rows, drift = [], 0

    for p in paths:
        if not os.path.isfile(p):
            sys.stderr.write("ERROR: protected path missing from the working tree: %s\n" % p)
            drift = 1
            continue
        try:
            filtered, blob, blob_id = renderings(commit, p)
        except RuntimeError as exc:
            sys.stderr.write("ERROR: %s\n" % exc)
            drift = 1
            continue

        wt = open(p, "rb").read()
        form = classify(wt, filtered, blob)
        if form is None:
            sys.stderr.write(
                "ERROR: %s matches NEITHER Git rendering of %s — this is real drift.\n"
                "         working tree : %s (%d bytes)\n"
                "         filtered     : %s (%d bytes)\n"
                "         blob         : %s (%d bytes)\n"
                % (p, commit, sha256_bytes(wt), len(wt),
                   sha256_bytes(filtered), len(filtered),
                   sha256_bytes(blob), len(blob)))
            drift = 1
            continue
        rows.append((sha256_bytes(wt), form, blob_id, p))

    if drift:
        sys.stderr.write("ERROR: refusing to generate a baseline from a drifted working tree.\n")
        return 1

    rows.sort(key=lambda r: r[3])
    n_filtered = sum(1 for r in rows if r[1] == "filtered")
    n_blob = sum(1 for r in rows if r[1] == "blob")
    n_ident = sum(1 for r in rows if r[1] == "identical")

    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("# protected-file baseline\n")
        f.write("# generated_from_commit: %s\n" % commit)
        f.write("# generated_at: %s\n" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        f.write("# core.autocrlf: %s\n" % (git(["config", "core.autocrlf"], check=False).stdout.decode().strip() or "unset"))
        f.write("# gitattributes: %s\n" % ("present" if os.path.exists(".gitattributes") else "absent"))
        f.write("#\n")
        f.write("# format: <raw_sha256>  <eol_form>  <blob_id>  <path>\n")
        f.write("#\n")
        f.write("#   raw_sha256  hashlib.sha256 over the EXACT working-tree bytes.\n")
        f.write("#   eol_form    which Git rendering of the commit those bytes matched:\n")
        f.write("#                 filtered  = git cat-file --filters (a fresh checkout; CRLF here)\n")
        f.write("#                 blob      = git cat-file blob      (stored verbatim; LF here)\n")
        f.write("#                 identical = both renderings are the same for this file\n")
        f.write("#               Pinning the observed form is what catches an LF-only rewrite of a\n")
        f.write("#               CRLF file, which `git diff` normalizes away and reports as clean.\n")
        f.write("#   blob_id     git object id at the commit; anchors the row to the commit.\n")
        f.write("#\n")
        f.write("# file_count: %d  (filtered=%d blob=%d identical=%d)\n"
                % (len(rows), n_filtered, n_blob, n_ident))
        f.write("# path_list: %s\n" % paths_file)
        f.write("#\n")
        f.write("# Verify with: bash scripts/harvest/verify_protected_baseline.sh\n")
        for raw_sha, form, blob_id, p in rows:
            f.write("%s  %s  %s  %s\n" % (raw_sha, form, blob_id, p))

    print("[baseline] wrote %d protected entries -> %s (commit %s; filtered=%d blob=%d identical=%d)"
          % (len(rows), out, commit, n_filtered, n_blob, n_ident))
    return 0


def cmd_verify(args):
    commit = os.environ.get("PROTECTED_BASE_COMMIT", DEFAULT_BASE_COMMIT)
    paths_file = os.environ.get("PROTECTED_PATHS_FILE", DEFAULT_PATHS_FILE)
    baseline = os.environ.get("PROTECTED_BASELINE", DEFAULT_BASELINE)

    if not os.path.exists(baseline):
        sys.stderr.write("ERROR: missing %s — run gen_protected_baseline.sh once, before implementation.\n" % baseline)
        return 1
    try:
        git(["cat-file", "-e", commit + "^{commit}"])
    except subprocess.CalledProcessError:
        sys.stderr.write("ERROR: implementation-start commit %s not found.\n" % commit)
        return 1

    try:
        _meta, recorded = load_baseline(baseline)
    except RuntimeError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1

    paths = read_paths(paths_file)
    fail = 0

    for p in paths:
        row = recorded.get(p)
        if row is None:
            sys.stderr.write("FAIL: %s is protected but absent from %s\n" % (p, baseline))
            fail = 1
            continue
        if not os.path.isfile(p):
            sys.stderr.write("FAIL: protected path missing from the working tree: %s\n" % p)
            fail = 1
            continue

        try:
            filtered, blob, blob_id = renderings(commit, p)
        except RuntimeError as exc:
            sys.stderr.write("FAIL: %s\n" % exc)
            fail = 1
            continue

        wt = open(p, "rb").read()
        wt_sha = sha256_bytes(wt)

        # check 1 (primary) — exact working-tree bytes vs the recorded rendering
        # of the commit, recomputed now. Not vs a number copied from the file:
        # the expected value is derived from the commit every time.
        expected = {"filtered": filtered, "blob": blob, "identical": blob}.get(row["eol_form"])
        if expected is None:
            sys.stderr.write("FAIL: %s has unknown eol_form %r in the baseline\n" % (p, row["eol_form"]))
            fail = 1
            continue
        expected_sha = sha256_bytes(expected)

        if wt_sha != expected_sha:
            observed = classify(wt, filtered, blob)
            sys.stderr.write(
                "FAIL: %s does not match the %s rendering of %s\n"
                "        expected (%s): %s\n"
                "        working tree : %s\n"
                % (p, row["eol_form"], commit, row["eol_form"], expected_sha, wt_sha))
            if observed is not None and observed != row["eol_form"]:
                sys.stderr.write(
                    "        NOTE: the bytes match the %r rendering instead. This is an\n"
                    "              EOL-only rewrite — `git diff` normalizes it away and reports\n"
                    "              the file clean, but the on-disk bytes changed.\n" % observed)
            fail = 1

        # check 2 — the baseline's own raw_sha256 must agree with the commit
        # rendering too, so a tampered baseline cannot hide a change.
        if row["raw_sha256"] != expected_sha:
            sys.stderr.write(
                "FAIL: %s disagrees with commit %s for %s (baseline tampered or stale)\n"
                "        baseline raw_sha256: %s\n"
                "        commit rendering   : %s\n"
                % (baseline, commit, p, row["raw_sha256"], expected_sha))
            fail = 1

        # check 3 — blob id anchors the row to the commit
        if row["blob_id"] != blob_id:
            sys.stderr.write(
                "FAIL: %s blob_id disagrees with commit %s for %s\n"
                "        baseline: %s\n        commit  : %s\n"
                % (baseline, commit, p, row["blob_id"], blob_id))
            fail = 1

    # check 4 — independent, eol-normalized: Git's own view of modification
    diff = git(["diff", "--exit-code", "--name-only", commit, "--"] + paths, check=False)
    if diff.returncode != 0:
        names = diff.stdout.decode(errors="replace").strip()
        if names:
            sys.stderr.write("FAIL: git reports modifications vs %s:\n%s\n" % (commit, names))
            fail = 1

    if fail:
        sys.stderr.write("ERROR: protected-baseline verification FAILED.\n")
        return 1
    if not args.quiet:
        print("[baseline] OK — %d protected files byte-match Git's rendering of %s "
              "(exact bytes + pinned eol_form + blob_id + git diff)" % (len(paths), commit))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate or verify the protected-file baseline.")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--replace-baseline", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)
    return cmd_generate(args) if args.cmd == "generate" else cmd_verify(args)


if __name__ == "__main__":
    sys.exit(main())
