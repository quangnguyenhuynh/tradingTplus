import json
from types import SimpleNamespace
from src.foreign_features import service

class Query:
    def __init__(self, rows): self.rows=rows; self.start=0; self.end=999
    def select(self,*a,**k): return self
    def in_(self,*a): return self
    def gte(self,*a): return self
    def lte(self,*a): return self
    def order(self,*a,**k): return self
    def range(self,a,b): self.start=a; self.end=b; return self
    def execute(self): return SimpleNamespace(data=self.rows[self.start:self.end+1])
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

def test_unknown_calendar_never_writes():
    db=DB([]); result=service.run_daily("20/08/2026",["SSI"],None,db=db)
    assert result["status"] == "PARTIAL" and result["window_unverified"] == 1 and db.writes == []
