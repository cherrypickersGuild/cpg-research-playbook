#!/usr/bin/env python3
"""hash_tree.py — deterministic recursive SHA-256 manifest of a directory.

Used wherever the plan needs to prove that a tree is byte-identical before and
after an operation: the real publication path during the acceptance run, and
state/matrix/ across the matrix-boundary test.

Why not `git status`: an untracked file created inside the tree would not show
up as a modification, and a gitignored file would not show up at all. Hashing
every regular file catches both.

  Usage:
    python scripts/harvest/hash_tree.py <dir> [--out FILE]

  Prints (or writes) one line per file, sorted by POSIX-normalized relative path:
      <sha256>  <bytes>  <relpath>

  A missing directory is not an error — it produces an empty manifest, so a
  before/after comparison works even when the tree is created by the operation
  under test.

  Exit 0 always, except on an unreadable file or unwritable --out (exit 1).
"""
import argparse
import hashlib
import os
import sys

CHUNK = 1 << 20


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def walk(root):
    """Yield (relpath, sha256, size) for every regular file under root.

    Symlinks are reported by their own path but never followed, so a link
    pointing outside the tree cannot silently pull foreign bytes into the
    manifest.
    """
    rows = []
    if not os.path.isdir(root):
        return rows
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            ap = os.path.join(dirpath, name)
            rel = os.path.relpath(ap, root).replace(os.sep, "/")
            if os.path.islink(ap):
                rows.append((rel, "SYMLINK:" + os.readlink(ap), -1))
                continue
            rows.append((rel, sha256_file(ap), os.path.getsize(ap)))
    rows.sort(key=lambda r: r[0])
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description="Deterministic recursive SHA-256 manifest.")
    p.add_argument("directory")
    p.add_argument("--out", default=None, help="write here instead of stdout")
    args = p.parse_args(argv)

    try:
        rows = walk(args.directory)
    except OSError as exc:
        sys.stderr.write("hash_tree: cannot read %s: %s\n" % (args.directory, exc.strerror))
        return 1

    lines = ["%s  %d  %s" % (h, size, rel) for rel, h, size in rows]
    body = "\n".join(lines) + ("\n" if lines else "")

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8", newline="\n") as f:
                f.write(body)
        except OSError as exc:
            sys.stderr.write("hash_tree: cannot write %s: %s\n" % (args.out, exc.strerror))
            return 1
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
