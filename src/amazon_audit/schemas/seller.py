from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=4, allow_inf_nan=False)]
Quantity = Annotated[int, Field(ge=0, le=1_000_000_000)]


class SellerRow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sku: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    asin: str = Field(pattern=r"^[A-Z0-9]{10}$")
    product_name: str = Field(min_length=1, max_length=200)
    period_start: date
    period_end: date
    units_sold: Quantity
    selling_price: Money
    discounts: Money | None = None
    refunds: Money | None = None
    cogs: Money | None = None
    shipping: Money | None = None
    inbound_freight: Money | None = None
    referral_fees: Money | None = None
    fulfillment_fees: Money | None = None
    storage_fees: Money | None = None
    advertising_spend: Money | None = None
    advertising_attributed_sales: Money | None = None
    inventory_on_hand: Quantity | None = None
    lead_time_days: Quantity | None = None
    historical_daily_sales_velocity: Money | None = None

    @model_validator(mode="after")
    def valid_period_and_revenue(self):
        if self.period_end < self.period_start:
            raise ValueError("Analysis period ends before it starts")
        if self.discounts is not None and self.refunds is not None:
            if self.discounts + self.refunds > self.units_sold * self.selling_price:
                raise ValueError(
                    "Discounts plus refunds exceed gross sales; use the normalized period contract"
                )
        return self
