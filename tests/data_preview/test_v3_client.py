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
