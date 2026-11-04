"""Bounded read-only daily RAW/CLEAN precision audit using exact RPC text reads."""
from collections import Counter,defaultdict
from src.contracts import map_record
from src.contracts.numeric import exact_json_loads,decimal_number
from src.contracts.registry import get_contract,get_mapping
from src.contracts.transforms import to_symbol
from src.ingest.shared.date_utils import parse_ddmmyyyy
from src.quality.validators.stock_daily_v1 import validate_payload
from src.quality.validators.index_daily_numeric import validate_index_payload


def read_exact_scope(client,dataset,kind,identifiers,start,end):
    rows=[];expected=None;seen=set();available=True
    identity='symbol' if dataset=='stock_daily' else 'index_code'
    for offset in range(0,10000,100):
        response=client.rpc('read_daily_numeric_scope_v1',dict(p_dataset=dataset,p_kind=kind,
            p_identifiers=identifiers,p_from=start,p_to=end,p_offset=offset,p_limit=100)).execute()
        if getattr(response,'error',None) or not isinstance(response.data,str):
            raise RuntimeError('Exact daily audit RPC unavailable or response unverified')
        page=exact_json_loads(response.data)
        count=page.get('total');items=page.get('rows');available=page.get('available')
        if type(count) is not int or count<0 or not isinstance(items,list) or type(available) is not bool or expected is not None and count!=expected:
            raise RuntimeError('Daily audit count/shape changed')
        expected=count
        if count>10000:raise ValueError('Daily audit row cap 10000 exceeded; narrow scope')
        for row in items:
            key=tuple(row.get(k) for k in (identity,'trading_date','source','data_hash','check_name'))
            if key in seen:raise RuntimeError('Daily audit repeated pagination identity')
            seen.add(key)
        rows.extend(items)
        if len(rows)==count:return rows,available
        if len(items)!=100 or len(rows)>count:raise RuntimeError('Daily audit pagination incomplete')
    raise ValueError('Daily audit row cap 10000 exceeded; narrow scope')


def inspect_daily_numeric(dataset,identifiers,start,end=None,*,client=None):
    if dataset not in ('stock_daily','index_daily'):raise ValueError('Use stock_daily or index_daily')
    ids=list(dict.fromkeys(to_symbol(i,{}) for i in identifiers))
    begin=parse_ddmmyyyy(start);finish=parse_ddmmyyyy(end or start)
    if not 1<=len(ids)<=50 or not 0<=(finish.date-begin.date).days<=30:
        raise ValueError('Use 1..50 explicit identifiers and an ordered range of at most 31 calendar days')
    if client is None:
        from src.database.client import SupabaseClient
        client=SupabaseClient().get()
    raw,_=read_exact_scope(client,dataset,'raw',ids,begin.iso,finish.iso)
    clean,_=read_exact_scope(client,dataset,'clean',ids,begin.iso,finish.iso)
    logs,issues_available=read_exact_scope(client,dataset,'issues',ids,begin.iso,finish.iso)
    identity='symbol' if dataset=='stock_daily' else 'index_code'
    key=lambda r:(str(r[identity]).upper(),r['trading_date'])
    clean_by_key=defaultdict(list)
    for row in clean:clean_by_key[key(row)].append(row)
    logs_by_key={key(row):row for row in logs}
    raw_keys={key(row) for row in raw};records=[];counts=Counter()
    contract=get_contract(dataset);mapping=get_mapping('ssi_v3',dataset)
    prefix='summary' if dataset=='stock_daily' else 'indexSummary'
    supported='ssi_v3' if dataset=='stock_daily' else 'SSI_v3_indexSummary'
    policy=validate_payload if dataset=='stock_daily' else validate_index_payload
    def add_record(record,issues):
        record['observations']=issues;records.append(record)
        for issue in issues:
            counts[(dataset,record.get('source'),record['identifier'],record['trading_date'],issue.get('field'),issue['code'],record.get('mapping_version'),record.get('policy_version'))]+=1
    for row in raw:
        canonical,day=key(row);matches=clean_by_key.get((canonical,day),[])
        existing=matches[0] if len(matches)==1 else None
        issues=[];audit=logs_by_key.get((canonical,day));report=None;partial=None
        if row[identity]!=canonical:
            issues.append(dict(field=identity,code='CASE_VARIANT_IDENTITY',action='CANONICAL_COMPARE_ONLY'))
        if not matches:issues.append(dict(field=None,code='RAW_ONLY',historical_failure='UNDETERMINED_RAW_ONLY'))
        if len(matches)>1:issues.append(dict(field=identity,code='AMBIGUOUS_CLEAN_CASE_IDENTITIES'))
        if row.get('source')!=supported:
            issues.append(dict(field=None,code='UNSUPPORTED_RAW_PROVENANCE'))
        else:
            candidate,report=policy(row['payload'],canonical,day)
            issues.extend(report.get('issues',[]))
            if report.get('decision')=='REJECTED':issues.append(dict(field=None,code='VALIDATION_REJECTED'))
            if isinstance(row['payload'],dict):
                partial=map_record('ssi_v3',dataset,{f'{prefix}.{k}':v for k,v in row['payload'].items()}, {'index':canonical}).partial_candidate
                for name,spec in contract['fields'].items():
                    if spec.get('numeric_semantics') is None:continue
                    value=partial.get(name)
                    if value is None:
                        if not mapping['fields'][name].get('derived') and not mapping['fields'][name].get('unsupported'):
                            issues.append(dict(field=name,code='MISSING_OPTIONAL' if name in report.get('missing_optional',[]) else 'MAPPING_TRANSFORM_FAILURE'))
                        continue
                    number=decimal_number(value)
                    if spec['numeric_semantics']=='monetary' and number!=number.to_integral_value():
                        issues.append(dict(field=name,code='VALID_FRACTIONAL_MONETARY_VALUE',value=str(number)))
                    if existing is not None and existing.get(name) is not None:
                        try:stored=decimal_number(existing[name])
                        except ValueError:
                            issues.append(dict(field=name,code='CLEAN_INVALID_NUMERIC'));continue
                        if stored!=number:
                            issues.append(dict(field=name,code='RAW_CLEAN_VALUE_MISMATCH',raw_value=str(number),clean_value=str(stored),
                                               note='Observed source-version difference; does not alone prove corruption'))
                for error in report.get('errors',[]):
                    name=error.get('field');spec=contract['fields'].get(name,{})
                    if error['code']=='TRANSFORM_ERROR' and spec.get('numeric_semantics')=='discrete_quantity':
                        issues.append(dict(field=name,code='DISCRETE_QUANTITY_TRANSFORM_FAILURE'))
                        aliases={a.casefold() for a in mapping['fields'][name].get('aliases',[])}
                        for source_field,value in row['payload'].items():
                            if f'{prefix}.{source_field}'.casefold() not in aliases:continue
                            try:number=decimal_number(value)
                            except ValueError:continue
                            if number!=number.to_integral_value():
                                issues.append(dict(field=name,code='NONINTEGRAL_DISCRETE_QUANTITY',value=str(number)))
        if existing is not None and (dataset=='index_daily' or existing.get('validation_status') is None):
            issues.append(dict(field=None,code='HISTORICAL_CLEAN_VALIDATION_UNVERIFIED'))
        add_record(dict(dataset=dataset,source=row.get('source'),identifier=canonical,raw_identity=row[identity],
            trading_date=day,raw_hash=row['data_hash'],clean_present=bool(matches),
            stored_validation_status=existing.get('validation_status') if existing else None,
            clean_matches_this_raw=existing.get('raw')==row['payload'] if existing and dataset=='stock_daily' else None,
            policy_version=report.get('policy_version') if report else None,mapping_version=report.get('mapping_version') if report else None,replay_decision=report.get('decision') if report else 'UNVERIFIED',
            mapping_report=report,current_quality_state=audit.get('status') if audit else 'NO_STOCK_ISSUE_ROW' if issues_available else 'UNAVAILABLE_INDEX_NO_PERSISTED_QUALITY_LOG',
            persisted_policy_version=(audit.get('details') or {}).get('policy_version') if audit else None,
            persisted_mapping_version=(audit.get('details') or {}).get('mapping_version') if audit else None,
            persisted_contract_version=(audit.get('details') or {}).get('contract_version') if audit else None,
            persisted_decision=(audit.get('details') or {}).get('decision') if audit else None,
            persisted_issues=(audit.get('details') or {}).get('issues',[]) if audit else [],
            current_quality_raw_hash=(audit.get('details') or {}).get('raw_hash') if audit else None,
            quality_history=(audit.get('details') or {}).get('history',[]) if audit else [],
            provenance_note='RAW-only replay cannot reconstruct old HTTP/DB/log failures; Index CLEAN has no RAW hash provenance'),issues)
    for row in clean:
        canonical,day=key(row)
        if (canonical,day) not in raw_keys:
            add_record(dict(dataset=dataset,source=row.get('source'),identifier=canonical,trading_date=day,
                            stored_validation_status=row.get('validation_status'),clean_present=True,policy_version=None),
                       [dict(field=None,code='CLEAN_ONLY'),dict(field=None,code='HISTORICAL_CLEAN_VALIDATION_UNVERIFIED')])
    return dict(flow='daily-numeric-quality',mode='READ_ONLY',status='OK',dataset=dataset,identifiers=ids,
                from_date=begin.iso,to_date=finish.iso,raw_records=len(raw),clean_records=len(clean),
                quality_log_available=issues_available,records=records,
                counts=[dict(dataset=k[0],source=k[1],identifier=k[2],trading_date=k[3],field=k[4],code=k[5],mapping_version=k[6],policy_version=k[7],count=n) for k,n in counts.items()],
                audit_note='Bounded observed pages, not a cross-request transaction snapshot; pause writers for authoritative reconciliation')
