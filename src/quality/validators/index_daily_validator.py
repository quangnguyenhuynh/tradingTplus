"""Exact numeric validation for the separate SSI v3 Index Daily pipeline."""
from __future__ import annotations
from typing import Any
from src.contracts.numeric import is_finite_number, decimal_number, exact_binary
from src.quality.validators.models import ValidationIssue, ValidationResult

POLICY_VERSION = 'index_daily_numeric_v1.0.0'
NON_NEGATIVE = (
    'total_trade_volume','total_trade_value','total_match_volume','total_match_value',
    'total_deal_volume','total_deal_value','total_advance_stock','total_ceiling_stock',
    'total_decline_stock','total_floor_stock','total_no_change_stock',
    'total_prop_buy_volume','total_prop_buy_value','total_prop_sell_volume',
    'total_prop_sell_value','total_foreign_buy_volume','total_foreign_buy_value',
    'total_foreign_sell_volume','total_foreign_sell_value',
)
NUMERIC = ('index_value','index_change','index_change_percentage',*NON_NEGATIVE,
           'net_foreign_purchase_volume','net_foreign_purchase_value')
QUANTITIES = frozenset(f for f in NUMERIC if f.endswith('_volume') or f.endswith('_stock'))


def validate_index_daily_record(record: dict) -> ValidationResult:
    errors=[];warnings=[];valid={}
    def issue(code, message, severity, field, actual=None, expected=None):
        (errors if severity=='error' else warnings).append(ValidationIssue(code,message,severity,field,actual,expected))
    for field in ('index_code','trading_date','index_value'):
        if record.get(field) in (None,''):
            issue('INDEX_REQUIRED_FIELD_MISSING',f'Required field {field} is missing','error',field)
    for field in NUMERIC:
        value=record.get(field)
        if value is None:continue
        if not is_finite_number(value):
            issue('INDEX_NON_FINITE_NUMERIC',f'{field} must be finite numeric','error',field,value);continue
        number=decimal_number(value)
        if field in QUANTITIES and number!=number.to_integral_value():
            issue('INDEX_NON_INTEGRAL_QUANTITY',f'{field} must be an exact integer','error',field,value);continue
        if field=='index_value' and number<=0:
            issue('INDEX_NON_POSITIVE_VALUE','index_value must be positive','error',field,value);continue
        if field in NON_NEGATIVE and number<0:
            issue('INDEX_NEGATIVE_COUNT_OR_TOTAL',f'{field} must be non-negative','error',field,value);continue
        valid[field]=number
    # No verified SSI monetary tolerance exists. Compare exact mathematical
    # totals; report differences as warnings, never replace source values.
    for total,match,deal in (('total_trade_volume','total_match_volume','total_deal_volume'),
                             ('total_trade_value','total_match_value','total_deal_value')):
        if all(f in valid for f in (total,match,deal)):
            expected=exact_binary(valid[match],valid[deal])
            if valid[total]!=expected:
                issue('INDEX_TOTAL_COMPONENT_MISMATCH',f'{total} differs from {match} + {deal}','warning',total,record[total],expected)
    for net,buy,sell in (('net_foreign_purchase_volume','total_foreign_buy_volume','total_foreign_sell_volume'),
                         ('net_foreign_purchase_value','total_foreign_buy_value','total_foreign_sell_value')):
        if all(f in valid for f in (net,buy,sell)):
            expected=exact_binary(valid[buy],valid[sell],'subtract')
            if valid[net]!=expected:
                issue('INDEX_FOREIGN_NET_MISMATCH',f'{net} differs from {buy} - {sell}','warning',net,record[net],expected)
    return ValidationResult(not errors,errors,warnings)
