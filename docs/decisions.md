# Sprint 1 decisions

1. **Local deterministic first.** Avoid provider bills and nondeterministic arithmetic. A provider protocol
   establishes a future integration boundary; financial outputs remain independent of model prose.
2. **One application and shared service.** FastAPI docs and a CLI provide the first interface. No frontend
   framework, message queue, microservices, browser automation or seller account connections are needed.
3. **Decimal arithmetic, Pandas input.** Pandas parses text without converting blanks or decimals to float.
   Pydantic validates each row. USD formulas and round-half-up outputs are explicit and independently tested.
4. **Normalized synthetic contract.** Real Amazon reports differ in granularity, signs and attribution windows.
   Native adapters are deferred rather than claiming arbitrary exports work. Blanks stay unknown.
5. **SQLAlchemy and SQLite.** Portable tables make future PostgreSQL adaptation practical. Development creates
   tables on startup; schema migration tooling is deferred and PostgreSQL itself is not yet validated.
6. **Checkpoint pure local components.** Handled failures can resume matching input and workflow versions.
   No external effects are retried; crash recovery, concurrent resume and distributed execution are deferred.
7. **HTML and JSON retained with run records.** UUID namespaces separate results; local report files are optional.
   Autoescaping and report CSP reduce HTML injection. No tenant access-control claim is made.
8. **Proposals only.** Actions carry human-approval markers. There is no financial/external/code execution tool,
   so a marker is not misrepresented as an implemented approval engine.
9. **Frozen dependency lock.** `uv.lock` records tested dependency resolution. Use `uv sync --frozen --extra dev`.
   The uv cache is redirected to `/tmp` for the cloud environment's read-only home directory.
10. **Source remains reviewable.** This task creates the project in the existing isolated checkout. It does not
    deploy publicly, buy services, contact sellers or push changes to GitHub automatically.
