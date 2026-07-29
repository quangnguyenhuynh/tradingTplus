"""Daily feature calculation and source-isolated execution."""
from .common import compute_daily_features


def run_daily_features_with_summary(*args, **kwargs):
    from .runner import run_daily_features_with_summary as run
    return run(*args, **kwargs)
