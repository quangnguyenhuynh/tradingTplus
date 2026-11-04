"""Real PostgreSQL, plus the application's exact JSON text RPC transport."""
import json
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
import pytest
from test_stock_daily_v1_postgres import db,SAMPLE
from src.database.client import SupabaseClient
from src.contracts.numeric import exact_json_dumps,exact_json_loads
from src.contracts.registry import get_contract
from src.providers.ssi.adapters.v3 import SSIV3Adapter
from src.providers.ssi.clients.rest_v3 import PageResult
from src.ingest.stock_daily.daily_service import fetch_daily_for_symbol_with_clients
from src.ingest.index_daily.index_daily_service import fetch_index_daily_with_clients
from src.quality.daily_numeric_diagnostics import inspect_daily_numeric
from src.quality.validators.stock_daily_v1 import validate_payload
import runpy
INDEX=runpy.run_path('tests/ingest/test_index_daily_pipeline.py')['V3_PAYLOAD']

@pytest.fixture
def daily_db(db):
 c,s,old_call=db
 columns=['index_code text not null','trading_date date not null']+[f'{f} numeric' for f in get_contract('index_daily')['fields'] if f not in ('index_code','trading_date')]
 c.execute(f'create table {s}.index_daily('+','.join(columns)+',primary key(index_code,trading_date))')
 c.execute(f'''create table {s}.index_raw_daily(index_code text not null,trading_date date not null,data_hash text not null,
 payload jsonb not null,source text not null,created_at timestamptz not null,fetched_at timestamptz,
 unique(index_code,trading_date,data_hash))''')
 calls=[]
 class RPC:
  def rpc(self,name,params):
   assert name in ('persist_stock_daily_numeric_v1','persist_daily_raw_numeric_v1','persist_index_daily_numeric_v1','read_daily_numeric_scope_v1')
   # Model the SDK's JSON request body: all exact documents are text values,
   # so ordinary JSON encoders never have to convert a Decimal to float.
   params=json.loads(json.dumps(params));calls.append((name,deepcopy(params)))
   def execute():
    query=f'select {s}.{name}('+','.join(k+' => %s' for k in params)+')'
    data=c.execute(query,tuple(params.values())).fetchone()[0]
    return SimpleNamespace(data=data)
   return SimpleNamespace(execute=execute)
 app_db=object.__new__(SupabaseClient);app_db.client=RPC()
 yield c,s,app_db,calls


def stock_ingest(app_db,value,**changes):
 payload={**SAMPLE,'totalMatchValue':value,**changes}
 client=SimpleNamespace(securities_summary=lambda *_:PageResult([payload],1,[]))
 result=fetch_daily_for_symbol_with_clients(SSIV3Adapter(client),app_db,'SSI','01/10/2026')
 return result,payload


def index_ingest(app_db,**changes):
 payload={**INDEX,**changes}
 client=SimpleNamespace(index_summary=lambda *_:PageResult([payload],1,[]))
 return fetch_index_daily_with_clients(SSIV3Adapter(client),app_db,'VNINDEX','25/08/2026')

@pytest.mark.parametrize('amount',['162662895000.001','303651874999.999','506132139999.992','478199435000.012',
 '9007199254740993','123456789012345678901234567890.000000000123456789'])
def test_stock_exact_pipeline_roundtrip_raw_and_clean(daily_db,amount):
 c,s,app,calls=daily_db
 result,payload=stock_ingest(app,Decimal(amount))
 assert result['daily_rows']==1 and result['status'] in ('OK','PARTIAL')
 assert c.execute(f"select total_match_val from {s}.stock_daily where symbol='SSI'").fetchone()==(Decimal(amount),)
 assert c.execute(f"select jsonb_typeof(payload->'totalMatchValue'),payload->>'totalMatchValue' from {s}.stock_raw_daily").fetchone()==('number',str(Decimal(amount)))
 created=c.execute(f"select created_at from {s}.stock_daily where symbol='SSI'").fetchone()[0]
 raw_audit=c.execute(f'select created_at,fetched_at from {s}.stock_raw_daily').fetchone()
 result2,_=stock_ingest(app,Decimal(amount))
 assert result2['daily_rows']==1
 assert c.execute(f"select created_at from {s}.stock_daily where symbol='SSI'").fetchone()[0]==created
 assert c.execute(f'select count(*) from {s}.stock_raw_daily').fetchone()==(1,)
 assert c.execute(f'select created_at,fetched_at from {s}.stock_raw_daily').fetchone()==raw_audit
 assert c.execute(f'select count(*) from {s}.stock_data_quality_logs').fetchone()[0]<=1


def test_rpc_retains_valid_prior_fractional_money_and_exact_derived(daily_db):
 c,s,app,calls=daily_db
 c.execute(f"insert into {s}.stock_daily(symbol,trading_date,total_deal_val) values('SSI','2026-10-01',12.345)")
 result,_=stock_ingest(app,'9007199254740993.001',totalDealValue=None)
 assert result['status']=='PARTIAL'
 assert c.execute(f"select total_deal_val,total_traded_value from {s}.stock_daily where symbol='SSI'").fetchone()==(Decimal('12.345'),Decimal('9007199254741005.346'))
 details=c.execute(f'select details from {s}.stock_data_quality_logs').fetchone()[0]
 assert 'total_deal_val' in details['preserved_fields']
 assert any(i['field']=='total_deal_val' and i['action']=='KEEP_EXISTING_FIELD' for i in details['issues'])


def test_monetary_warning_cannot_downgrade_valid(daily_db):
 c,s,app,calls=daily_db
 assert stock_ingest(app,'100')[0]['status']=='OK'
 result,_=stock_ingest(app,'100.001')
 assert result['status']=='FAILED' and 'CLEAN_VALID_DOWNGRADE_BLOCKED' in result['errors']
 assert c.execute(f"select total_match_val,validation_status from {s}.stock_daily where symbol='SSI'").fetchone()==(Decimal('100'),'VALID')


def test_new_policy_archives_old_rejection_and_is_idempotent(daily_db):
 c,s,app,calls=daily_db
 from src.ingest.stock_daily.daily_mapper import build_raw_daily_record
 payload={**SAMPLE,'totalMatchValue':'100.001'}
 raw=build_raw_daily_record('SSI','01/10/2026',payload)
 app.upsert_raw_daily([raw])
 old=dict(policy_version='stock_daily_validation_v1.0.0',mapping_version='2.0.0',contract_version='2.0.0',
          decision='REJECTED',issues=[dict(field='total_match_val',code='TRANSFORM_ERROR',severity='ERROR',action='REJECT',message='Old integer-only monetary policy')])
 app.persist_stock_daily_validation_v1('SSI','2026-10-01',raw['data_hash'],None,old)
 assert c.execute(f"select count(*) from {s}.stock_daily where symbol='SSI'").fetchone()==(0,)
 stock_ingest(app,'100.001');stock_ingest(app,'100.001')
 details=c.execute(f'select details from {s}.stock_data_quality_logs').fetchone()[0]
 assert details['policy_version']=='stock_daily_validation_v1.1.0'
 assert details['history'][0]['policy_version']=='stock_daily_validation_v1.0.0'
 assert details['history'][0]['decision']=='REJECTED'
 assert details['decision']=='PARTIAL'
 assert len(details['history'])==1


def test_index_signed_decimal_pipeline_and_retained_optional(daily_db):
 c,s,app,calls=daily_db
 result=index_ingest(app,totalBuyForeignValue='0.1',totalSellForeignValue='1978131345916.2',netPurchasesForeignValue='-1978131345916.1')
 assert result['status']=='OK'
 assert c.execute(f'select net_foreign_purchase_value from {s}.index_daily').fetchone()==(Decimal('-1978131345916.1'),)
 result=index_ingest(app,totalBuyForeignValue=None,totalSellForeignValue='1978131345916.2',netPurchasesForeignValue='-1978131345916.1')
 assert result['status']=='PARTIAL'
 assert c.execute(f'select total_foreign_buy_value from {s}.index_daily').fetchone()==(Decimal('0.1'),)
 assert result['persistence_reports'][0]['preserved_fields']==['total_foreign_buy_value']

@pytest.mark.parametrize('changes',[{'totalAdvanceStock':'1.5'},{'totalTradeValue':'-0.1'},{'indexValue':'0'},{'indexCode':'VN30'},{'tradingDate':'2026/08/26'}])
def test_rejected_index_attempt_never_overwrites_clean(daily_db,changes):
 c,s,app,calls=daily_db
 assert index_ingest(app)['status']=='OK'
 result=index_ingest(app,**changes)
 assert result['status']=='FAILED' and result['clean_rows']==0
 assert c.execute(f'select index_value from {s}.index_daily').fetchone()==(Decimal('1280.50'),)


def test_index_readback_failure_rolls_back_clean_raw_remains(daily_db):
 c,s,app,calls=daily_db
 c.execute(f'create function {s}.skip_insert() returns trigger language plpgsql as $$ begin return null; end $$')
 c.execute(f'create trigger skip_insert before insert on {s}.index_daily for each row execute function {s}.skip_insert()')
 result=index_ingest(app)
 assert result['status']=='FAILED' and result['persistence_failures']==1
 assert c.execute(f'select count(*) from {s}.index_daily').fetchone()==(0,)
 assert c.execute(f'select count(*) from {s}.index_raw_daily').fetchone()==(1,)


def test_raw_conflicting_hash_cannot_modify_original(daily_db):
 c,s,app,calls=daily_db
 stock_ingest(app,'100.001')
 params=next(p for n,p in calls if n=='persist_daily_raw_numeric_v1')
 rows=exact_json_loads(params['p_rows_json']);rows[0]['payload']['totalMatchValue']='999'
 with pytest.raises(Exception,match='RAW immutable readback mismatch'):
  app.upsert_raw_daily(rows)
 assert c.execute(f"select payload->>'totalMatchValue' from {s}.stock_raw_daily").fetchone()==('100.001',)


def test_exact_diagnostic_replays_and_case_comparison_no_writes(daily_db):
 c,s,app,calls=daily_db
 stock_ingest(app,Decimal('9007199254740993.123456789'))
 before=c.execute(f'select count(*) from {s}.stock_data_quality_logs').fetchone()
 report=inspect_daily_numeric('stock_daily',['SSI'],'01/10/2026',client=app.client)
 assert report['mode']=='READ_ONLY' and any(i['code']=='VALID_FRACTIONAL_MONETARY_VALUE' for r in report['records'] for i in r['observations'])
 assert not any(i['code']=='RAW_CLEAN_VALUE_MISMATCH' for r in report['records'] for i in r['observations'])
 assert c.execute(f'select count(*) from {s}.stock_data_quality_logs').fetchone()==before
 index_ingest(app)
 c.execute(f"update {s}.index_raw_daily set index_code='VNIndex'")
 calls.clear()
 report=inspect_daily_numeric('index_daily',['VNINDEX'],'25/08/2026',client=app.client)
 assert all(n=='read_daily_numeric_scope_v1' for n,_ in calls)
 assert report['records'][0]['clean_present'] and report['records'][0]['raw_identity']=='VNIndex'
 assert not any(i['code']=='RAW_ONLY' for r in report['records'] for i in r['observations'])
 assert report['quality_log_available'] is False


def test_rpc_security_and_read_only_volatility(daily_db):
 c,s,app,calls=daily_db
 rows=c.execute("select proname,prosecdef,provolatile,has_function_privilege('anon',p.oid,'execute'),has_function_privilege('authenticated',p.oid,'execute'),has_function_privilege('service_role',p.oid,'execute') from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname=%s and proname in ('persist_daily_raw_numeric_v1','persist_stock_daily_numeric_v1','persist_index_daily_numeric_v1','read_daily_numeric_scope_v1')",(s,)).fetchall()
 assert len(rows)==4 and all(row[1] is False and row[3:]==(False,False,True) for row in rows)
 assert next(r for r in rows if r[0]=='read_daily_numeric_scope_v1')[2]=='s'


def test_index_merge_discloses_new_component_inconsistency(daily_db):
 c,s,app,calls=daily_db
 assert index_ingest(app)['status']=='OK'
 c.execute(f'update {s}.index_daily set total_deal_value=12.345')
 result=index_ingest(app,totalDealValue=None)
 assert result['status']=='PARTIAL'
 issues=result['persistence_reports'][0]['merge_issues']
 assert any(i['field']=='total_trade_value' and i['code']=='INDEX_TOTAL_COMPONENT_MISMATCH' and i['expected_value']=='912.345' for i in issues)


def test_equivalent_numeric_raw_versions_do_not_claim_unique_previous_hash(daily_db):
 from src.ingest.stock_daily.daily_mapper import build_raw_daily_record
 c,s,app,calls=daily_db
 stock_ingest(app,Decimal('100.001'))
 second={**SAMPLE,'totalMatchValue':Decimal('100.0010')}
 app.upsert_raw_daily([build_raw_daily_record('SSI','01/10/2026',second)])
 stock_ingest(app,Decimal('100.001'))
 details=c.execute(f'select details from {s}.stock_data_quality_logs').fetchone()[0]
 assert details['previous_clean_raw_hash'] is None and details['previous_clean_raw_hash_match_count']==2
 assert c.execute(f'select count(*) from {s}.stock_raw_daily').fetchone()==(2,)


def test_index_raw_source_collision_fails_without_overwriting_legacy(daily_db):
 from src.ingest.index_daily.index_daily_mapper import build_index_raw_daily_record
 from psycopg.types.json import Jsonb
 c,s,app,calls=daily_db
 raw=build_index_raw_daily_record('VNINDEX','25/08/2026',INDEX)
 c.execute(f"insert into {s}.index_raw_daily(index_code,trading_date,data_hash,payload,source,created_at) values('VNINDEX','2026-08-25',%s,%s,'SSI_DailyIndex','2026-01-01Z')",(raw['data_hash'],Jsonb(INDEX)))
 result=index_ingest(app)
 assert result['status']=='FAILED' and result['persistence_failures']==1
 assert c.execute(f'select source from {s}.index_raw_daily').fetchone()==('SSI_DailyIndex',)
 assert c.execute(f'select count(*) from {s}.index_daily').fetchone()==(0,)
