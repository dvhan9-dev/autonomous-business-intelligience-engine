from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from amazon_audit.schemas.seller import SellerRow

CENT = Decimal("0.01")


def money(value: Decimal | None) -> str | None:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP)) if value is not None else None


def subtract(base: Decimal | None, *costs: Decimal | None) -> Decimal | None:
    if base is None or any(cost is None for cost in costs):
        return None
    return base - sum(costs, Decimal(0))


def ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def precise(value: Decimal | None) -> str | None:
    return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)) if value is not None else None


def calculate(row: SellerRow) -> dict:
    gross_sales = row.units_sold * row.selling_price
    net = subtract(gross_sales, row.discounts, row.refunds)
    gross = subtract(net, row.cogs, row.shipping, row.inbound_freight)
    contribution = subtract(
        gross, row.referral_fees, row.fulfillment_fees, row.storage_fees, row.advertising_spend
    )
    coverage = ratio(
        Decimal(row.inventory_on_hand) if row.inventory_on_hand is not None else None,
        row.historical_daily_sales_velocity,
    )
    reorder = None
    risk = "unknown"
    if row.historical_daily_sales_velocity is not None and row.lead_time_days is not None:
        reorder = int(
            (row.historical_daily_sales_velocity * row.lead_time_days).to_integral_value(
                rounding=ROUND_CEILING
            )
        )
        if row.inventory_on_hand is not None:
            if row.historical_daily_sales_velocity == 0:
                risk = "no_observed_demand"
            else:
                risk = "at_risk" if row.inventory_on_hand <= reorder else "covered"
    missing = [field for field in SellerRow.model_fields if getattr(row, field) is None]
    return {
        "sku": row.sku,
        "asin": row.asin,
        "product_name": row.product_name,
        "units_sold": row.units_sold,
        "gross_sales": money(gross_sales),
        "net_sales": money(net),
        "gross_profit": money(gross),
        "contribution_profit": money(contribution),
        "contribution_margin": precise(ratio(contribution, net)),
        "acos": precise(ratio(row.advertising_spend, row.advertising_attributed_sales)),
        "tacos": precise(ratio(row.advertising_spend, net)),
        "estimated_inventory_coverage_days": precise(coverage),
        "estimated_reorder_point_units": reorder,
        "stockout_risk": risk,
        "missing_fields": missing,
        "inventory_estimate": {
            "confidence": "medium" if risk != "unknown" else "low",
            "assumptions": "Constant supplied historical daily velocity and lead time; "
            "no safety stock, inbound inventory, seasonality or demand uncertainty.",
        },
        "source": row.model_dump(mode="json"),
    }


def summarize(products: list[dict]) -> dict:
    result = {"sku_count": len(products), "currency": "USD"}
    for field in ("net_sales", "gross_profit", "contribution_profit"):
        known = [Decimal(product[field]) for product in products if product[field] is not None]
        result[field] = money(sum(known, Decimal(0))) if known else None
        result[field + "_known_skus"] = len(known)
    result["complete_profitability_skus"] = result["contribution_profit_known_skus"]
    result["totals_policy"] = "Sum of known SKU values only; partial totals are not whole-business profit."
    return result
