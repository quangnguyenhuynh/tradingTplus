"""Deprecated legacy signal MVP entrypoint.

The former implementation depended on removed legacy feature columns. It remains
importable but deliberately performs no database query or signal generation.
"""


def run_signal_engine(target_date=None):
    raise RuntimeError(
        "Legacy signal MVP is disabled: its rules depend on feature columns removed by "
        "20260729_drop_legacy_feature_columns.sql. Redesign against the canonical contract first."
    )
