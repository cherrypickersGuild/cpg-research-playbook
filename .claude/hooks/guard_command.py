#!/usr/bin/env python3
"""PreToolUse Bash guard for the AX pipeline repo.

Reads the hook JSON from stdin, extracts the Bash command, and BLOCKS a
recognized-dangerous command by writing an explanation to stderr and exiting 2
(the PreToolUse block contract). Exit 0 = allow. Exit code 1 is NEVER used to
signal a policy decision.

Fail-closed: if stdin is not valid JSON, the raw text is scanned anyway, so a
malformed payload cannot smuggle a dangerous command past the guard.

Blocked classes:
  1.  failure-masking pipelines        ( || true , || : , | tee )
  1b. protected commands (fetch/pull/tests/builds/lint/validation) whose live
      output is piped into head/tail/grep/sed/awk/tee — masks their exit code;
      the safe form writes to a temp file first, then inspects that file
  2.  force push                       ( git push --force / --force-with-lease / -f )
  3.  hard reset                       ( git reset --hard )
  4.  destructive git clean            ( git clean with -f / -d / -x )
  5.  broad recursive deletion         ( rm -r + -f , or rm -r of a broad target )
  6.  production-data writes            ( redirect / rm / mv / cp / tee / sed -i into
                                          the real state/ dir, or STATE_DIR=state )
"""
import json
import re
import sys

raw = sys.stdin.read()
cmd = ""
try:
    data = json.loads(raw)
    if isinstance(data, dict):
        ti = data.get("tool_input") or {}
        if isinstance(ti, dict):
            cmd = ti.get("command", "") or ""
except (ValueError, TypeError):
    cmd = ""

# Scan the parsed command if present, else the raw payload (fail-closed).
hay = cmd if cmd else raw

# A repo-relative production state/ path (NOT /tmp/state, $d/state, my_state/, ...)
PROD_STATE = re.compile(r"""(?:^|[\s"'=(>|&:])(?:\./)?state/""")
SHORT_F = re.compile(r"(?<!\S)-[A-Za-z]*f[A-Za-z]*(?!\S)")
SHORT_R = re.compile(r"(?<!\S)-[A-Za-z]*[rR][A-Za-z]*(?!\S)")
BROAD = re.compile(r"(?<!\S)(?:/|~|\*|\.|\./|\$HOME|\$\{HOME\})(?=\s|$)")
PROTECTED = re.compile(
    r"\bgit\s+(?:fetch|pull)\b"
    r"|\b(?:make|ninja|cmake|mvn|gradle|tsc)\b"
    r"|\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:test|build|lint)\b"
    r"|\b(?:pytest|ctest)\b|\bgo\s+(?:test|build)\b|\bcargo\s+(?:test|build)\b"
    r"|\b(?:eslint|flake8|ruff|pylint|shellcheck|mypy|black)\b"
    r"|\bvalidate_task\.sh\b|\bsafe_push_main\.sh\b"
    r"|\btests?/[\w./-]*test[\w./-]*\.sh\b|\btest_[\w./-]*\.sh\b"
)
FILTER_PIPE = re.compile(r"\|\s*(?:head|tail|grep|sed|awk|tee)\b")


def block(reason):
    sys.stderr.write("BLOCKED by guard_command.py: " + reason + "\n")
    sys.stderr.write("Command: " + hay.strip()[:500] + "\n")
    sys.exit(2)


# 1. failure-masking pipelines
if re.search(r"\|\|\s*(?:true|:)(?:\s|;|&|$)", hay):
    block("'|| true' / '|| :' masks a real non-zero exit code.")
if re.search(r"\|\s*tee\b", hay):
    block("piping into 'tee' masks the upstream command's exit code.")

# 1b. protected command whose live output is piped into an output filter
if PROTECTED.search(hay) and FILTER_PIPE.search(hay):
    block("piping a protected command's live output into head/tail/grep/sed/awk/tee "
          "masks its exit code — write to a temp file first, then inspect the file.")

# 2. force push
if re.search(r"\bgit\b.*\bpush\b", hay, re.S):
    if re.search(r"--force\b|--force-with-lease\b", hay) or SHORT_F.search(hay):
        block("force push is not allowed.")

# 3. hard reset
if re.search(r"\bgit\b.*\breset\b.*--hard\b", hay, re.S):
    block("'git reset --hard' discards work irreversibly.")

# 4. destructive git clean
if re.search(r"\bgit\b.*\bclean\b", hay, re.S) and re.search(r"(?<!\S)-{1,2}[A-Za-z]*[fdx]", hay):
    block("destructive 'git clean' (-f/-d/-x) removes untracked files irreversibly.")

# 5. broad recursive deletion
if re.search(r"\brm\b", hay):
    if SHORT_R.search(hay) or re.search(r"--recursive\b", hay):
        if SHORT_F.search(hay) or re.search(r"--force\b", hay) or BROAD.search(hay):
            block("broad/forced recursive 'rm' is not allowed.")

# 6. production-data writes / tests pointed at production state
if re.search(r">>?\s*(?:\./)?state/", hay):
    block("redirecting output into the production state/ dir is not allowed.")
if re.search(r"\brm\b", hay) and PROD_STATE.search(hay):
    block("removing files under the production state/ dir is not allowed.")
if re.search(r"\b(?:mv|cp|rsync|install|tee|dd|truncate)\b", hay) and PROD_STATE.search(hay):
    block("writing into the production state/ dir is not allowed.")
if re.search(r"\bsed\b.*\s-i\b", hay, re.S) and PROD_STATE.search(hay):
    block("in-place edit (sed -i) of production state/ is not allowed.")
if re.search(r"""STATE_DIR\s*=\s*["']?(?:\./)?state(?:[/"'\s]|$)""", hay):
    block("pointing STATE_DIR at the real state/ dir targets production registries.")

sys.exit(0)
