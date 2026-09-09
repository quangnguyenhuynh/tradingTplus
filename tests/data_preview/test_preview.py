import json
from types import SimpleNamespace
import pytest
from src.data_contracts import get_contract, get_mapping, map_record
from src.data_preview.service import run_preview, render_preview
from src.ssi.v3 import SSIV3Client, SSIReadError

class FakeV3:
 def securities_summary(self,s,d):return SimpleNamespace(items=[{'symbol':s,'tradingDate':d,'open':30000,'high':31000,'low':29500,'close':30500,'foreignBuyVolume':10,'foreignSellVolume':15}],raw_pages=[{'data':'summary'}],pages=1)
 def masterdata(self,d):return SimpleNamespace(items=[{'symbol':'SSI','tradingDate':d,'reference':29900,'ceiling':32000,'floor':28000}],raw_pages=[{'data':'master'}],pages=1)
 def ohlc_1m(self,s,d):return SimpleNamespace(items=[{'time':d+' 09:01:00','open':30,'high':31,'low':29,'close':30.5,'volume':100,'value':999}],raw_pages=[{'data':'ohlc'}],pages=1)
 def index_summary(self,i,d):return SimpleNamespace(items=[{'tradingDate':d,'indexValue':1200,'totalTrade':12345}],raw_pages=[{'data':'index'}],pages=1)

def test_v3_mapping_all_datasets_and_canonical_fields():
 for ds,code in [('stock_daily','SSI'),('stock_intraday','SSI'),('index_daily','VNINDEX')]:
  out=run_preview(ds,code,'2026-09-08',client=FakeV3())
  assert out['status']=='OK'
  assert set(out['records'][0]['canonical'])==set(get_contract(ds)['fields'])
 assert run_preview('stock_intraday','SSI','2026-09-08',client=FakeV3())['records'][0]['canonical']['value']==3050

def test_trace_status_raw_unchanged_and_safe_semantics():
 out=run_preview('stock_daily','SSI','2026-09-08',client=FakeV3())
 row=out['records'][0]; trace={x['field']:x for x in row['fields']}
 assert trace['net_foreign_vol']['status']=='DERIVED' and row['canonical']['net_foreign_vol']==-5
 assert trace['close_price_adjusted']['status']=='UNSUPPORTED'
 assert row['canonical']['total_buy_trade'] is None and row['canonical']['total_traded_vol'] is None
 assert out['raw']['securitiesSummary']==[{'data':'summary'}]

def test_missing_foreign_side_is_not_zero():
 class Missing(FakeV3):
  def securities_summary(self,s,d):
   x=super().securities_summary(s,d);del x.items[0]['foreignSellVolume'];return x
 out=run_preview('stock_daily','SSI','2026-09-08',client=Missing())
 assert out['records'][0]['canonical']['net_foreign_vol'] is None

def test_intraday_bad_or_wrong_date_timestamp_invalid():
 class Bad(FakeV3):
  def ohlc_1m(self,s,d):return SimpleNamespace(items=[{'time':'2026-09-09 09:00:00','volume':1}],raw_pages=[],pages=1)
 out=run_preview('stock_intraday','SSI','2026-09-08',client=Bad())
 assert out['status']=='INVALID'
 assert next(x for x in out['records'][0]['fields'] if x['field']=='time')['status']=='INVALID'

def test_index_request_context_and_conflict():
 assert run_preview('index_daily','VNINDEX','2026-09-08',client=FakeV3())['records'][0]['canonical']['index_code']=='VNINDEX'
 class Conflict(FakeV3):
  def index_summary(self,i,d):return SimpleNamespace(items=[{'index':'HNXINDEX'}],raw_pages=[],pages=1)
 with pytest.raises(SSIReadError):run_preview('index_daily','VNINDEX','2026-09-08',client=Conflict())

def test_json_and_comparison_missing_source():
 one=run_preview('stock_daily','SSI','2026-09-08',client=FakeV3())
 assert json.loads(render_preview(one,'json'))['source']=='ssi_v3'
 assert 'raw' not in json.loads(render_preview(one,'json'))

def test_v2_regression_mapping_unchanged():
 payload={'Time':'09:00:00','Open':1,'High':2,'Low':1,'Close':2,'Volume':3}
 assert map_record('ssi_v2','stock_intraday',payload,{'symbol':'SSI','date':'08/09/2026','value':6}).candidate['time']=='2026-09-08T02:00:00Z'

def test_v3_declarations_cover_contract_and_do_not_map_trade_count():
 for ds in ('stock_daily','stock_intraday','index_daily'):
  assert set(get_mapping('ssi_v3',ds)['fields'])==set(get_contract(ds)['fields'])
 assert get_mapping('ssi_v3','index_daily')['fields']['total_trade']['unsupported']
