from types import SimpleNamespace
import pytest
from src.database.client import SupabaseClient

@pytest.mark.parametrize('decision,count',[('VALID',1),('PARTIAL',1),('REJECTED',0)])
def test_rpc_acknowledgement_checked_without_retry(decision,count):
 db=object.__new__(SupabaseClient);calls=[]
 response=SimpleNamespace(data=dict(decision=decision,clean_rows=count,issue_count=0,raw_hash='HASH',atomic=True))
 def rpc(name,params):
  calls.append((name,params));return SimpleNamespace(execute=lambda:response)
 db.client=SimpleNamespace(rpc=rpc)
 db._with_retry=lambda *a,**k:pytest.fail('Ambiguous write retry forbidden')
 result=db.persist_stock_daily_validation_v1('TCB','2026-03-05','HASH',None,{'decision':decision})
 assert len(calls)==1 and calls[0][0]=='persist_stock_daily_numeric_v1' and result['decision']==decision

@pytest.mark.parametrize('data',[None,{},dict(decision='VALID',clean_rows=0,issue_count=0,raw_hash='HASH',atomic=True),
 dict(decision='VALID',clean_rows=1,issue_count=0,raw_hash='WRONG',atomic=True)])
def test_bad_acknowledgements_fail_closed(data):
 db=object.__new__(SupabaseClient)
 db.client=SimpleNamespace(rpc=lambda *a:SimpleNamespace(execute=lambda:SimpleNamespace(data=data)))
 with pytest.raises(RuntimeError):db.persist_stock_daily_validation_v1('TCB','2026-03-05','HASH',{}, {})
