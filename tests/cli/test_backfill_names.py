"""Source-backfill CLI names and compatibility; all active runners are faked."""
import json
import socket
from pathlib import Path

import pytest
import requests

import src.cli as cli
import src.cli.index as index_cli
import src.cli.maintenance as maintenance_cli
from src.database.client import SupabaseClient
from src.providers.ssi.clients.rest_v3 import SSIV3Client

PAIRS = [('stock-eod-backfill', 'stock-eod-backfill', 'symbols', 'stock_daily'),
         ('stock-intraday-backfill', 'backfill-intraday', 'symbols', 'stock_intraday'),
         ('index-eod-backfill', 'index-eod-backfill', 'indexes', 'index_daily')]
NAMES = [name for canonical, legacy, *_ in PAIRS for name in (canonical, legacy)]


@pytest.fixture(autouse=True)
def no_external_services(monkeypatch):
    attempted = []
    def fail(*a, **kw):
        attempted.append(True)
        raise AssertionError('network/client/extra pipeline accessed')
    monkeypatch.setattr(requests.sessions.Session, 'request', fail)
    monkeypatch.setattr(socket, 'create_connection', fail)
    monkeypatch.setattr(SupabaseClient, '__init__', fail)
    monkeypatch.setattr(SSIV3Client, '__init__', fail)
    monkeypatch.setattr('src.ingest.stock_intraday.manual.run_manual_intraday', fail)
    monkeypatch.setattr(maintenance_cli, 'run_backfill_pipeline', fail)
    monkeypatch.setattr(maintenance_cli, 'run_intraday_backfill_pipeline', fail)
    yield
    assert not attempted


@pytest.mark.parametrize('canonical,legacy,scope,dataset', PAIRS)
@pytest.mark.parametrize('flags', [('--from', '--to'), ('--from-date', '--to-date')])
def test_alias_parser_arguments_identical(canonical, legacy, scope, dataset, flags):
    parser = cli.build_parser()
    namespaces = []
    for name in (canonical, legacy):
        args = parser.parse_args([name, flags[0], '01/10/2026', flags[1], '20/10/2026',
                                  '--' + scope, 'SSI' if scope == 'symbols' else 'VNINDEX', '--data-source', 'ssi_v3'])
        assert args.command == name  # argparse deliberately preserves invocation.
        values = vars(args); values.pop('command')
        namespaces.append(values)
    assert namespaces[0] == namespaces[1]
    assert namespaces[0]['from_date'] == '01/10/2026' and namespaces[0]['to_date'] == '20/10/2026'
    assert namespaces[0]['data_source'] == 'ssi_v3'


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('args', [[], ['--from', '01/10/2026'], ['--to-date', '20/10/2026'],
                                  ['--from', '01/10/2026', '--to', '20/10/2026', '--write'],
                                  ['--from', '01/10/2026', '--to', '20/10/2026', '--dry-run']])
def test_required_dates_and_unsupported_flags_before_dispatch(name, args, monkeypatch):
    monkeypatch.setattr(cli, 'import_module', lambda *_: pytest.fail('handler loaded'))
    assert cli.main([name, *args]) == 2


@pytest.mark.parametrize('name', NAMES + [None])
def test_all_help_is_offline_and_canonical_discoverable(name, capsys, monkeypatch):
    monkeypatch.setattr(cli, 'import_module', lambda *_: pytest.fail('handler loaded'))
    assert cli.main(([name] if name else []) + ['--help']) == 0
    text = capsys.readouterr().out
    if name is None:
        for canonical, legacy, *_ in PAIRS:
            assert (f'{canonical} ({legacy})' if canonical != legacy else canonical) in text
        assert 'read-only unless --write' in text
    else:
        canonical = next(c for c, old, *_ in PAIRS if name in (c, old))
        assert canonical in text


@pytest.mark.parametrize('scope', ['symbols', 'indexes'])
@pytest.mark.parametrize('status,exit_code', [('OK', 0), ('PARTIAL', 0), ('FAILED', 1)])
@pytest.mark.parametrize('source', [None, 'ssi_v3'])
def test_active_canonical_and_alias_same_runner_args_json_exit(scope, status, exit_code, source, monkeypatch, capsys):
    canonical, legacy = (PAIRS[0][:2] if scope == 'symbols' else PAIRS[2][:2])
    module = maintenance_cli if scope == 'symbols' else index_cli
    function = 'run_daily_backfill_pipeline' if scope == 'symbols' else 'run_index_backfill_pipeline'
    calls = []
    def runner(*args, **kwargs):
        calls.append((args, kwargs))
        return {'flow': legacy, 'status': status, 'day_summaries': [{'flow': legacy + '-day'}], 'errors': []}
    monkeypatch.setattr(module, function, runner)
    inputs = ['ssi', ' HPG ', 'SSI'] if scope == 'symbols' else ['vnindex', ' HNXINDEX ', 'VNINDEX']
    for name in (canonical, legacy):
        argv = [name, '--from', '2026-10-01', '--to-date', '2026-10-20', '--' + scope, *inputs]
        if source: argv += ['--data-source', source]
        assert cli.main(argv) == exit_code
        output = capsys.readouterr()
        assert output.err == ''
        assert json.loads(output.out) == {'flow': legacy, 'status': status, 'day_summaries': [{'flow': legacy + '-day'}], 'errors': []}
    # Index normalization preserves first-seen spelling (master resolution is
    # case-insensitive); stock normalization uppercases. Keep both unchanged.
    expected = {scope: ['SSI', 'HPG'] if scope == 'symbols' else ['vnindex', 'HNXINDEX']}
    if source: expected['data_source'] = source
    assert calls == [(('2026-10-01', '2026-10-20'), expected)] * 2


@pytest.mark.parametrize('name', ['stock-eod-backfill', 'stock-eod-backfill', 'index-eod-backfill', 'index-eod-backfill'])
def test_omitted_scope_and_source_preserve_defaults(name, monkeypatch, capsys):
    index = name.startswith('index-')
    module = index_cli if index else maintenance_cli
    calls = []
    def runner(*args, **kwargs): calls.append((args, kwargs)); return {'status': 'OK'}
    monkeypatch.setattr(module, 'run_index_backfill_pipeline' if index else 'run_daily_backfill_pipeline', runner)
    assert cli.main([name, '--from', '01/10/2026', '--to', '20/10/2026']) == 0
    assert calls == [(('01/10/2026', '20/10/2026'), {'indexes' if index else 'symbols': None})]


@pytest.mark.parametrize('canonical,legacy,scope,dataset', PAIRS)
def test_source_preflight_uses_correct_dataset_without_adapter(canonical, legacy, scope, dataset, monkeypatch):
    seen = []
    monkeypatch.setattr(cli, 'resolve_source', lambda ds, source, **kw: seen.append((ds, source, kw)))
    if dataset == 'stock_intraday':
        monkeypatch.setattr(maintenance_cli, 'run_intraday_backfill_pipeline', lambda *a, **kw: {'status': 'OK'})
    else:
        module = index_cli if dataset == 'index_daily' else maintenance_cli
        monkeypatch.setattr(module, 'run_index_backfill_pipeline' if dataset == 'index_daily' else 'run_daily_backfill_pipeline', lambda *a, **kw: {'status': 'OK'})
    for name in (canonical, legacy):
        assert cli.main([name, '--from', '01/10/2026', '--to', '20/10/2026', '--' + scope, 'SSI' if scope == 'symbols' else 'VNINDEX', '--data-source', 'ssi_v3']) == 0
    assert seen == [(dataset, 'ssi_v3', {'production': dataset != 'stock_intraday'})] * 2


@pytest.mark.parametrize('name', ['stock-intraday-backfill', 'backfill-intraday'])
@pytest.mark.parametrize('source', [None, 'ssi_v3'])
def test_intraday_names_both_route_guarded_runner(name, source, monkeypatch, capsys):
    captured = []
    monkeypatch.setattr(maintenance_cli, 'run_intraday_backfill_pipeline',
                        lambda *a, **kw: captured.append((a, kw)) or {'status': 'OK', 'flow': 'backfill-intraday'})
    argv = [name, '--from-date', '01/10/2026', '--to-date', '20/10/2026', '--symbols', 'SSI', 'HPG']
    if source: argv += ['--data-source', source]
    assert cli.main(argv) == 0
    assert json.loads(capsys.readouterr().out)['flow'] == 'backfill-intraday'
    expected = {'symbols': ['SSI', 'HPG'], 'write': False}
    if source: expected['data_source'] = source
    assert captured == [(('01/10/2026', '20/10/2026'), expected)]


@pytest.mark.parametrize('name', NAMES)
def test_rejected_source_preserves_exit_two_before_handler(name, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'import_module', lambda *_: pytest.fail('handler loaded'))
    assert cli.main([name, '--from', '01/10/2026', '--to', '20/10/2026', *(['--symbols', 'SSI'] if 'intraday' in name else []), '--data-source', 'ssi_v2']) == 2
    assert 'unsupported data source: ssi_v2' in capsys.readouterr().err


def test_no_normalization_of_unrelated_commands():
    assert cli.BACKFILL_COMMANDS == {'stock-intraday-backfill': 'backfill-intraday'}


def test_documented_primary_names_and_guarded_intraday():
    for language in ('md', 'vi.md'):
        runbook = Path(f'docs/backfill/README.{language}').read_text()
        for canonical, legacy, *_ in PAIRS:
            assert f'`{canonical}`' in runbook and f'`{legacy}`' in runbook
        assert 'NOT_IMPLEMENTED' in runbook
        assert 'python main.py stock-intraday-backfill --help' in runbook
        assert 'python main.py stock-intraday-backfill --from' in runbook
        assert 'DRY_RUN' in runbook
        assert 'python main.py stock-eod-backfill --from' in runbook
        assert 'python main.py index-eod-backfill --from' in runbook
