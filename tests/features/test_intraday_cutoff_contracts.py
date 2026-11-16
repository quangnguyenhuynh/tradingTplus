"""Intraday cutoff, timezone-equivalence, and bar-start contract regressions.

These cases cover contract edges that the existing feature tests do not
already assert:

* a bucket becomes eligible only once its configured Vietnam-session close is
  reached, so the exact cutoff instant is inclusive while one second earlier is
  not (including the still-open 1m candle at ``as_of``);
* UTC and ``Asia/Ho_Chi_Minh`` representations of the same instant select the
  same buckets, for both raw source rows and aggregated output;
* aggregated buckets are labelled with their Vietnam bucket start, not with the
  first observed candle;
* a cutoff scoped to one Vietnam trading date keeps prior-date warm-up buckets
  but never admits buckets from the next Vietnam date.

Fixtures are synthetic and in-memory; no SSI, Supabase, or database access is
used.
"""

import socket

import pandas as pd
import pytest

from src.features.stock.intraday import aggregate_timeframe, filter_closed_buckets


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def _deny(*_args, **_kwargs):
        raise AssertionError(
            "network access is not permitted in intraday cutoff contract tests"
        )

    monkeypatch.setattr(socket.socket, "connect", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)


def _candle(timestamp: str, close: float = 10.0) -> dict:
    return {
        "time": timestamp,
        "open": close,
        "high": close + 0.2,
        "low": close - 0.2,
        "close": close,
        "volume": 100,
        "value": close * 100,
    }


@pytest.mark.parametrize(
    ("timeframe", "bucket_start_vn", "cutoff_vn", "expected_closed"),
    [
        pytest.param(
            "1m",
            "2026-05-20T14:29:00+07:00",
            "2026-05-20T14:30:00+07:00",
            True,
            id="1m-exact-close",
        ),
        pytest.param(
            "1m",
            "2026-05-20T14:29:00+07:00",
            "2026-05-20T14:29:59+07:00",
            False,
            id="1m-second-before-close",
        ),
        pytest.param(
            "1m",
            "2026-05-20T14:30:00+07:00",
            "2026-05-20T14:30:00+07:00",
            False,
            id="1m-open-candle-at-cutoff",
        ),
        pytest.param(
            "5m",
            "2026-05-20T09:30:00+07:00",
            "2026-05-20T09:35:00+07:00",
            True,
            id="5m-exact-close",
        ),
        pytest.param(
            "5m",
            "2026-05-20T09:30:00+07:00",
            "2026-05-20T09:34:59+07:00",
            False,
            id="5m-second-before-close",
        ),
        pytest.param(
            "15m",
            "2026-05-20T09:00:00+07:00",
            "2026-05-20T09:15:00+07:00",
            True,
            id="15m-exact-close",
        ),
        pytest.param(
            "15m",
            "2026-05-20T09:00:00+07:00",
            "2026-05-20T09:14:59+07:00",
            False,
            id="15m-second-before-close",
        ),
        pytest.param(
            "60m",
            "2026-05-20T09:00:00+07:00",
            "2026-05-20T10:00:00+07:00",
            True,
            id="60m-exact-close",
        ),
        pytest.param(
            "60m",
            "2026-05-20T09:00:00+07:00",
            "2026-05-20T09:59:59+07:00",
            False,
            id="60m-second-before-close",
        ),
    ],
)
def test_cutoff_closes_bucket_only_once_its_configured_close_is_reached(
    timeframe,
    bucket_start_vn,
    cutoff_vn,
    expected_closed,
):
    frame = pd.DataFrame([_candle(bucket_start_vn)])

    result = filter_closed_buckets(frame, timeframe, pd.Timestamp(cutoff_vn))

    assert (len(result) == 1) is expected_closed
    if expected_closed:
        assert pd.Timestamp(result.iloc[0]["time"]) == pd.Timestamp(bucket_start_vn)


def test_utc_and_vietnam_cutoff_representations_select_the_same_closed_buckets():
    vn_starts = [
        "2026-05-20T09:01:00+07:00",
        "2026-05-20T09:04:00+07:00",
        "2026-05-20T09:16:00+07:00",
    ]
    frame_vn = pd.DataFrame([_candle(value) for value in vn_starts])
    frame_utc = pd.DataFrame(
        [
            _candle(pd.Timestamp(value).tz_convert("UTC").isoformat())
            for value in vn_starts
        ]
    )

    aggregated_vn = aggregate_timeframe(frame_vn, "15m")
    aggregated_utc = aggregate_timeframe(frame_utc, "15m")

    pd.testing.assert_frame_equal(aggregated_vn, aggregated_utc)
    assert str(aggregated_vn["time"].dt.tz) == "UTC"

    cutoffs = (
        pd.Timestamp("2026-05-20T02:15:00Z"),
        pd.Timestamp("2026-05-20T09:15:00+07:00"),
    )
    baseline = None
    for frame in (aggregated_vn, aggregated_utc):
        for cutoff in cutoffs:
            kept = filter_closed_buckets(frame, "15m", cutoff)["time"].tolist()
            if baseline is None:
                baseline = kept
            assert kept == baseline

    assert baseline == [pd.Timestamp("2026-05-20T02:00:00Z")]


@pytest.mark.parametrize(
    ("timeframe", "candle_starts_vn", "expected_bucket_starts_utc"),
    [
        pytest.param(
            "5m",
            ("09:01", "09:02", "09:04", "09:06"),
            ("2026-05-20T02:00:00Z", "2026-05-20T02:05:00Z"),
            id="5m-left-labels",
        ),
        pytest.param(
            "15m",
            ("09:01", "09:14", "09:16"),
            ("2026-05-20T02:00:00Z", "2026-05-20T02:15:00Z"),
            id="15m-left-labels",
        ),
        pytest.param(
            "60m",
            ("10:31", "10:59"),
            ("2026-05-20T03:00:00Z",),
            id="60m-left-labels",
        ),
    ],
)
def test_aggregated_bucket_time_is_the_vietnam_bar_start(
    timeframe,
    candle_starts_vn,
    expected_bucket_starts_utc,
):
    frame = pd.DataFrame(
        [_candle(f"2026-05-20T{value}:00+07:00") for value in candle_starts_vn]
    )

    aggregated = aggregate_timeframe(frame, timeframe)

    assert aggregated["time"].tolist() == [
        pd.Timestamp(value) for value in expected_bucket_starts_utc
    ]
    assert aggregated["time"].iloc[0] < pd.Timestamp(
        f"2026-05-20T{candle_starts_vn[0]}:00+07:00"
    )


def test_cutoff_on_prior_trading_date_never_closes_next_date_buckets():
    frame = pd.DataFrame(
        [
            _candle("2026-05-20T14:30:00+07:00"),
            _candle("2026-05-20T14:45:00+07:00"),
            _candle("2026-05-21T09:00:00+07:00"),
        ]
    )

    result = filter_closed_buckets(
        frame,
        "15m",
        pd.Timestamp("2026-05-20T15:00:00+07:00"),
    )

    assert [pd.Timestamp(value) for value in result["time"]] == [
        pd.Timestamp("2026-05-20T07:30:00Z"),
        pd.Timestamp("2026-05-20T07:45:00Z"),
    ]


def test_cutoff_keeps_prior_date_warmup_but_drops_open_current_date_bucket():
    frame = pd.DataFrame(
        [
            _candle("2026-05-19T09:00:00+07:00"),
            _candle("2026-05-19T14:45:00+07:00"),
            _candle("2026-05-20T09:45:00+07:00"),
            _candle("2026-05-20T10:00:00+07:00"),
        ]
    )

    result = filter_closed_buckets(
        frame,
        "15m",
        pd.Timestamp("2026-05-20T10:00:00+07:00"),
    )

    assert [pd.Timestamp(value) for value in result["time"]] == [
        pd.Timestamp("2026-05-19T02:00:00Z"),
        pd.Timestamp("2026-05-19T07:45:00Z"),
        pd.Timestamp("2026-05-20T02:45:00Z"),
    ]
