"""Pure Index Daily mapping and validation; optional errors reject, no quarantine."""
from dataclasses import asdict
from src.contracts import map_record
from src.contracts.transforms import to_date, to_symbol
from src.contracts.registry import MappingConfigurationError
from .index_daily_validator import POLICY_VERSION, validate_index_daily_record


def validate_index_payload(payload,index_code,date):
    if not isinstance(payload,dict):
        return None,dict(policy_version=POLICY_VERSION,decision='REJECTED',issues=[dict(field=None,code='INVALID_RECORD',severity='ERROR',action='REJECT',message='Expected object')])
    try:
        code=to_symbol(index_code,{})
        mapped=map_record('ssi_v3','index_daily',{f'indexSummary.{k}':v for k,v in payload.items()},{'index':code})
    except (MappingConfigurationError,ValueError):
        return None,dict(policy_version=POLICY_VERSION,decision='REJECTED',issues=[dict(field=None,code='MAPPING_CONFIGURATION_ERROR',severity='ERROR',action='REJECT',message='Mapping/identity unavailable')])
    candidate=mapped.candidate;report=dict(mapped.report);issues=[]
    for field in report.get('predecoded_float_fields',[]):
        issues.append(dict(field=field,code='PREDECODED_FLOAT_PRECISION_UNVERIFIED',severity='WARNING',
                           action='KEEP_PREDECODED_VALUE',message='Input was already float; original source digits cannot be reconstructed'))
    for error in report['errors']:
        issues.append(dict(field=error.get('field'),code=error['code'],severity='ERROR',action='REJECT',message=error.get('message',error['code'])))
    # The verified v3 endpoint is scoped by the requested index; many responses
    # omit an identifier. If an identifier is present, case-only normalization
    # is allowed but a conflicting value is never repaired from the request.
    identities=[v for k,v in payload.items() if str(k).casefold() in ('index','indexcode','indexid') and v not in (None,'')]
    try: identity_ok=all(to_symbol(v,{})==code for v in identities)
    except ValueError:identity_ok=False
    if not identity_ok or candidate is not None and candidate['trading_date']!=to_date(date,{}):
        issues.append(dict(field=None,code='REQUEST_SCOPE_MISMATCH',severity='ERROR',action='REJECT',message='Index/date differs from request'))
    if candidate is not None:
        validation=validate_index_daily_record(candidate)
        issues.extend(dict(field=i.field,code=i.code,severity=i.severity.upper(),action='REJECT' if i.severity=='error' else 'KEEP_EXACT_SOURCE',message=i.message,actual_value=i.actual_value,expected_value=i.expected_value) for i in validation.errors+validation.warnings)
    rejected=any(i['action']=='REJECT' for i in issues)
    report.update(policy_version=POLICY_VERSION,decision='REJECTED' if rejected else 'VALID_WITH_WARNINGS' if issues else 'VALID',issues=issues,
                  records_valid=int(not rejected),records_rejected=int(rejected))
    if rejected:
        report['errors']=[{'field':i['field'],'code':i['code']} for i in issues if i['action']=='REJECT']
    return None if rejected else candidate,report
