import csv
import io
from datetime import date
from decimal import Decimal
from pathlib import Path

from amazon_audit.schemas.seller import SellerRow


def generate_csv() -> bytes:
    """Reproducible fictitious products; no real ASINs/accounts are represented."""
    names = [
        "Beard Oil",
        "Face Wash",
        "Shave Balm",
        "Hair Clay",
        "Body Wash",
        "Beard Comb",
        "Scalp Serum",
        "Lip Balm",
        "Hand Cream",
        "Shave Brush",
        "Hair Wax",
        "Face Scrub",
        "Beard Shampoo",
        "Cuticle Oil",
        "Moisturizer",
        "Grooming Kit",
        "Soap Bar",
        "Hair Tonic",
        "Foot Cream",
        "Travel Balm",
        "Shave Soap",
        "Beard Butter",
        "Body Lotion",
        "Hair Paste",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(SellerRow.model_fields))
    writer.writeheader()
    for index, name in enumerate(names):
        units = 40 + index * 9
        price = Decimal("12.99") + Decimal(index % 7) * 3
        revenue = price * units
        row = SellerRow(
            sku=f"SYN-{index + 1:03d}",
            asin=f"SYN{index + 1:07d}",
            product_name=f"Synthetic {name}",
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            units_sold=units,
            selling_price=price,
            discounts=(revenue * Decimal("0.04")).quantize(Decimal(".01")),
            refunds=(revenue * Decimal("0.02")).quantize(Decimal(".01")),
            cogs=units * Decimal("3.50" if index % 5 else "8.90"),
            shipping=units * Decimal("0.30"),
            inbound_freight=units * Decimal("0.45"),
            referral_fees=(revenue * Decimal("0.15")).quantize(Decimal(".01")),
            fulfillment_fees=units * Decimal("3.60"),
            storage_fees=Decimal(12 + index * 2),
            advertising_spend=(revenue * Decimal("0.30" if index % 4 == 0 else "0.12")).quantize(
                Decimal(".01")
            ),
            advertising_attributed_sales=(revenue * Decimal("0.40")).quantize(Decimal(".01")),
            inventory_on_hand=20 if index % 6 == 0 else (1500 if index % 7 == 0 else 240 + index * 10),
            lead_time_days=21 + index % 4 * 7,
            historical_daily_sales_velocity=(Decimal(units) / 30).quantize(Decimal(".0001")),
        ).model_dump(mode="json")
        if index == 22:
            row["cogs"] = None  # Deliberate unknown, not zero.
        if index == 23:
            row["advertising_attributed_sales"] = "0"
            row["advertising_spend"] = "0"
            row["historical_daily_sales_velocity"] = "0"
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


def write_synthetic(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(generate_csv())
