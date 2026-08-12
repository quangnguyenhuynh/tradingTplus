from datetime import date

import pytest

from src.analogs.runtime import feature_trading_session


def test_feature_time_uses_timezone_aware_vietnam_trading_session():
    assert feature_trading_session("2026-01-04T18:00:00+00:00") == date(2026, 1, 5)
    with pytest.raises(ValueError, match="timezone-aware"):
        feature_trading_session("2026-01-05T01:00:00")
