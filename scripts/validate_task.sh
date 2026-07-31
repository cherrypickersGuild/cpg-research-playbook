#!/usr/bin/env bash
# validate_task.sh — single allowlisted, OFFLINE validation entry point.
# Focused checks for the files changed in the working tree:
#   bash -n (shell) · py_compile (python) · jq empty (json, read-only) ·
#   the tests/ regressions mapped to those files.
#
# Isolation is PROVEN, not assumed:
#   * external agents disabled (CLAUDE_BIN -> failing mock)
#   * STATE_DIR points at a throwaway temp dir (belt — NOT treated as proof)
#   * only tests on an AUDITED allowlist of isolation-safe tests are run; any
#     other (unaudited) test is skipped with a clear message, never trusted
#   * production state/ is content-hash-snapshotted before AND after; ANY change
#     fails the run non-zero and is reported (never auto-restored/overwritten)
#   * the four repository runtime paths are checked before AND after; any that
#     exists fails the run and is reported (never removed) — see RUNTIME_PATHS
# Real exit codes are preserved throughout; no meaningful command is piped
# through a filter.
#
#   Usage: bash scripts/validate_task.sh [--all] [file ...]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cat > "$WORK/mock_claude.sh" <<'EOF'
#!/usr/bin/env bash
echo "validate_task.sh: live claude/agent invocation is disabled during validation" >&2
exit 97
EOF
chmod +x "$WORK/mock_claude.sh"
export CLAUDE_BIN="$WORK/mock_claude.sh"
export STATE_DIR="$WORK/state"; mkdir -p "$STATE_DIR"

# --- audited allowlist of isolation-safe tests -----------------------------
# Each was inspected and confirmed to run under a temp dir / temp STATE_DIR with
# a mock or `false` CLAUDE_BIN, contact no real remote, and never write the
# production state/ dir. Tests NOT listed here are skipped, not trusted.
ISOLATED=(
  test_ax_case_harvest_dates.sh test_clean_json.sh test_entity_github_stars.sh
  test_entity_url_schema.sh test_harvest_bounded.sh test_harvest_targets.sh
  test_harvest_1g_shape_guard.sh
  test_github_meta.sh test_harvest_github_cache.sh
  test_ledger_patch_merge.sh test_merge_entity_type_error.sh
  test_merge_error_propagation.sh test_pipeline_ledger_error.sh
  test_guard_command.sh test_safe_commit.sh test_safe_push_main.sh
  test_permission_rules.sh
  test_parallel_harvest.sh test_matrix_harvest.sh
  # --- taxonomy harvest (Stage 8, S8-1; plan decisions D1-D4) --------------
  # All 39 committed wrappers, individually — no aggregate entry, no wildcard,
  # no dynamic discovery. Each was audited against the criterion above: each
  # derives its own ROOT, writes only under its own `mktemp -d` or an injected
  # --state-root, asserts production state/ (and in 33 of 39, config/) is
  # unmodified afterwards, and contacts no remote. test_taxonomy_migration.sh
  # proves by AST scan of its own source that no call site passes `--apply`
  # without `--state-root`; test_taxonomy_domain_throttle.sh binds a LOCAL
  # recording server on loopback and issues no outbound request.
  test_taxonomy_adapter_concurrency.sh   test_taxonomy_adapters.sh
  test_taxonomy_aliases.sh               test_taxonomy_artifacts.sh
  test_taxonomy_budget.sh                test_taxonomy_cell_artifact.sh
  test_taxonomy_classify.sh              test_taxonomy_config.sh
  test_taxonomy_coverage.sh              test_taxonomy_coverage_report.sh
  test_taxonomy_customer_interaction.sh  test_taxonomy_dedupe.sh
  test_taxonomy_domain_throttle.sh       test_taxonomy_eligibility.sh
  test_taxonomy_extract.sh               test_taxonomy_facet_ambiguity.sh
  test_taxonomy_facet_identity.sh        test_taxonomy_facet_states.sh
  test_taxonomy_facetassign.sh           test_taxonomy_facets.sh
  test_taxonomy_http.sh                  test_taxonomy_identity.sh
  test_taxonomy_ledger.sh                test_taxonomy_manifest.sh
  test_taxonomy_migration.sh             test_taxonomy_pool.sh
  test_taxonomy_protected_baseline.sh    test_taxonomy_records.sh
  test_taxonomy_recovery.sh              test_taxonomy_run_cells.sh
  test_taxonomy_schema.sh                test_taxonomy_source_cache.sh
  test_taxonomy_target_accounting.sh     test_taxonomy_target_determinism.sh
  test_taxonomy_target_evidence.sh       test_taxonomy_target_fetch.sh
  test_taxonomy_target_fixtures.sh       test_taxonomy_target_ownership.sh
  test_taxonomy_verify.sh
  # --- Stage 9, S9-1: the live execution seam and CLI foundation -----------
  # Same criterion as the 39 above. Offline: every run goes through the fixture
  # transport or an injected test-local one, a sentinel at the transport
  # boundary proves default_opener is never reached, and every byte lands under
  # a `mktemp -d` the suite removes. It selects NO external Stage 9 state root
  # and creates none — validate_state_root refuses and never creates.
  test_taxonomy_cli.sh
  # --- Stage 9, S9-2: the configured-source preflight ----------------------
  # Same criterion. Its only traffic is a ThreadingHTTPServer this suite binds
  # on 127.0.0.1:0 and shuts down itself; a socket-level guard refuses every
  # non-loopback host and is proved wired by tripping it. Every other probe goes
  # through a stub client. Lease roots are `mktemp -d` and removed on every exit
  # path; no --state-root is accepted and no retained Stage 9 root is created.
  test_taxonomy_preflight.sh
  # --- Stage 9, S9-3: bounded smoke and read-only run validation -----------
  # Same criterion. Every smoke it drives uses the FIXTURE transport, a
  # socket-level guard refuses every non-loopback host and is proved wired by
  # tripping it, and the external state roots it hands the CLI are `mktemp -d`
  # directories it removes itself. The validator writes nothing at all.
  test_taxonomy_smoke.sh
  # --- Stage 9, S9-4: run comparison and publication diff ------------------
  # Same criterion, and the easiest of the four to audit: both commands READ.
  # Every run tree it compares is written by the suite itself under a `mktemp -d`
  # it removes, no transport is constructed on any path, and the publication
  # roots it names are temp directories or paths it deliberately leaves absent —
  # the repository's data/harvested/ is never created, looked at only.
  test_taxonomy_compare.sh
)
is_isolated() {
  local b; b="$(basename "$1")"
  local t; for t in "${ISOLATED[@]}"; do [ "$t" = "$b" ] && return 0; done
  return 1
}

FAIL=0
run() { local label="$1"; shift
  if "$@"; then echo "  ok   - $label"
  else local rc=$?; echo "  FAIL - $label (exit $rc)"; FAIL=1; fi; }

MODE="changed"; declare -a FILES=()
[ "${1:-}" = "--all" ] && { MODE="all"; shift; }
if [ "$#" -gt 0 ]; then FILES=("$@"); MODE="explicit"
elif [ "$MODE" = "changed" ]; then
  while IFS= read -r f; do [ -n "$f" ] && FILES+=("$f"); done < <(
    { git diff --name-only --diff-filter=d HEAD 2>/dev/null
      git ls-files --others --exclude-standard; } | sort -u )
fi

echo "== validate_task.sh (mode: $MODE) =="
declare -a TESTS=()
add_test() { [ -f "$1" ] || return 0; case " ${TESTS[*]:-} " in *" $1 "*) ;; *) TESTS+=("$1");; esac; }

for f in "${FILES[@]:-}"; do
  [ -z "$f" ] && continue; [ -f "$f" ] || continue
  case "$f" in
    *.sh)   run "bash -n $f"    bash -n "$f" ;;
    *.py)   run "py_compile $f" python -m py_compile "$f" ;;
    *.json) run "jq empty $f"   jq empty "$f" ;;
  esac
  case "$f" in
    scripts/lib/clean_json.sh)                    add_test tests/test_clean_json.sh ;;
    scripts/merge_entity_registry.sh)             add_test tests/test_merge_entity_type_error.sh; add_test tests/test_entity_github_stars.sh; add_test tests/test_matrix_harvest.sh ;;
    scripts/merge_ax_case_harvest_registry.sh|scripts/merge_case_db.sh) add_test tests/test_merge_error_propagation.sh ;;
    scripts/run_stage1.sh|scripts/discover.sh)    add_test tests/test_ledger_patch_merge.sh; add_test tests/test_pipeline_ledger_error.sh ;;
    scripts/backfill_entity_target_url.py)        add_test tests/test_entity_url_schema.sh ;;
    scripts/github_meta.py)                       add_test tests/test_github_meta.sh; add_test tests/test_harvest_github_cache.sh ;;
    scripts/harvest_entities.sh)                  add_test tests/test_harvest_bounded.sh; add_test tests/test_harvest_targets.sh; add_test tests/test_harvest_1g_shape_guard.sh; add_test tests/test_harvest_github_cache.sh; add_test tests/test_github_meta.sh; add_test tests/test_entity_github_stars.sh; add_test tests/test_clean_json.sh; add_test tests/test_parallel_harvest.sh ;;
    scripts/lib/lockdir.sh)                       add_test tests/test_parallel_harvest.sh; add_test tests/test_matrix_harvest.sh ;;
    scripts/merge_building_blocks.sh|scripts/split_entity_registry.py|scripts/harvest_parallel.sh) add_test tests/test_parallel_harvest.sh ;;
    scripts/matrix_spec.py|scripts/expand_queries_cell.sh|scripts/harvest_matrix_cell.sh|scripts/run_matrix.sh|scripts/merge_matrix.sh) add_test tests/test_matrix_harvest.sh ;;
    scripts/harvest_all.sh)                       add_test tests/test_parallel_harvest.sh; add_test tests/test_harvest_targets.sh ;;
    scripts/harvest_ax_cases.sh)                  add_test tests/test_ax_case_harvest_dates.sh; add_test tests/test_harvest_bounded.sh; add_test tests/test_clean_json.sh ;;
    .claude/hooks/guard_command.py)               add_test tests/test_guard_command.sh; add_test tests/test_permission_rules.sh ;;
    scripts/safe_commit.sh)                       add_test tests/test_safe_commit.sh; add_test tests/test_permission_rules.sh ;;
    scripts/safe_push_main.sh)                    add_test tests/test_safe_push_main.sh; add_test tests/test_permission_rules.sh ;;

    # ===================================================================== #
    # taxonomy harvest — Stage 8, S8-1                                      #
    # ===================================================================== #
    # Routed by OWNERSHIP, not import fan-out: each production file selects
    # the wrapper whose declared subject is that file's contract, plus any
    # wrapper that committed evidence shows drives it AS ITS SUBJECT. Routing
    # by imports would be useless — src/harvest/schema.py is imported by 25 of
    # the 39 suites and urlkey.py by 17 — and would be a blanket "run all 39"
    # arm in disguise. There is no blanket arm.
    #
    # Every target is spelled `tests/<name>.sh`, byte-identical to what the
    # `tests/*.sh` glob below emits, because add_test de-duplicates on the
    # exact path STRING. `./tests/x.sh` and `tests/x.sh` would both be added
    # and the suite would run twice.

    # -- deliberately unmapped, matched first so no later pattern claims them.
    # Package plumbing with no behavioural surface: a change that matters lands
    # in a mapped sibling. hash_tree.py has zero consumers anywhere in
    # src/harvest/**, scripts/harvest/** or tests/** — mapping it would invent
    # coverage that does not exist. Both are recorded in the Stage 8 plan.
    src/harvest/__init__.py|src/harvest/adapters/__init__.py|src/harvest/migrate/__init__.py) ;;
    scripts/harvest/hash_tree.py) ;;

    # -- src/harvest/** : core modules
    src/harvest/adapters/*.py)                    add_test tests/test_taxonomy_adapters.sh; add_test tests/test_taxonomy_adapter_concurrency.sh ;;
    src/harvest/aliases.py)                       add_test tests/test_taxonomy_aliases.sh; add_test tests/test_taxonomy_eligibility.sh ;;
    src/harvest/artifacts.py)                     add_test tests/test_taxonomy_artifacts.sh; add_test tests/test_taxonomy_cell_artifact.sh; add_test tests/test_taxonomy_ledger.sh; add_test tests/test_taxonomy_coverage_report.sh; add_test tests/test_taxonomy_manifest.sh ;;
    src/harvest/budget.py)                        add_test tests/test_taxonomy_budget.sh ;;
    src/harvest/classify.py)                      add_test tests/test_taxonomy_classify.sh ;;
    src/harvest/coverage.py|src/harvest/scheduler.py) add_test tests/test_taxonomy_coverage.sh; add_test tests/test_taxonomy_coverage_report.sh ;;
    src/harvest/dedupe.py)                        add_test tests/test_taxonomy_dedupe.sh ;;
    src/harvest/domainlease.py)                   add_test tests/test_taxonomy_domain_throttle.sh; add_test tests/test_taxonomy_http.sh ;;
    src/harvest/extract.py)                       add_test tests/test_taxonomy_extract.sh ;;
    src/harvest/facetassign.py)                   add_test tests/test_taxonomy_facetassign.sh ;;
    src/harvest/facets.py)                        add_test tests/test_taxonomy_facets.sh; add_test tests/test_taxonomy_facet_ambiguity.sh; add_test tests/test_taxonomy_facet_identity.sh; add_test tests/test_taxonomy_facet_states.sh; add_test tests/test_taxonomy_customer_interaction.sh ;;
    src/harvest/fixtures.py)                      add_test tests/test_taxonomy_adapters.sh; add_test tests/test_taxonomy_source_cache.sh; add_test tests/test_taxonomy_target_fixtures.sh ;;
    src/harvest/httpclient.py)                    add_test tests/test_taxonomy_http.sh; add_test tests/test_taxonomy_domain_throttle.sh ;;
    src/harvest/ledger.py)                        add_test tests/test_taxonomy_ledger.sh ;;
    src/harvest/migrate/*.py)                     add_test tests/test_taxonomy_migration.sh ;;
    src/harvest/pool.py)                          add_test tests/test_taxonomy_pool.sh ;;
    src/harvest/preflight.py)                     add_test tests/test_taxonomy_preflight.sh ;;
    src/harvest/runvalidate.py)                   add_test tests/test_taxonomy_smoke.sh ;;
    src/harvest/records.py)                       add_test tests/test_taxonomy_records.sh; add_test tests/test_taxonomy_schema.sh ;;
    src/harvest/request_key.py)                   add_test tests/test_taxonomy_pool.sh; add_test tests/test_taxonomy_dedupe.sh ;;
    src/harvest/compare.py)                       add_test tests/test_taxonomy_compare.sh ;;
    src/harvest/cli.py)                           add_test tests/test_taxonomy_cli.sh; add_test tests/test_taxonomy_preflight.sh; add_test tests/test_taxonomy_smoke.sh; add_test tests/test_taxonomy_compare.sh ;;
    src/harvest/run_cells.py)                     add_test tests/test_taxonomy_run_cells.sh; add_test tests/test_taxonomy_recovery.sh; add_test tests/test_taxonomy_cli.sh; add_test tests/test_taxonomy_smoke.sh ;;
    src/harvest/schema.py)                        add_test tests/test_taxonomy_schema.sh; add_test tests/test_taxonomy_records.sh ;;
    src/harvest/slug.py)                          add_test tests/test_taxonomy_facet_identity.sh; add_test tests/test_taxonomy_facets.sh; add_test tests/test_taxonomy_config.sh ;;
    src/harvest/sourcecache.py)                   add_test tests/test_taxonomy_source_cache.sh ;;
    src/harvest/targetfetch.py)                   add_test tests/test_taxonomy_target_fetch.sh; add_test tests/test_taxonomy_target_ownership.sh; add_test tests/test_taxonomy_target_evidence.sh; add_test tests/test_taxonomy_target_accounting.sh; add_test tests/test_taxonomy_target_determinism.sh ;;
    src/harvest/urlkey.py)                        add_test tests/test_taxonomy_identity.sh; add_test tests/test_taxonomy_aliases.sh; add_test tests/test_taxonomy_facet_identity.sh ;;
    src/harvest/verify.py)                        add_test tests/test_taxonomy_verify.sh ;;

    # -- scripts/harvest/** : CLI and checkers
    scripts/harvest/harvest.sh)                   add_test tests/test_taxonomy_cli.sh ;;
    scripts/harvest/migrate.sh)                   add_test tests/test_taxonomy_migration.sh ;;
    scripts/harvest/check_config.py)              add_test tests/test_taxonomy_config.sh ;;
    scripts/harvest/check_facets.py)              add_test tests/test_taxonomy_facets.sh; add_test tests/test_taxonomy_migration.sh ;;
    scripts/harvest/check_fixtures.py)            add_test tests/test_taxonomy_source_cache.sh; add_test tests/test_taxonomy_target_fixtures.sh; add_test tests/test_taxonomy_adapters.sh ;;
    scripts/harvest/gen_facet_schema.py)          add_test tests/test_taxonomy_facets.sh; add_test tests/test_taxonomy_facetassign.sh ;;
    scripts/harvest/protected_baseline.py|scripts/harvest/gen_protected_baseline.sh|scripts/harvest/verify_protected_baseline.sh) add_test tests/test_taxonomy_protected_baseline.sh ;;

    # -- config/harvest/**
    config/harvest/topics/*.v1.json)              add_test tests/test_taxonomy_config.sh; add_test tests/test_taxonomy_adapters.sh; add_test tests/test_taxonomy_adapter_concurrency.sh ;;
    config/harvest/facets/*.v1.json)              add_test tests/test_taxonomy_facets.sh; add_test tests/test_taxonomy_facet_ambiguity.sh; add_test tests/test_taxonomy_facet_states.sh; add_test tests/test_taxonomy_facet_identity.sh; add_test tests/test_taxonomy_customer_interaction.sh; add_test tests/test_taxonomy_facetassign.sh ;;
    config/harvest/precedence.v1.json)            add_test tests/test_taxonomy_classify.sh ;;
    config/harvest/policy.v1.json)                add_test tests/test_taxonomy_verify.sh ;;
    config/harvest/coverage_targets.v1.json)      add_test tests/test_taxonomy_coverage.sh; add_test tests/test_taxonomy_facets.sh ;;
    config/harvest/canonicalization.v1.json)      add_test tests/test_taxonomy_aliases.sh; add_test tests/test_taxonomy_pool.sh ;;
    config/harvest/migration_overrides.v1.json)   add_test tests/test_taxonomy_migration.sh ;;
    # no consumer exists in production code or tests; check_config.py is its
    # only committed authority, so no behavioural suite is claimed for it.
    config/harvest/watchlists/*.v1.json)          add_test tests/test_taxonomy_config.sh ;;

    # -- schemas/harvest/**
    schemas/harvest/record.v1.json)               add_test tests/test_taxonomy_schema.sh; add_test tests/test_taxonomy_records.sh ;;
    schemas/harvest/taxonomy.v1.json)             add_test tests/test_taxonomy_config.sh ;;
    schemas/harvest/facet_vocabulary.v1.json|schemas/harvest/facets.generated.v1.json) add_test tests/test_taxonomy_facets.sh; add_test tests/test_taxonomy_facetassign.sh ;;
    schemas/harvest/cell_artifact.v1.json|schemas/harvest/topic_artifact.v1.json) add_test tests/test_taxonomy_cell_artifact.sh ;;
    schemas/harvest/ledger.v1.json|schemas/harvest/rejection.v1.json) add_test tests/test_taxonomy_ledger.sh ;;
    schemas/harvest/run_manifest.v1.json)         add_test tests/test_taxonomy_manifest.sh ;;
    schemas/harvest/coverage_report.v1.json)      add_test tests/test_taxonomy_coverage_report.sh ;;
    schemas/harvest/alias_conflict.v1.json)       add_test tests/test_taxonomy_aliases.sh; add_test tests/test_taxonomy_eligibility.sh ;;
    schemas/harvest/candidate_pool.v1.json|schemas/harvest/discovery_lane.v1.json) add_test tests/test_taxonomy_pool.sh ;;
  esac
done
[ "$MODE" = "all" ] && { for t in tests/*.sh; do add_test "$t"; done; }

# run only tests on the audited isolation allowlist
declare -a SAFE=()
for t in "${TESTS[@]:-}"; do
  [ -z "$t" ] && continue
  if is_isolated "$t"; then SAFE+=("$t")
  else echo "  WARN - skipping $t (not on the audited isolation allowlist)"; fi
done

# snapshot production state/ CONTENT (hashes) + porcelain before running anything
snapshot_state() {
  if [ -d state ]; then
    find state -type f | LC_ALL=C sort | while IFS= read -r p; do
      printf '%s  %s\n' "$(git hash-object "$p" 2>/dev/null || echo MISSING)" "$p"
    done
  fi
  echo "PORCELAIN:"; git status --porcelain -- state/
}
BEFORE="$(snapshot_state)"

# --- repository runtime paths (Stage 8, S8-1; plan decision D9) ------------
# The four paths the taxonomy pipeline writes at runtime. No test may create
# any of them: every write belongs under an injected temporary root.
#
# These are `[ -e ]` tests, not `git status`, for two independent reasons:
#   * state/taxonomy_harvest/ is gitignored (.gitignore: /state/taxonomy_harvest/),
#     so porcelain cannot see a leaked migration bundle at all;
#   * data/harvested/, runs/ and LATEST_RUN_ID sit at the repository root,
#     outside the state/ tree snapshot_state() walks.
# snapshot_state() remains the independent second witness for the first path,
# since `find state -type f` does see ignored files.
#
# Checked BEFORE the first wrapper and AFTER the last, so a leak is reported
# once by the harness rather than being attributed to whichever wrapper's own
# epilogue happens to run next. 16 of the 39 taxonomy wrappers carry their own
# leak guard; this does not replace or weaken them.
#
# Nothing is deleted, restored or relocated — matching the state/ snapshot's
# deliberate refusal to auto-restore. A leak is evidence; removing it destroys
# the evidence.
RUNTIME_PATHS=(state/taxonomy_harvest data/harvested runs LATEST_RUN_ID)
runtime_leaks() {
  local p
  for p in "${RUNTIME_PATHS[@]}"; do [ -e "$p" ] && printf '%s\n' "$p"; done
  return 0
}
report_leaks() {  # report_leaks <when> <paths>
  echo "  FAIL - repository runtime path(s) present $1 the run (NOT removing):"
  local p; for p in $2; do echo "           $p"; done
  echo "         every write must stay under an injected temporary root."
}
RUNTIME_BEFORE="$(runtime_leaks)"
[ -n "$RUNTIME_BEFORE" ] && { report_leaks "BEFORE" "$RUNTIME_BEFORE"; FAIL=1; }

for t in "${SAFE[@]:-}"; do [ -z "$t" ] && continue; run "offline $t" bash "$t"; done

RUNTIME_AFTER="$(runtime_leaks)"
if [ -n "$RUNTIME_AFTER" ]; then
  report_leaks "AFTER" "$RUNTIME_AFTER"; FAIL=1
else
  echo "  ok   - repository runtime paths absent (${RUNTIME_PATHS[*]})"
fi

AFTER="$(snapshot_state)"
if [ "$BEFORE" != "$AFTER" ]; then
  echo "  FAIL - production state/ CHANGED during validation (NOT auto-restoring):"
  if ! diff <(printf '%s\n' "$BEFORE") <(printf '%s\n' "$AFTER"); then :; fi
  FAIL=1
else
  echo "  ok   - production state/ unchanged (content hashes + porcelain)"
fi

[ "${#FILES[@]}" -eq 0 ] && [ "$MODE" != "all" ] && echo "  (no changed files to validate)"
echo
[ "$FAIL" -eq 0 ] && echo "== validate_task.sh: PASS ==" || echo "== validate_task.sh: FAIL =="
exit "$FAIL"
