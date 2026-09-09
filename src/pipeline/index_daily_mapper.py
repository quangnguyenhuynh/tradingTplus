"""SSI v2 DailyIndex compatibility wrappers over the shared mapping engine."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime
from typing import Any
from src.data_contracts import map_record
from src.pipeline.date_utils import parse_ddmmyyyy

INDEX_DAILY_CLEAN_SOURCE_ALIASES = {k: tuple(v.get("aliases", ())) for k, v in __import__('src.data_contracts.registry', fromlist=['get_mapping']).get_mapping('ssi_v2','index_daily')['fields'].items()}
def get_index_payload_value(payload: dict, *keys: str) -> Any:
    lower={str(k).casefold():v for k,v in payload.items()}
    return next((lower[k.casefold()] for k in keys if k.casefold() in lower),None)
def payload_index_code(payload: dict) -> str | None:
    value=get_index_payload_value(payload,*INDEX_DAILY_CLEAN_SOURCE_ALIASES['index_code']); return str(value).strip() if value not in (None,'') else None
def payload_index_date(payload: dict) -> str | None:
    value=get_index_payload_value(payload,*INDEX_DAILY_CLEAN_SOURCE_ALIASES['trading_date'])
    if value in (None,''): return None
    for fmt in ('%d/%m/%Y','%Y-%m-%d','%d-%m-%Y','%Y/%m/%d'):
        try:return datetime.strptime(str(value).strip()[:10],fmt).date().isoformat()
        except ValueError:pass
    return None
def build_index_raw_daily_record(requested_code: str,date: str,payload: dict)->dict:
    code=payload_index_code(payload) or requested_code; trading_date=payload_index_date(payload) or parse_ddmmyyyy(date).iso
    canonical=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str)
    return {'index_code':code,'trading_date':trading_date,'data_hash':hashlib.sha256(canonical.encode()).hexdigest(),'payload':payload,'source':'SSI_DailyIndex'}
def map_index_daily_record(requested_code: str,date: str,payload: dict):
    result=map_record('ssi_v2','index_daily',payload,{})
    clean=result.candidate
    if clean is None:return None,result.report
    if clean['index_code'].casefold()!=requested_code.casefold() or clean['trading_date']!=parse_ddmmyyyy(date).iso:
        report={**result.report,'records_valid':0,'records_rejected':1,'errors':result.report['errors']+[{'code':'REQUEST_SCOPE_MISMATCH'}]}; return None,report
    clean['index_code']=requested_code
    return clean,result.report
def build_index_daily_record(requested_code: str,date: str,payload: dict)->dict|None:return map_index_daily_record(requested_code,date,payload)[0]
def summarize_index_payload_mapping(payload:dict,record:dict|None)->dict[str,Any]:
    report=map_record('ssi_v2','index_daily',payload,{}).report
    return {'raw_field_count':len(payload),'normalized_field_count':len(record) if record is not None else 0,'omitted_from_clean':report.get('unused_source_fields',[])}
