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


def latest_weekday_on_or_before(reference: date | datetime | None = None) -> date:
    """Return reference date if weekday, otherwise the closest prior weekday.

    This is a calendar helper only; it must not be treated as proof that the
    returned date was an exchange trading day. SSI payload validation decides
    whether market data exists for the date.
    """
    if reference is None:
        current = today_vn()
    elif isinstance(reference, datetime):
        current = reference.astimezone(VN_TZ).date() if reference.tzinfo else reference.date()
    else:
        current = reference
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def parse_ddmmyyyy(value: str) -> ValidatedDate:
    try:
        parsed = datetime.strptime(value, "%d/%m/%Y").date()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Date must use DD/MM/YYYY format, got: {value!r}") from exc
    return ValidatedDate(raw=value, date=parsed)


def trading_date_iso(value: str) -> str | None:
    """Return an ISO date for a SSI ``DD/MM/YYYY`` request value."""
    try:
        return parse_ddmmyyyy(value).iso
    except (TypeError, ValueError):
        return None


def parse_iso_date(value: str) -> ValidatedDate:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Date must use YYYY-MM-DD format, got: {value!r}") from exc
    return ValidatedDate(raw=value, date=parsed)


def parse_index_date(value: str) -> ValidatedDate:
    """Parse either documented date format used by the index CLI commands."""
    for date_format in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return ValidatedDate(raw=value, date=datetime.strptime(value, date_format).date())
        except (TypeError, ValueError):
            continue
    raise ValueError(f"Date must use YYYY-MM-DD or DD/MM/YYYY format, got: {value!r}")


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
