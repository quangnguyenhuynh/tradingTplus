"""Idempotent persistence boundary and approval gate."""

from __future__ import annotations

from typing import Protocol


class SignalRepository(Protocol):
    def strategy_status(self, strategy_code: str, version: int, config_hash: str) -> str | None: ...
    def upsert_setup(self, record: dict) -> dict: ...
    def upsert_signal(self, record: dict) -> dict: ...
    def signal_exists(self, strategy_code: str, version: int, config_hash: str, symbol: str, signal_session: str) -> bool: ...


def write_setup(repository: SignalRepository, record: dict) -> dict:
    return repository.upsert_setup(record)


def write_live_signal(repository: SignalRepository, strategy, record: dict) -> dict:
    status = repository.strategy_status(strategy.strategy_code, strategy.version, strategy.config_hash)
    if status != "approved":
        raise PermissionError(f"Strategy {strategy.strategy_code}/{strategy.version} is not approved")
    return repository.upsert_signal(record)
