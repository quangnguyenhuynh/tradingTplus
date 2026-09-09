"""SSI v2 1-minute candle compatibility wrappers over the shared mapping engine."""
import hashlib
import json
import logging
from datetime import date as Date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo
from src.data_contracts import map_record
from src.data_contracts.transforms import TRANSFORMS, TransformError
from src.intraday_value import calculate_trade_value

logger=logging.getLogger(__name__); VN_TZ=ZoneInfo('Asia/Ho_Chi_Minh'); UTC_TZ=ZoneInfo('UTC')
def parse_time(date_str:str,time_str:str)->datetime|None:
    try:base=datetime.strptime(date_str,'%d/%m/%Y').date()
    except (ValueError,TypeError):return None
    return parse_candle_time(base,time_str)
def parse_candle_time(base_date:Date,time_str:Any)->datetime|None:
    try:
        h,m,s=map(int,str(time_str).split(':')); return datetime.combine(base_date,time(h,m,s),tzinfo=VN_TZ).astimezone(UTC_TZ)
    except (ValueError,TypeError):return None
def nullable_float(value:Any)->float|None:
    if value in (None,'') or isinstance(value,bool):return None
    try:
        v=float(value); return v if v==v and abs(v)!=float('inf') else None
    except (ValueError,TypeError):return None
def nullable_int(value:Any)->int|None:
    try:return TRANSFORMS['int'](value,{}) if value not in (None,'') else None
    except TransformError:return None
def daily_context_payload(record:dict|None)->dict:
    if not record:return {}
    return {'RefPrice':record.get('ref_price'),'CeilingPrice':record.get('ceiling_price'),'FloorPrice':record.get('floor_price'),**record}
def _batch_report(reports:list[dict],received:int)->dict:
    keys=('missing_required','missing_optional','unused_source_fields','transform_errors','alias_conflicts','contract_errors','errors')
    out={'source':'ssi_v2','dataset':'stock_intraday','contract_version':'1.0.0','mapping_version':'1.0.0','records_received':received,'records_valid':sum(r['records_valid'] for r in reports),'records_rejected':received-sum(r['records_valid'] for r in reports)}
    for key in keys:out[key]=[item for report in reports for item in report.get(key,[])]
    return out
def map_intraday_records(symbol:str,date:str,daily:dict|None,candles:list[dict]):
    try:base_date=datetime.strptime(date,'%d/%m/%Y').date()
    except (ValueError,TypeError):
        logger.warning('%s: invalid trading date: %s',symbol,date); return [],[],{'source':'ssi_v2','dataset':'stock_intraday','records_received':len(candles),'records_valid':0,'records_rejected':len(candles),'errors':[{'code':'INVALID_REQUEST_DATE'}]}
    daily=daily or {}; reference=nullable_float(daily.get('RefPrice',daily.get('ref_price'))); ceiling=nullable_float(daily.get('CeilingPrice',daily.get('ceiling_price'))); floor=nullable_float(daily.get('FloorPrice',daily.get('floor_price')))
    raw_records=[]; clean_records=[]; reports=[]; debug_samples=[]
    for candle in candles:
        source_time=candle.get('Time',''); timestamp=parse_candle_time(base_date,source_time)
        if timestamp is None:
            result=map_record('ssi_v2','stock_intraday',candle,{'symbol':symbol,'date':date,'reference_price':reference,'ceiling_price':ceiling,'floor_price':floor}); reports.append(result.report); logger.warning('%s: rejecting candle with invalid timestamp: %s',symbol,source_time); continue
        volume=nullable_int(candle.get('Volume')); close=nullable_float(candle.get('Close')); value=calculate_trade_value(close,volume)
        base={'symbol':symbol,'time':timestamp.strftime('%Y-%m-%dT%H:%M:%SZ'),'open':nullable_float(candle.get('Open')),'high':nullable_float(candle.get('High')),'low':nullable_float(candle.get('Low')),'close':close,'volume':volume}
        raw_records.append({**base,'payload':candle,'data_hash':hashlib.sha256(json.dumps(candle,sort_keys=True).encode()).hexdigest()})
        result=map_record('ssi_v2','stock_intraday',candle,{'symbol':symbol,'date':date,'value':value,'reference_price':reference,'ceiling_price':ceiling,'floor_price':floor}); reports.append(result.report)
        if result.candidate is not None:
            clean_records.append(result.candidate)
            if len(debug_samples)<5:debug_samples.append({**result.candidate,'value_type':type(result.candidate['value']).__name__})
    if debug_samples:logger.debug('Normalized intraday sample rows for %s %s: %s',symbol,date,debug_samples)
    return raw_records,clean_records,_batch_report(reports,len(candles))
def build_intraday_records(symbol:str,date:str,daily:dict|None,candles:list[dict])->tuple[list[dict],list[dict]]:
    raw,clean,_=map_intraday_records(symbol,date,daily,candles); return raw,clean
def deduplicate_intraday_records(records:list[dict])->list[dict]:
    keyed={}
    for index,record in enumerate(records):keyed[(record.get('symbol'),record.get('timeframe'),record.get('time'))]=(index,record)
    return [record for _,record in sorted(keyed.values(),key=lambda item:(item[1].get('time') or '',item[0]))]
