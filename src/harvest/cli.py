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
that is removed when it exits. None of those commands exists yet.
"""
import argparse
import os
import sys
import time

from . import httpclient
from . import run_cells

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

# Every command the Stage 9 plan describes, mapped to the checkpoint that owns
# it. This exists so an unimplemented command gets a specific answer instead of a
# bare "unknown", and so nobody has to grep the plan to find out why it is
# missing. Membership here confers nothing: none of these is registered in
# COMMANDS, and each needs its own approved checkpoint.
PLANNED_COMMANDS = {
    "preflight-sources": "S9-2 (implementation) then S9-L1 (live execution)",
    "smoke": "S9-3 (implementation) then S9-L2 (live execution)",
    "validate": "S9-3",
    "compare-runs": "S9-4",
    "diff": "S9-4",
    "linkcheck": "S9-6 (implementation) then S9-L4 (live execution)",
}

# Registered subcommands: name -> callable(argv) -> exit code. EMPTY AT S9-1.
# Later checkpoints add their own entry in the checkpoint that implements them.
COMMANDS = {}


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


# -------------------------------------------------------------------- usage
def _usage(stream):
    stream.write("""usage: %s <command> [options]

commands:
  --help, -h      show this text

No harvest subcommand is implemented yet. Stage 9 registers each one in the
checkpoint that implements it:

%s

A retained Stage 9 run lives under an explicit --state-root OUTSIDE the
repository. This command selects no such path and creates nothing.
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

    return handler(args[1:])


if __name__ == "__main__":
    sys.exit(main())
