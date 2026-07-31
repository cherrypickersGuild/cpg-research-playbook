#!/usr/bin/env python3
"""cli.py — the taxonomy harvest command surface (Stage 9, checkpoint S9-1).

The foundation, and only the foundation. This module makes a live run
*constructible*; it does not make one *happen*, and at S9-1 there is no
subcommand that could. `COMMANDS` is empty on purpose: a placeholder that exits 0
while doing nothing is worse than an honest non-zero "not implemented", because
the first is indistinguishable from success in a log.

What lives here:

  * argument-parser construction, for the subcommands later checkpoints register;
  * repository-root resolution;
  * `validate_state_root` — the one shared refusal for every later command that
    reads or writes a retained Stage 9 run;
  * `live_transport` — the single reviewable owner of the decision to go to the
    network;
  * deterministic usage, help and exit codes.

What deliberately does NOT live here: classification, scoring, canonicalization,
identity, dedupe, facet assignment, artifact assembly, schema validation, source
probing, smoke execution, comparison, link checking, promotion. This layer routes
and validates arguments. Every judgement belongs to the committed modules, and a
test scans this file's own AST to keep it that way — no vocabulary, no matcher,
no canonicalizer, no second serializer.

D9-A, the runtime-root decision: a Stage 9 live execution writes to an explicitly
supplied, retained state root OUTSIDE the repository. `validate_state_root`
refuses anything else. It does not choose a path, does not create one, and
deletes nothing — S9-1 selects no external root at all.

E9-2 narrows the rule the plan stated broadly: an external `--state-root` is
required by every command that reads or writes a retained run (smoke, validate,
compare-runs, diff, linkcheck). `preflight-sources` is the deliberate exception —
it creates no run, reads none, writes no state, and uses a temporary lease root
that is removed when it exits. `linkcheck` is the only one that does not yet
exist.
"""
import argparse
import os
import shutil
import sys
import tempfile
import time

from . import artifacts
from . import compare as compare_mod
from . import httpclient
from . import preflight as preflight_mod
from . import run_cells
from . import runvalidate

# `<repo>/src/harvest/cli.py` -> `<repo>`. Resolved from this file rather than
# from the working directory, so the answer does not depend on where the shell
# happened to be when it invoked us.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROG = "harvest.sh"

# The lease tree of a live run, under the caller's external state root. Named by
# IMPLEMENTATION_PLAN.md §1. Derived here and created by nobody: the committed
# lease implementation makes its own directories when it first takes a slot.
LOCKS_DIRNAME = "locks"

# The four paths that must never exist inside the repository. Identical to
# `scripts/validate_task.sh`'s RUNTIME_PATHS, restated here because this is the
# other end of the same guarantee: the harness refuses to find them, and this
# refuses to be pointed at them.
PROHIBITED_RUNTIME_PATHS = (
    os.path.join("state", "taxonomy_harvest"),
    os.path.join("data", "harvested"),
    "runs",
    "LATEST_RUN_ID",
)

# Every command the Stage 9 plan describes that is NOT yet implemented, mapped to
# the checkpoint that owns it. This exists so an unimplemented command gets a
# specific answer instead of a bare "unknown", and so nobody has to grep the plan
# to find out why it is missing. Membership here confers nothing, and an entry is
# removed only by the checkpoint that implements it.
PLANNED_COMMANDS = {
    "linkcheck": "S9-6 (implementation) then S9-L4 (live execution)",
}

# The upper bound on `--timeout-sec`. Read from the committed policy rather than
# typed here, so the ceiling is the configured request timeout and a preflight can
# never be told to wait longer than an ordinary request may.
TIMEOUT_POLICY_KEY = "request_timeout_sec"


class CliError(Exception):
    """An argument this layer refuses. Never a pipeline failure."""


# --------------------------------------------------------------- repository
def repository_root():
    """The repository this CLI belongs to."""
    return REPO_ROOT


def _within(child, parent):
    """Is `child` `parent` or beneath it, after normalization?

    Compared with `normcase` so a Windows drive letter or a separator flavour
    cannot smuggle a repository path past the check, and by whole path segment so
    `<repo>-elsewhere` is not mistaken for a child of `<repo>`.
    """
    child_n = os.path.normcase(os.path.normpath(child))
    parent_n = os.path.normcase(os.path.normpath(parent))
    return child_n == parent_n or child_n.startswith(parent_n + os.sep)


def validate_state_root(path, *, repo_root=None):
    """Resolve and refuse. Returns the normalized absolute path; creates nothing.

    The refusals, in order, each with its own message:

      * nothing supplied, or only whitespace;
      * a relative path — `--state-root ../out` is precisely the ambiguity D9-A
        exists to remove, so the caller states an absolute path or is refused;
      * the repository root itself;
      * one of the four prohibited runtime paths, named explicitly even though
        the containment check below would also catch them;
      * anything else inside the repository, INCLUDING a path that only lands
        there after `..` is normalized away.

    It does not create the root, does not write a marker, and deletes nothing.
    Whether the path exists is not this function's business: S9-1 selects no
    external root, and the checkpoint that finally does will create it itself.
    """
    root = repo_root if repo_root is not None else REPO_ROOT
    root = os.path.abspath(root)

    if path is None or not isinstance(path, str) or not path.strip():
        raise CliError("--state-root is required and must be a non-empty path")

    raw = path.strip()
    expanded = os.path.expanduser(raw)
    if not os.path.isabs(expanded):
        raise CliError(
            "--state-root must be an absolute path, got %r. A relative state "
            "root is the ambiguity the external-root decision exists to remove: "
            "state it in full." % (raw,))

    resolved = os.path.normpath(os.path.abspath(expanded))

    if os.path.normcase(resolved) == os.path.normcase(os.path.normpath(root)):
        raise CliError(
            "--state-root may not be the repository root %r. A retained Stage 9 "
            "run lives OUTSIDE the repository." % (root,))

    for prohibited in PROHIBITED_RUNTIME_PATHS:
        candidate = os.path.normpath(os.path.join(root, prohibited))
        if _within(resolved, candidate):
            raise CliError(
                "--state-root may not be %r or beneath it: that is one of the "
                "four repository runtime paths the validation harness requires "
                "to stay absent." % (candidate,))

    if _within(resolved, root):
        raise CliError(
            "--state-root %r resolves inside the repository %r. A retained "
            "Stage 9 run lives OUTSIDE it, so the repository's runtime paths "
            "stay absent and its baselines stay clean." % (resolved, root))

    return resolved


# ---------------------------------------------------------------- transport
def locks_root(state_root):
    """`<state-root>/locks` — derived, and created by nobody here."""
    return os.path.join(state_root, LOCKS_DIRNAME)


def live_transport(state_root, *, repo_root=None):
    """The ONE constructor that decides to go to the network.

    Deliberately the only place in the tree where `httpclient.default_opener` and
    `time.sleep` are named together: they travel as one frozen `Transport`
    because a live opener with a suppressed sleep would issue real requests with
    pacing disabled, against hosts that mandate a crawl-delay.

    Constructing this issues no request and creates no directory. The lease root
    is a path; the committed lease implementation makes it when it first needs a
    slot. Nothing in S9-1 calls this from an operational command, because there
    is no operational command.
    """
    resolved = validate_state_root(state_root, repo_root=repo_root)
    return run_cells.Transport(opener=httpclient.default_opener,
                               sleep=time.sleep,
                               lease_root=locks_root(resolved))


# ------------------------------------------------------------------- parser
def build_parser(command, description):
    """An `argparse` parser for one subcommand, with this CLI's conventions.

    Provided so the checkpoints that register commands share one prog name, one
    formatter and one `--state-root` spelling instead of three drifting copies.
    No subcommand exists yet, so at S9-1 this has exactly one caller: its test.
    """
    return argparse.ArgumentParser(
        prog="%s %s" % (PROG, command), description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)


def add_state_root_argument(parser, *, required=True):
    """The one spelling of `--state-root`, for every state-bearing command."""
    parser.add_argument(
        "--state-root", required=required, default=None, metavar="PATH",
        help="absolute path to the retained state root, OUTSIDE the repository")
    return parser


# -------------------------------------------------- preflight-sources (S9-2)
def _timeout_policy(policy, timeout_sec):
    """A copy of the committed policy with the probe timeout narrowed.

    The timeout is applied through the ONE seam the committed client already
    offers — `HttpClient(policy, …)` reads its timeouts out of
    `policy["budgets"]` — so no second HTTP implementation exists and
    `httpclient.py` is byte-unchanged. `HttpClient.preflight()` takes no per-call
    timeout, and inventing one here would mean emulating a timeout above a client
    that already owns it.

    Connect and read timeouts are clamped DOWN to the requested value when they
    would exceed it. Without that a `--timeout-sec 2` would be quietly defeated by
    the configured 15-second read timeout, and the option would be a lie.
    """
    narrowed = dict(policy)
    budgets = dict(narrowed.get("budgets", {}))
    budgets[TIMEOUT_POLICY_KEY] = timeout_sec
    for key in ("connect_timeout_sec", "read_timeout_sec"):
        current = budgets.get(key)
        if current is None or current > timeout_sec:
            budgets[key] = timeout_sec
    narrowed["budgets"] = budgets
    return narrowed


def _validate_timeout(raw, policy):
    """Finite, positive, and never longer than an ordinary configured request."""
    ceiling = policy.get("budgets", {}).get(TIMEOUT_POLICY_KEY)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise CliError("--timeout-sec must be a number, got %r" % (raw,))
    if value != value or value in (float("inf"), float("-inf")):
        raise CliError("--timeout-sec must be finite, got %r" % (raw,))
    if value <= 0:
        raise CliError("--timeout-sec must be greater than zero, got %r" % (raw,))
    if ceiling is not None and value > ceiling:
        raise CliError(
            "--timeout-sec %g exceeds the configured request timeout of %g. A "
            "preflight probe may be narrowed, never widened." % (value, ceiling))
    return value


def cmd_preflight_sources(argv):
    """Probe every configured source once and print the rows. Retains nothing.

    E9-5 is the precise boundary: this creates no taxonomy run and writes nothing
    in the repository, but the committed HTTP stack coordinates through a
    filesystem lease tree, so ONE temporary lease root is created outside the
    repository and removed on every exit path — success, reported failure, and
    interruption alike. It is infrastructure scratch, never a retained Stage 9
    state root, which is why this command neither accepts nor requires
    `--state-root`.

    E9-6 is the output: one JSON array of committed `source_preflight[]` rows,
    sorted by `source_id`, with no envelope. That is exactly the value a future
    manifest's `source_preflight` field takes, so the report needs no second
    schema and no translation.
    """
    parser = build_parser(
        "preflight-sources",
        "Probe every configured source once. Creates no run and retains nothing.")
    parser.add_argument("--sources", default=None, metavar="ID[,ID...]",
                        help="comma-separated source ids; default is all of them")
    parser.add_argument("--timeout-sec", default=None, metavar="N",
                        help="narrow the per-probe timeout; never widens it")
    args = parser.parse_args(argv)

    # `_run_policy` is the committed reader and returns the document UNMODIFIED.
    # Used rather than opening the policy file here, so this layer names no config
    # path and there is no second interpretation of it.
    policy = run_cells._run_policy()

    # EVERYTHING that can be decided without a request is decided first, so an
    # unknown source id or a bad timeout costs no traffic at all.
    selection = preflight_mod.parse_selection(args.sources)
    sources = preflight_mod.configured_sources()
    preflight_mod.select(sources, selection)
    if args.timeout_sec is not None:
        policy = _timeout_policy(policy, _validate_timeout(args.timeout_sec, policy))

    lease_root = tempfile.mkdtemp(prefix="harvest_preflight_leases_")
    try:
        transport = run_cells.Transport(opener=httpclient.default_opener,
                                        sleep=time.sleep, lease_root=lease_root)
        client = httpclient.HttpClient(policy, lease_root=transport.lease_root,
                                       opener=transport.opener,
                                       sleep=transport.sleep)
        rows = preflight_mod.preflight_sources(client, selection=selection)
    finally:
        # Every exit path, including an interruption: this root is ours, it is
        # outside the repository, and nothing else may be removed by this line.
        shutil.rmtree(lease_root, ignore_errors=True)

    # The complete document, always — a failing source is reported, never
    # dropped, and never turned into a partial result that reads like a whole one.
    sys.stdout.buffer.write(artifacts.serialize(rows))
    sys.stdout.buffer.flush()
    return 0 if preflight_mod.all_ok(rows) else 1


# ------------------------------------------------------------- smoke (S9-3)
def _positive_int(name, raw, ceiling):
    """A cap the caller may only NARROW. Validated before anything is built."""
    try:
        value = int(str(raw), 10)
    except (TypeError, ValueError):
        raise CliError("%s must be a positive integer, got %r" % (name, raw))
    if value < 1:
        raise CliError("%s must be >= 1, got %r" % (name, raw))
    if value > ceiling:
        raise CliError(
            "%s %d exceeds the configured smoke cap of %d. A smoke bound may be "
            "narrowed, never widened — widening it would make the run something "
            "the policy never approved." % (name, value, ceiling))
    return value


def cmd_smoke(argv):
    """One bounded, enrichment-free, 12-cell run into an external state root.

    Everything decidable without traffic is decided first — the state root, both
    caps, the run id — so a typo costs no request. Only then is a live transport
    built, the configured sources preflighted once each, and `run_cells.run()`
    called EXACTLY ONCE. There is no automatic retry: a failed smoke is evidence.

    A smoke is `mode="smoke"` with enrichment off, which makes it
    `publication_eligible: false` through the COMMITTED derivation — this adds no
    predicate, and target-page fetching is unreachable with enrichment false.
    """
    parser = build_parser(
        "smoke",
        "One bounded 12-cell run into an external state root. Never publishes.")
    add_state_root_argument(parser)
    parser.add_argument("--no-enrich", action="store_true", default=True,
                        help="disable target-page fetching (the only mode)")
    parser.add_argument("--max-candidates", default=None, metavar="N",
                        help="narrow the per-cell candidate cap")
    parser.add_argument("--max-accepted", default=None, metavar="N",
                        help="narrow the per-cell accepted cap")
    parser.add_argument("--run-id", default=None, metavar="ID",
                        help="use this run id instead of a clock-derived one")
    args = parser.parse_args(argv)

    state_root = validate_state_root(args.state_root)
    policy = run_cells._run_policy()
    smoke = policy.get("smoke", {})
    max_candidates = smoke.get("max_candidates_per_cell")
    max_accepted = smoke.get("max_accepted_per_cell")
    if args.max_candidates is not None:
        max_candidates = _positive_int("--max-candidates", args.max_candidates,
                                       max_candidates)
    if args.max_accepted is not None:
        max_accepted = _positive_int("--max-accepted", args.max_accepted,
                                     max_accepted)
    if max_accepted > max_candidates:
        raise CliError(
            "--max-accepted %d exceeds --max-candidates %d: a cap that can never "
            "bind is not a bound." % (max_accepted, max_candidates))

    run_id_value = None
    if args.run_id is not None:
        run_id_value = runvalidate.validate_run_id(args.run_id)
        if artifacts.run_is_finished(state_root, run_id_value):
            raise CliError(
                "run %s already finished in %s. A finished run's artifacts are "
                "immutable, and this is refused BEFORE the preflight so a repeat "
                "costs no request." % (run_id_value, state_root))

    budget_sec = policy.get("budgets", {}).get("smoke_budget_sec")

    # The command-wide clock starts HERE, immediately before the first request.
    started = time.monotonic()
    transport = live_transport(state_root)
    client = httpclient.HttpClient(policy, lease_root=transport.lease_root,
                                   opener=transport.opener, sleep=transport.sleep)
    rows = preflight_mod.preflight_sources(client)
    elapsed = time.monotonic() - started

    bounds = run_cells.RunBounds(
        max_candidates_per_cell=max_candidates,
        max_accepted_per_cell=max_accepted,
        smoke_budget_sec=budget_sec,
        elapsed_before_run_sec=elapsed)
    if bounds.remaining_run_sec <= 0:
        raise CliError(
            "the source preflight consumed the whole %ss smoke budget (%.1fs); "
            "refusing to start a run with no time left rather than writing a tree "
            "that cannot finish." % (budget_sec, elapsed))

    result = run_cells.run(state_root, transport=transport, mode="smoke",
                           enrich=False, source_preflight=rows, bounds=bounds,
                           run_id_value=run_id_value, max_cells=run_cells.MAX_CELLS)

    written = [path for path in result.paths if path.endswith(".json")]
    pointer = artifacts.read_latest_run_id(state_root)
    if len(written) != runvalidate.TOTAL_JSON or pointer != result.run_id:
        sys.stderr.write(
            "%s: smoke did not publish completely — %d JSON artifacts (expected "
            "%d) and LATEST_RUN_ID names %r. Nothing was removed; the tree is "
            "evidence.\n" % (PROG, len(written), runvalidate.TOTAL_JSON, pointer))
        return 1

    sys.stdout.buffer.write(artifacts.serialize({
        "run_id": result.run_id,
        "mode": "smoke",
        "json_artifacts": len(written),
        "pointer": artifacts.LATEST_RUN_ID_NAME,
        "source_preflight_rows": len(rows),
        "publication_eligible": False,
    }))
    sys.stdout.buffer.flush()
    return 0


# ---------------------------------------------------------- validate (S9-3)
def cmd_validate(argv):
    """Read one completed run and report whether it is sound. Writes nothing."""
    parser = build_parser(
        "validate",
        "Validate the latest complete run in a state root. Read-only, offline.")
    add_state_root_argument(parser)
    parser.add_argument("--run-id", required=True, metavar="ID",
                        help="the run to validate; must be the one LATEST_RUN_ID names")
    args = parser.parse_args(argv)

    state_root = validate_state_root(args.state_root)
    run_id = runvalidate.validate_run_id(args.run_id)
    if not os.path.isdir(state_root):
        raise CliError("--state-root %s does not exist or is not a directory"
                       % state_root)

    report = runvalidate.validate_run(state_root, run_id)
    sys.stdout.buffer.write(artifacts.serialize(report))
    sys.stdout.buffer.flush()
    return 0 if report["valid"] else 1


# ------------------------------------------------- compare-runs, diff (S9-4)
def cmd_compare_runs(argv):
    """Compare two runs under one state root. Offline, read-only.

    `--run-id` is given exactly twice. Both runs may be historical: comparison
    asks whether two runs agree, not whether either is the run the pointer names,
    so this does NOT go through `runvalidate.validate_run()` and does not require
    or move `LATEST_RUN_ID`.

    Exit 0 when every invariant holds — content changes present or not — and 1
    when an invariant was violated or a field moved that no committed schema
    class covers. The complete report is printed either way.
    """
    parser = build_parser(
        "compare-runs",
        "Compare two runs' 18 selected documents. Offline, read-only.")
    add_state_root_argument(parser)
    parser.add_argument("--run-id", action="append", default=None, metavar="ID",
                        help="give exactly twice: the two runs to compare")
    args = parser.parse_args(argv)

    state_root = validate_state_root(args.state_root)
    run_ids = list(args.run_id or [])
    if len(run_ids) != 2:
        raise CliError(
            "compare-runs needs exactly two --run-id values, got %d. A comparison "
            "has two sides." % len(run_ids))
    run_a, run_b = (runvalidate.validate_run_id(value) for value in run_ids)
    if not os.path.isdir(state_root):
        raise CliError("--state-root %s does not exist or is not a directory"
                       % state_root)

    report = compare_mod.compare_runs(state_root, run_a, run_b)
    sys.stdout.buffer.write(artifacts.serialize(report))
    sys.stdout.buffer.flush()
    return 0 if report["idempotent"] else 1


def cmd_diff(argv):
    """Compare one staged run with the publication root. Offline, read-only.

    The default publication root is the repository's `data/harvested/`, which
    Stage 9 expects to be ABSENT — reported exactly as that, which is a real
    answer and not an empty diff. Nothing is created, staged or promoted, so this
    always exits 0 once it has read: `diff` describes a difference and has no
    authority to act on one.
    """
    parser = build_parser(
        "diff",
        "Compare one run with the publication root. Offline, read-only.")
    add_state_root_argument(parser)
    parser.add_argument("--run-id", required=True, metavar="ID",
                        help="the staged run to compare")
    parser.add_argument("--publication-root", default=None, metavar="DIR",
                        help="default: the repository's data/harvested/")
    args = parser.parse_args(argv)

    state_root = validate_state_root(args.state_root)
    run_id = runvalidate.validate_run_id(args.run_id)
    if not os.path.isdir(state_root):
        raise CliError("--state-root %s does not exist or is not a directory"
                       % state_root)

    publication_root = args.publication_root
    if publication_root is None:
        publication_root = os.path.join(repository_root(), "data", "harvested")

    report = compare_mod.diff_publication(state_root, run_id, publication_root)
    sys.stdout.buffer.write(artifacts.serialize(report))
    sys.stdout.buffer.flush()
    return 0


# Registered subcommands: name -> callable(argv) -> exit code. A command appears
# here only in the checkpoint that implements it.
COMMANDS = {
    "preflight-sources": cmd_preflight_sources,
    "smoke": cmd_smoke,
    "validate": cmd_validate,
    "compare-runs": cmd_compare_runs,
    "diff": cmd_diff,
}


# -------------------------------------------------------------------- usage
def _usage(stream):
    stream.write("""usage: %s <command> [options]

commands:
  preflight-sources   probe every configured source once and print one JSON
                      array of source_preflight rows, sorted by source_id.
                      Creates no run and retains nothing.
                      [--sources ID[,ID...]] [--timeout-sec N]
                      exit 0 when every row is ok, 1 when any is not.
  smoke               one bounded, enrichment-free 12-cell run into an external
                      state root. Publishes 42 JSON artifacts and the pointer;
                      never publication-eligible.
                      --state-root PATH [--no-enrich] [--max-candidates N]
                      [--max-accepted N] [--run-id ID]
                      exit 0 on complete publication, non-zero otherwise.
  validate            read the latest complete run and report whether it is
                      sound. Offline, read-only, repairs nothing.
                      --state-root PATH --run-id ID
                      exit 0 when valid, 1 when not.
  compare-runs        compare two runs' 18 selected documents and classify every
                      difference as permitted, content or invariant. Offline,
                      read-only; either run may be historical.
                      --state-root PATH --run-id A --run-id B
                      exit 0 when every invariant holds, 1 when one does not.
  diff                compare one run with the publication root. Offline,
                      read-only; writes, stages and promotes nothing.
                      --state-root PATH --run-id ID [--publication-root DIR]
                      exit 0 once read; an absent publication root is a result.
  --help, -h          show this text

Planned and NOT implemented. Stage 9 registers each in the checkpoint that
implements it:

%s

A retained Stage 9 run lives under an explicit --state-root OUTSIDE the
repository. No implemented command selects such a path or creates one.
""" % (PROG, "\n".join("  %-18s %s" % (name, PLANNED_COMMANDS[name])
                       for name in sorted(PLANNED_COMMANDS))))


def main(argv=None):
    """Dispatch. Returns an exit code; raises nothing to the shell."""
    args = list(sys.argv[1:] if argv is None else argv)

    if not args:
        _usage(sys.stderr)
        return 2

    command = args[0]
    if command in ("--help", "-h", "help"):
        _usage(sys.stdout)
        return 0

    handler = COMMANDS.get(command)
    if handler is None:
        sys.stderr.write("%s: unknown command %r\n" % (PROG, command))
        if command in PLANNED_COMMANDS:
            sys.stderr.write(
                "  %r is PLANNED and NOT implemented; it is owned by %s, which "
                "is unapproved.\n" % (command, PLANNED_COMMANDS[command]))
        _usage(sys.stderr)
        return 2

    try:
        return handler(args[1:])
    except SystemExit as exc:
        # `argparse` reports a usage error by RAISING SystemExit(2). Letting that
        # escape would break this function's one promise — it returns an exit
        # code and raises nothing — and would make an in-process caller see an
        # exception where the shell sees a clean 2. Normalized here, so both
        # observers agree.
        return 2 if exc.code is None else int(exc.code)
    except (CliError, preflight_mod.PreflightError,
            runvalidate.RunValidateError, run_cells.RunCellsError,
            compare_mod.CompareError) as exc:
        # A refused argument or a refused configuration. Exit 2 — the same code
        # argparse uses for a usage error — and print to stderr, so stdout stays
        # JSON-only and a caller parsing it is never handed prose. Nothing has
        # been probed at this point: every such refusal happens before the first
        # request.
        sys.stderr.write("%s: %s\n" % (PROG, exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
