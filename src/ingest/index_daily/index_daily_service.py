"""Separate Index Daily RAW-first exact mapping, validation and CLEAN persistence."""
from __future__ import annotations
from typing import Any
from src.database.client import SupabaseClient
from src.ingest.index_daily.index_daily_fetcher import fetch_index_daily
from src.ingest.index_daily.index_daily_mapper import build_index_raw_daily_record
from src.ingest.index_daily.index_daily_persistence import persist_index_daily,persist_index_raw_daily
from src.providers.ssi.base import DataSourceAdapter


def fetch_index_daily_with_clients(ssi: DataSourceAdapter,db: SupabaseClient,index_code: str,date: str)->dict[str,Any]:
    summary=dict(index_code=index_code,date=date,raw_rows=0,clean_rows=0,rejected_rows=0,
                 warning_count=0,persistence_failures=0,errors=[],status='FAILED')
    try:adapted=fetch_index_daily(ssi,index_code,date)
    except Exception:
        summary['errors'].append('SSI_INDEX_FETCH_OR_MAPPING_FAILED');return summary
    if not adapted.raw:
        summary['errors'].append('NO_INDEX_SOURCE_RECORDS');return summary
    rows=[build_index_raw_daily_record(index_code,date,p,source=adapted.raw_source or adapted.source) for p in adapted.raw]
    summary['mapping_report']=adapted.mapping_report
    summary['validation_reports']=adapted.mapping_report.get('record_reports',[])
    try:
        persist_index_raw_daily(db,rows);summary['raw_rows']=len(rows)
        for position,row in enumerate(rows):
            report=summary['validation_reports'][position]
            candidate=adapted.clean[position]
            summary['warning_count']+=sum(i['severity']=='WARNING' for i in report.get('issues',[]))
            if candidate is None:
                summary['rejected_rows']+=1
                summary['errors'].extend(i['code'] for i in report.get('issues',[]) if i['action']=='REJECT')
                if not summary['errors']:summary['errors'].append('INDEX_MAPPING_REJECTED')
                continue
            result=persist_index_daily(db,candidate,raw_hash=row['data_hash'],report=report)
            summary['clean_rows']+=result['clean_rows']
            summary.setdefault('persistence_reports',[]).append(result)
            summary['warning_count']+=int(bool(result.get('preserved_fields')))+len(result.get('merge_issues',[]))
        summary['status']='FAILED' if not summary['clean_rows'] else 'PARTIAL' if summary['rejected_rows'] or summary['warning_count'] else 'OK'
    except Exception:
        summary.update(status='FAILED',persistence_failures=1)
        summary['errors'].append('INDEX_DB_PERSISTENCE_FAILED_APPLY_20261104_DAILY_NUMERIC_PRECISION_OR_RECONCILE_RAW')
    return summary
