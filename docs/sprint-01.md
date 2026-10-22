# Sprint 1 delivery and verification

## Delivered

The first working vertical slice imports a reproducible 24-SKU synthetic dataset, validates and
normalizes it, calculates profitability, prioritizes deterministic review opportunities and stores
JSON, HTML, evaluation and task metadata. Both a CLI and local FastAPI application execute the same
workflow. Three pure local components implement analyst, evaluator and improvement planner roles.
The reusable core has no Amazon imports. Improvements are proposals; there is no self-modifying code.

The demonstration yields **26 opportunities**, $69,345.28 known net sales across 24 SKUs,
$48,632.49 known gross profit across 23 SKUs, and $14,619.39 known contribution profit across 23 SKUs.
These are synthetic observations. Totals intentionally have different completeness sets, because
one SKU has missing COGS. They must not be presented as whole-business accounting results.

Actual sample artifacts: `reports/samples/audit.html` and `reports/samples/audit.json`.
The JSON contains the actual execution ID, input digest, evaluation and assumptions; corresponding
execution/task records exist in the current instance's ignored `runtime/entrepreneur.db`.
The file-based CLI demonstration also produced UUID-scoped HTML and JSON under `runtime/demo/`.
Run IDs/timestamps change on a new demonstration. Sample output is a historical artifact, not a live endpoint.

## Executed checks

- `uv sync --frozen --extra dev` succeeded and was repeated successfully with an existing environment.
- `uv run --frozen pytest -q`: **42 passed**, no failed/skipped/expected-failure tests.
- Ruff checks and formatting checks passed.
- Source distribution and wheel built with `uv build`.
- Built wheel installed into a separate virtual environment outside the checkout; a full 24-SKU
  audit completed and rendered the packaged Jinja2 template. This validates package data inclusion.
- CLI generated the CSV and completed an audit with JSON/HTML files.
- A running Uvicorn server passed HTTP health, multipart upload, execution JSON retrieval and HTML
  retrieval. All three task statuses completed and the evaluation passed.
- The server was stopped/restarted after final code changes; the HTTP workflow was rerun successfully.
  Task input references correctly point to the preceding persisted output references.
- An independent database connection verified committed run/report state.
- Tests exercise handled failures/resume across database reconnection, resume identity mismatches,
  rejected evaluation criteria persistence, invalid JSON outputs, invalid files/size/row limits,
  report escaping and dataset namespace separation.

The test stack emits one upstream Starlette warning that its httpx TestClient integration is deprecated
in favor of httpx2. All tests execute and pass; upgrading the test transport is future maintenance.
There are no live AI-provider, seller-account, PostgreSQL or production deployment checks; none is claimed.

## Deliberate limitations

Only normalized synthetic USD data is supported. Native seller export mappings, real customer security,
billing, competitor snapshots, carrying/capital-cost modeling, causal ad optimization and live provider
adapters are not implemented. Inventory has no safety stock, inbound orders or forecast uncertainty.
The local runner supports handled failures but not worker-crash recovery or concurrent resumption.
No generic opportunity scoring/experiment lifecycle is implemented yet; interfaces and the roadmap
keep the long-term vision separate from this tested foundation.

## Next sprint

Validate one seller's willingness to pay through a founder-approved experiment. Implement the
security prerequisites before accepting real data, reconcile native export mappings, and add a
small generic experiment/evidence ledger. Defer infrastructure and autonomous external actions until justified.

## Repository and environment handoff

Source, tests, documentation, the dependency lock and synthetic samples are included in the initial
foundation commit. Runtime databases, dependencies and caches remain ignored. The founder explicitly
approved the initial GitHub push to main after reviewing the Sprint 1 delivery.
No public deployment, paid services or external seller actions occurred.

The reusable install/start instructions are saved separately in the environment configuration draft.
Draft saving does not publish the environment or prove restoration in a new task. Review/save the
configuration and publish through environment settings when ready; fresh-task restoration is unverified.
