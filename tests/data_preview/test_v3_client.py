from types import SimpleNamespace
import pytest, requests
from src.ssi.v3 import SSIV3Client, SSIReadError
class Session:
 def __init__(self,responses):self.responses=list(responses);self.calls=[]
 def request(self,*a,**kw):self.calls.append((a,kw));r=self.responses.pop(0);return r
class Resp:
 def __init__(self,status,body):self.status_code=status;self.body=body
 def json(self):return self.body

def test_pagination_envelopes_and_empty_termination():
 s=Session([Resp(200,{'data':{'items':[{'x':1}]}}),Resp(200,{'items':[]})]);c=SSIV3Client(s,page_size=1);c.token='x';p=c.paged('/x',{})
 assert p.items==[{'x':1}] and p.pages==2

def test_pagination_loop_detected():
 s=Session([Resp(200,[{'x':1}]),Resp(200,[{'x':1}])]);c=SSIV3Client(s,page_size=1);c.token='x'
 with pytest.raises(SSIReadError,match='loop'):c.paged('/x',{})

def test_parameter_error_not_retried_and_server_error_bounded():
 s=Session([Resp(400,{}),Resp(200,{})]);c=SSIV3Client(s,max_attempts=3);c.token='x'
 with pytest.raises(SSIReadError):c._request('GET','/x')
 assert len(s.calls)==1
 s=Session([Resp(500,{})]*3);c=SSIV3Client(s,max_attempts=3);c.token='x'
 with pytest.raises(SSIReadError):c._request('GET','/x')
 assert len(s.calls)==3

def test_http_200_api_envelope_error_is_not_treated_as_empty_data():
 s=Session([Resp(200,{'code':'E_INVALID','msg':'bad request'})]);c=SSIV3Client(s);c.token='x'
 with pytest.raises(SSIReadError) as error:c._request('GET','/x',params={'symbol':'SSI'})
 message=str(error.value)
 assert "endpoint=GET /api/v3/x" in message
 assert "params={'symbol': 'SSI'}" in message
 assert "http_status=200" in message
 assert "api_code='E_INVALID'" in message and "api_msg='bad request'" in message


@pytest.mark.parametrize("day", ["08/09/2026", "2026-09-08"])
def test_securities_summary_normalizes_dates_and_builds_required_v3_params(day):
 s=Session([Resp(200,{'data':[]})]);c=SSIV3Client(s,page_size=10);c.token='x'
 c.securities_summary('SSI',day)
 _,kwargs=s.calls[0]
 assert kwargs['params']=={
  'symbol':'SSI','from':'2026/09/08','to':'2026/09/08',
  'pageIndex':1,'pageSize':10,
 }


def test_http_error_reports_sanitized_request_and_envelope():
 s=Session([Resp(400,{'code':'E_DATE','msg':'invalid date'})]);c=SSIV3Client(s,max_attempts=1);c.token='secret-token'
 with pytest.raises(SSIReadError) as error:
  c._request('GET','/data/securitiesSummary',params={'symbol':'SSI','from':'bad','accessToken':'must-not-leak'})
 message=str(error.value)
 assert 'GET /api/v3/data/securitiesSummary' in message and 'http_status=400' in message
 assert "api_code='E_DATE'" in message and "api_msg='invalid date'" in message
 assert 'must-not-leak' not in message and 'secret-token' not in message
