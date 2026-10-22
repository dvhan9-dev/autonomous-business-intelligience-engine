import hashlib
import json
import logging
import uuid
from collections.abc import Callable
from typing import Protocol

from sqlalchemy import select

from platform_core.models.tasks import EvaluationRejected, ExecutionOutput, TaskContext, utc_now
from platform_core.persistence.store import Run, Store, Task

logger = logging.getLogger(__name__)


class Component(Protocol):
    name: str

    def execute(self, context: TaskContext, payload: dict) -> ExecutionOutput: ...


class WorkflowError(Exception):
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"Workflow failed; see execution {run_id}")


class Orchestrator:
    """Sequential, resumable local execution. Single worker; no distributed leases.

    Reuse a completed stage only for the same business, workflow version and input digest.
    Components must be pure/idempotent. External actions require a separate approval mechanism.
    """

    def __init__(self, store: Store):
        self.store = store

    def execute(
        self,
        *,
        business_id: str,
        workflow: str,
        input_bytes: bytes,
        stages: list[Component],
        initial_payload: dict,
        finalize: Callable[[TaskContext, dict], tuple[dict, str]],
        run_id: str | None = None,
    ) -> str:
        digest = "sha256:" + hashlib.sha256(input_bytes).hexdigest()
        resuming = run_id is not None
        run_id = run_id or str(uuid.uuid4())
        context = TaskContext(run_id=run_id, business_id=business_id, input_reference=digest)
        with self.store.session() as session:
            run = session.get(Run, run_id)
            if run is None:
                if resuming:
                    raise ValueError("Resume requires an existing execution")
                session.add(
                    Run(
                        id=run_id,
                        business_id=business_id,
                        workflow=workflow,
                        input_reference=digest,
                        status="running",
                    )
                )
            else:
                if (run.business_id, run.workflow, run.input_reference) != (business_id, workflow, digest):
                    raise ValueError("Resume requires matching business, workflow and input digest")
                if run.status == "completed":
                    return run_id
                if run.status == "running":
                    raise ValueError(
                        "Run is already running; automatic recovery of interrupted workers is unsupported"
                    )
                run.status, run.error, run.completed_at = "running", None, None
        payload = initial_payload
        previous_reference = digest
        try:
            for stage in stages:
                with self.store.session() as session:
                    task = session.scalar(select(Task).where(Task.run_id == run_id, Task.stage == stage.name))
                    if task and task.status == "completed":
                        payload = json.loads(task.output_json)
                        previous_reference = task.output_reference
                        continue
                    if task is None:
                        task = Task(
                            id=str(uuid.uuid4()),
                            run_id=run_id,
                            business_id=business_id,
                            stage=stage.name,
                            component=type(stage).__name__,
                            input_reference=previous_reference,
                        )
                        session.add(task)
                    task.status, task.started_at, task.completed_at, task.error = (
                        "running",
                        utc_now(),
                        None,
                        None,
                    )
                    task_id = task.id
                logger.info(
                    json.dumps(
                        {
                            "event": "task_started",
                            "run_id": run_id,
                            "task_id": task_id,
                            "component": stage.name,
                        }
                    )
                )
                try:
                    output = stage.execute(context, payload)
                    serialized = json.dumps(output.payload, allow_nan=False)
                except Exception as exc:
                    with self.store.session() as session:
                        task = session.get(Task, task_id)
                        task.status, task.completed_at, task.error = "failed", utc_now(), type(exc).__name__
                        if isinstance(exc, EvaluationRejected):
                            task.evaluation_json = exc.evaluation.model_dump_json()
                    raise
                payload = output.payload
                with self.store.session() as session:
                    task = session.get(Task, task_id)
                    task.status, task.completed_at = "completed", utc_now()
                    task.output_reference = f"db:tasks/{task_id}/output"
                    task.output_json = serialized
                    previous_reference = task.output_reference
                    task.estimated_cost_usd = output.estimated_cost_usd
                    if "evaluation" in payload:
                        task.evaluation_json = json.dumps(payload["evaluation"])
                logger.info(json.dumps({"event": "task_completed", "run_id": run_id, "task_id": task_id}))
            result, html = finalize(context, payload)
            with self.store.session() as session:
                run = session.get(Run, run_id)
                run.result_json, run.report_html = json.dumps(result, allow_nan=False), html
                run.status, run.completed_at = "completed", utc_now()
        except Exception as exc:
            with self.store.session() as session:
                run = session.get(Run, run_id)
                run.status, run.completed_at, run.error = "failed", utc_now(), type(exc).__name__
            logger.error(
                json.dumps({"event": "workflow_failed", "run_id": run_id, "error_type": type(exc).__name__})
            )
            raise WorkflowError(run_id) from exc
        return run_id
