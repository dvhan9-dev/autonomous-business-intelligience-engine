import pytest

from platform_core.models.tasks import ExecutionOutput
from platform_core.orchestration.runner import Orchestrator, WorkflowError
from platform_core.persistence.store import Store


class Step:
    def __init__(self, name, fail=False):
        self.name, self.fail, self.calls = name, fail, 0

    def execute(self, context, payload):
        self.calls += 1
        if self.fail:
            raise RuntimeError("SENSITIVE SOURCE DETAIL")
        return ExecutionOutput(payload={**payload, self.name: "done"})


def test_failure_then_resume_skips_completed_steps(tmp_path, caplog):
    database_url = f"sqlite:///{tmp_path / 'tasks.db'}"
    store = Store(database_url)
    first, second = Step("first"), Step("second", fail=True)
    options = dict(
        business_id="demo",
        workflow="test-v1",
        input_bytes=b"input",
        stages=[first, second],
        initial_payload={},
        finalize=lambda context, payload: (payload, "<p>Report</p>"),
    )
    with pytest.raises(WorkflowError) as error:
        Orchestrator(store).execute(**options)
    run_id = error.value.run_id
    failed = store.run(run_id)
    assert failed["status"] == "failed"
    assert failed["error"] == "RuntimeError"
    assert [task["status"] for task in failed["tasks"]] == ["completed", "failed"]
    assert "SENSITIVE SOURCE DETAIL" not in caplog.text
    second.fail = False
    store.engine.dispose()
    fresh_store = Store(database_url)
    assert Orchestrator(fresh_store).execute(**options, run_id=run_id) == run_id
    assert first.calls == 1 and second.calls == 2
    completed = fresh_store.run(run_id)
    assert completed["status"] == "completed"
    assert all(task["output_reference"] and task["completed_at"] for task in completed["tasks"])
    assert Orchestrator(fresh_store).execute(**options, run_id=run_id) == run_id
    assert second.calls == 2
    for override in [{"business_id": "other"}, {"input_bytes": b"different"}, {"workflow": "test-v2"}]:
        with pytest.raises(ValueError, match="matching"):
            Orchestrator(fresh_store).execute(**{**options, **override}, run_id=run_id)


def test_failed_evaluation_persists_criteria(tmp_path):
    from platform_core.models.tasks import Evaluation, EvaluationRejected

    class RejectingEvaluator:
        name = "evaluator"

        def execute(self, context, payload):
            raise EvaluationRejected(Evaluation(passed=False, criteria={"reconciles": False}))

    store = Store(f"sqlite:///{tmp_path / 'evaluation.db'}")
    with pytest.raises(WorkflowError) as error:
        Orchestrator(store).execute(
            business_id="demo",
            workflow="reject-v1",
            input_bytes=b"data",
            stages=[RejectingEvaluator()],
            initial_payload={},
            finalize=lambda context, payload: (payload, ""),
        )
    run = store.run(error.value.run_id)
    assert run["status"] == "failed"
    assert run["tasks"][0]["evaluation"] == {"passed": False, "criteria": {"reconciles": False}, "notes": []}


def test_unserializable_component_output_is_a_failed_task(tmp_path):
    class InvalidOutput:
        name = "invalid"

        def execute(self, context, payload):
            return ExecutionOutput(payload={"invalid": float("nan")})

    store = Store(f"sqlite:///{tmp_path / 'invalid.db'}")
    with pytest.raises(WorkflowError) as error:
        Orchestrator(store).execute(
            business_id="demo",
            workflow="invalid-v1",
            input_bytes=b"data",
            stages=[InvalidOutput()],
            initial_payload={},
            finalize=lambda context, payload: (payload, ""),
        )
    run = store.run(error.value.run_id)
    assert run["status"] == "failed"
    assert run["tasks"][0]["status"] == "failed"
    assert run["tasks"][0]["error"] == "ValueError"


def test_resume_missing_run_is_rejected(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'missing.db'}")
    with pytest.raises(ValueError, match="existing execution"):
        Orchestrator(store).execute(
            business_id="demo",
            workflow="test-v1",
            input_bytes=b"data",
            stages=[],
            initial_payload={},
            finalize=lambda context, payload: (payload, ""),
            run_id="00000000-0000-0000-0000-000000000000",
        )
