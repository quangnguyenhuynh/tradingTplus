from src.providers.ssi.capabilities import CapabilityUnavailableError
"""Offline canonical candle helpers; source mapping awaits a verified v3 adapter."""
from datetime import date as Date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo
from src.contracts.transforms import TRANSFORMS, TransformError

VN_TZ=ZoneInfo('Asia/Ho_Chi_Minh'); UTC_TZ=ZoneInfo('UTC')
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
def map_intraday_records(symbol:str,date:str,daily:dict|None,candles:list[dict]):
    raise CapabilityUnavailableError("stock_intraday")
def build_intraday_records(symbol:str,date:str,daily:dict|None,candles:list[dict])->tuple[list[dict],list[dict]]:
    raise CapabilityUnavailableError("stock_intraday")
def deduplicate_intraday_records(records:list[dict])->list[dict]:
    keyed={}
    for index,record in enumerate(records):keyed[(record.get('symbol'),record.get('timeframe'),record.get('time'))]=(index,record)
    return [record for _,record in sorted(keyed.values(),key=lambda item:(item[1].get('time') or '',item[0]))]
