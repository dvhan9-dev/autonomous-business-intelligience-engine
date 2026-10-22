# Autonomous Entrepreneur — Sprint 1

A local, deterministic proof of concept for an **Amazon FBA Profit Intelligence Service**.
Import a normalized synthetic seller CSV, calculate SKU profitability, identify review opportunities,
and generate HTML and JSON reports with persisted execution records. No AI subscription or API key is needed.

**Synthetic data only. Bind to loopback. This is not a production service for real seller data.**
The $79 audit and future $49–$99 subscription are unvalidated pricing hypotheses, not proven demand.

## Install and run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). From this repository root:

```bash
export UV_CACHE_DIR=/tmp/entrepreneur-uv-cache
uv sync --frozen --extra dev
uv run --frozen entrepreneur generate
uv run --frozen entrepreneur audit data/synthetic/seller.csv --output-dir runtime/reports
uv run --frozen uvicorn api.app:app --host 127.0.0.1 --port 8000
```

The CLI prints the actual UUID and locations of `audit.html` and `audit.json` under
`runtime/reports/<run-id>/`. It also persists the execution, three component tasks, evaluation,
results and report in `runtime/entrepreneur.db`. The server uses the same database by default.
The generated CSV contains 24 fictional SKUs, including losses, high ad spend, excess inventory,
stockout risks, one missing COGS value and a zero-ad-sales case. Synthetic ASINs are placeholders.

For a conventional pip installation instead of uv, create/activate a Python 3.12 virtual environment
and run `python -m pip install -e '.[dev]'` (not lockfile-frozen).

## API demonstration

With the server running, use its interactive API documentation at the `/docs` route, or:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail -X POST 'http://127.0.0.1:8000/audits?business_id=synthetic-demo' \
  -F 'file=@data/synthetic/seller.csv;type=text/csv'
```

The response contains `run_id`, `result_path`, and `report_path`. Substitute the actual ID:

```bash
curl --fail http://127.0.0.1:8000/audits/REPLACE_WITH_RUN_ID
curl --fail http://127.0.0.1:8000/audits/REPLACE_WITH_RUN_ID/report -o runtime/api-report.html
```

`GET /audits/{run_id}` returns status, task metadata and the structured result.
`GET /audits/{run_id}/report` returns escaped HTML. Health checks database connectivity.
Uploads accept CSV only, default to 2 MiB maximum, and allow at most 10,000 rows; an additional
64 KiB multipart envelope allowance bounds the entire request, even without Content-Length.
All documented columns must be present, in any order. See [the data contract](docs/data-contract.md).
Validation errors return 422 with a persisted failed execution ID; wrong file types return 415,
size violations 413, incompatible resume requests 409, and internal workflow errors 500 with an execution ID.
Transport-level rejections happen before a workflow exists and are not audit executions.

## Checks

```bash
uv run --frozen pytest -q
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

Tests cover independent financial expectations, zero/unknown propagation, attribution, inventory,
CSV validation, upload limits including streaming bodies, escaping, end-to-end API results,
business/run separation, failure persistence, and stage-level resume across database reconnection.

## Configuration and recovery

`.env.example` lists supported variables; export values explicitly (no automatic dotenv loading).
`ENTREPRENEUR_DATABASE_URL` defaults to `sqlite:///runtime/entrepreneur.db`.
`ENTREPRENEUR_MAX_UPLOAD_BYTES` defaults to `2097152`; API accepts a maximum of 20 MiB.
Run commands from the repository root so relative database paths resolve consistently.
Only local synthetic use is supported; one server worker, no public binding or external actions.

Failed pure stages can be retried with **identical input bytes**, business ID and workflow version:

```bash
uv run --frozen entrepreneur audit data/synthetic/seller.csv --business-id synthetic-demo \
  --resume REPLACE_WITH_FAILED_RUN_ID
```

Or re-upload with `POST /audits?business_id=synthetic-demo&resume=<run-id>`.
Completed stages are loaded from the database rather than rerun. Completed runs return their existing ID.
A changed CSV is a new execution, not a resume. A process killed while marked `running` requires
manual investigation; automatic crash recovery and concurrent resumptions are not supported.
This preserves idempotency without pretending to provide distributed task guarantees.

## What is included

- `src/platform_core`: generic SQLAlchemy records, structured tasks, sequential orchestration,
  provider interface, explicit failure states and stage checkpoints. It imports no Amazon logic.
- `src/amazon_audit`: Pydantic CSV contract, Pandas import, Decimal calculations, rule-based
  opportunities, analyst/evaluator/improvement-planner components, and Jinja2 report templates.
- `src/api`: FastAPI upload, retrieval and report interface; no complex frontend.
- `reports/samples/audit.html` and `audit.json`: actual output from the first synthetic demonstration.
- `docs`: architecture, formula contract, decisions, security gaps, roadmap and sprint evidence.

Inventory metrics are estimates with assumptions and confidence. Recommendations are deterministic
review rules with supporting calculations; no uplift is fabricated and no action is executed.
There are no scraping, seller-account, billing or live AI integrations. Workflow improvements
are proposals only. See [security limitations](docs/security.md) before planning any real-data pilot.

The next goal is one founder-approved seller validation interview and a secure pilot workflow,
not building every element of the long-term platform at once.
