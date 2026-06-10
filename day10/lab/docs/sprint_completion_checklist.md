# 4-Sprint Completion Checklist

Audit date: 2026-06-10

## Sprint 1 - Analyze & Ingest: COMPLETE

- [x] Analyzed 247 raw records and 39 unique `doc_id` values.
- [x] Found missing valid source `access_control_sop` and registered it.
- [x] Compared required top-1 sources in grading questions.
- [x] Log contains `run_id`, raw, cleaned, and quarantine counts.
- [x] Source map completed in `docs/data_contract.md`.

Evidence: `artifacts/logs/run_optimized-final.log`,
`artifacts/manifests/manifest_optimized-final.json`.

## Sprint 2 - Clean, Validate & Embed: COMPLETE

- [x] Standard pipeline exits 0 without `--skip-validate`.
- [x] Added at least 3 measurable cleaning rules.
- [x] Added at least 2 expectations with warn/halt severity.
- [x] Cleaned and quarantine CSVs are written.
- [x] Stable `chunk_id`, Chroma upsert, and stale-ID prune are implemented.
- [x] Official grading passes 10/10.

Evidence: `transform/cleaning_rules.py`, `quality/expectations.py`,
`artifacts/eval/grading_run.jsonl`.

## Sprint 3 - Inject & Before/After: COMPLETE

- [x] Inject run disables refund correction and intentionally skips validation.
- [x] Inject log records a halt expectation failure with 2 violations.
- [x] Before eval contains 1 forbidden hit.
- [x] After eval contains 0 forbidden hits.
- [x] Quality report interprets the result.

Evidence: `artifacts/logs/run_inject-bad.log`,
`artifacts/eval/after_inject_bad.csv`,
`artifacts/eval/eval_optimized_final.csv`, `docs/quality_report.md`.

## Sprint 4 - Monitoring, Docs & Report: COMPLETE

- [x] Pipeline architecture, data contract, and runbook completed.
- [x] Freshness FAIL is explained against the 24-hour SLA.
- [x] Group report includes metric impact and 3 peer-review questions.
- [x] README includes a one-line completion command.
- [x] Individual report draft exists.

Evidence: `docs/*.md`, `reports/group_report.md`,
`reports/individual/data_pipeline_owner.md`.

## Before Submission

- Replace the name in `reports/individual/data_pipeline_owner.md`.
- Replace generic team/member details if the instructor requires real identities.
