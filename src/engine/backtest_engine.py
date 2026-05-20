"""Backtest engine placeholder.

File này tách riêng để sau này triển khai pipeline backtest.
Hiện tại chưa có logic backtest chính thức trong repo.
"""


def run_backtest_engine(*args, **kwargs):
    """Entry point tạm cho backtest.

    Trả về thông báo rõ ràng để tránh hiểu nhầm rằng backtest đã được triển khai.
    """
    raise NotImplementedError(
        "Backtest engine chưa được triển khai. "
        "Hiện repo mới có ingest -> feature -> signal."
    )


if __name__ == "__main__":
    run_backtest_engine()
