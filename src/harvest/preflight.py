#!/usr/bin/env python3
"""preflight.py — the configured-source preflight (Stage 9, checkpoint S9-2).

Assembly, and only assembly. The probe itself is the committed
`HttpClient.preflight()`, which has existed since Stage 2 and is **byte-unchanged**
by this checkpoint: it already performs one bounded request through the real
robots matcher, the real budget and the real pacing, already classifies a failure
as `adapter_error` or `infrastructure_error`, and already returns a dict shaped
for `run_manifest.v1.json`'s `source_preflight[]`. What was missing was a caller
that knows *which* sources exist and stamps each row with the `source_id` the
schema requires and the probe cannot know.

So this module owns exactly four things: reading the configured source set through
the committed reader, selecting from it, calling the committed probe once per
selected source, and projecting the schema-admitted row. It owns no HTTP, no
robots matching, no retry, no redirect handling, no pacing, no timeout
implementation, no adapter parsing, no classification, no scoring, no identity, no
artifact assembly, no second schema and no persistence.

Three properties are worth stating because each is a way this could go wrong:

  * ONE SOURCE, ONE PROBE. Each selected source is preflighted exactly once, and
    a test counts the calls. A source that is configured twice is a configuration
    defect and fails BEFORE any request, rather than being probed twice or
    silently deduplicated.
  * A FAILURE IS A ROW, NOT AN EXCEPTION. `HttpClient.preflight()` never raises,
    and neither does this: a dead feed is reported as a row with its committed
    reason, and every other selected source is still probed and still reported.
    Dropping a failure would make "25 rows, all ok" indistinguishable from
    "3 rows, all ok".
  * NOTHING IS RETAINED. No taxonomy run, no cell, topic, ledger, rejection,
    coverage, conflict, manifest or pointer; no `--state-root`; nothing written
    inside the repository. E9-5 states the precise boundary: the committed HTTP
    stack coordinates through a filesystem lease tree, so a transient one is
    created OUTSIDE the repository by the caller and removed on every exit path.
    That is infrastructure scratch, not a retained Stage 9 state root.

Not here: `smoke`, `validate`, `compare-runs`, `diff`, `linkcheck` — each owned by
a later, unapproved checkpoint. And this module has never been pointed at a real
source: S9-2 is implementation and offline proof, S9-L1 is the execution, and
S9-L1 is unapproved.
"""
from . import run_cells

# The committed `run_manifest.v1.json` `source_preflight[]` item keys. The schema
# is `additionalProperties: false`, so this is a projection, not a superset: a key
# the probe grows that the schema does not admit must be dropped here rather than
# written into a manifest that would then refuse to validate.
#
# `source_id` is FIRST because it is the one key the probe cannot supply — it has
# a URL, not an identity — and stamping it from configuration is this module's
# reason to exist.
ROW_KEYS = ("source_id", "url", "result", "reason", "http_status", "content_type",
            "robots_allowed", "crawl_delay_sec", "bytes", "elapsed_ms")

# The two the schema marks required. Named so a projection that loses one fails
# here, loudly, instead of at a manifest write three checkpoints later.
REQUIRED_ROW_KEYS = ("source_id", "result")

OK = "ok"


class PreflightError(Exception):
    """A configuration or selection this module refuses. Never a probe failure.

    A probe failure is a ROW. This is raised only for things that must stop the
    command before any request leaves: a duplicated `source_id`, an unknown
    selection, an empty selection.
    """


def configured_sources(topics_dir=None):
    """Every configured source, flattened and keyed by `source_id`.

    Read through `run_cells.configured_cells()`, the committed reader, rather
    than by opening the topic files again: a second interpretation of the same
    configuration is a second thing that can drift.

    A duplicated `source_id` raises. The alternative — probing it twice, or
    silently keeping one — makes the row count disagree with the configuration,
    and the schema keys rows by `source_id`.
    """
    sources = {}
    for cell in run_cells.configured_cells(topics_dir=topics_dir):
        for source in cell["sources"]:
            source_id = source.get("source_id")
            if not source_id:
                raise PreflightError(
                    "cell %r has a source with no source_id" % cell["cell_id"])
            if source_id in sources:
                raise PreflightError(
                    "source_id %r is configured more than once (seen in %r and "
                    "%r). A preflight row is keyed by source_id, so a duplicate "
                    "would make the report disagree with the configuration."
                    % (source_id, sources[source_id]["cell_id"], cell["cell_id"]))
            sources[source_id] = {"source_id": source_id,
                                  "url": source.get("url"),
                                  "cell_id": cell["cell_id"]}
            if not sources[source_id]["url"]:
                raise PreflightError("source %r has no url" % source_id)
    return sources


def parse_selection(raw):
    """`--sources a,b,c` -> an ordered, validated list of source ids.

    One documented rule for each edge, because "be liberal in what you accept" is
    how a typo becomes a silently shorter run:

      * `None` — no filter. Every configured source.
      * surrounding whitespace around an id is STRIPPED, deliberately: a shell
        user writing `--sources "a, b"` means two ids, and refusing that would be
        pedantry rather than safety.
      * an EMPTY id (`a,,b`, or a trailing comma) is REFUSED. It is unambiguous
        evidence of a mistake, and there is no reading of it that means anything.
      * a DUPLICATE id is REFUSED, not deduplicated. `--sources a,a` means the
        caller believes something untrue about their own selection, and one probe
        for two requested ids would hide it.
      * an empty selection overall is REFUSED — a command that probes nothing and
        exits 0 is indistinguishable from a command that worked.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise PreflightError("--sources takes a comma-separated list of ids")
    parts = [part.strip() for part in raw.split(",")]
    if any(part == "" for part in parts):
        raise PreflightError(
            "--sources contains an empty id (%r). A stray or trailing comma is a "
            "mistake, not an empty selection." % raw)
    seen = set()
    for part in parts:
        if part in seen:
            raise PreflightError(
                "--sources names %r more than once. One source is one probe and "
                "one row; a repeated id is refused rather than deduplicated, so "
                "the mistake is visible." % part)
        seen.add(part)
    if not parts:
        raise PreflightError("--sources selected nothing")
    return parts


def select(sources, selection=None):
    """Resolve a selection against the configured set. Sorted by `source_id`.

    Sorted HERE, once, so neither the configuration file order nor the order the
    caller happened to type their ids can reach the output. Unknown ids are
    refused as a set, so a caller with three typos learns about three.
    """
    if selection is None:
        chosen = sorted(sources)
    else:
        unknown = sorted(set(selection) - set(sources))
        if unknown:
            raise PreflightError(
                "--sources names %d id(s) that are not configured: %s. "
                "Configured ids: %s"
                % (len(unknown), ", ".join(repr(u) for u in unknown),
                   ", ".join(sorted(sources))))
        chosen = sorted(selection)
    if not chosen:
        raise PreflightError(
            "nothing selected: refusing to report an empty preflight, which is "
            "indistinguishable from a preflight that found no problems")
    return chosen


def _row(source, probed):
    """Project the committed probe result onto the schema-admitted keys.

    `source_id` is stamped from CONFIGURATION and overwrites nothing the probe
    could have supplied — the probe is given a URL and has no notion of identity,
    so it cannot name a different source even by accident.

    The result classification, the reason and every measurement are the probe's,
    copied verbatim. Reinterpreting one here would mean two authorities disagree
    about what a `404` means.
    """
    row = {"source_id": source["source_id"]}
    for key in ROW_KEYS:
        if key == "source_id":
            continue
        if key in probed:
            row[key] = probed[key]
    for key in REQUIRED_ROW_KEYS:
        if key not in row:
            raise PreflightError(
                "the preflight row for %r has no %r, which the committed schema "
                "requires" % (source["source_id"], key))
    return row


def preflight_sources(client, *, selection=None, topics_dir=None):
    """Probe the selected configured sources once each. Returns sorted rows.

    `client` is a committed `HttpClient`, constructed by the caller with the
    policy and transport it wants. This function makes no client, opens no
    socket of its own and reads no policy: it decides WHICH urls are probed and
    WHAT the rows look like, and the client decides everything about HOW.

    Selection and configuration are fully validated BEFORE the first probe, so an
    unknown source id costs no request.

    Only the configured source URL is preflighted. A target page is not reachable
    from here — this module never sees one.
    """
    sources = configured_sources(topics_dir=topics_dir)
    chosen = select(sources, selection)

    rows = []
    for source_id in chosen:
        source = sources[source_id]
        # ONE call, per source, to the committed probe. It never raises, so a
        # dead source becomes a row and the loop continues.
        probed = client.preflight(source["url"])
        rows.append(_row(source, probed))
    return rows


def all_ok(rows):
    """True only when every row reports `ok`. An empty set is not success."""
    return bool(rows) and all(row.get("result") == OK for row in rows)
