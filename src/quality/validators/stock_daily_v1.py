"""Explicit SSI v3 Stock Daily V1 field quarantine; no persistence or network."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import math

from src.contracts import map_record
from src.contracts.registry import get_mapping, MappingConfigurationError
from src.contracts.derived import apply_derived_fields
from src.contracts.transforms import to_date
from .daily_validator import validate_daily_record

POLICY_VERSION = 'stock_daily_validation_v1.0.0'
CORE = frozenset(('symbol','trading_date','open_price','highest_price','lowest_price','close_price',
                  'total_match_vol','total_match_val'))
PRICES = ('open_price','highest_price','lowest_price','close_price')
OPTIONAL = frozenset(('price_change','per_price_change','average_price','foreign_remaining_room','foreign_total_room',
    'foreign_buy_vol_total','foreign_sell_vol_total','foreign_buy_val_total','foreign_sell_val_total',
    'total_deal_vol','total_deal_val','total_buy_trade','total_buy_trade_vol','total_sell_trade','total_sell_trade_vol'))
RECOVERABLE = frozenset(('BELOW_MINIMUM','TRANSFORM_ERROR'))


def issue(field, code, action, message='', severity='ERROR'):
    return dict(field=field,code=code,severity=severity,action=action,message=message or code)


def validate_payload(payload, symbol, date):
    """Never mutate RAW; structural ambiguity always rejects the entire record."""
    qualified = {f'summary.{k}':v for k,v in payload.items()} if isinstance(payload,dict) else None
    if qualified is None:
        return None, dict(policy_version=POLICY_VERSION,decision='REJECTED',issues=[issue(None,'INVALID_RECORD','REJECT')],
                          mapping_version='2.0.0',contract_version='2.0.0',errors=[{'code':'INVALID_RECORD'}])
    try:
        mapped = map_record('ssi_v3','stock_daily',qualified,{})
        mapping=get_mapping('ssi_v3','stock_daily')
    except MappingConfigurationError:
        return None, dict(policy_version=POLICY_VERSION,decision='REJECTED',
            mapping_version='UNVERIFIED',contract_version='UNVERIFIED',
            issues=[issue(None,'MAPPING_CONFIGURATION_ERROR','REJECT')],errors=[{'code':'MAPPING_CONFIGURATION_ERROR'}])
    candidate = deepcopy(mapped.partial_candidate)
    report = deepcopy(mapped.report)
    issues=[]
    # The shared int transform historically passes through float. Recover exact
    # integral source values locally and reject fractions/alias ambiguity before
    # field quarantine; do not change transforms for other datasets.
    for field, rule in mapping['fields'].items():
        if rule.get('transform') != 'int' or not rule.get('aliases'): continue
        values=[value for key,value in payload.items()
                if any(('summary.'+str(key)).casefold()==alias.casefold() for alias in rule['aliases'])
                and value is not None and value!='']
        if not values: continue
        try:
            parsed=[Decimal(str(value)) for value in values]
            if any(isinstance(value,bool) for value in values) or any(not n.is_finite() or n!=n.to_integral_value() for n in parsed):
                raise ValueError('Non-integral value')
            code='ALIAS_CONFLICT' if any(n!=parsed[0] for n in parsed[1:]) else None
            if code is None and not any(e.get('field')==field and e['code']=='TRANSFORM_ERROR' for e in report['errors']):
                candidate[field]=int(parsed[0])
        except (InvalidOperation,ValueError,OverflowError):
            code='TRANSFORM_ERROR'
        if code and not any(e.get('field')==field and e['code']==code for e in report['errors']):
            report['errors'].append({'field':field,'code':code})
    mapping_failure_count=len(report['errors'])
    for error in report['errors']:
        field,code=error.get('field'),error['code']
        rule=mapping['fields'].get(field,{})
        aliases={alias.casefold() for alias in rule.get('aliases',[])}
        nonempty=[value for key,value in qualified.items() if key.casefold() in aliases and value not in (None,'')]
        recover = field in OPTIONAL and code in RECOVERABLE and not (code=='TRANSFORM_ERROR' and len(nonempty)>1)
        issues.append(issue(field,code,'SET_NULL' if recover else 'REJECT',error.get('message','')))
        if recover:candidate[field]=None
    for field in report['missing_optional']:
        if field in OPTIONAL or field in ('total_match_vol','total_match_val'):
            issues.append(issue(field,'MISSING_OPTIONAL','KEEP_NULL',severity='WARNING'))
    try: expected_date=to_date(date,{})
    except ValueError: expected_date=None
    if candidate.get('symbol') != symbol.strip().upper() or candidate.get('trading_date') != expected_date:
        issues.append(issue(None,'REQUEST_SCOPE_MISMATCH','REJECT'))
    for field in PRICES:
        value=candidate.get(field)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            issues.append(issue(field,'CORE_PRICE_INVALID','REJECT'))
    for field in ('total_match_vol','total_match_val'):
        value=candidate.get(field)
        if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0):
            issues.append(issue(field,'CORE_MATCH_INVALID','REJECT'))
    apply_derived_fields('stock_daily',candidate)
    validation=validate_daily_record(candidate)
    # Existing optional-market warnings are already represented above. Derived NULL
    # is intentional when either input is missing, never replaced by fabricated zero.
    for v in validation.errors+validation.warnings:
        if v.code=='DAILY_OPTIONAL_MARKET_FIELD_MISSING':continue
        recover=v.field in OPTIONAL and v.code in ('DAILY_NON_POSITIVE_PRICE','DAILY_PRICE_CHANGE_MISMATCH','DAILY_PERCENT_CHANGE_MISMATCH')
        action='SET_NULL' if recover else ('REJECT' if v in validation.errors else 'WARN')
        issues.append(issue(v.field,v.code,action,v.message,v.severity.upper()))
        if recover:candidate[v.field]=None
    apply_derived_fields('stock_daily',candidate)
    for field,value in candidate.items():
        if isinstance(value,float) and not math.isfinite(value):
            issues.append(issue(field,'NON_FINITE_DERIVED','REJECT'))
    decision='REJECTED' if any(i['action']=='REJECT' for i in issues) else 'PARTIAL' if issues else 'VALID'
    for i in issues:
        if i['action']=='REJECT' and not any(e.get('code')==i['code'] and e.get('field')==i['field'] for e in report['errors']):
            report['errors'].append({'field':i['field'],'code':i['code']})
    report.update(mapping_failures=mapping_failure_count,
                  policy_version=POLICY_VERSION,decision=decision,issues=issues,
                  clean_persistence_permitted=decision!='REJECTED',records_valid=int(decision!='REJECTED'),
                  records_rejected=int(decision=='REJECTED'))
    if decision=='REJECTED':return None,report
    candidate.update(source='ssi_v3',raw=payload,validation_status=decision)
    return candidate,report
