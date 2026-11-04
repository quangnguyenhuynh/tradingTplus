from decimal import Decimal
from types import SimpleNamespace
import runpy
import pytest
from src.contracts.numeric import exact_json_dumps
from src.quality.daily_numeric_diagnostics import inspect_daily_numeric
from src.cli import main
STOCK=runpy.run_path('tests/data_sources/test_ssi_v3_stock_daily.py')['SAMPLE']
INDEX=runpy.run_path('tests/ingest/test_index_daily_pipeline.py')['V3_PAYLOAD']

class ReadOnly:
 def __init__(self,raw,clean=(),logs=(),index=False):self.rows={'raw':list(raw),'clean':list(clean),'issues':list(logs)};self.calls=[];self.index=index
 def rpc(self,name,params):
  assert name=='read_daily_numeric_scope_v1','Write RPC forbidden'
  self.calls.append((name,params));rows=self.rows[params['p_kind']]
  page=rows[params['p_offset']:params['p_offset']+params['p_limit']]
  return SimpleNamespace(execute=lambda:SimpleNamespace(data=exact_json_dumps(dict(available=not(self.index and params['p_kind']=='issues'),rows=page,total=len(rows)))))


def raw_stock(payload=STOCK,hash='a'):
 return dict(symbol='SSI',trading_date='2026-10-01',source='ssi_v3',data_hash=hash,payload=payload)


def observations(result):return [i for r in result['records'] for i in r['observations']]


def test_read_only_exact_decimal_replay_and_current_history():
 raw=raw_stock({**STOCK,'totalMatchValue':Decimal('303651874999.999')})
 clean=dict(symbol='SSI',trading_date='2026-10-01',total_match_val=Decimal('303651874999.998'),validation_status=None)
 logs=[dict(symbol='SSI',trading_date='2026-10-01',check_name='stock_daily_validation_v1',status='RESOLVED',
            details=dict(policy_version='stock_daily_validation_v1.1.0',history=[dict(policy_version='stock_daily_validation_v1.0.0',decision='REJECTED')]))]
 client=ReadOnly([raw],[clean],logs)
 result=inspect_daily_numeric('stock_daily',['SSI'],'01/10/2026',client=client)
 assert any(i['code']=='RAW_CLEAN_VALUE_MISMATCH' and i['raw_value']=='303651874999.999' for i in observations(result))
 assert result['records'][0]['current_quality_state']=='RESOLVED'
 assert result['records'][0]['quality_history'][0]['decision']=='REJECTED'
 assert len(client.calls)==3 and all(n=='read_daily_numeric_scope_v1' for n,_ in client.calls)


def test_raw_only_clean_only_and_nonintegral_classification():
 client=ReadOnly([raw_stock({**STOCK,'totalMatch':'1.5'})],
     [dict(symbol='SSI',trading_date='2026-10-02',validation_status=None)])
 report=inspect_daily_numeric('stock_daily',['SSI'],'01/10/2026','02/10/2026',client=client)
 codes={i['code'] for i in observations(report)}
 assert {'RAW_ONLY','CLEAN_ONLY','NONINTEGRAL_DISCRETE_QUANTITY','VALIDATION_REJECTED'}<=codes


def test_index_case_and_legacy_source_not_false_missing():
 rows=[dict(index_code='VNIndex',trading_date='2026-08-25',source='SSI_DailyIndex',data_hash='a',payload={}),
       dict(index_code='VNINDEX',trading_date='2026-08-25',source='SSI_v3_indexSummary',data_hash='b',payload=INDEX)]
 report=inspect_daily_numeric('index_daily',['VNINDEX'],'25/08/2026',client=ReadOnly(rows,[dict(index_code='VNINDEX',trading_date='2026-08-25',index_value=Decimal('1280.50'))],index=True))
 codes={i['code'] for i in observations(report)}
 assert 'CASE_VARIANT_IDENTITY' in codes and 'UNSUPPORTED_RAW_PROVENANCE' in codes and 'RAW_ONLY' not in codes
 assert report['quality_log_available'] is False


def test_stable_pagination_over_one_page():
 rows=[raw_stock(hash=str(n)) for n in range(101)]
 client=ReadOnly(rows)
 report=inspect_daily_numeric('stock_daily',['SSI'],'01/10/2026',client=client)
 assert report['raw_records']==101 and len(client.calls)==4
 assert [p['p_offset'] for _,p in client.calls if p['p_kind']=='raw']==[0,100]

@pytest.mark.parametrize('ids,start,end',[([], '01/10/2026',None),(['SSI'],'02/10/2026','01/10/2026'),(['SSI'],'01/01/2026','01/03/2026')])
def test_bad_scope_before_database(ids,start,end):
 client=ReadOnly([])
 with pytest.raises(ValueError):inspect_daily_numeric('stock_daily',ids,start,end,client=client)
 assert client.calls==[]


def test_cli_routes_and_suppresses_db_exception(monkeypatch,capsys):
 import src.cli.quality as handler
 def fail(*a,**k):raise RuntimeError('secret configuration')
 monkeypatch.setattr(handler,'inspect_daily_numeric',fail)
 assert main(['daily-numeric-quality','--dataset','stock_daily','--identifiers','SSI','--date','01/10/2026'])==1
 assert 'secret' not in capsys.readouterr().out
 assert main(['daily-numeric-quality','--dataset','index_daily','--identifiers','VNINDEX','--from','01/10/2026'])==2


def test_cap_fails_before_unbounded_reads():
 client=ReadOnly([])
 client.rpc=lambda *a,**k:SimpleNamespace(execute=lambda:SimpleNamespace(data='{"available":true,"rows":[],"total":10001}'))
 with pytest.raises(ValueError,match='cap'):inspect_daily_numeric('stock_daily',['SSI'],'01/10/2026',client=client)

@pytest.mark.parametrize('mode',['changed_count','duplicate'])
def test_pagination_fails_closed_on_changed_count_or_duplicate(mode):
 rows=[raw_stock(hash=str(n)) for n in range(100)]
 class Faulty:
  def rpc(self,name,params):
   offset=params['p_offset']
   page=rows if offset==0 else [rows[0]]
   count=100 if offset and mode=='changed_count' else 101
   return SimpleNamespace(execute=lambda:SimpleNamespace(data=exact_json_dumps(dict(available=True,total=count,rows=page))))
 with pytest.raises(RuntimeError):inspect_daily_numeric('stock_daily',['SSI'],'01/10/2026',client=Faulty())


def test_old_persisted_rejection_is_distinct_from_new_read_only_replay():
 raw=raw_stock({**STOCK,'totalMatchValue':'303651874999.999'})
 issue=dict(field='total_match_val',code='TRANSFORM_ERROR',action='REJECT')
 log=dict(symbol='SSI',trading_date='2026-10-01',check_name='stock_daily_validation_v1',status='ACTIVE',
          details=dict(policy_version='stock_daily_validation_v1.0.0',mapping_version='2.0.0',contract_version='2.0.0',
                       decision='REJECTED',issues=[issue],raw_hash='old-attempt'))
 client=ReadOnly([raw],logs=[log])
 row=inspect_daily_numeric('stock_daily',['SSI'],'01/10/2026',client=client)['records'][0]
 assert row['replay_decision']=='PARTIAL' and row['persisted_decision']=='REJECTED'
 assert row['persisted_mapping_version']=='2.0.0' and row['mapping_version']=='3.0.0'
 assert row['current_quality_raw_hash']=='old-attempt' and row['persisted_issues']==[issue]
 assert all(name=='read_daily_numeric_scope_v1' for name,_ in client.calls)
