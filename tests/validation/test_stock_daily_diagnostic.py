"""Read-only persisted-data diagnostics cannot call SSI or mutate DB state."""
from copy import deepcopy
from types import SimpleNamespace
import runpy
import pytest
from src.quality.stock_daily_diagnostics import inspect_daily
from src.ingest.stock_daily.daily_mapper import build_raw_daily_record
from src.cli import main
SAMPLE=runpy.run_path('tests/data_sources/test_ssi_v3_stock_daily.py')['SAMPLE']

class Client:
 def __init__(self):
  self.raw=[build_raw_daily_record('SSI','01/10/2026',{**SAMPLE,'remainForeignRoom':-1})]
  self.clean=[];self.calls=[]
 def table(self,table):
  assert table in ('stock_raw_daily','stock_daily');self.current=table;self.calls.append(table);return self
 def select(self,*a,**k):return self
 def in_(self,*a):return self
 def gte(self,*a):return self
 def lte(self,*a):return self
 def order(self,*a):return self
 def range(self,*a):return self
 def execute(self):
  rows=self.raw if self.current=='stock_raw_daily' else self.clean
  return SimpleNamespace(data=deepcopy(rows),count=len(rows))

def test_raw_clean_missing_policy_error_counts_and_no_mutation():
 client=Client();before=deepcopy(client.raw)
 report=inspect_daily(['SSI'],'01/10/2026',missing_only=True,client=client)
 assert client.calls==['stock_raw_daily','stock_daily'] and client.raw==before
 row=report['records'][0]
 assert row['policy_report']['decision']=='PARTIAL' and row['clean_present'] is False
 assert row['historical_failure']=='UNDETERMINED_RAW_ONLY'
 assert any(e['field']=='foreign_remaining_room' and e['code']=='BELOW_MINIMUM' for e in report['issues_by_field_code'])
 client.clean=[{'symbol':'SSI','trading_date':'2026-10-01','validation_status':None}]
 assert inspect_daily(['SSI'],'01/10/2026',missing_only=True,client=client)['records']==[]
 assert inspect_daily(['SSI'],'01/10/2026',client=client)['records'][0]['stored_validation_status'] is None

@pytest.mark.parametrize('argv',[['--symbols','SSI','--from','01/10/2026'],['--symbols','SSI','--date','01/10/2026','--to','02/10/2026'],['--date','01/10/2026']])
def test_cli_invalid_scope_before_db(argv):
 assert main(['stock-eod-quality',*argv])==2

def test_cli_real_route_readonly(monkeypatch,capsys):
 client=Client()
 monkeypatch.setattr('src.database.client.SupabaseClient',lambda:SimpleNamespace(get=lambda:client))
 assert main(['stock-eod-quality','--symbols','SSI','--date','01/10/2026','--raw-clean-missing'])==0
 assert 'READ_ONLY' in capsys.readouterr().out

@pytest.mark.parametrize('start,end',[('2026-10-02','2026-10-01'),('2026-01-01','2026-03-01')])
def test_bounded_date_scope(start,end):
 with pytest.raises(ValueError):inspect_daily(['SSI'],start,end,client=Client())

def test_database_errors_do_not_expose_sensitive_messages(monkeypatch,capsys):
 def fail(*a,**k):raise RuntimeError('secret-token')
 monkeypatch.setattr('src.quality.stock_daily_diagnostics.inspect_daily',fail)
 assert main(['stock-eod-quality','--symbols','SSI','--date','01/10/2026'])==1
 out=capsys.readouterr()
 assert 'secret-token' not in out.out+out.err and 'DIAGNOSTIC_DB_READ_FAILED' in out.out
