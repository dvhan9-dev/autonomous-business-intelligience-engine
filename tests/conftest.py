from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from amazon_audit.schemas.seller import SellerRow
from api.app import create_app


@pytest.fixture
def seller_row():
    return SellerRow(
        sku="TEST-001",
        asin="SYN0000001",
        product_name="Synthetic Test",
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        units_sold=100,
        selling_price=Decimal("20"),
        discounts=Decimal("100"),
        refunds=Decimal("50"),
        cogs=Decimal("500"),
        shipping=Decimal("30"),
        inbound_freight=Decimal("20"),
        referral_fees=Decimal("300"),
        fulfillment_fees=Decimal("350"),
        storage_fees=Decimal("25"),
        advertising_spend=Decimal("200"),
        advertising_attributed_sales=Decimal("800"),
        inventory_on_hand=30,
        lead_time_days=15,
        historical_daily_sales_velocity=Decimal("3"),
    )


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'api.db'}", max_upload_bytes=20000)) as test_client:
        yield test_client
