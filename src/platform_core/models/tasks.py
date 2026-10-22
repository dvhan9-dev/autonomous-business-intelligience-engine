from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Status(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class TaskContext(BaseModel):
    run_id: str
    business_id: str
    input_reference: str


class Proposal(BaseModel):
    title: str
    rationale: str
    proposed_action: str
    requires_human_approval: bool = True
    status: str = "proposed"


class Evaluation(BaseModel):
    passed: bool
    criteria: dict[str, bool]
    notes: list[str] = Field(default_factory=list)


class ExecutionOutput(BaseModel):
    payload: dict[str, Any]
    estimated_cost_usd: str = "0.00"


class EvaluationRejected(Exception):
    def __init__(self, evaluation: Evaluation):
        self.evaluation = evaluation
        super().__init__("Output failed deterministic evaluation")
