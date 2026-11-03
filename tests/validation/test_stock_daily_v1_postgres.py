"""Atomic CLEAN/issue and migration tests on local disposable PostgreSQL only."""
import os
from pathlib import Path
from urllib.parse import urlparse
import uuid
import runpy
import pytest
psycopg=pytest.importorskip('psycopg')
from psycopg.types.json import Jsonb
from src.quality.validators.stock_daily_v1 import validate_payload
from src.ingest.stock_daily.daily_mapper import build_raw_daily_record
SAMPLE=runpy.run_path('tests/data_sources/test_ssi_v3_stock_daily.py')['SAMPLE']

@pytest.fixture
def db():
 url=os.getenv('TEST_DATABASE_URL')
 if not url:pytest.skip('Disposable TEST_DATABASE_URL required')
 if urlparse(url).hostname not in ('localhost','127.0.0.1','postgres'):pytest.skip('Only local disposable PostgreSQL allowed')
 c=psycopg.connect(url,autocommit=True);s='quality_test_'+uuid.uuid4().hex
 c.execute(f'create schema {s}')
 base=Path('migrations/20260706_complete_ssi_ingest_schema.sql').read_text()
 base=base[base.index('create table if not exists public.stock_daily'):base.index('create table if not exists public.index_daily')]
 c.execute(base.replace('public.',s+'.'))
 c.execute(f'alter table {s}.stock_daily add column source text')
 c.execute(f'''create table {s}.stock_raw_daily(symbol text,trading_date date,source text,data_hash text,payload jsonb,created_at timestamptz,
 unique(symbol,trading_date,source,data_hash));
 create table {s}.stock_data_quality_logs(id bigserial primary key,symbol text not null,trading_date date not null,
 timeframe text,check_name text,severity text,status text,issue_count integer,details jsonb,created_at timestamptz,
 unique(symbol,trading_date,check_name));''')
 # Reproduce the inspected current schema, including both October migrations.
 for name in ('20261002_promote_stock_daily_ssi_v3.sql','20261002_rename_stock_daily_foreign_remaining_room.sql'):
  prior=Path('migrations',name).read_text().replace('public.',s+'.').replace("'public'",f"'{s}'")
  c.execute(prior)
 for role in ('anon','authenticated','service_role'):
  c.execute(f'do $$ begin create role {role}; exception when duplicate_object then null; end $$')
 sql=Path('migrations/20261103_stock_daily_quality_v1.sql').read_text().replace('public.',s+'.')
 c.execute(f"insert into {s}.stock_daily(symbol,trading_date) values('LEGACY','2020-01-01')")
 c.execute(sql);c.execute(sql)
 assert c.execute(f"select validation_status from {s}.stock_daily where symbol='LEGACY'").fetchone()==(None,)
 def call(payload):
  candidate,report=validate_payload(payload,'SSI','01/10/2026')
  report['processed_at']='2026-11-03T00:00:00+00:00'
  raw=build_raw_daily_record('SSI','01/10/2026',payload)
  c.execute(f'insert into {s}.stock_raw_daily(symbol,trading_date,source,data_hash,payload) values(%s,%s,%s,%s,%s) on conflict do nothing',
            ('SSI','2026-10-01','ssi_v3',raw['data_hash'],Jsonb(payload)))
  return c.execute(f'select {s}.persist_stock_daily_validation_v1(%s,%s,%s,%s,%s)',
            ('SSI','2026-10-01',raw['data_hash'],Jsonb(candidate),Jsonb(report))).fetchone()[0]
 yield c,s,call
 c.execute(f'drop schema {s} cascade');c.close()

def test_valid_without_issue_log_and_rejected_never_overwrites(db):
 c,s,call=db
 assert call(SAMPLE)['decision']=='VALID'
 assert c.execute(f'select count(*) from {s}.stock_data_quality_logs').fetchone()==(0,)
 assert call({**SAMPLE,'open':None})['decision']=='REJECTED'
 assert c.execute(f"select validation_status,open_price from {s}.stock_daily where symbol='SSI'").fetchone()==('VALID',20150)
 assert c.execute(f'select status from {s}.stock_data_quality_logs').fetchone()==('ACTIVE',)

def test_partial_idempotency_resolution_and_downgrade_block(db):
 c,s,call=db
 bad={**SAMPLE,'remainForeignRoom':-1}
 for _ in range(3):assert call(bad)['decision']=='PARTIAL'
 assert c.execute(f"select foreign_remaining_room,validation_status from {s}.stock_daily where symbol='SSI'").fetchone()==(None,'PARTIAL')
 row=c.execute(f'select details from {s}.stock_data_quality_logs').fetchone()[0]
 assert row['history']==[] and row['issues'][0]['code']=='BELOW_MINIMUM'
 assert call(SAMPLE)['decision']=='VALID'
 assert c.execute(f'select status,issue_count from {s}.stock_data_quality_logs').fetchone()==('RESOLVED',0)
 assert call(bad)['decision']=='REJECTED'
 assert c.execute(f"select validation_status,foreign_remaining_room from {s}.stock_daily where symbol='SSI'").fetchone()==('VALID',2100488217)
 for _ in range(3):call(SAMPLE);call(bad)
 assert c.execute(f'select count(*) from {s}.stock_data_quality_logs').fetchone()==(1,)
 assert len(c.execute(f'select details from {s}.stock_data_quality_logs').fetchone()[0]['history'])<=3

@pytest.mark.parametrize('value',[None,-1])
def test_null_does_not_erase_legacy_known_field(db,value):
 c,s,call=db
 c.execute(f"insert into {s}.stock_daily(symbol,trading_date,foreign_remaining_room) values('SSI','2026-10-01',123)")
 result=call({**SAMPLE,'remainForeignRoom':value})
 assert result['decision']=='PARTIAL' and 'foreign_remaining_room' in result['preserved_fields']
 assert c.execute(f"select foreign_remaining_room from {s}.stock_daily where symbol='SSI'").fetchone()==(123,)


def test_log_failure_rolls_back_clean_but_raw_survives(db):
 c,s,call=db
 c.execute(f"alter table {s}.stock_data_quality_logs add constraint fail_log check(check_name<>'stock_daily_validation_v1')")
 with pytest.raises(psycopg.Error):call({**SAMPLE,'remainForeignRoom':-1})
 assert c.execute(f"select count(*) from {s}.stock_daily where symbol='SSI'").fetchone()==(0,)
 assert c.execute(f'select count(*) from {s}.stock_raw_daily').fetchone()==(1,)

def test_rpc_invoker_and_permissions(db):
 c,s,call=db
 row=c.execute("select prosecdef,has_function_privilege('anon',p.oid,'execute'),has_function_privilege('service_role',p.oid,'execute') from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname=%s and p.proname='persist_stock_daily_validation_v1'",(s,)).fetchone()
 assert row==(False,False,True)

@pytest.mark.parametrize('table',['stock_daily','stock_data_quality_logs'])
def test_trigger_ignored_write_cannot_report_success(db,table):
 c,s,call=db
 c.execute(f'create function {s}.ignore_insert() returns trigger language plpgsql as $$ begin return null; end $$')
 c.execute(f'create trigger ignore_insert before insert on {s}.{table} for each row execute function {s}.ignore_insert()')
 with pytest.raises(psycopg.Error,match='readback'):call({**SAMPLE,'remainForeignRoom':-1})
 assert c.execute(f"select count(*) from {s}.stock_daily where symbol='SSI'").fetchone()==(0,)
