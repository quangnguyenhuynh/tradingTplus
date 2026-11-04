"""Exact daily numeric arithmetic and JSON tokens; no database or source access."""
from decimal import Decimal, InvalidOperation, localcontext
import json
import math
import re

NUMBER = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z')


def is_finite_number(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, Decimal):
        return value.is_finite()
    return isinstance(value, int) or isinstance(value, float) and math.isfinite(value)


def exact_abs(value):
    return value.copy_abs() if isinstance(value, Decimal) else abs(value)


def decimal_number(value):
    """A predecoded float preserves only its displayed value, never lost digits."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError('expected finite decimal')
    text = str(value).strip()
    if not NUMBER.fullmatch(text):
        raise ValueError('expected finite decimal')
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError('expected finite decimal') from exc
    if not number.is_finite():
        raise ValueError('expected finite decimal')
    return number


def integer_number(value):
    number = decimal_number(value)
    if number != number.to_integral_value():
        raise ValueError('expected exact integer quantity')
    return int(number)


def exact_binary(left, right, operation='add'):
    """Add/subtract/multiply finite numbers without Decimal context rounding."""
    if isinstance(left, int) and isinstance(right, int):
        return left + right if operation == 'add' else left - right if operation == 'subtract' else left * right
    a, b = decimal_number(left), decimal_number(right)
    if operation == 'multiply':
        precision = len(a.as_tuple().digits) + len(b.as_tuple().digits) + 2
    else:
        precision = max(a.adjusted(), b.adjusted()) - min(a.as_tuple().exponent, b.as_tuple().exponent) + 3
    with localcontext() as context:
        context.prec = max(precision, 1)
        # No arbitrary application scale; PostgreSQL's documented NUMERIC limits
        # remain the final storage limits. Widen arithmetic exponent bounds.
        context.Emax = max(context.Emax, a.adjusted() + b.adjusted() + 2)
        context.Emin = min(context.Emin, a.as_tuple().exponent + b.as_tuple().exponent - 2)
        return a + b if operation == 'add' else a - b if operation == 'subtract' else a * b


def exact_json_dumps(value, *, sort_keys=False, separators=(',', ':'), ensure_ascii=False, indent=None, _level=0):
    """Emit Decimal as JSON number tokens, never float or quoted numeric strings.

    RPC text parameters carry these bytes through the SDK's ordinary encoder;
    SQL casts that text to JSONB before numeric population/readback. Strings in
    original RAW stay strings. Legacy float input cannot regain source precision.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return json.dumps(value, ensure_ascii=ensure_ascii)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError('Non-finite JSON decimal')
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('Non-finite JSON float')
        return json.dumps(value, allow_nan=False)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError('JSON object keys must be strings')
        keys = sorted(value) if sort_keys else value
        parts=[json.dumps(key, ensure_ascii=ensure_ascii) + (': ' if indent is not None else separators[1]) + exact_json_dumps(value[key], sort_keys=sort_keys, separators=separators, ensure_ascii=ensure_ascii,indent=indent,_level=_level+1) for key in keys]
        if indent is not None and parts:
            padding=' '*(indent*(_level+1))
            return '{\n'+padding+(',\n'+padding).join(parts)+'\n'+' '*(indent*_level)+'}'
        return '{' + separators[0].join(parts) + '}'
    if isinstance(value, (list, tuple)):
        parts=[exact_json_dumps(item, sort_keys=sort_keys, separators=separators, ensure_ascii=ensure_ascii,indent=indent,_level=_level+1) for item in value]
        if indent is not None and parts:
            padding=' '*(indent*(_level+1))
            return '[\n'+padding+(',\n'+padding).join(parts)+'\n'+' '*(indent*_level)+']'
        return '[' + separators[0].join(parts) + ']'
    raise TypeError(f'Unsupported exact JSON type: {type(value).__name__}')


def exact_json_loads(text):
    def reject_constant(_):
        raise ValueError('Non-finite JSON constant')
    return json.loads(text, parse_float=Decimal, parse_constant=reject_constant)
