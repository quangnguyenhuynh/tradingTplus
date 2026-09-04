from datetime import date

import pytest

from src.pipeline import index_daily
from src.pipeline.date_utils import latest_weekday_on_or_before


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        (date(2026, 9, 4), date(2026, 9, 4)),
        (date(2026, 9, 7), date(2026, 9, 7)),
        (date(2026, 9, 5), date(2026, 9, 4)),
        (date(2026, 9, 6), date(2026, 9, 4)),
    ],
)
def test_latest_weekday_on_or_before(reference, expected):
    assert latest_weekday_on_or_before(reference) == expected


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (date(2026, 9, 4), "04/09/2026"),
        (date(2026, 9, 7), "07/09/2026"),
        (date(2026, 9, 5), "04/09/2026"),
        (date(2026, 9, 6), "04/09/2026"),
    ],
)
def test_index_daily_default_date_uses_weekday_on_or_before(monkeypatch, current, expected):
    monkeypatch.setattr(
        index_daily,
        "latest_weekday_on_or_before",
        lambda: latest_weekday_on_or_before(current),
    )
    assert index_daily._resolve_index_daily_date(None) == expected


@pytest.mark.parametrize("value", ["03/09/2026", "2026-09-03"])
def test_index_daily_explicit_date_formats_are_preserved(value):
    assert index_daily._resolve_index_daily_date(value) == "03/09/2026"
