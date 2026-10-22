# Security boundary and pre-pilot work

This build is a single-operator **synthetic-only development tool**. Do not expose its server publicly
or upload real customer data. Business IDs and UUIDs separate datasets logically; they do not enforce
tenant authorization. Reports and task outputs contain financial information by design.

Implemented: strict normalized CSV schema, finite nonnegative numerics, row/byte limits, streaming
whole-request cap, safe UUID output namespaces, input digest for resume, HTML autoescape, report CSP,
no uploaded filenames used as filesystem paths, no stored raw uploads, closed upload handles,
metadata-only structured logs and sanitized persisted exception types. No API credentials are used.
No CSV spreadsheet exports are generated; future CSV export needs formula-injection protection.
Git ignores `.env`, runtime databases, caches and runtime reports. Committed sample outputs are synthetic.
Request access logging may contain business IDs/query parameters; do not use sensitive names as IDs.

Before real customer data:

- Authentication, tenant authorization and ownership checks on every upload/run/report endpoint; evaluate CSRF
  and browser access controls appropriate to the chosen auth scheme. UUIDs are not access control.
- Encryption at rest, TLS at the service boundary, secure secret bindings, least-privilege database access,
  backups, retention/deletion policy, audit access logs, incident response and restore testing.
- Per-user quotas, rate limiting, production request timeouts, concurrency control, worker isolation,
  durable task leases and recovery. The in-process runner is not a production queue.
- Malware/content validation and isolated import workers for untrusted datasets; review multipart spool
  permissions and clean-up after abnormal termination. Bound memory/CPU and retention volume as well as upload size.
- Schema migrations, PostgreSQL integration tests and transactional concurrency tests before multi-user rollout.
- Consent, data processing terms, a reviewed normalization/reconciliation process, and financial review.
- Explicit approval records with actor, action scope, payload digest and expiry before any consequential
  external action. A boolean marker in a recommendation is a UI contract, not an authorization mechanism.
- Sandbox proposed workflow/code changes, review evidence, test and obtain approval before applying them.

No scraping, private-account access, financial transactions, customer messaging, provider calls or
production self-modification is implemented. The application therefore cannot autonomously perform them.
