import json
from types import SimpleNamespace
from src.foreign_features import service

class Query:
    def __init__(self, rows):
        self.rows=rows; self.start=0; self.end=999; self.start_date=None; self.end_date=None; self.symbols=None
    def select(self,*a,**k): return self
    def in_(self,column,values):
        if column=="symbol": self.symbols=set(values)
        return self
    def gte(self,column,value):
        if column=="trading_date": self.start_date=value
        return self
    def lte(self,column,value):
        if column=="trading_date": self.end_date=value
        return self
    def order(self,*a,**k): return self
    def range(self,a,b): self.start=a; self.end=b; return self
    def execute(self):
        rows=list(self.rows)
        if self.symbols is not None:
            rows=[r for r in rows if r.get("symbol") in self.symbols]
        if self.start_date is not None:
            rows=[r for r in rows if str(r.get("trading_date"))>=self.start_date]
        if self.end_date is not None:
            rows=[r for r in rows if str(r.get("trading_date"))<=self.end_date]
        return SimpleNamespace(data=rows[self.start:self.end+1])
class DB:
    def __init__(self,rows): self.rows=rows; self.writes=[]; self.client=self
    def get_symbols(self): return ["SSI"]
    def table(self,name): return Query(self.rows if name=="stock_daily" else [])
    def _with_retry(self,fn,**kw): return fn()
    def _upsert_in_batches(self,*args,**kwargs): self.writes.append((args,kwargs))

def test_preview_and_check_are_read_only(tmp_path):
    sessions=[f"2026-08-{i:02d}" for i in range(1,21)]
    path=tmp_path/"cal.json"; path.write_text(json.dumps({"source":"test fixture","market":"HOSE","sessions":sessions}))
    rows=[{"symbol":"SSI","trading_date":d,"foreign_buy_val_total":2,"foreign_sell_val_total":1,"net_foreign_val":1,"total_traded_value":10,"foreign_buy_vol_total":2,"foreign_sell_vol_total":1,"net_foreign_vol":1} for d in sessions]
    db=DB(rows)
    assert service.preview("20/08/2026","SSI",str(path),db=db)["status"] == "OK"
    checked=service.check("20/08/2026","20/08/2026",["SSI"],str(path),db=db)
    assert checked["status"] == "PARTIAL" and checked["missing_features"] == 1
    assert db.writes == []

def test_missing_stock_daily_calendar_never_writes():
    db=DB([]); result=service.run_daily("20/08/2026",["SSI"],None,db=db)
    assert result["status"] == "PARTIAL" and result["window_unverified"] == 1 and db.writes == []


def test_missing_calendar_file_infers_sessions_from_stock_daily_and_writes():
    sessions=[f"2026-08-{i:02d}" for i in range(1,21)]
    rows=[{"symbol":"SSI","trading_date":d,"foreign_buy_val_total":2,"foreign_sell_val_total":1,"net_foreign_val":1,"total_traded_value":10,"foreign_buy_vol_total":2,"foreign_sell_vol_total":1,"net_foreign_vol":1} for d in sessions]
    db=DB(rows)
    result=service.run_daily("20/08/2026",["SSI"],None,db=db)
    assert result["status"] == "OK"
    assert result["calendar_source"] == "stock_daily"
    assert len(db.writes) == 1
    assert db.writes[0][0][1][0]["trading_date"] == "2026-08-20"


def test_stock_daily_calendar_uses_market_dates_to_expose_missing_symbol_source():
    sessions=[f"2026-08-{i:02d}" for i in range(1,21)]
    rows=[{"symbol":"HPG","trading_date":d,"foreign_buy_val_total":2,"foreign_sell_val_total":1,"net_foreign_val":1,"total_traded_value":10,"foreign_buy_vol_total":2,"foreign_sell_vol_total":1,"net_foreign_vol":1} for d in sessions]
    rows.extend({"symbol":"SSI","trading_date":d,"foreign_buy_val_total":2,"foreign_sell_val_total":1,"net_foreign_val":1,"total_traded_value":10,"foreign_buy_vol_total":2,"foreign_sell_vol_total":1,"net_foreign_vol":1} for d in sessions if d!="2026-08-18")
    db=DB(rows)
    result=service.preview("20/08/2026","SSI",None,db=db)
    assert result["status"] == "PARTIAL"
    assert result["rows"][0]["quality_status"]["5"]["status"] == "MISSING_SOURCE"
