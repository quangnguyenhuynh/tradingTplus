"""Exercise the actual installed PostgREST SDK encoder with an HTTP mock."""
from decimal import Decimal
import json
import httpx
from postgrest import SyncPostgrestClient
import pytest
from src.database.client import SupabaseClient
from src.contracts.numeric import exact_json_loads


def client_with_response(response):
 requests=[]
 def handle(request):
  requests.append((request.url.path,json.loads(request.content)))
  return httpx.Response(200,json=response)
 http=httpx.Client(transport=httpx.MockTransport(handle))
 db=object.__new__(SupabaseClient)
 db.client=SyncPostgrestClient('https://numeric.test/rest/v1',http_client=http)
 return db,requests,http


def test_actual_sdk_stock_rpc_transports_json_number_tokens_inside_text():
 db,calls,http=client_with_response(dict(decision='PARTIAL',clean_rows=1,issue_count=1,raw_hash='HASH',atomic=True))
 try:
  amount=Decimal('9007199254740993.1234567890123456789')
  db.persist_stock_daily_validation_v1('TCB','2025-03-12','HASH',
      {'total_match_val':amount,'raw':{'number':amount,'string':str(amount)}},{'decision':'PARTIAL'})
  assert calls[0][0].endswith('/rpc/persist_stock_daily_numeric_v1')
  params=calls[0][1];assert isinstance(params['p_candidate_json'],str)
  candidate=exact_json_loads(params['p_candidate_json'])
  assert candidate['total_match_val']==candidate['raw']['number']==amount
  assert candidate['raw']['string']==str(amount)
 finally:http.close()


def test_actual_sdk_raw_rpc_keeps_numeric_and_string_raw_semantics():
 db,calls,http=client_with_response(dict(rows_verified=1,immutable=True,exact=True))
 try:
  raw={'symbol':'TCB','trading_date':'2025-03-12','source':'ssi_v3','data_hash':'a'*64,
       'payload':{'number':Decimal('303651874999.999'),'string':'303651874999.999'}}
  db.upsert_raw_daily([raw])
  params=calls[0][1];row=exact_json_loads(params['p_rows_json'])[0]
  assert row['payload']['number']==Decimal('303651874999.999')
  assert row['payload']['string']=='303651874999.999'
  assert 'created_at' in row and 'fetched_at' in row
  assert 'created_at' not in raw
 finally:http.close()


def test_actual_sdk_index_rpc_keeps_signed_decimals():
 db,calls,http=client_with_response(dict(decision='VALID',clean_rows=1,raw_hash='HASH',exact=True))
 try:
  amount=Decimal('-1978131345916.1')
  db.persist_index_daily_numeric_v1('VNINDEX','2026-07-28','HASH',{'net_foreign_purchase_value':amount},{'decision':'VALID'})
  assert exact_json_loads(calls[0][1]['p_candidate_json'])['net_foreign_purchase_value']==amount
 finally:http.close()

@pytest.mark.parametrize('reply',[{},dict(rows_verified=True,immutable=True,exact=True),
 dict(rows_verified=0,immutable=True,exact=True),dict(rows_verified=1,immutable=True,exact=False)])
def test_raw_ack_fails_closed_and_is_not_retried(reply):
 db,calls,http=client_with_response(reply)
 try:
  with pytest.raises(RuntimeError):db.upsert_raw_daily([{'payload':{}}])
  assert len(calls)==1
 finally:http.close()


def test_actual_sdk_read_rpc_returns_exact_json_text():
 from src.quality.daily_numeric_diagnostics import read_exact_scope
 amount=Decimal('9007199254740993.123456789')
 text='{"available":true,"total":1,"rows":[{"symbol":"TCB","trading_date":"2025-03-12","total_match_val":'+str(amount)+'}]}'
 db,calls,http=client_with_response(text)
 try:
  rows,available=read_exact_scope(db.client,'stock_daily','clean',['TCB'],'2025-03-12','2025-03-12')
  assert available and rows[0]['total_match_val']==amount
  assert calls[0][0].endswith('/rpc/read_daily_numeric_scope_v1')
 finally:http.close()
