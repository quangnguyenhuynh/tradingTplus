"""Bounded read-only RAW/CLEAN comparison using the production V1 policy."""
from collections import Counter
from datetime import timedelta
from src.ingest.shared.date_utils import parse_ddmmyyyy
from src.contracts.transforms import to_symbol
from src.quality.validators.stock_daily_v1 import validate_payload


def read_scope(client, table, symbols, start, end):
    rows=[];expected=None;seen=set()
    for offset in range(0,10000,100):
        query=client.table(table).select('*',count='exact').in_('symbol',symbols).gte('trading_date',start).lte('trading_date',end)
        for key in (('symbol','trading_date','source','data_hash') if table=='stock_raw_daily' else ('symbol','trading_date')):
            query=query.order(key)
        response=query.range(offset,offset+99).execute()
        page=response.data;count=response.count
        if getattr(response,'error',None) or not isinstance(page,list) or type(count) is not int or (expected is not None and expected!=count):
            raise RuntimeError('Diagnostic DB read incomplete')
        expected=count
        for row in page:
            key=tuple(row.get(k) for k in ('symbol','trading_date','source','data_hash'))
            if key in seen:raise RuntimeError('Diagnostic pagination repeated an identity')
            seen.add(key)
        rows.extend(page)
        if len(rows)==count:return rows
        if len(page)!=100 or len(rows)>count:raise RuntimeError('Diagnostic pagination truncated')
    raise ValueError('Diagnostic row cap 10000 exceeded; narrow scope')


def inspect_daily(symbols, start, end=None, *, missing_only=False, client=None):
    normalized=list(dict.fromkeys(to_symbol(s,{}) for s in symbols))
    if not normalized or len(normalized)>50:raise ValueError('Use 1 to 50 explicit symbols')
    begin=parse_ddmmyyyy(start);finish=parse_ddmmyyyy(end or start)
    if finish.date<begin.date or (finish.date-begin.date).days>30:raise ValueError('Use an ordered range of at most 31 calendar days')
    if client is None:
        from src.database.client import SupabaseClient
        client=SupabaseClient().get()
    raw=read_scope(client,'stock_raw_daily',normalized,begin.iso,finish.iso)
    clean=read_scope(client,'stock_daily',normalized,begin.iso,finish.iso)
    clean_by_key={(r['symbol'],r['trading_date']):r for r in clean}
    records=[];counts=Counter()
    for row in raw:
        existing=clean_by_key.get((row['symbol'],row['trading_date']))
        if missing_only and existing is not None:continue
        if row['source']!='ssi_v3':
            report={'decision':'UNSUPPORTED','issues':[{'field':None,'code':'UNSUPPORTED_RAW_SOURCE'}]}
        else:
            _,report=validate_payload(row['payload'],row['symbol'],row['trading_date'])
        for issue in report['issues']:counts[(issue.get('field'),issue['code'])]+=1
        records.append(dict(symbol=row['symbol'],trading_date=row['trading_date'],raw_hash=row['data_hash'],
            source=row['source'],clean_present=existing is not None,
            stored_validation_status=existing.get('validation_status') if existing else None,
            policy_report=report,
            historical_failure='UNDETERMINED_RAW_ONLY' if existing is None else None,
            persistence_note='RAW-only replay cannot reconstruct historical HTTP/DB/log failures or multi-record response context'))
    return dict(flow='stock-eod-quality',mode='READ_ONLY',status='OK',records=records,
                raw_records=len(raw),clean_records=len(clean),matched_records=len(records),
                issues_by_field_code=[dict(field=f,code=c,count=n) for (f,c),n in counts.items()])
