import argparse
import json
import logging
import os
from pathlib import Path
from uuid import UUID

from amazon_audit.service import execute_audit
from amazon_audit.synthetic import write_synthetic
from platform_core.orchestration.runner import WorkflowError
from platform_core.persistence.store import Store


def prepare_store(database_url: str | None = None) -> Store:
    from sqlalchemy.engine import make_url

    url = database_url or os.getenv("ENTREPRENEUR_DATABASE_URL", "sqlite:///runtime/entrepreneur.db")
    parsed = make_url(url)
    if parsed.drivername.startswith("sqlite") and parsed.database and parsed.database != ":memory:":
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    return Store(url)


def main():
    parser = argparse.ArgumentParser(description="Synthetic-only local Amazon profit audit")
    subcommands = parser.add_subparsers(dest="command", required=True)
    generate = subcommands.add_parser("generate")
    generate.add_argument("--output", type=Path, default=Path("data/synthetic/seller.csv"))
    audit = subcommands.add_parser("audit")
    audit.add_argument("input", type=Path)
    audit.add_argument("--business-id", default="synthetic-demo")
    audit.add_argument("--output-dir", type=Path, default=Path("runtime/reports"))
    audit.add_argument("--resume", type=UUID)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if arguments.command == "generate":
        write_synthetic(arguments.output)
        print(f"Synthetic CSV: {arguments.output}")
        return
    store = prepare_store()
    limit = int(os.getenv("ENTREPRENEUR_MAX_UPLOAD_BYTES", "2097152"))
    with arguments.input.open("rb") as source:
        content = source.read(limit + 1)
    try:
        run_id = execute_audit(
            store, content, arguments.business_id, str(arguments.resume) if arguments.resume else None, limit
        )
    except WorkflowError as exc:
        parser.exit(1, f"Audit failed: {exc}. Inspect execution metadata in the database.\n")
    result = store.run(run_id)["result"]
    destination = arguments.output_dir / run_id
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (destination / "audit.html").write_text(store.report(run_id), encoding="utf-8")
    print(
        json.dumps(
            {
                "run_id": run_id,
                "report": str(destination / "audit.html"),
                "json": str(destination / "audit.json"),
                "evaluation": result["evaluation"]["passed"],
            }
        )
    )


if __name__ == "__main__":
    main()
