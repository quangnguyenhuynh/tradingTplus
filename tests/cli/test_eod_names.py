"""Public EOD command boundary; no network, ingest or database operations."""
import pytest
import src.cli as cli

CANONICAL=('stock-eod','stock-eod-backfill','index-eod','index-eod-backfill')
REMOVED=('daily','stock-daily','stock-daily-backfill','backfill-daily','index-daily','index-daily-backfill','index-backfill')

@pytest.mark.parametrize('name',REMOVED)
@pytest.mark.parametrize('tail',[[],['--help'],['28/10/2026'],['--from','01/10/2026','--to','28/10/2026']])
def test_removed_names_fail_before_dispatch(name,tail,monkeypatch,capsys):
 monkeypatch.setattr(cli,'import_module',lambda *_:pytest.fail('handler loaded'))
 assert cli.main([name,*tail])==2
 assert 'invalid choice' in capsys.readouterr().err

@pytest.mark.parametrize('name',CANONICAL)
def test_canonical_help_offline(name,monkeypatch,capsys):
 monkeypatch.setattr(cli,'import_module',lambda *_:pytest.fail('handler loaded'))
 assert cli.main([name,'--help'])==0
 text=capsys.readouterr().out
 assert name in text
 for removed in REMOVED:assert f'main.py {removed} [' not in text

def test_parser_has_no_hidden_aliases_and_preserves_other_commands():
 parser=cli.build_parser();choices=next(a for a in parser._actions if hasattr(a,'choices') and isinstance(a.choices,dict)).choices
 assert set(CANONICAL)<=set(choices) and not set(REMOVED)&set(choices)
 for name in ('features-daily','features-intraday','index-features-daily','index-features-backfill','foreign-features-daily',
              'index-preview','index-check','analogs','stock-intraday','stock-intraday-backfill','sync-master-data'):
  assert name in choices

@pytest.mark.parametrize('name,dataset',[('stock-eod','stock_daily'),('stock-eod-backfill','stock_daily'),
 ('index-eod','index_daily'),('index-eod-backfill','index_daily')])
def test_correct_source_before_domain_dispatch(name,dataset,monkeypatch):
 seen=[]
 monkeypatch.setattr(cli,'resolve_source',lambda ds,source,**kw:seen.append((ds,source,kw)))
 class Handler:
  @staticmethod
  def run(args):
   assert args.command==name
   return 0
 monkeypatch.setattr(cli,'import_module',lambda *_:Handler)
 tail=['--from','01/10/2026','--to','28/10/2026'] if name.endswith('backfill') else []
 assert cli.main([name,*tail,'--data-source','ssi_v3'])==0
 assert seen==[(dataset,'ssi_v3',{'production':True})]

def test_public_internal_apis_still_exported():
 import src.ingest as ingest
 for name in ('daily_run','run_daily_ingest','run_stock_eod_pipeline','run_index_daily_ingest',
              'run_index_backfill_pipeline','run_daily_backfill_pipeline'):
  assert callable(getattr(ingest,name))
