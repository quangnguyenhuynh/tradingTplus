from copy import deepcopy
from decimal import Decimal,localcontext
import json
import runpy
import pytest
from src.contracts.transforms import to_decimal,to_exact_int,to_int,TransformError
from src.contracts.numeric import exact_json_dumps,exact_json_loads,exact_binary
from src.contracts.engine import map_record
from src.quality.validators.stock_daily_v1 import validate_payload
from src.quality.validators.index_daily_numeric import validate_index_payload
from src.quality.validators.index_daily_validator import validate_index_daily_record
from src.ingest.stock_daily.daily_mapper import build_raw_daily_record
from src.providers.ssi.clients.rest_v3 import SSIV3Client

STOCK=runpy.run_path('tests/data_sources/test_ssi_v3_stock_daily.py')['SAMPLE']
INDEX=runpy.run_path('tests/ingest/test_index_daily_pipeline.py')['V3_PAYLOAD']

@pytest.mark.parametrize('value',['162662895000.001','303651874999.999','506132139999.992','478199435000.012',
 '9007199254740993','-1978131345916.1','123456789012345678901234567890.000000000123456789'])
def test_decimal_parse_and_json_number_tokens_exact(value):
 number=to_decimal(value,{})
 assert number==Decimal(value)
 encoded=exact_json_dumps({'n':number,'raw':value})
 assert ':"'+value+'"' in encoded and exact_json_loads(encoded)['n']==number
 assert isinstance(exact_json_loads(encoded)['n'],(Decimal,int))

@pytest.mark.parametrize('value',[True,False,'NaN','Infinity','-Infinity',float('nan'),float('inf'),'1_000','bad',{},None])
def test_bad_decimal_rejected(value):
 with pytest.raises(TransformError):to_decimal(value,{})

@pytest.mark.parametrize('value',['9007199254740993.001','1.5',True,'NaN','Infinity'])
def test_discrete_values_not_rounded(value):
 with pytest.raises(TransformError):to_exact_int(value,{})
 assert to_exact_int('9007199254740993',{})==9007199254740993

@pytest.mark.parametrize('symbol,date,amount',[('BID','2025/03/12','162662895000.001'),('TCB','2025/03/12','303651874999.999'),('VCB','2025/03/12','506132139999.992'),('TCB','2025/04/29','478199435000.012')])
def test_stock_confirmed_fraction_shape_preserved_with_warning(symbol,date,amount):
 raw={**STOCK,'symbol':symbol,'tradingDate':date,'totalMatchValue':amount};before=deepcopy(raw)
 candidate,report=validate_payload(raw,symbol,date)
 assert candidate['total_match_val']==Decimal(amount) and report['decision']=='PARTIAL'
 assert candidate['total_traded_value']==exact_binary(Decimal(amount),Decimal(STOCK['totalDealValue']))
 assert any(i['field']=='total_match_val' and i['code']=='FRACTIONAL_MONETARY_VALUE' for i in report['issues'])
 assert raw==before and not any(i['code']=='TRANSFORM_ERROR' for i in report['issues'])


def test_all_stock_money_and_derived_values_exact_under_small_context():
 raw={**STOCK,'totalMatchValue':'123456789012345678901234567890.001','totalDealValue':'.002',
      'totalForeignBuyValue':'.001','totalForeignSellValue':'123456789012345678901234567890.003'}
 with localcontext() as ctx:
  ctx.prec=4
  candidate,report=validate_payload(raw,'SSI','01/10/2026')
 assert candidate['total_traded_value']==Decimal('123456789012345678901234567890.003')
 assert candidate['net_foreign_val']==Decimal('-123456789012345678901234567890.002')
 assert report['decision']=='PARTIAL'


def test_exact_alias_conflict_and_equal_decimals():
 raw={**STOCK,'remainForeignRoom':'9007199254740992','foreignRoom':'9007199254740993'}
 assert validate_payload(raw,'SSI','01/10/2026')[0] is None
 same=map_record('ssi_v3','stock_daily',{'summary.symbol':'SSI','summary.tradingDate':'2026-10-01','summary.average':'10.000','summary.averagePrice':10})
 assert same.candidate['average_price']==Decimal('10')


def test_raw_hash_compatibility_for_existing_string_payloads():
 import hashlib
 expected=hashlib.sha256(json.dumps(STOCK,sort_keys=True).encode()).hexdigest()
 assert build_raw_daily_record('SSI','01/10/2026',STOCK)['data_hash']==expected
 assert exact_json_loads(exact_json_dumps({'x':Decimal('0.123456789012345678901')}))['x']==Decimal('0.123456789012345678901')


def test_daily_http_decoder_uses_bytes_not_float():
 class Response:
  status_code=200
  content=b'{"data":[{"totalMatchValue":9007199254740993.123456789}]}'
  def json(self):pytest.fail('Daily decode must not call default JSON float decoder')
 class Session:
  def request(self,*a,**kw):return Response()
 client=SSIV3Client(Session());client.token='test'
 body=client._request('GET','/data/securitiesSummary')
 assert body['data'][0]['totalMatchValue']==Decimal('9007199254740993.123456789')

@pytest.mark.parametrize('field,value',[('totalAdvanceStock','1.5'),('totalTrade','2.1'),('totalMatchValue','-0.1'),('indexValue','0'),('indexValue',None),('indexCode','VN30'),('tradingDate','2026/08/26')])
def test_index_core_quantity_sign_scope_strict(field,value):
 candidate,report=validate_index_payload({**INDEX,field:value},'VNINDEX','25/08/2026')
 assert candidate is None and report['decision']=='REJECTED'


def test_index_money_signed_net_and_case_only_identity():
 raw={**INDEX,'indexCode':'VNIndex','totalBuyForeignValue':'0.1',
      'totalSellForeignValue':'1978131345916.2','netPurchasesForeignValue':'-1978131345916.1'}
 candidate,report=validate_index_payload(raw,'VNINDEX','25/08/2026')
 assert candidate['net_foreign_purchase_value']==Decimal('-1978131345916.1')
 assert report['decision']=='VALID'


def test_index_large_money_consistency_has_no_relative_tolerance():
 record={'index_code':'VNINDEX','trading_date':'2026-08-25','index_value':Decimal('1234.56789'),
 'total_match_value':Decimal('100000000000000000000.1'),'total_deal_value':Decimal('0.2'),
 'total_trade_value':Decimal('100000000000000000000.301')}
 result=validate_index_daily_record(record)
 assert [i.code for i in result.warnings]==['INDEX_TOTAL_COMPONENT_MISMATCH']
 record['total_trade_value']=Decimal('100000000000000000000.3')
 assert validate_index_daily_record(record).warnings==[]


def test_predecoded_float_is_explicitly_unverified_not_claimed_exact():
 candidate,report=validate_payload({**STOCK,'open':20150.0},'SSI','01/10/2026')
 assert candidate['open_price']==Decimal('20150.0') and report['decision']=='PARTIAL'
 assert any(i['code']=='PREDECODED_FLOAT_PRECISION_UNVERIFIED' and i['field']=='open_price' for i in report['issues'])
 candidate,report=validate_index_payload({**INDEX,'indexValue':1280.5},'VNINDEX','25/08/2026')
 assert candidate['index_value']==Decimal('1280.5') and report['decision']=='VALID_WITH_WARNINGS'
 assert report['predecoded_float_fields']==['index_value']
