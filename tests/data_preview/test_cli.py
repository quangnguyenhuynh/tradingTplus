import json
import main

def fake(*args,**kwargs):
 return {'mode':'PREVIEW — no database writes','dataset':args[0],'requested_date':args[2],'status':'OK','records':[],'raw':{'x':1}}

def test_cli_default_source_json_without_database(monkeypatch,capsys):
 monkeypatch.setattr(main,'run_preview',fake)
 assert main.main(['data-preview','stock-daily','--symbol','SSI','--date','08/09/2026','--format','json'])==0
 assert json.loads(capsys.readouterr().out)['dataset']=='stock_daily'

def test_cli_source_compare_exclusive_and_only_diff_scope(capsys):
 assert main.main(['data-preview','stock-daily','--symbol','SSI','--date','08/09/2026','--data-source','ssi_v2','--compare','ssi_v2','ssi_v3'])==2
 assert main.main(['data-preview','stock-daily','--symbol','SSI','--date','08/09/2026','--only-diff'])==2
