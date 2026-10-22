"""CLI pilot scope and mode regressions; all external services are faked."""
import json
import pytest
from src.cli import main


@pytest.mark.parametrize('argv', [[], ['2026-10-20'], ['--symbols', 'SSI'],
    ['2026-10-20', '--symbols', 'SSI', 'HPG'], ['2026-10-20', '--symbols', 'SSI', 'SSI'],
    ['2026-10-20', '--symbols', 'ALL'], ['2026-10-20', '--symbols', '*'],
    ['2026-10-20', '--symbols', 'SSI,HPG'], ['2999-01-01', '--symbols', 'SSI'],
    ['invalid', '--symbols', 'SSI']])
def test_cli_rejects_scope_before_clients(argv, monkeypatch):
    def fail(*a, **k): raise AssertionError('unexpected service')
    monkeypatch.setattr('src.ingest.stock_intraday.manual.SSIV3Adapter', fail)
    monkeypatch.setattr('src.ingest.stock_intraday.manual.SupabaseClient', fail)
    assert main(['stock-intraday', *argv]) == 2


@pytest.mark.parametrize('flags,write', [([], False), (['--dry-run'], False), (['--write'], True)])
def test_cli_passes_only_explicit_write(flags, write, monkeypatch, capsys):
    seen = []
    def fake(date, **kwargs):
        seen.append((date, kwargs))
        return {'status': 'OK', 'mode': 'WRITE' if kwargs['write'] else 'DRY_RUN'}
    monkeypatch.setattr('src.cli.stock.run_stock_intraday_pipeline', fake)
    assert main(['stock-intraday', '2026-10-20', '--symbols', 'SSI', '--data-source', 'ssi_v3', *flags]) == 0
    assert seen == [('2026-10-20', {'symbols': ['SSI'], 'write': write, 'data_source': 'ssi_v3'})]
    assert json.loads(capsys.readouterr().out)['mode'] == ('WRITE' if write else 'DRY_RUN')


@pytest.mark.parametrize('status', ['PARTIAL', 'BLOCKED', 'FAILED'])
def test_cli_failures_are_nonzero(status, monkeypatch):
    monkeypatch.setattr('src.cli.stock.run_stock_intraday_pipeline', lambda *a, **k: {'status': status})
    assert main(['stock-intraday', '2026-10-20', '--symbols', 'SSI', '--write']) == 1


def test_cli_modes_mutually_exclusive():
    assert main(['stock-intraday', '2026-10-20', '--symbols', 'SSI', '--write', '--dry-run']) == 2


def test_cli_source_checks_intraday_dataset(monkeypatch):
    seen = []
    def resolve(dataset, source, **kwargs): seen.append((dataset, source, kwargs))
    monkeypatch.setattr('src.cli.resolve_source', resolve)
    monkeypatch.setattr('src.cli.stock.run_stock_intraday_pipeline', lambda *a, **k: {'status': 'OK'})
    assert main(['stock-intraday', '2026-10-20', '--symbols', 'SSI', '--data-source', 'ssi_v3']) == 0
    assert seen == [('stock_intraday', 'ssi_v3', {'production': False})]


def test_cli_rejects_v2_before_handler(monkeypatch):
    def fail(*a, **k): raise AssertionError('handler loaded')
    monkeypatch.setattr('src.cli.import_module', fail)
    assert main(['stock-intraday', '2026-10-20', '--symbols', 'SSI', '--data-source', 'ssi_v2']) == 2
