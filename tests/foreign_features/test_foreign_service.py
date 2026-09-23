from datetime import date, timedelta
from types import SimpleNamespace

from src.foreign_features import loader, persistence, service


class Query:
    def __init__(self, rows):
        self.rows = list(rows); self.filters = []; self.orders = []; self.start = None; self.end = None; self.cap = None
    def select(self, *args, **kwargs): return self
    def in_(self, field, values): self.filters.append(("in", field, set(values))); return self
    def eq(self, field, value): self.filters.append(("eq", field, value)); return self
    def gte(self, field, value): self.filters.append(("gte", field, value)); return self
    def lte(self, field, value): self.filters.append(("lte", field, value)); return self
    def lt(self, field, value): self.filters.append(("lt", field, value)); return self
    def gt(self, field, value): self.filters.append(("gt", field, value)); return self
    def order(self, field, desc=False): self.orders.append((field, desc)); return self
    def range(self, start, end): self.start = start; self.end = end; return self
    def limit(self, value): self.cap = value; return self
    def execute(self):
        rows = self.rows
        for op, field, value in self.filters:
            if op == "in": rows = [r for r in rows if r.get(field) in value]
            elif op == "eq": rows = [r for r in rows if r.get(field) == value]
            elif op == "gte": rows = [r for r in rows if str(r.get(field)) >= value]
            elif op == "lte": rows = [r for r in rows if str(r.get(field)) <= value]
            elif op == "lt": rows = [r for r in rows if str(r.get(field)) < value]
            elif op == "gt": rows = [r for r in rows if str(r.get(field)) > value]
        for field, desc in reversed(self.orders): rows = sorted(rows, key=lambda r: str(r.get(field)), reverse=desc)
        if self.cap is not None: rows = rows[:self.cap]
        if self.start is not None: rows = rows[self.start:self.end + 1]
        return SimpleNamespace(data=rows)


class DB:
    def __init__(self, rows, symbols=("SSI",), existing=None):
        self.tables = {"stock_daily": list(rows), "stock_foreign_features_daily": list(existing or [])}
        self.symbols = list(symbols); self.writes = []; self.client = self
    def get_symbols(self): return self.symbols
    def table(self, name): return Query(self.tables[name])
    def _with_retry(self, fn, **kwargs): return fn()
    def _upsert_in_batches(self, table, rows, **kwargs): self.writes.append((table, rows, kwargs))


def dates(count, start=date(2026, 7, 1)):
    return [(start + timedelta(days=i * 2)).isoformat() for i in range(count)]


def row(day, symbol="SSI", buy=2, sell=1, turnover=10):
    return {"symbol": symbol, "trading_date": day, "foreign_buy_val_total": buy,
            "foreign_sell_val_total": sell, "net_foreign_val": buy-sell,
            "total_traded_value": turnover, "foreign_buy_vol_total": buy,
            "foreign_sell_vol_total": sell, "net_foreign_vol": buy-sell}


def ddmmyyyy(iso): return date.fromisoformat(iso).strftime("%d/%m/%Y")


def test_preview_show_source_ignores_deprecated_calendar_and_check_is_read_only(tmp_path):
    ds = dates(20); db = DB([row(d) for d in ds])
    missing = tmp_path / "does-not-exist.json"
    preview = service.preview(ddmmyyyy(ds[-1]), "SSI", str(missing), show_source=True, db=db)
    assert preview["status"] == "OK" and len(preview["rows"][0]["source_rows"]) == 20
    assert preview["warnings"][0].startswith("DEPRECATED_CALENDAR_FILE_IGNORED")
    checked = service.check(ddmmyyyy(ds[-1]), ddmmyyyy(ds[-1]), ["SSI"], db=db)
    assert checked["status"] == "PARTIAL" and checked["missing_features"] == 1
    assert db.writes == []


def test_target_without_own_source_does_not_use_other_symbol_or_write():
    target = "2026-08-28"
    db = DB([row(target, "HPG")], symbols=("SSI", "HPG"))
    result = service.run_daily("28/08/2026", ["SSI"], dry_run=False, db=db)
    assert result["errors"] == [{"symbol": "SSI", "date": target, "reason": "NO_SOURCE_FOR_DATE"}]
    assert result["written"] == 0 and db.writes == []


def test_multi_symbol_backfill_has_per_symbol_warmup_and_only_range_outputs():
    ssi = dates(24); hpg = dates(24, start=date(2026, 7, 2))
    db = DB([row(d, "SSI") for d in ssi] + [row(d, "HPG") for d in hpg], symbols=("SSI", "HPG"))
    start, end = ssi[20], ssi[22]
    result = service.run_backfill(ddmmyyyy(start), ddmmyyyy(end), ["SSI", "HPG"], dry_run=True, db=db)
    assert result["dry_run"] is True and result["written"] == 0 and db.writes == []
    assert all(start <= item["trading_date"] <= end for item in result["rows"])
    assert result["affected_after_range"]["dates_by_symbol"]["SSI"] == ssi[23:24]
    ssi_row = next(item for item in result["rows"] if item["symbol"] == "SSI" and item["trading_date"] == start)
    assert ssi_row["net_value_20d"] == "20"


def test_recalculation_invalid_metric_is_explicit_null_on_upsert():
    ds = dates(20); rows = [row(d) for d in ds]; rows[-1]["foreign_buy_val_total"] = None
    db = DB(rows)
    result = service.run_daily(ddmmyyyy(ds[-1]), ["SSI"], db=db)
    assert result["written"] == 1
    written = db.writes[0][1][0]
    assert "activity_value_5d" in written and written["activity_value_5d"] is None


def test_source_and_existing_loaders_page_without_truncation(monkeypatch):
    monkeypatch.setattr(loader, "PAGE_SIZE", 2); monkeypatch.setattr(persistence, "PAGE_SIZE", 2)
    ds = dates(5); source = [row(d) for d in ds]
    existing = [{"symbol": "SSI", "trading_date": d, "formula_version": 2, "source_fingerprint": str(i)} for i, d in enumerate(ds)]
    db = DB(source, existing=existing)
    assert len(loader.load_rows(db, ["SSI"], ds[0], ds[-1], warmup_rows=0)) == 5
    assert len(persistence.load_existing(db, ["SSI"], ds[0], ds[-1])) == 5
