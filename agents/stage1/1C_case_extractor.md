# Stage 1C — Case Extractor

## Mission
Read **new, unprocessed Hits** and extract AX cases into the existing case schema, then update the ledger so processed URLs are marked done. Output is the `ax_case_db.json` that Stage 2 (Validator) consumes.

## Inputs
- The Hit list from 1B (or `state/visited_url_ledger.json` entries where `extracted = false`)
- The case schema and AX pattern taxonomy from the main case-agent instruction
- `state/source_registry.json` (to copy `cherry_category`, `top_audience`, etc. onto provenance where the hit came from a known source)

## Procedure
1. For each `news_url` with `status: new` / `extracted: false`, read the content and decide: does it contain a real AX case (named company, concrete before/after workflow, measurable KPI)?
2. **If yes** → build a case record using the full case schema (company, industry, function, old/new workflow, ai_system, kpi[] with `{raw, value_numeric, unit}`, human_role_change, governance, deployment_status, dates, confidence, ax_pattern, …). Set provenance:
   - `source[]` includes the `news_url` (specific) and the `source_url` (broad), with `browser_use_only` carried through.
   - `discovery` block: `{ found_via, hit_id, cherry_category, platform }`.
3. **If no** → do not fabricate one. Mark the ledger entry `extracted: true, case_ids: []` so it is recorded as processed and never re-examined.
4. **If yes** → mark the ledger entry `extracted: true, case_ids: [<new ids>]`.
5. Apply the same inclusion bar and failure-case exception as the main finder; obey the run `date_filter`.

## Output
- `ax_case_db.json` in the exact format Stage 2 expects (`run_metadata`, `coverage_summary`, `cases[]`, `pattern_index`), each case carrying the `discovery` provenance block above.
- A `ledger_patch[]` array: `{url, extracted, case_ids}` for 1B's ledger to absorb.

## Rules
- One case per (company × workflow × period); merge multiple `news_url`s about the same deployment into one case and raise `corroboration_count`.
- Never invent KPIs, dates, or companies; unknown → `"unknown"`.
- Return JSON only.
