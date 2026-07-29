#!/usr/bin/env python3
"""artifacts.py — deterministic, atomic artifact writing (S5-1).

Stage 4 built records in memory and wrote nothing. This module is the one place
that puts bytes on disk, and it exists so that every artifact in Stage 5 gets the
same three guarantees rather than each writer inventing its own:

  * ONE SERIALIZATION. Identical logical input yields identical bytes. Key order
    comes from `sort_keys`, not from dict insertion order, so a document built by
    two different code paths still hashes the same. The explicit `newline="\\n"`
    matters: this repository is checked out on Windows, and text mode would
    otherwise turn every artifact into CRLF and break byte-comparison against a
    POSIX run.
  * NOTHING PARTIAL IS EVER READABLE. Writes go to a uniquely named temp file in
    the DESTINATION directory, are fsynced, and are then moved into place with
    `os.replace`. A reader sees the previous complete artifact or the new
    complete artifact — never a half-written one. The temp name is unique per
    write (`uuid4`), never a fixed `<file>.tmp`, because a fixed name is a shared
    name and two writers would interleave through it.
  * NOTHING INVALID REACHES DISK. `write_document` validates against the
    committed schema BEFORE serializing. A document that does not validate raises
    and writes no file at all, so the artifact tree can be trusted without
    re-reading it.

A temp file never outlives its write: failure and interruption both clean up, so
an interrupted run leaves the previous artifact intact and no debris behind.

Not here: what any artifact MEANS. No cell, topic, ledger, rejection, coverage or
manifest semantics (S5-2 … S5-5), no cell execution (S5-6), no locking, no
concurrency, no network. This module knows about paths, bytes and schemas.
"""
import datetime
import json
import os
import uuid

from . import schema

# `YYYYMMDDTHHMMSSZ-<pid>`, the run identifier format fixed by
# IMPLEMENTATION_PLAN.md §10.
RUN_ID_FORMAT = "%Y%m%dT%H%M%SZ"

# Every in-flight write is `<dir>/.tmp_<uuid4hex>_<basename>`. The prefix is
# matched by the committed `state/.tmp_*` ignore rule and is what a sweeper
# looks for; no code path ever READS a file with this prefix.
TEMP_PREFIX = ".tmp_"


class ArtifactError(Exception):
    """A contract violation this module refuses to paper over."""


# --------------------------------------------------------------- serialization
def serialize(doc):
    """The one serialization. Deterministic bytes, UTF-8, LF, trailing newline.

    `sort_keys` makes byte output a function of content rather than of how the
    dict happened to be built. `ensure_ascii=False` keeps non-ASCII titles
    readable instead of escaping them into `\\uXXXX`.
    """
    text = json.dumps(doc, sort_keys=True, ensure_ascii=False, indent=2,
                      separators=(",", ": ")) + "\n"
    return text.encode("utf-8")


# ----------------------------------------------------------------- atomic write
def _temp_path(directory, name):
    return os.path.join(directory, "%s%s_%s" % (TEMP_PREFIX, uuid.uuid4().hex, name))


def _fsync_dir(directory):
    """Make the rename itself durable, where the platform allows it.

    Opening a directory read-only is a POSIX facility; Windows refuses it. That
    is a durability nicety, not a correctness requirement — `os.replace` has
    already made the swap atomic — so failure here is ignored rather than
    surfaced as an artifact failure.
    """
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_atomic(path, data):
    """Write `data` to `path` so that no partial file is ever observable.

    The temp file is created in the DESTINATION directory, not a system temp
    dir, because `os.replace` is only atomic within one filesystem. Missing
    parent directories are created — the artifact layout is nested, and having
    every caller repeat that is how a caller eventually forgets.
    """
    if not isinstance(data, bytes):
        raise ArtifactError("write_atomic needs bytes, got %s" % type(data).__name__)

    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    tmp = _temp_path(directory, os.path.basename(path))
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        # BaseException, not Exception: KeyboardInterrupt is exactly the
        # interruption this cleanup exists for. The temp file must not outlive
        # the write that created it.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _fsync_dir(directory)
    return path


def write_document(path, doc, schema_name):
    """Validate against the committed schema, then serialize, then write.

    Validation comes first so an invalid document leaves the filesystem exactly
    as it was — no truncated file, no stale temp, no "write it and check later".
    """
    errors = schema.validate(doc, schema_name)
    if errors:
        raise ArtifactError("document does not validate against %s (%d problem(s)): %s"
                            % (schema_name, len(errors), "; ".join(errors[:3])))
    return write_atomic(path, serialize(doc))


# ------------------------------------------------------------------- run paths
def run_id(clock=None, pid=None):
    """`YYYYMMDDTHHMMSSZ-<pid>`. Both parts injectable so runs are reproducible."""
    now = clock() if clock is not None else datetime.datetime.now(datetime.timezone.utc)
    return "%s-%d" % (now.strftime(RUN_ID_FORMAT),
                      os.getpid() if pid is None else pid)


def run_dir(root, run_id_value):
    """The per-run directory under an injected root. Creates nothing."""
    if not run_id_value:
        raise ArtifactError("run_dir needs a run_id")
    return os.path.join(root, "runs", run_id_value)
