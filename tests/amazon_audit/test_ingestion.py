import csv
import io

import pytest

from amazon_audit.ingestion.csv_import import InvalidDataset, import_csv
from amazon_audit.schemas.seller import SellerRow
from amazon_audit.synthetic import generate_csv


def csv_bytes(records, headers=None):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers or list(SellerRow.model_fields))
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue().encode()


def test_synthetic_data_is_reproducible_and_preserves_missing_zero():
    assert generate_csv() == generate_csv()
    rows = import_csv(generate_csv())
    assert len(rows) == 24
    assert rows[22].cogs is None
    assert rows[23].advertising_spend == 0
    assert rows[23].advertising_attributed_sales == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("units_sold", "1.5"),
        ("units_sold", "-1"),
        ("cogs", "NaN"),
        ("selling_price", "Infinity"),
        ("advertising_spend", "-1"),
        ("period_end", "2020-01-01"),
        ("asin", "invalid"),
        ("sku", "../../escape"),
        ("discounts", "9999999"),
        ("inventory_on_hand", "1.1"),
    ],
)
def test_rejects_invalid_fields_without_echoing_record(seller_row, field, value):
    row = seller_row.model_dump(mode="json")
    row.update({field: value, "product_name": "SECRET PRODUCT"})
    with pytest.raises(InvalidDataset) as failure:
        import_csv(csv_bytes([row]))
    assert "SECRET PRODUCT" not in str(failure.value)


def test_duplicates_and_mixed_periods_rejected(seller_row):
    row = seller_row.model_dump(mode="json")
    with pytest.raises(InvalidDataset, match="Duplicate SKU"):
        import_csv(csv_bytes([row, row]))
    other = {**row, "sku": "OTHER", "period_start": "2026-09-02"}
    with pytest.raises(InvalidDataset, match="single analysis period"):
        import_csv(csv_bytes([row, other]))


@pytest.mark.parametrize("content", [b"", b"sku,sku\n1,2\n", b"\xff", b"\x00", b'"unclosed'])
def test_rejects_malformed_csv(content):
    with pytest.raises(InvalidDataset):
        import_csv(content)


def test_limits_and_extra_columns(seller_row):
    content = generate_csv()
    with pytest.raises(InvalidDataset, match="limit"):
        import_csv(content, max_bytes=10)
    row = seller_row.model_dump(mode="json")
    row["unexpected"] = "value"
    with pytest.raises(InvalidDataset, match="headers"):
        import_csv(csv_bytes([row], list(row)))


def test_header_order_bom_and_whitespace_normalization(seller_row):
    row = seller_row.model_dump(mode="json")
    row["sku"] = " TEST-001 "
    content = b"\xef\xbb\xbf" + csv_bytes([row], list(reversed(row)))
    assert import_csv(content)[0].sku == "TEST-001"


def test_row_limit(monkeypatch):
    monkeypatch.setattr("amazon_audit.ingestion.csv_import.MAX_ROWS", 20)
    with pytest.raises(InvalidDataset, match="too many rows"):
        import_csv(generate_csv())
