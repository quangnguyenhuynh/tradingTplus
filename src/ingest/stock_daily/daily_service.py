"""RAW-first Stock Daily V1 validation and atomic clean/current-issue persistence."""
from src.ingest.stock_daily.daily_fetcher import fetch_daily_price
from src.ingest.stock_daily.daily_mapper import build_raw_daily_record
from src.ingest.stock_daily.daily_persistence import persist_raw_daily
from src.quality.validators.stock_daily_v1 import POLICY_VERSION


def fetch_daily_for_symbol_with_clients(ssi, db, symbol, date):
    summary=dict(symbol=symbol,date=date,daily_valid=False,daily_rows=0,daily_errors=0,daily_warnings=0,
                 valid_clean_writes=0,partial_clean_writes=0,rejected_records=0,mapping_failures=0,
                 persistence_failures=0,validation_issues=0,status='FAILED',error_type=None,errors=[])
    try:
        adapted=fetch_daily_price(ssi,symbol,date)
    except Exception:
        summary.update(error_type='API_ERROR',errors=['SSI_FETCH_OR_MAPPING_ERROR'])
        return summary
    if not adapted.raw:
        summary.update(error_type='NO_DATA',errors=['NO_SOURCE_RECORDS'])
        return summary
    summary['mapping_report']=adapted.mapping_report
    summary['daily_payload']=adapted.raw[0]
    reports=adapted.mapping_report.get('record_reports',[])
    multiple=len(adapted.raw)!=1
    raw_records=[build_raw_daily_record(symbol,date,p,source=adapted.source) for p in adapted.raw]
    try:
        for raw in raw_records:persist_raw_daily(db,raw)
        for index,raw in enumerate(raw_records):
            report=reports[index] if not multiple and index<len(reports) else dict(
                policy_version=POLICY_VERSION,mapping_version=adapted.mapping_report.get('mapping_version'),
                contract_version=adapted.mapping_report.get('contract_version'),decision='REJECTED',
                issues=[dict(field=None,code='MULTIPLE_RECORDS' if multiple else 'POLICY_REPORT_MISSING',
                             severity='ERROR',action='REJECT',message='Source cannot be validated unambiguously')])
            candidate=adapted.clean[index] if not multiple and index<len(adapted.clean) else None
            summary['validation_report']=report
            result=db.persist_stock_daily_validation_v1(symbol,raw['trading_date'],raw['data_hash'],candidate,report)
            decision=result['decision'];count=result['clean_rows']
            final_issues=result.get('issues',report['issues'])
            summary['persistence_issues']=final_issues
            summary.update(validation_status=decision,daily_rows=summary['daily_rows']+count)
            summary['validation_issues']+=result['issue_count']
            summary['daily_errors']+=sum(i['severity']=='ERROR' for i in final_issues)
            summary['daily_warnings']+=sum(i['severity']=='WARNING' for i in final_issues)
            summary['mapping_failures']+=int(bool(report.get('mapping_failures',report.get('errors'))))
            if decision=='REJECTED':
                summary['rejected_records']+=1
                summary['errors'].extend(i['code'] for i in final_issues)
                if not summary['errors']:summary['errors'].append('CLEAN_VALID_DOWNGRADE_BLOCKED')
            else:summary['valid_clean_writes' if decision=='VALID' else 'partial_clean_writes']+=count
        summary['daily_valid']=summary['daily_rows']>0
        summary['status']='FAILED' if summary['rejected_records'] else 'PARTIAL' if summary['partial_clean_writes'] else 'OK'
        if summary['rejected_records']:summary['error_type']='MISMATCH'
    except Exception:
        # RAW may already be committed. RPC failure is never treated as success or
        # automatically retried; its transaction rolls back clean/log together.
        summary.update(status='FAILED',error_type='DB_PERSISTENCE',persistence_failures=1)
        summary['errors'].append('DB_PERSISTENCE_FAILED_APPLY_20261104_DAILY_NUMERIC_PRECISION_OR_RECONCILE_RAW')
    return summary
