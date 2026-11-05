"""Full JSON baselines captured on dev before the structure-only move."""
from copy import deepcopy
from datetime import date
import importlib
import inspect
import json
from pathlib import Path
from unittest.mock import patch
import pytest

BASELINE=Path(__file__).parents[1]/'fixtures'/'eod_backfill_baseline.json'
CASES={
 'mixed_explicit':dict(start='10/07/2026',end='14/07/2026',scope='explicit',source='ssi_v3',states={'13/07/2026':'PARTIAL','14/07/2026':'FAILED'}),
 'omitted_scope':dict(start='13/07/2026',end='14/07/2026',scope=None),
 'weekend_only':dict(start='11/07/2026',end='12/07/2026',scope='explicit'),
 'exception_continuation':dict(start='13/07/2026',end='14/07/2026',scope='explicit',states={'13/07/2026':'RAISE'}),
 'failed_without_details':dict(start='13/07/2026',end='13/07/2026',scope='explicit',states={'13/07/2026':'FAILED'},details=False),
 'reversed':dict(start='14/07/2026',end='13/07/2026',scope='explicit'),
 'future':dict(start='06/11/2026',end='06/11/2026',scope='explicit'),
 'empty_scope':dict(start='13/07/2026',end='13/07/2026',scope=[]),
 'invalid_status':dict(start='13/07/2026',end='13/07/2026',scope='explicit',states={'13/07/2026':'UNRECOGNIZED'}),
 'source_before_range':dict(start='14/07/2026',end='13/07/2026',scope='explicit',source='blocked'),
}


def exercise(module,domain,spec):
    """Stub only source resolution and the existing per-day ingest boundary."""
    events=[]
    scope=([' ssi ','HPG','SSI'] if domain=='stock' else [' vnindex ','VN30','VNINDEX']) if spec['scope']=='explicit' else spec['scope']
    def resolve(dataset,source):
        events.append(dict(kind='resolve_source',dataset=dataset,source=source))
        if source=='blocked':raise ValueError('synthetic provider unavailable')
    def ingest(day,*args,**kwargs):
        events.append(dict(kind='ingest',args=deepcopy([day,*args]),kwargs=deepcopy(kwargs)))
        state=spec.get('states',{}).get(day,'OK')
        if state=='RAISE':raise RuntimeError('synthetic source outage')
        selected=(args[0] if args else kwargs.get('symbols'))
        selected=list(selected) if selected is not None else (['SSI','HPG'] if domain=='stock' else ['VNINDEX','VN30'])
        errors=[dict(error='synthetic rejection',error_type='MISMATCH')] if state=='FAILED' and spec.get('details',True) else []
        summary=dict(date=day,status=state,errors=errors,error_count=len(errors))
        if domain=='stock':
            summary.update(symbols=selected,symbol_count=len(selected),valid_clean_writes=2 if state=='OK' else 0,
                partial_clean_writes=1 if state=='PARTIAL' else 0,rejected_records=2 if state=='FAILED' else 0,
                mapping_failures=1 if state=='FAILED' else 0,persistence_failures=0,validation_issues=int(state!='OK'))
        else:
            summary.update(indexes=selected,index_count=len(selected),index_daily_count=2 if state=='OK' else 1 if state=='PARTIAL' else 0)
        return summary
    runner='run_daily_backfill_pipeline' if domain=='stock' else 'run_index_backfill_pipeline'
    dependency='run_daily_ingest' if domain=='stock' else 'run_index_daily_ingest'
    kwargs={'symbols' if domain=='stock' else 'indexes':scope}
    if 'source' in spec:kwargs['data_source']=spec['source']
    with patch.object(module,'resolve_source',resolve),patch.object(module,dependency,ingest),patch('src.ingest.shared.date_utils.today_vn',return_value=date(2026,11,5)):
        try:outcome=dict(result=getattr(module,runner)(spec['start'],spec['end'],**kwargs))
        except Exception as exc:outcome=dict(exception=dict(type=type(exc).__name__,message=str(exc)))
    return dict(events=events,**outcome)


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    import requests
    import httpx
    def fail(*args,**kwargs):pytest.fail('Offline backfill refactor tests must not call external services')
    monkeypatch.setattr(requests.sessions.Session,'request',fail)
    monkeypatch.setattr(httpx.Client,'send',fail)


@pytest.mark.parametrize('domain',['stock','index'])
@pytest.mark.parametrize('case',list(CASES))
def test_complete_json_matches_pre_refactor_dev(domain,case):
    baseline=json.loads(BASELINE.read_text())
    name='src.ingest.stock_daily.backfill' if domain=='stock' else 'src.ingest.index_daily.index_backfill'
    actual=exercise(importlib.import_module(name),domain,CASES[case])
    assert actual==baseline['cases'][domain][case]


def test_canonical_ownership_public_exports_and_compatibility():
    import src.ingest as public
    stock=importlib.import_module('src.ingest.stock_daily.backfill')
    index=importlib.import_module('src.ingest.index_daily.index_backfill')
    legacy=importlib.import_module('src.ingest.maintenance.backfill')
    shared=importlib.import_module('src.ingest.shared.backfill_range')
    assert public.run_daily_backfill_pipeline is stock.run_daily_backfill_pipeline is legacy.run_daily_backfill_pipeline
    assert public.run_index_backfill_pipeline is index.run_index_backfill_pipeline
    assert public.run_intraday_backfill_pipeline is legacy.run_intraday_backfill_pipeline
    assert legacy._run_ingest_backfill is stock._run_ingest_backfill
    for name in ('_BackfillRange','_resolve_range','_range_status','_failure_day','_base_range_summary'):
        assert getattr(legacy,name) is getattr(shared,name)
    for name in ('_resolve_range','_failure_day','_base_range_summary'):
        assert getattr(index,name) is getattr(shared,name)
    assert stock.run_daily_backfill_pipeline.__module__=='src.ingest.stock_daily.backfill'
    for name in ('run_intraday_ingest','run_manual_intraday','check_ingest'):
        assert not hasattr(stock,name)
    assert list(inspect.signature(stock.run_daily_backfill_pipeline).parameters)==['from_date','to_date','symbols','data_source']
    assert list(inspect.signature(index.run_index_backfill_pipeline).parameters)==['from_date','to_date','indexes','data_source']


def test_shared_calendar_stays_inclusive_and_weekend_only_is_noop():
    shared=importlib.import_module('src.ingest.shared.backfill_range')
    value=shared._resolve_range('2026-07-10','14/07/2026')
    assert value.eligible_dates==('10/07/2026','13/07/2026','14/07/2026')
    assert value.skipped_weekend_dates==('11/07/2026','12/07/2026')
    assert value.requested_calendar_days==5
    assert shared._resolve_range('11/07/2026','12/07/2026').eligible_dates==()


def test_index_and_shared_imports_do_not_depend_on_maintenance():
    import ast
    root=Path(__file__).parents[2]
    for name in ('src/ingest/index_daily/index_backfill.py','src/ingest/shared/backfill_range.py','src/ingest/stock_daily/backfill.py'):
        tree=ast.parse((root/name).read_text())
        assert not any(isinstance(node,ast.ImportFrom) and (node.module or '').startswith('src.ingest.maintenance') for node in ast.walk(tree))
