# Normalized synthetic seller CSV and formulas

UTF-8 (optional BOM), comma-separated, a header and 1–10,000 rows, one row per unique SKU and one
shared inclusive analysis period. All columns below must exist; order may vary. Unknown/duplicate
columns, duplicate SKUs, mismatched field counts and malformed data are rejected. Whitespace is trimmed.
Missing optional values are **blank cells**, not `NA`, `NaN`, zero or infinity. A literal zero is an
observed zero. Required text, dates, units and selling price may not be blank.

| Column | Meaning | Blank allowed |
| --- | --- | --- |
| sku | Unique seller identifier; letters, digits, underscore, dot, hyphen; max 80 | No |
| asin | 10 uppercase alphanumeric characters; synthetic placeholders in demo | No |
| product_name | Display text, max 200 characters; HTML escaped | No |
| period_start, period_end | ISO dates, end >= start, same for every row | No |
| units_sold | Nonnegative integer units before refund adjustments | No |
| selling_price | USD per unit; use period weighted pre-discount price | No |
| discounts, refunds | Total USD reductions; combined cannot exceed gross sales | Yes |
| cogs | Period cost of sold units, excluding freight supplied separately | Yes |
| shipping | Period direct shipping costs not included in other costs | Yes |
| inbound_freight | Period allocation to sold units, excluding shipping/COGS | Yes |
| referral_fees | Period actual Amazon referral fees | Yes |
| fulfillment_fees | Period actual FBA fulfillment fees, excluding separate freight | Yes |
| storage_fees | Period actual allocated storage fees; no carrying-cost estimate | Yes |
| advertising_spend | Period ad spend | Yes |
| advertising_attributed_sales | Ad-platform attributed sales in matched attribution window | Yes |
| inventory_on_hand | Nonnegative integer units available at period end | Yes |
| lead_time_days | Nonnegative integer replenishment lead time | Yes |
| historical_daily_sales_velocity | Nonnegative supplied historical units/day, up to 4 decimals | Yes |

Money/velocity fields accept finite nonnegative decimals (up to 16 digits and 4 decimal places).
Integer quantities have a maximum of 1 billion. Negative corrections require a future native-export
normalizer; they are not silently converted to absolute values. Fees must already be consistently
allocated to the same SKU and period. This contract is not a direct Amazon settlement or ad-export parser.
Refund timing, VAT, multi-currency conversion and multiple order-line prices need upstream normalization.

Let `U` = units, `P` = per-unit selling price, `D` = discounts, `R` = refunds,
`C` = COGS, `S` = shipping, `I` = inbound freight, `Fᵣ` = referral fees, `F𝒻` = fulfillment fees,
`Fₛ` = storage fees, `A` = advertising spend, `Aₛ` = attributed sales.

| Metric | Formula |
| --- | --- |
| Gross sales | U × P |
| Net sales | U × P − D − R |
| Gross profit | Net sales − C − S − I |
| Contribution profit | Gross profit − Fᵣ − F𝒻 − Fₛ − A |
| Contribution margin | Contribution profit / net sales |
| ACOS | A / Aₛ |
| TACOS | A / net sales |
| Estimated inventory coverage (days) | On-hand units / historical units per day |
| Estimated reorder point (units) | ceil(historical units per day × lead time days) |
| Stockout risk | At risk if velocity > 0 and inventory <= reorder point; covered otherwise |

All operands for a metric must be known, else the output is null. Nonpositive ratio denominators
produce null, even 0/0. Zero velocity produces undefined coverage and `no_observed_demand` risk
when lead time and inventory are known. Missing required inventory inputs produce `unknown` risk.
Calculations use Decimal, then USD half-up rounding to cents and ratios/coverage to four decimals.
Ratios are fractions (0.25 means 25%). Reorder points round upward to whole units.
Summary totals sum displayed known SKU values and disclose the known-SKU count for each metric.
If all values are unknown, the total is null, not zero. Different completeness sets make subtraction
between partial totals invalid; contribution profit is summed from known per-SKU profit.

**Advertising attribution is not incremental revenue.** Attributed sales overlap total sales and can
use different attribution windows and refund policies. They are only the denominator of ACOS and are
never added to net sales. TACOS uses all net sales, not attributed sales. Neither ratio demonstrates
causality or justifies an automatic ad budget change.

Inventory outputs are **estimates, medium confidence when inputs exist**: constant historical velocity,
constant lead time, no inbound orders, safety stock, seasonality, service-level target or demand variance.
Unknown inputs reduce confidence to low. Supplied velocity is not inferred from a single period's units.
No competitor margins, budgets, volumes or acquisition costs are invented. Profit uplift and incremental
ad returns remain null/unmodeled. Review priorities are fixed rules: missing data, negative contribution
and stockout risk P1; margin below 10% or TACOS over 20% P2; coverage above 120 days P3.
Rules show source calculations and human-reviewed next actions, not optimal prices or guaranteed savings.
Contribution excludes overhead, tax, debt interest, capital cost and founder labor; it is not net income.
