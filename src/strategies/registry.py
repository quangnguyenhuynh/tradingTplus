from .breakout_v1 import BreakoutV1
from .pullback_v1 import PullbackV1

_STRATEGIES = {(item.strategy_code, item.version): item for item in (BreakoutV1(), PullbackV1())}


def get_strategy(strategy_code: str, version: int = 1):
    try:
        return _STRATEGIES[(strategy_code.upper(), int(version))]
    except KeyError as exc:
        raise ValueError(f"Unknown strategy/version: {strategy_code}/{version}") from exc


def list_strategies():
    return tuple(_STRATEGIES[key] for key in sorted(_STRATEGIES))
