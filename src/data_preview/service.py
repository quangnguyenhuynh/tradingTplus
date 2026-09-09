"""Provider-neutral read/map/validate/compare preview; deliberately has no DB imports."""
from __future__ import annotations
import json, math, sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from typing import Any, Callable
from src.data_contracts import get_contract, get_mapping, map_record
from src.data_contracts.transforms import TRANSFORMS, TransformError
from src.intraday_value import calculate_trade_value
from src.ssi.v3 import SSIV3Client, SSIReadError

STATUSES=('MAPPED','DERIVED','UNSUPPORTED','MISSING','INVALID')
def _get(row,path):
    lower={str(k).casefold():v for k,v in row.items()}; return lower.get(path.casefold())
def _flatten(endpoint,row): return {f'{endpoint}.{k}':v for k,v in row.items()}
def _safe_params(dataset,code,date,source):
    if source=='ssi_v3':
        return {'stock_daily':{'securitiesSummary':{'symbol':code,'from':date,'to':date},'masterdata':{'from':date,'to':date}},'stock_intraday':{'ohlc':{'symbol':code,'from':date+' 00:00:00','to':date+' 23:59:59','timeFrame':'1m'}},'index_daily':{'indexSummary':{'index':code,'tradingDate':date}}}[dataset]
    return {'source':'legacy SSI v2','symbol_or_index':code,'date':date}
def _map_v3(dataset,row,context):
    contract=get_contract(dataset); mapping=get_mapping('ssi_v3',dataset); clean={}; trace=[]; invalid=False
    for field,spec in contract['fields'].items():
        rule=mapping['fields'][field]; raw=None; path=None; status='MISSING'; reason='Mapped source field is absent'
        if rule.get('unsupported'):
            clean[field]=None; trace.append({'field':field,'status':'UNSUPPORTED','source_path':None,'before':None,'after':None,'transform':None,'reason':rule['reason']}); continue
        if 'context' in rule: raw=context.get(rule['context']); path=f"request.{rule['context']}"
        elif 'constant' in rule: raw=rule['constant']; path='mapping.constant'
        else:
            for alias in rule.get('aliases',[]):
                value=_get(row,alias)
                if value not in (None,''):raw=value;path=alias;break
        value=None
        if raw not in (None,''):
            try:value=TRANSFORMS[rule['transform']](raw,context); status='MAPPED';reason=None
            except TransformError as exc:status='INVALID';reason=str(exc);invalid=True
        clean[field]=value; trace.append({'field':field,'status':status,'source_path':path or (rule.get('aliases') or [None])[0],'before':raw,'after':value,'transform':rule['transform'],'reason':reason})
    # Confirmed same-row derivations only.
    for target,left,right in [('net_foreign_vol','foreign_buy_vol_total','foreign_sell_vol_total'),('net_foreign_val','foreign_buy_val_total','foreign_sell_val_total')]:
        if target in clean and clean.get(left) is not None and clean.get(right) is not None:
            clean[target]=clean[left]-clean[right]; t=next(x for x in trace if x['field']==target); t.update(status='DERIVED',after=clean[target],transform=f'{left} - {right}',reason='Both normalized inputs are present from securitiesSummary')
    if dataset=='stock_intraday' and clean.get('close') is not None and clean.get('volume') is not None:
        clean['value']=calculate_trade_value(clean['close'],clean['volume']); t=next(x for x in trace if x['field']=='value');t.update(status='DERIVED',after=clean['value'],transform='round(close * volume)',reason='Canonical estimated value; API value remains raw')
    # Business invariants are separate from mapping.
    issues=[]
    if all(clean.get(x) is not None for x in ('open','high','low','close')):
        if clean['high']<max(clean['open'],clean['close'],clean['low']) or clean['low']>min(clean['open'],clean['close'],clean['high']):issues.append({'code':'INVALID_OHLC'})
    for f,s in contract['fields'].items():
        v=clean.get(f)
        if s.get('required') and v is None:issues.append({'field':f,'code':'MISSING_REQUIRED'})
        if isinstance(v,float) and not math.isfinite(v):issues.append({'field':f,'code':'NON_FINITE'})
        if v is not None and s.get('minimum') is not None and v<s['minimum']:issues.append({'field':f,'code':'BELOW_MINIMUM'})
    return {'canonical':clean,'fields':trace,'validation':{'status':'INVALID' if invalid or issues else 'VALID','issues':issues}}
def _fetch_v3(dataset,code,date,client):
    raw={}; meta={}
    if dataset=='stock_daily':
        s=client.securities_summary(code,date); m=client.masterdata(date); raw={'securitiesSummary':s.raw_pages,'masterdata':m.raw_pages}; meta={'pages':s.pages+m.pages,'records_received':len(s.items)+len(m.items)}
        summaries=[x for x in s.items if str(x.get('symbol','')).upper()==code]
        masters=[x for x in m.items if str(x.get('symbol','')).upper()==code and str(x.get('tradingDate',x.get('date',''))).replace('/','-')[:10] in (date,date.replace('-','/'))]
        rows=[{**_flatten('summary',x),**(_flatten('masterdata',masters[0]) if masters else {})} for x in summaries]
    elif dataset=='stock_intraday':
        p=client.ohlc_1m(code,date);raw={'ohlc':p.raw_pages};meta={'pages':p.pages,'records_received':len(p.items)};rows=[_flatten('ohlc',x) for x in p.items]
    else:
        p=client.index_summary(code,date);raw={'indexSummary':p.raw_pages};meta={'pages':1,'records_received':len(p.items)};rows=[]
        for x in p.items:
            actual=x.get('index') or x.get('indexCode')
            if actual and str(actual).upper()!=code:raise SSIReadError('indexSummary identity conflicts with requested single index')
            y=dict(x);y.setdefault('index',code);y.setdefault('tradingDate',date);rows.append(_flatten('indexSummary',y))
    return rows,raw,meta

def _fetch_v2(dataset,code,date,client_factory=None):
    from src.ssi.api import SSIApi
    # The legacy client emits progress to stdout; preserve valid JSON stdout.
    with redirect_stdout(sys.stderr):
        c=(client_factory or SSIApi)(); dd=datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y')
        if dataset=='stock_daily':items=c.get_daily_price_items(code,dd)
        elif dataset=='stock_intraday':items=c.get_intraday(code,dd)
        else:items=c.get_daily_index_items(code,dd)
    return items,{'legacy':items},{'pages':None,'records_received':len(items)}
def _one_source(dataset,code,date,source,client=None,v2_factory=None):
    fetched=datetime.now(timezone.utc).isoformat(); rows,raw,meta=(_fetch_v3(dataset,code,date,client or SSIV3Client()) if source=='ssi_v3' else _fetch_v2(dataset,code,date,v2_factory))
    records=[]
    for row in rows:
        context={'symbol':code,'date':datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y')}
        if source=='ssi_v3':mapped=_map_v3(dataset,row,context)
        else:
            result=map_record('ssi_v2',dataset,row,context); mapped={'canonical':result.candidate or {f:None for f in get_contract(dataset)['fields']},'fields':[],'validation':{'status':'VALID' if result.candidate else 'INVALID','issues':result.report['errors']}}
        records.append(mapped)
    mapping=get_mapping(source,dataset)
    return {'mode':'PREVIEW — no database writes','dataset':dataset,'source':source,'code':code,'requested_date':date,'endpoints':_safe_params(dataset,code,date,source),'fetched_at':fetched,'contract_version':mapping['contract_version'],'mapping_version':mapping['mapping_version'],**meta,'status':'EMPTY' if not rows else ('INVALID' if any(x['validation']['status']=='INVALID' for x in records) else 'OK'),'records':records,'raw':raw}
def _key(dataset,r):
    c=r['canonical'];return {'stock_daily':(c.get('symbol'),c.get('trading_date')),'stock_intraday':(c.get('symbol'),c.get('time'),c.get('timeframe')),'index_daily':(c.get('index_code'),c.get('trading_date'))}[dataset]
def _compare(dataset,left,right):
    a={_key(dataset,r):r for r in left['records']};b={_key(dataset,r):r for r in right['records']};out=[]
    for key in sorted(set(a)|set(b),key=str):
        for field in get_contract(dataset)['fields']:
            av=a.get(key,{}).get('canonical',{}).get(field);bv=b.get(key,{}).get('canonical',{}).get(field);diff=abs(av-bv) if isinstance(av,(int,float)) and isinstance(bv,(int,float)) else None
            status='BOTH_MISSING' if av is None and bv is None else 'MISSING_RECORD' if key not in a or key not in b else 'NOT_COMPARABLE' if av is None or bv is None else 'MATCH' if av==bv else 'DIFFERENT'
            out.append({'key':key,'field':field,'ssi_v2':av,'ssi_v3':bv,'absolute_difference':diff,'relative_difference':diff/abs(av) if diff is not None and av else None,'status':status})
    return out

def run_preview(dataset,code,date,source='ssi_v3',compare=None,client=None,v2_factory=None):
    if compare:
        results=[];errors=[]
        for s in compare:
            try:results.append(_one_source(dataset,code,date,s,client if s=='ssi_v3' else None,v2_factory))
            except Exception as exc:errors.append({'source':s,'error':str(exc)})
        return {'mode':'PREVIEW — no database writes','dataset':dataset,'requested_date':date,'sources':results,'errors':errors,'status':'INCOMPLETE' if errors else 'OK','comparison':_compare(dataset,next(x for x in results if x['source']=='ssi_v2'),next(x for x in results if x['source']=='ssi_v3')) if len(results)==2 else []}
    return _one_source(dataset,code,date,source,client,v2_factory)
def render_preview(result,fmt='table',show_raw=False,only_diff=False):
    value=json.loads(json.dumps(result,default=str));
    if not show_raw:
        value.pop('raw',None)
        for source in value.get('sources',[]):source.pop('raw',None)
    if only_diff:value['comparison']=[x for x in value.get('comparison',[]) if x['status']!='MATCH']
    if fmt=='json':return json.dumps(value,ensure_ascii=False,indent=2)
    lines=[value['mode'],f"dataset={value['dataset']} date={value['requested_date']} status={value['status']}"]
    if 'comparison' in value:
        lines += ['field | v2 | v3 | abs diff | status']+[f"{x['field']} | {x['ssi_v2']} | {x['ssi_v3']} | {x['absolute_difference']} | {x['status']}" for x in value['comparison'][:100]]
        if len(value['comparison'])>100:lines.append(f"… {len(value['comparison'])-100} rows omitted from table; use --format json for all rows")
    else:
        for record in value['records'][:20]:
            lines.append(json.dumps(record['canonical'],ensure_ascii=False,default=str));lines.extend(f"  {x['field']}: {x['status']} {x['source_path']} {x['before']!r} -> {x['after']!r} {x['reason'] or ''}" for x in record['fields'])
    if show_raw:lines.append(json.dumps(value.get('raw',[s.get('raw') for s in value.get('sources',[])]),ensure_ascii=False,default=str))
    return '\n'.join(lines)
