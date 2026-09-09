import main
import pytest


@pytest.mark.parametrize('dataset', ['stock-daily', 'stock-intraday', 'index-daily'])
def test_data_preview_removed_from_production_cli(dataset, capsys):
    assert main.main(['data-preview', dataset]) == 2
    assert 'invalid choice' in capsys.readouterr().err


def test_production_help_has_no_data_preview(capsys):
    assert main.main(['--help']) == 0
    assert 'data-preview' not in capsys.readouterr().out
    assert not hasattr(main, 'run_preview') and not hasattr(main, 'render_preview')
