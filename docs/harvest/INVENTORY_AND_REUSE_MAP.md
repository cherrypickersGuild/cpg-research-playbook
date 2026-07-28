# Repository inventory and reuse map

Written at implementation start (commit `8865c54e2cc8d879410576f247baac4aea149f34`) from a direct
reading of the code, not from documentation. Every claim below was confirmed against the source.

## 1 · What already exists

Three harvest families share one set of primitives:

| Family | Orchestrator | Worker | Merge | Authoritative state |
|---|---|---|---|---|
| entity (4 fixed topics) | `harvest_all.sh` / `harvest_parallel.sh` | `harvest_entities.sh <topic>` | `merge_entity_registry.sh` → `merge_building_blocks.sh` | `state/BuildingBlocks_*.json` → derived `state/entity_registry.json` |
| matrix (category × topic) | `run_matrix.sh` | `expand_queries_cell.sh` + `harvest_matrix_cell.sh` | `merge_matrix.sh` | `state/matrix/<cell>.json` → derived `matrix_union.json` |
| AX cases | `harvest_all.sh` / `harvest_parallel.sh` | `harvest_ax_cases.sh` | `merge_ax_case_harvest_registry.sh` | `state/ax_case_harvest_registry.json` |
| legacy 1A–1G discovery | `run_pipeline.sh` → `run_stage1.sh`, `discover.sh`, `refresh.sh` | inline | `merge_case_db.sh` | `state/ax_case_db.json`, `state/visited_url_ledger.json` |

Corpus at implementation start: 1,161 entities (agent 293 · mcp 305 · prompt 204 · skill 359),
231 AX cases, 1,132 ledger rows. `state/matrix/` does not exist — the matrix path is implemented and
tested but has never been run against production state.

## 2 · The three findings that drove the new design

### 2.1 No local HTTP fetching exists anywhere

`scripts/github_meta.py` is the **only** script in the repository that makes an HTTP request, and it
only ever talks to `https://api.github.com/repos/{owner}/{repo}`. Verified by grep across all `*.sh`
and `*.py`: no `curl`, no `wget`, no `requests`/`httpx`/`aiohttp`. `backfill_entity_target_url.py`
imports `urllib.parse` for string manipulation only.

All content fetching happens inside a `claude -p` lane via `WebSearch`/`WebFetch`, gated by
`--allowedTools`. Consequences, all confirmed in the data:

- no robots.txt handling anywhere (the word "robots" does not appear in the repo);
- no per-domain throttling in code — `throttled_domains[]` is a field the 1B/1F agent specs ask the
  *model* to return, and **no script ever reads it back**;
- `http_status_last` and `content_hash` exist in the ledger schema and are **always `null`**;
- therefore link-check mode is impossible today.

Adding a local fetch path is genuinely new machinery, not a refactor.

### 2.2 No URL canonicalization in the live dedup path

Every URL comparison in the harvest loop is raw exact string equality: `unique_by(.url)`,
`select(.url==$e.url)`, `| unique` on `attempted_urls`. `http://x.com/a`, `https://www.x.com/a/` and
`…?utm_source=…` are three distinct ledger rows.

The only URL normalizer in the repo is `backfill_entity_target_url.py:84-95` — an offline one-shot
repair tool, not wired into the harvest. The agent specs *instruct the model* to normalize
(`00_discovery_overview.md:45`), which is prose guidance with no code enforcement.

Dedup happens in three layers, none of which normalizes: ledger `url` (exact), per-run
`attempted_urls[]` (exact), and `entity_key` at merge time (`topic|lower(name)` — a *name* key, not
a URL key).

### 2.3 The taxonomy is a hierarchy, not a cross-product

`matrix_spec.py` generates the full cross-product of two independent axes and names cells
positionally: `cell_id = "category#%d_topic#%d" % (i, j)` where `i`/`j` are 1-based indices into the
lists **as typed**. Reordering the input lists renames every cell. That is correct for an
exploratory matrix and wrong for a stable published taxonomy, where `Cases ⊃ {Domain Applications,
Case Studies, Product Discovery}` is 3 cells, not 3×3.

## 3 · Reuse decisions

### 3.1 Reused unmodified

| Component | Why it is safe |
|---|---|
| `scripts/lib/lockdir.sh` | Sourced-only, fully path-parameterised (`lock_acquire <dir> <label>`). Built on `mkdir` atomicity because Git Bash has no `flock`. No legacy-state coupling. New locks live at `state/taxonomy_harvest/locks/hx_<cell_id>.lock`. |
| `scripts/lib/clean_json.sh` | Sourced-only, stdin→stdout, no paths at all. Used only by the `model_search` adapter. |
| `scripts/github_meta.py` | Audited in full — see below. |

**`github_meta.py` audit.** Reads only `--hits`; writes only `--out` and `--cache`, both CLI
arguments, via `mkstemp(dir=dest)` + `os.replace`. No hardcoded path, no `STATE_DIR`, no legacy state
path. Token read from `GITHUB_TOKEN`/`GH_TOKEN`, sent only as a header, never logged or persisted.
**No locking**, and `load_cache → mutate → atomic_write_json` is last-writer-wins: the atomic rename
prevents corruption, but two processes sharing a `--cache` lose entries.

*Verdict:* safe to reuse unmodified **iff every cell passes its own `--cache`/`--out` under
`state/taxonomy_harvest/cache/<cell_id>/`**. That is a hard constraint in the cell worker and is
asserted by a test.

### 3.2 Deliberately duplicated, with the risk stated

Sharing these would require editing the protected matrix path, so limited duplication is accepted.

| Primitive | Authoritative implementation | New implementation | Convergence risk |
|---|---|---|---|
| Bounded worker pool (`jobs -rp`) | `run_matrix.sh:157-193` | `scripts/harvest/run_topics.sh` (~35 lines) | **Low.** Both covered by their own concurrency tests. A fix in one diverges silently. The idiom avoids `kill -0` (zombies read as alive) and `wait -n` (reaps without saying which child) — that reasoning must be preserved in both. |
| Atomic write-then-rename | inline `mktemp`+`mv` across ~8 bash scripts | python `mkstemp`+`os.replace` in `src/harvest/` | **Low.** Cross-language; cannot be shared. Both tested. |
| Ledger seed/patch | `harvest_matrix_cell.sh:200-252` (jq) | python, keyed on `identity_url` | **Medium.** Two ledger schemas coexist indefinitely: the legacy one keys raw `source_url` with no canonicalization, the new one keys a canonicalized immutable identity. |
| Merge/dedup identity | `merge_matrix.sh:84-85`, `(category, topic, name)` | `identity_url` + precedence | **Medium — the real semantic fork.** The matrix *deliberately wants* the same tool in two cells to be two findings ("matters for healthcare agents" / "…for finance agents"). This taxonomy forbids independent duplication across categories. Convergence needs a product decision, not a refactor. |
| Cell manifest | `matrix_spec.py`, positional `i`/`j` | `plan_cells.py`, slug-keyed | **Low.** |
| Query expansion | `expand_queries_cell.sh` | not used | **Low.** Deterministic adapters need no generated query set. |

### 3.3 Not reused

`harvest_entities.sh` (668 lines), `harvest_matrix_cell.sh` (314) and `harvest_ax_cases.sh` (408)
are the same loop three times — candidate → attempted → ledger seed → prefetch → extract → patch →
guard → merge → progress. The new cell worker follows the same *shape* (which is well-proven) but
not the same code, because its discovery is adapter-driven rather than model-driven and its identity
is URL-based rather than name-based.

## 4 · Idioms carried forward

Taken from the existing code because they encode hard-won lessons:

- **Data passed by path, not by value.** Model lanes are told filenames and use `Read`; nothing large
  is inlined into a prompt.
- **Unique temp names, never a fixed `<file>.tmp`.** `harvest_entities.sh:479-482` documents why: a
  fixed name is a shared name and will interleave under concurrency.
- **Completion decided by re-running `--check`, never by trusting a child's exit code**
  (`harvest_all.sh`).
- **`IFS=$'\t\r'` when reading jq `@tsv`.** This platform's jq emits CRLF; without the `\r` the last
  field carries a trailing carriage return.
- **Shape guards after JSON validity.** `jq empty` proves well-formedness, not shape; a prose-derived
  `[]` passes `jq empty` and then breaks the merge.
- **Failure is loud.** `jq … > tmp && mv` leaves jq on the LHS of `&&`, which `set -e` ignores — the
  existing scripts use an explicit `if`/`else` with `rm -f` on the failure path.

## 5 · Two platform traps worth recording

### 5.1 Line endings, and why the working tree is mixed

`core.autocrlf=true` and there is **no `.gitattributes`**. Git stores LF blobs; a checkout writes
CRLF. So `sha256(working tree) != sha256(git cat-file blob <commit>:<path>)` for every text file, and
that inequality means *nothing* about modification.

More surprising: **the working tree is genuinely mixed**, and this is pre-existing, not drift. Of the
18 protected paths:

- **10 are pure LF on disk** — every `*.sh` and `*.py` (`run_matrix.sh`, `matrix_spec.py`,
  `github_meta.py`, `lockdir.sh`, `test_matrix_harvest.sh`, …). These were last written by tooling
  that emits LF, not by a Git checkout.
- **8 are pure CRLF on disk** — `merge_entity_registry.sh` and the seven large JSON state files,
  which came from a checkout.
- **0 match neither.** There is no actual drift.

`git diff` normalizes, so it reports all 18 clean either way.

The baseline therefore compares the working tree against **Git's own rendering of the commit**, and
accepts either of the two renderings Git can legitimately produce — `git cat-file --filters
--path=<p>` (what a fresh checkout writes) or `git cat-file blob` (stored verbatim) — while
**pinning which one was observed** per file as `eol_form`.

That pinning is the point. An LF-only rewrite of a file that was CRLF at baseline changes its
`raw_sha256` *and* flips its `eol_form`, so it fails — even though `git diff` still calls the file
clean. `tests/test_taxonomy_protected_baseline.sh` case C proves exactly this, asserting first that
`git diff` reports the rewrite as clean and then that verification still fails.

Requiring the filtered rendering for all 18 would have falsely reported drift on 10 unmodified files;
requiring the blob for all 18 would have falsely reported drift on the other 8.

### 5.2 Git Bash `/tmp` is invisible to native Windows Python

`mktemp -d` returns an MSYS virtual path (`/tmp/tmp.XXXX`). Bash resolves it, so `[ -f "$p" ]`
succeeds — but the `python` on PATH is a **native Windows** build (`C:\Users\SJ\anaconda3\python.exe`)
which cannot open it: `FileNotFoundError`.

Any test that creates a temp directory in Bash and then hands the path to Python will fail in a way
that looks like a missing file rather than a path-translation problem. Two workarounds, both used
here: `cd` into the directory first and pass only **relative** paths to Python (what
`protected_baseline.py` and the `pyin()` helper in the test do), or translate with `cygpath -w`.

The same applies to `$TMPDIR`, which is unset in this shell — redirecting to `"$TMPDIR/x"` silently
becomes `/x` and fails on permissions.
