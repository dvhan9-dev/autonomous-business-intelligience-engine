from decimal import Decimal


def identify(products: list[dict]) -> list[dict]:
    opportunities = []

    def add(product, code, priority, title, evidence, action, confidence="high"):
        opportunities.append(
            {
                "sku": product["sku"],
                "code": code,
                "priority": priority,
                "title": title,
                "evidence": evidence,
                "suggested_action": action,
                "confidence": confidence,
                "estimated_profit_uplift_usd": None,
                "requires_human_approval": True,
                "origin": "deterministic_rule",
            }
        )

    for p in products:
        if p["missing_fields"]:
            add(
                p,
                "missing_data",
                1,
                "Complete missing inputs before acting",
                {"missing_fields": p["missing_fields"]},
                "Obtain source records; blanks are never assumed zero.",
            )
        profit = Decimal(p["contribution_profit"]) if p["contribution_profit"] is not None else None
        if profit is not None and profit < 0:
            add(
                p,
                "negative_contribution",
                1,
                "Review a loss-making SKU",
                {"contribution_profit_usd": p["contribution_profit"]},
                "Reconcile costs, then model pricing, fees and ad changes before approval.",
            )
        elif p["contribution_margin"] is not None and Decimal(p["contribution_margin"]) < Decimal("0.10"):
            add(
                p,
                "thin_margin",
                2,
                "Review thin contribution margin",
                {"margin": p["contribution_margin"], "review_threshold": "0.10"},
                "Inspect price, discount and cost drivers; validate demand before any price change.",
            )
        if p["tacos"] is not None and Decimal(p["tacos"]) > Decimal("0.20"):
            add(
                p,
                "advertising_intensity",
                2,
                "Investigate advertising efficiency",
                {"tacos": p["tacos"], "review_threshold": "0.20", "acos": p["acos"]},
                "Review search terms and incrementality. High spend alone does not justify cutting ads.",
                "medium",
            )
        if p["stockout_risk"] == "at_risk":
            add(
                p,
                "stockout_risk",
                1,
                "Review replenishment timing (estimate)",
                {
                    "inventory_on_hand": p["source"]["inventory_on_hand"],
                    "estimated_reorder_point_units": p["estimated_reorder_point_units"],
                    "estimated_coverage_days": p["estimated_inventory_coverage_days"],
                },
                "Confirm inbound orders and demand before approving a purchase.",
                "medium",
            )
        coverage = p["estimated_inventory_coverage_days"]
        if coverage is not None and Decimal(coverage) > 120:
            add(
                p,
                "excess_coverage",
                3,
                "Review slow-moving inventory (estimate)",
                {"estimated_coverage_days": coverage, "review_threshold_days": 120},
                "Review aged inventory and cash tied up; "
                "quantify storage and demand before reallocating capital.",
                "medium",
            )
    return sorted(opportunities, key=lambda item: (item["priority"], item["sku"], item["code"]))
