"""Phase 1 same-symbol EOD Historical Analog analysis."""

from .core import build_dimensions, match_snapshot, resolve_outcomes
from .profile import AnalogProfile, config_hash, load_profile, validate_profile

__all__ = [
    "AnalogProfile",
    "build_dimensions",
    "config_hash",
    "load_profile",
    "match_snapshot",
    "resolve_outcomes",
    "validate_profile",
]
