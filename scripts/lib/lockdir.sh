#!/usr/bin/env bash
# lockdir.sh — a tiny, portable, advisory mutual-exclusion helper.
#
# Sourced, not executed. Provides:
#     lock_acquire <lock_dir> <label>   -> 0 acquired, 1 held by someone else
#     lock_release <lock_dir>           -> 0 always (safe if never acquired)
#     lock_owner   <lock_dir>           -> prints the holder line, if any
#
# Why mkdir and not flock: `mkdir` is atomic create-or-fail on every filesystem
# this repo runs on, including Windows/Git Bash where `flock` is absent. The
# loser of the race gets a non-zero mkdir and never enters the critical section.
#
# What it protects: a lock guards a WRITER, not a file's bytes. Every writer in
# the parallel harvest already writes through a unique temp + atomic rename, so
# readers never observe a half-written file. The lock exists to stop two writers
# doing read-modify-write on the same file concurrently (the lost-update race),
# and to stop two SESSIONS harvesting the same topic into the same shard.
#
# Staleness: a crashed holder must not wedge the repo forever. The holder writes
# pid/host/label/started_at into <lock_dir>/owner. A lock is breakable when its
# owner process is provably gone, or when it is older than LOCK_STALE_SEC
# (default 7200 = 2 h, comfortably longer than the ~18-min harvest loop plus
# retries). "Cannot determine liveness" counts as ALIVE — breaking a live lock is
# far worse than waiting.
#
# Advisory only: it binds the scripts that call it. It cannot stop a human `jq >
# file`, and it is not a substitute for the atomic-rename discipline.

LOCK_STALE_SEC="${LOCK_STALE_SEC:-7200}"

# _lock_now_epoch — seconds since epoch, portable.
_lock_now_epoch() { date +%s; }

# _lock_pid_alive <pid> -> 0 alive/unknown, 1 provably gone
_lock_pid_alive() {
  local pid="$1"
  case "$pid" in ''|*[!0-9]*) return 0 ;; esac   # unparseable -> assume alive
  if kill -0 "$pid" 2>/dev/null; then return 0; fi
  # kill -0 failing can mean "gone" OR "not permitted" (different user/session).
  # Distinguish where we cheaply can; otherwise assume alive.
  if command -v ps >/dev/null 2>&1 && ps -p "$pid" >/dev/null 2>&1; then return 0; fi
  return 1
}

lock_owner() {
  [ -f "$1/owner" ] && cat "$1/owner" 2>/dev/null
}

# lock_acquire <lock_dir> <label>
# Exports LOCK_HELD_DIR on success so lock_release can be called bare from a trap.
lock_acquire() {
  local dir="$1" label="${2:-unlabeled}"
  mkdir -p "$(dirname "$dir")" 2>/dev/null || true

  if mkdir "$dir" 2>/dev/null; then
    printf 'pid=%s host=%s label=%s started_at=%s epoch=%s\n' \
      "$$" "$(hostname 2>/dev/null || echo unknown)" "$label" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(_lock_now_epoch)" > "$dir/owner"
    LOCK_HELD_DIR="$dir"
    return 0
  fi

  # Held. Decide whether the holder is stale enough to break.
  local owner started_epoch pid age
  owner="$(lock_owner "$dir")"
  pid="$(printf '%s' "$owner"   | sed -n 's/.*pid=\([0-9]*\).*/\1/p')"
  started_epoch="$(printf '%s' "$owner" | sed -n 's/.*epoch=\([0-9]*\).*/\1/p')"
  age=$(( $(_lock_now_epoch) - ${started_epoch:-0} ))
  [ -z "$started_epoch" ] && age="$LOCK_STALE_SEC"   # ownerless dir: treat as stale

  if _lock_pid_alive "${pid:-}" && [ "$age" -lt "$LOCK_STALE_SEC" ]; then
    echo "[lock] $dir is held: ${owner:-<no owner file>} (age ${age}s) — not breaking." >&2
    return 1
  fi

  echo "[lock] breaking stale lock $dir (owner: ${owner:-<none>}, age ${age}s, stale_after ${LOCK_STALE_SEC}s)" >&2
  rm -f "$dir/owner" 2>/dev/null || true
  rmdir "$dir" 2>/dev/null || true
  if mkdir "$dir" 2>/dev/null; then
    printf 'pid=%s host=%s label=%s started_at=%s epoch=%s\n' \
      "$$" "$(hostname 2>/dev/null || echo unknown)" "$label" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(_lock_now_epoch)" > "$dir/owner"
    LOCK_HELD_DIR="$dir"
    return 0
  fi
  # Someone else won the re-acquire race after we broke it — they hold it now.
  echo "[lock] lost the re-acquire race for $dir — another process holds it." >&2
  return 1
}

# lock_release [lock_dir] — defaults to the dir this process acquired.
lock_release() {
  local dir="${1:-${LOCK_HELD_DIR:-}}"
  [ -n "$dir" ] || return 0
  [ -d "$dir" ] || return 0
  # Only release a lock we actually own — never yank someone else's.
  if [ -f "$dir/owner" ] && ! grep -q "pid=$$ " "$dir/owner" 2>/dev/null; then
    return 0
  fi
  rm -f "$dir/owner" 2>/dev/null || true
  rmdir "$dir" 2>/dev/null || true
  [ "${LOCK_HELD_DIR:-}" = "$dir" ] && LOCK_HELD_DIR=""
  return 0
}
