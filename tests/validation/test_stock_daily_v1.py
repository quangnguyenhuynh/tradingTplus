"""Real v3 field-shape replay with illustrative TCB room=-1; not a live TCB payload."""
from copy import deepcopy
import runpy
import pytest
from src.quality.validators.stock_daily_v1 import validate_payload
from src.providers.ssi.adapters.v3 import SSIV3Adapter
from src.providers.ssi.clients.rest_v3 import PageResult
from src.ingest.stock_daily.daily_service import fetch_daily_for_symbol_with_clients
from src.ingest.stock_daily.daily_mapper import build_raw_daily_record

SAMPLE=runpy.run_path('tests/data_sources/test_ssi_v3_stock_daily.py')['SAMPLE']

def test_valid_no_issues_and_original_payload_unchanged():
 raw=deepcopy(SAMPLE);before=deepcopy(raw)
 clean,report=validate_payload(raw,'SSI','01/10/2026')
 assert clean['validation_status']==report['decision']=='VALID' and report['issues']==[]
 assert raw==before and clean['raw']==raw

@pytest.mark.parametrize('date',['2026/03/05','2026/03/06'])
def test_confirmed_tcb_failure_class_is_quarantined(date):
 raw={**SAMPLE,'symbol':'TCB','tradingDate':date,'remainForeignRoom':'-1'};before=deepcopy(raw)
 clean,report=validate_payload(raw,'TCB',date)
 assert clean['validation_status']=='PARTIAL' and clean['foreign_remaining_room'] is None
 assert clean['open_price']==float(raw['open']) and raw==before
 assert any(i['field']=='foreign_remaining_room' and i['code']=='BELOW_MINIMUM' and i['action']=='SET_NULL' for i in report['issues'])

@pytest.mark.parametrize('field,value',[('remainForeignRoom','broken'),('totalForeignBuy','bad'),('totalDeal','-2'),('average','NaN')])
def test_explicit_optional_recovery_only(field,value):
 clean,report=validate_payload({**SAMPLE,field:value},'SSI','01/10/2026')
 assert report['decision']=='PARTIAL' and clean is not None
 if field=='totalForeignBuy':assert clean['net_foreign_vol'] is None
 if field=='totalDeal':assert clean['total_traded_vol'] is None

@pytest.mark.parametrize('change',[
 {'open':None},{'high':'bad'},{'low':-1},{'close':0},{'high':1},
 {'totalMatch':-1},{'totalMatchValue':'invalid'},{'totalMatchValue':'-0.001'}, {'symbol':'TCB'},
 {'tradingDate':'2026/10/02'},{'foreignRoom':'123'}, {'foreignRoom':'invalid'}, {'FOREIGNROOM':'invalid'},
])
def test_core_scope_and_alias_conflicts_reject(change):
 clean,report=validate_payload({**SAMPLE,**change},'SSI','01/10/2026')
 assert clean is None and report['decision']=='REJECTED'
 assert any(i['action']=='REJECT' for i in report['issues'])

def test_nullable_core_match_is_partial_not_zero_or_no_trade_inference():
 clean,report=validate_payload({**SAMPLE,'totalMatch':None},'SSI','01/10/2026')
 assert report['decision']=='PARTIAL' and clean['total_match_vol'] is None and clean['total_traded_vol'] is None
 clean,report=validate_payload({**SAMPLE,'totalMatch':'0','totalMatchValue':'0'},'SSI','01/10/2026')
 assert clean['total_match_vol']==0 and report['decision']=='VALID'

class DB:
 def __init__(self):self.raw=[];self.calls=[]
 def upsert_raw_daily(self,rows):self.raw.extend(rows)
 def persist_stock_daily_validation_v1(self,symbol,date,raw_hash,clean,report):
  assert self.raw and self.raw[-1]['data_hash']==raw_hash
  self.calls.append((clean,report))
  return dict(decision=report['decision'],clean_rows=int(clean is not None),issue_count=len(report['issues']))

class Client:
 def __init__(self,rows):self.rows=rows
 def securities_summary(self,*a):return PageResult(self.rows,1,[])

@pytest.mark.parametrize('change,status',[({},'OK'),({'remainForeignRoom':-1},'PARTIAL'),({'open':None},'FAILED')])
def test_service_raw_first_and_reported_decision(change,status):
 db=DB();raw={**SAMPLE,**change}
 report=fetch_daily_for_symbol_with_clients(SSIV3Adapter(Client([raw])),db,'SSI','01/10/2026')
 assert report['status']==status and db.raw[0]['payload']==raw and len(db.calls)==1
 if status=='PARTIAL':assert report['partial_clean_writes']==1
 if status=='FAILED':assert report['rejected_records']==1

def test_quality_log_failure_is_not_success():
 db=DB()
 def failure(*a):raise RuntimeError('secret DB response')
 db.persist_stock_daily_validation_v1=failure
 report=fetch_daily_for_symbol_with_clients(SSIV3Adapter(Client([SAMPLE])),db,'SSI','01/10/2026')
 assert report['status']=='FAILED' and report['persistence_failures']==1 and report['daily_rows']==0
 assert 'secret' not in str(report)

def test_persistence_downgrade_error_is_reported_exactly():
 db=DB()
 def blocked(*args):
  report=args[-1]
  issues=report['issues']+[dict(field=None,code='CLEAN_VALID_DOWNGRADE_BLOCKED',
      severity='ERROR',action='KEEP_EXISTING_CLEAN',message='Existing VALID')]
  return dict(decision='REJECTED',clean_rows=0,issue_count=len(issues),issues=issues)
 db.persist_stock_daily_validation_v1=blocked
 report=fetch_daily_for_symbol_with_clients(SSIV3Adapter(Client([{**SAMPLE,'remainForeignRoom':-1}])),db,'SSI','01/10/2026')
 assert report['status']=='FAILED' and 'CLEAN_VALID_DOWNGRADE_BLOCKED' in report['errors']
 assert report['rejected_records']==1 and report['partial_clean_writes']==0 and report['mapping_failures']==1

def test_mapping_configuration_failure_retains_rejected_evidence(monkeypatch):
 from src.contracts.registry import MappingConfigurationError
 def fail(*a,**k):raise MappingConfigurationError('bad config')
 monkeypatch.setattr('src.quality.validators.stock_daily_v1.map_record',fail)
 candidate,report=validate_payload(SAMPLE,'SSI','01/10/2026')
 assert candidate is None and report['decision']=='REJECTED'
 assert report['issues'][0]['code']=='MAPPING_CONFIGURATION_ERROR'

def test_large_integer_precision_and_fractional_core_failure():
 clean,report=validate_payload({**SAMPLE,'totalMatch':'9007199254740993'},'SSI','01/10/2026')
 assert clean['total_match_vol']==9007199254740993
 clean,report=validate_payload({**SAMPLE,'totalMatch':'9007199254740993.5'},'SSI','01/10/2026')
 assert clean is None and report['decision']=='REJECTED'
 clean,report=validate_payload({**SAMPLE,'remainForeignRoom':'9007199254740992','foreignRoom':'9007199254740993'},'SSI','01/10/2026')
 assert clean is None and any(i['code']=='ALIAS_CONFLICT' for i in report['issues'])
