from amazon_audit.analysis.opportunities import identify
from amazon_audit.calculations.profitability import calculate, summarize
from amazon_audit.ingestion.csv_import import DEFAULT_MAX_BYTES, import_csv
from amazon_audit.reporting.report import render_report
from platform_core.models.tasks import Evaluation, EvaluationRejected, ExecutionOutput, Proposal, TaskContext
from platform_core.orchestration.runner import Orchestrator
from platform_core.persistence.store import Store

WORKFLOW = "amazon-profit-audit-v1"
ASSUMPTIONS = [
    "Sprint 1 demonstration: synthetic normalized USD inputs only; not a native Amazon export adapter.",
    "All costs, discounts, refunds and attributed sales are period totals; selling price is per unit. "
    "COGS excludes separately supplied shipping and inbound freight. Fulfillment fees exclude those inputs.",
    "Net sales = units × selling price − discounts − refunds. "
    "Gross profit = net sales − COGS − shipping − inbound freight.",
    "Contribution profit = gross profit − referral fees − fulfillment fees "
    "− storage fees − advertising spend. "
    "Contribution margin = contribution profit / net sales. This is not accounting net income.",
    "ACOS = advertising spend / advertising-attributed sales; TACOS = advertising spend / net sales. "
    "Attributed sales overlap total sales and are NEVER added to revenue. "
    "Match attribution windows before use.",
    "Coverage estimate = inventory / supplied historical daily sales velocity. "
    "Reorder estimate = ceil(velocity × lead time); "
    "at risk when inventory ≤ reorder estimate and velocity > 0. "
    "Estimates assume stable demand and lead time, no inbound inventory or safety stock; medium confidence "
    "when inputs exist. Zero velocity means undefined coverage and no observed demand, "
    "not infinite coverage.",
    "Missing inputs stay null and propagate to dependent calculations; actual zeros stay zero. "
    "Ratios with nonpositive denominators are undefined (null). Money is rounded half up to cents; "
    "ratios/coverage to four decimals. Totals sum displayed SKU values.",
    "Heuristic review thresholds: margin <10%, TACOS >20%, coverage >120 days. "
    "They are investigation triggers, not universal targets. No competitor financial metrics are inferred.",
    "Storage fees are observed inputs; inventory carrying cost, capital cost, price elasticity, "
    "incremental ad returns and profit uplift are not estimated without additional evidence.",
    "Local deterministic execution has $0.00 estimated external API cost; "
    "compute and human labor are excluded.",
]


class Analyst:
    name = "analyst"

    def __init__(self, content: bytes, max_bytes: int):
        self.content, self.max_bytes = content, max_bytes

    def execute(self, context: TaskContext, payload: dict) -> ExecutionOutput:
        rows = import_csv(self.content, self.max_bytes)
        products = [calculate(row) for row in rows]
        return ExecutionOutput(
            payload={
                "schema_version": "1.0",
                "workflow_version": WORKFLOW,
                "run_id": context.run_id,
                "business_id": context.business_id,
                "input_reference": context.input_reference,
                "period": {"start": rows[0].period_start.isoformat(), "end": rows[0].period_end.isoformat()},
                "products": products,
                "summary": summarize(products),
                "opportunities": identify(products),
                "assumptions": ASSUMPTIONS,
            }
        )


class Evaluator:
    name = "evaluator"

    def execute(self, context: TaskContext, payload: dict) -> ExecutionOutput:
        products = payload["products"]
        evaluation = Evaluation(
            passed=True,
            criteria={
                "nonempty_analysis": len(products) > 0,
                "unique_skus": len({p["sku"] for p in products}) == len(products),
                "summary_reconciles": payload["summary"] == summarize(products),
                "financial_formulas_reconcile": all(calculate_row_matches(p) for p in products),
                "opportunities_have_evidence": all(bool(o["evidence"]) for o in payload["opportunities"]),
                "opportunities_require_approval": all(
                    o["requires_human_approval"] for o in payload["opportunities"]
                ),
            },
            notes=[
                "Completeness is disclosed, not assumed. "
                "Passing validates workflow integrity, not business viability."
            ],
        )
        evaluation.passed = all(evaluation.criteria.values())
        if not evaluation.passed:
            raise EvaluationRejected(evaluation)
        return ExecutionOutput(payload={**payload, "evaluation": evaluation.model_dump()})


def calculate_row_matches(product: dict) -> bool:
    from amazon_audit.schemas.seller import SellerRow

    expected = calculate(SellerRow.model_validate(product["source"]))
    return expected == product


class ImprovementPlanner:
    name = "improvement_planner"

    def execute(self, context: TaskContext, payload: dict) -> ExecutionOutput:
        missing = sum(bool(p["missing_fields"]) for p in payload["products"])
        proposals = [
            Proposal(
                title="Validate the audit with one seller interview",
                rationale="Synthetic output cannot establish willingness to pay for the $79 hypothesis.",
                proposed_action=(
                    "Prepare a sample audit and an interview plan for founder approval; "
                    "send nothing automatically."
                ),
            )
        ]
        if missing:
            proposals.append(
                Proposal(
                    title="Improve source-data completeness",
                    rationale=f"{missing} SKUs have missing inputs.",
                    proposed_action=(
                        "Design an import mapping and completeness checklist; "
                        "obtain approval before code changes."
                    ),
                )
            )
        proposals.append(
            Proposal(
                title="Calibrate inventory assumptions",
                rationale="Current coverage estimates omit uncertainty and inbound purchase orders.",
                proposed_action=(
                    "Propose historical backtests and safety-stock inputs "
                    "before changing replenishment rules."
                ),
            )
        )
        return ExecutionOutput(
            payload={
                **payload,
                "improvement_proposals": [p.model_dump() for p in proposals],
                "estimated_execution_cost_usd": "0.00",
            }
        )


def execute_audit(
    store: Store,
    content: bytes,
    business_id: str = "synthetic-demo",
    run_id: str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> str:
    # Keep the generic orchestrator free of Amazon models, formulas and report templates.
    def finalize(context: TaskContext, payload: dict) -> tuple[dict, str]:
        return payload, render_report(payload)

    return Orchestrator(store).execute(
        business_id=business_id,
        workflow=WORKFLOW,
        input_bytes=content,
        stages=[Analyst(content, max_bytes), Evaluator(), ImprovementPlanner()],
        initial_payload={},
        finalize=finalize,
        run_id=run_id,
    )
