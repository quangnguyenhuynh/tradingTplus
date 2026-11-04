"""Read-only daily numeric diagnostics; no SSI or persistence entrypoint."""
from .common import _print_summary
from src.quality.daily_numeric_diagnostics import inspect_daily_numeric


def run(args):
    if args.date and args.to_date or args.from_date and not args.to_date:
        raise ValueError('Use --date alone or --from/--to together')
    try:
        result=inspect_daily_numeric(args.dataset,args.identifiers,args.date or args.from_date,args.to_date)
    except ValueError:raise
    except Exception:
        _print_summary(dict(flow='daily-numeric-quality',mode='READ_ONLY',status='FAILED',
                            error_type='EXACT_DIAGNOSTIC_READ_FAILED_APPLY_20261104_DAILY_NUMERIC_PRECISION'))
        return 1
    _print_summary(result)
    return 0
