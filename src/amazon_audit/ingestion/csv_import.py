import csv
import io

import pandas as pd
from pydantic import ValidationError

from amazon_audit.schemas.seller import SellerRow

MAX_ROWS = 10_000
DEFAULT_MAX_BYTES = 2_097_152


class InvalidDataset(ValueError):
    """Messages contain field/row references only, never seller values."""


def import_csv(content: bytes, max_bytes: int = DEFAULT_MAX_BYTES) -> list[SellerRow]:
    if not content or len(content) > max_bytes:
        raise InvalidDataset("CSV is empty or exceeds the upload limit")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidDataset("CSV must use UTF-8 encoding") from exc
    if "\x00" in text:
        raise InvalidDataset("CSV contains invalid null bytes")
    try:
        reader = csv.reader(io.StringIO(text), strict=True)
        headers = next(reader)
        if headers != list(SellerRow.model_fields):
            # Order can vary; duplicate names cannot silently overwrite each other.
            if len(headers) != len(set(headers)) or set(headers) != set(SellerRow.model_fields):
                raise InvalidDataset("CSV headers must match the documented normalized schema exactly")
        count = 0
        for count, row in enumerate(reader, start=1):
            if count > MAX_ROWS or len(row) != len(headers):
                raise InvalidDataset("CSV has too many rows or inconsistent field counts")
        if count == 0:
            raise InvalidDataset("CSV contains no product rows")
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, skip_blank_lines=False)
    except (csv.Error, StopIteration, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise InvalidDataset("Malformed CSV") from exc
    records = []
    for number, raw in enumerate(frame.to_dict(orient="records"), start=2):
        normalized = {key: value.strip() if value.strip() else None for key, value in raw.items()}
        try:
            records.append(SellerRow.model_validate(normalized))
        except ValidationError as exc:
            fields = sorted({str(error["loc"][0]) if error["loc"] else "row" for error in exc.errors()})
            raise InvalidDataset(f"Invalid fields at CSV row {number}: {', '.join(fields)}") from exc
    if len({row.sku for row in records}) != len(records):
        raise InvalidDataset("Duplicate SKU: supply one aggregated row per SKU")
    if len({(row.period_start, row.period_end) for row in records}) != 1:
        raise InvalidDataset("All rows must share a single analysis period")
    return records
