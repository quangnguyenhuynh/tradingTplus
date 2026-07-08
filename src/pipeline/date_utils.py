from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

VN_TZ = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class ValidatedDate:
    raw: str
    date: date

    @property
    def ddmmyyyy(self) -> str:
        return self.date.strftime("%d/%m/%Y")

    @property
    def iso(self) -> str:
        return self.date.isoformat()

    @property
    def is_weekend(self) -> bool:
        return self.date.weekday() >= 5


def today_vn() -> date:
    return datetime.now(VN_TZ).date()


def latest_previous_weekday(reference: date | None = None) -> date:
    """Return the latest weekday strictly before reference (or before today in VN time)."""
    current = (reference or today_vn()) - timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def parse_ddmmyyyy(value: str) -> ValidatedDate:
    try:
        parsed = datetime.strptime(value, "%d/%m/%Y").date()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Date must use DD/MM/YYYY format, got: {value!r}") from exc
    return ValidatedDate(raw=value, date=parsed)


def parse_iso_date(value: str) -> ValidatedDate:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Date must use YYYY-MM-DD format, got: {value!r}") from exc
    return ValidatedDate(raw=value, date=parsed)


def validate_not_future(value: ValidatedDate, *, today: date | None = None) -> None:
    current = today or today_vn()
    if value.date > current:
        raise ValueError(f"Date {value.ddmmyyyy} is in the future relative to {current.isoformat()}")


def validate_not_weekend(value: ValidatedDate) -> None:
    if value.is_weekend:
        raise ValueError(f"Date {value.ddmmyyyy} is a weekend")


def validate_safe_write_date(value: ValidatedDate, *, force: bool = False, today: date | None = None) -> None:
    """Reject future/weekend write targets unless force=True."""
    if force:
        return
    validate_not_future(value, today=today)
    validate_not_weekend(value)
