# Matrix harvest — arbitrary (category × topic) cells, in parallel

The entity harvest (`docs/entity_harvest_workflow.md`) covers four fixed topics, each seeded by a
hand-curated awesome-list. The **matrix harvest** covers anything you can type: give it a list of
categories and a list of topics, and it expands queries and harvests every intersection
concurrently.

```
bash scripts/run_matrix.sh --categories "healthcare,finance" --topics "agent,rag"
```

builds a 2×2 matrix and runs four independent lanes at once:

| | topic #1 `agent` | topic #2 `rag` |
|---|---|---|
| **category #1** `healthcare` | `category#1_topic#1.json` | `category#1_topic#2.json` |
| **category #2** `finance` | `category#2_topic#1.json` | `category#2_topic#2.json` |

## The cell contract

A **cell** is one (category, topic) pair. `i` and `j` are **1-based indices into the lists as you
typed them** — that is the whole meaning of the `category#i_topic#j.json` filenames, and it means
list order is significant: reordering the lists renames every cell. Nothing has to guess what an
index means, because `state/matrix/manifest.json` records the mapping and every cell file repeats
its own `category` and `topic` inside.

A cell owns every file written for it, which is what makes cells safe to run concurrently:

```
state/matrix/manifest.json                        index: i/j -> names (written by matrix_spec.py)
state/matrix/queries_category#i_topic#j.json      the cell's expanded query set   [kept]
state/matrix/category#i_topic#j.json              the cell's harvested entities   [kept]
state/matrix/matrix_union.json                    derived read-only view          [kept]
state/matrix/.ledger_… .attempted_… .hits_…       transient per-cell working files [gitignored]
state/matrix/.batch_… .raw_… .err_… .ghcache_…
state/locks/expand_category#i_topic#j.lock        one expander per cell
state/locks/harvest_category#i_topic#j.lock       one harvester per cell
```

## Two phases, both parallel

**Query expansion** (`scripts/expand_queries_cell.sh`) is Stage 1A scoped to a single cell. The
original 1A expands every seed topic in one `claude` call into one shared
`state/search_strategy_db.json` — one monolith, no way to parallelise. The per-cell version expands
exactly one intersection into a file only that cell writes, so all expansions run at once. Queries
must be about the topic **as it applies to that category**; a generic tool with no connection to the
category does not belong in the cell.

It **augments, never clobbers**: the existing query set is the de-dup baseline, and a result holding
fewer queries than it started with is rejected outright rather than installed. A prompt saying
"preserve existing rows" is not a guarantee — this is the enforcement.

**Harvest** (`scripts/harvest_matrix_cell.sh`) is the same loop as the entity harvest — candidate
sourcing → GitHub metadata prefetch → Stage 1G extraction → merge → bounded progress accounting —
with the cell's query set standing in for the awesome-list seed. It reuses the tested pieces rather
than reimplementing them (`lib/lockdir.sh`, `lib/clean_json.sh`, `merge_entity_registry.sh`,
`github_meta.py`), and stamps `topic` and `category` onto every entity **from the manifest**, so a
mislabelled row from the model cannot end up in the wrong cell.

By default each lane runs *expand → harvest* for its own cell, so a cell starts harvesting the
moment **its own** expansion finishes — no global barrier. Use `--phased` if you want every
expansion done (and reviewable) before any harvesting begins.

## Concurrency is capped

`MAX_PARALLEL` (default **4**) bounds how many lanes are in flight; the rest queue. This matters: a
4×5 matrix is 20 cells, and launching 20 model lanes at once would exhaust the account session limit
in minutes and fail all of them together — the opposite of what parallelism is for. Lanes also start
`STAGGER_SEC` (default 15 s) apart. Raise `MAX_PARALLEL` only if you know you have the quota.

Parallelism cuts wall-clock; it does **not** raise the quota ceiling. It consumes it faster.

## Usage

```
# type the lists; expand and harvest every intersection
bash scripts/run_matrix.sh --categories "healthcare,finance" --topics "agent,rag"

# see the plan without launching anything
bash scripts/run_matrix.sh --categories "healthcare,finance" --topics "agent,rag" --dry-run

# expansion only — review the query sets before spending harvest budget
bash scripts/run_matrix.sh --categories "healthcare" --topics "agent,rag" --expand-only

# harvest using query sets that already exist (reuses the manifest; no retyping,
# so the cells cannot be accidentally renumbered)
bash scripts/run_matrix.sh --harvest-only --target 80

# just two cells of a bigger matrix, and build the union view
bash scripts/run_matrix.sh --categories "a,b,c" --topics "x,y" --cells "1:1,3:2" --fold

# a reusable spec file instead of CLI lists
bash scripts/matrix_spec.py --spec matrix.json          # {"categories":[…],"topics":[…],"pairs":[[i,j],…]}
```

Options: `--target N` (verified entities per cell, default 60) · `--queries N` (active queries per
cell, default 24) · `--phased` · `--fold` · `--dry-run`.
Env: `MAX_PARALLEL` (4) · `STAGGER_SEC` (15) · `POLL_SEC` (2) · `CLAUDE_BIN` · `STATE_DIR` · `MODEL`
· plus the per-cell loop knobs `BATCH_SIZE` (12), `MAX_LOOPS` (12), `NO_PROGRESS_THRESHOLD` (3).

Per-cell console output goes to `state/logs/matrix_<run_id>/<cell_id>.log`; interleaving a dozen
lanes onto one terminal is unreadable.

## Single-cell operation

Every cell script works standalone, so you can run cells from separate sessions with no orchestrator
— the per-cell locks stop two sessions taking the same cell:

```
python scripts/matrix_spec.py --categories "healthcare,finance" --topics "agent,rag"
bash scripts/expand_queries_cell.sh 1 1        # session A
bash scripts/harvest_matrix_cell.sh 1 1 60
bash scripts/merge_matrix.sh                   # once, when all cells are done
```

`--check` on either script prints one status line and exits 0 with **no** `claude` call and **no**
side effects (no directory, no file, no lock).

## The union view

`scripts/merge_matrix.sh` folds the cell files into `state/matrix/matrix_union.json`. The cell files
stay authoritative; the union is derived, written by a single process under a lock, and idempotent.

Identity across cells is **(category, topic, name)**, not the `topic|name` `entity_key` used *inside*
a cell. Two cells sharing a topic legitimately hold the same tool: "this matters for healthcare
agents" and "…for finance agents" are two findings, and collapsing them on `entity_key` alone would
silently delete one. A cell file that is missing is fine (not harvested yet); a cell file that is
present but invalid aborts the fold.

## Honest limits

- **List order is load-bearing.** Reordering `--categories` renames every cell. Use `--harvest-only`
  (which reuses the manifest) rather than retyping lists for a follow-up run.
- **Duplicate or case-variant names are refused**, not deduped — two identical categories would
  harvest the same thing into two cells and the duplicated work would look like real coverage.
- **A cell with no query set cannot be harvested.** That is a hard error, not a warning: falling back
  to the model inventing its own scope is exactly the uncontrolled sourcing this design avoids.
- **Cost scales with cells.** An n×m matrix is n·m harvests. `--dry-run` first, and start with a
  small `--target`.
