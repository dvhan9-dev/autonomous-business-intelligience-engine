from decimal import Decimal

import pytest

from amazon_audit.analysis.opportunities import identify
from amazon_audit.calculations.profitability import calculate, money, summarize


def test_financial_formulas_with_independently_calculated_values(seller_row):
    metrics = calculate(seller_row)
    assert metrics["gross_sales"] == "2000.00"
    assert metrics["net_sales"] == "1850.00"
    assert metrics["gross_profit"] == "1300.00"
    assert metrics["contribution_profit"] == "425.00"
    assert metrics["contribution_margin"] == "0.2297"
    assert metrics["acos"] == "0.2500"
    assert metrics["tacos"] == "0.1081"
    assert metrics["estimated_inventory_coverage_days"] == "10.0000"
    assert metrics["estimated_reorder_point_units"] == 45
    assert metrics["stockout_risk"] == "at_risk"


def test_attribution_does_not_add_revenue(seller_row):
    original = calculate(seller_row)
    changed = calculate(seller_row.model_copy(update={"advertising_attributed_sales": Decimal("99999")}))
    for field in ["net_sales", "gross_profit", "contribution_profit", "tacos"]:
        assert original[field] == changed[field]
    assert original["acos"] != changed["acos"]


@pytest.mark.parametrize("field", ["cogs", "shipping", "referral_fees", "advertising_spend", "discounts"])
def test_missing_is_not_zero(seller_row, field):
    missing = calculate(seller_row.model_copy(update={field: None}))
    zero = calculate(seller_row.model_copy(update={field: Decimal(0)}))
    assert missing["contribution_profit"] is None
    assert zero["contribution_profit"] is not None
    assert field in missing["missing_fields"]


def test_zero_denominators_and_no_demand(seller_row):
    metrics = calculate(
        seller_row.model_copy(
            update={
                "units_sold": 0,
                "discounts": Decimal(0),
                "refunds": Decimal(0),
                "advertising_attributed_sales": Decimal(0),
                "historical_daily_sales_velocity": Decimal(0),
            }
        )
    )
    assert metrics["contribution_margin"] is None
    assert metrics["acos"] is None
    assert metrics["tacos"] is None
    assert metrics["estimated_inventory_coverage_days"] is None
    assert metrics["estimated_reorder_point_units"] == 0
    assert metrics["stockout_risk"] == "no_observed_demand"


def test_reorder_ceiling_boundary_and_missing(seller_row):
    row = seller_row.model_copy(
        update={"historical_daily_sales_velocity": Decimal("3.01"), "inventory_on_hand": 46}
    )
    assert calculate(row)["estimated_reorder_point_units"] == 46
    assert calculate(row)["stockout_risk"] == "at_risk"
    assert calculate(row.model_copy(update={"inventory_on_hand": 47}))["stockout_risk"] == "covered"
    assert calculate(row.model_copy(update={"lead_time_days": None}))["stockout_risk"] == "unknown"


def test_half_up_rounding_and_partial_totals(seller_row):
    assert money(Decimal("1.005")) == "1.01"
    assert money(Decimal("-1.005")) == "-1.01"
    full = calculate(seller_row)
    partial = calculate(seller_row.model_copy(update={"cogs": None}))
    summary = summarize([full, partial])
    assert summary["net_sales"] == "3700.00"
    assert summary["contribution_profit"] == "425.00"
    assert summary["contribution_profit_known_skus"] == 1
    assert summarize([partial])["contribution_profit"] is None


def test_opportunities_have_calculations_and_no_fabricated_uplift(seller_row):
    metrics = calculate(seller_row.model_copy(update={"advertising_spend": Decimal("1000")}))
    opportunities = identify([metrics])
    assert {o["code"] for o in opportunities} == {
        "negative_contribution",
        "advertising_intensity",
        "stockout_risk",
    }
    assert [o["priority"] for o in opportunities] == sorted(o["priority"] for o in opportunities)
    assert all(o["evidence"] and o["requires_human_approval"] for o in opportunities)
    assert all(o["estimated_profit_uplift_usd"] is None for o in opportunities)


def test_evaluator_rejects_corrupted_calculation(seller_row):
    from amazon_audit.service import Evaluator
    from platform_core.models.tasks import EvaluationRejected, TaskContext

    product = calculate(seller_row)
    product["contribution_profit"] = "999.00"
    payload = {"products": [product], "summary": summarize([product]), "opportunities": []}
    with pytest.raises(EvaluationRejected) as failure:
        Evaluator().execute(TaskContext(run_id="run", business_id="demo", input_reference="test"), payload)
    assert failure.value.evaluation.criteria["financial_formulas_reconcile"] is False
