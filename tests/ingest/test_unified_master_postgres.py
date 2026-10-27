"""Execute real migrations only on explicitly local disposable test PostgreSQL."""
import os
from pathlib import Path
from urllib.parse import urlparse
import uuid
import pytest
psycopg=pytest.importorskip('psycopg')

@pytest.fixture
def db():
 url=os.getenv('TEST_DATABASE_URL')
 if not url:pytest.skip('Local disposable TEST_DATABASE_URL required')
 if urlparse(url).hostname not in ('localhost','127.0.0.1','postgres'):
  pytest.skip('Migration writes are restricted to local disposable PostgreSQL')
 schema='master_test_'+uuid.uuid4().hex
 conn=psycopg.connect(url,autocommit=True)
 conn.execute(f'create schema {schema}')
 base=Path('migrations/20260706_complete_ssi_ingest_schema.sql').read_text()
 base=base[base.index('create table if not exists public.securities'):base.index('create table if not exists public.stock_daily')]
 conn.execute(base.replace('public.',schema+'.'))
 conn.execute(f'''create table {schema}.symbols(symbol text primary key,market text,name text,created_at timestamptz,
 status text not null default 'active',intraday_status text not null default 'inactive')''')
 conn.execute(f"insert into {schema}.symbols values ('SSI','HOSE','Existing','2020-01-01','inactive','active')")
 conn.execute(f'create table {schema}.dependent(symbol text references {schema}.symbols(symbol))')
 conn.execute(f"insert into {schema}.dependent values ('SSI')")
 def migration(name):return Path('migrations/'+name).read_text().replace('public.',schema+'.').replace("'public'::regnamespace",f"'{schema}'::regnamespace")
 yield conn,schema,migration
 conn.execute('rollback')
 conn.execute(f'drop schema {schema} cascade')
 conn.close()

def test_expand_precision_flags_nulls_raw_foreign_keys_and_rerun(db):
 c,s,m=db
 c.execute(f'''insert into {s}.securities(symbol,stock_name,market,lot_size,raw) values
 ('SSI','Existing',NULL,123.456789012345678901,'{{"keep":true}}'),('NEW','New', 'HNX',9007199254740993,'{{"n":1}}')''')
 sql=m('20261027_expand_symbols_master.sql');c.execute(sql);c.execute(sql)
 assert c.execute(f"select status,intraday_status,created_at::date::text,market,lot_size::text,raw from {s}.symbols where symbol='SSI'").fetchone()==('inactive','active','2020-01-01','HOSE','123.456789012345678901',{'keep':True})
 assert c.execute(f"select status,intraday_status,lot_size::text from {s}.symbols where symbol='NEW'").fetchone()==('inactive','inactive','9007199254740993')
 assert c.execute(f'select count(*) from {s}.dependent').fetchone()==(1,)
 with pytest.raises(psycopg.Error,match='explicit owner approval'):c.execute(m('20261027_retire_securities_optional.sql'))
 c.execute('rollback')
 assert c.execute(f'select count(*) from {s}.securities').fetchone()==(2,)

@pytest.mark.parametrize('name,market',[('Conflict','HOSE'),('Existing','HNX')])
def test_conflicts_rollback_expansion_without_mutation(db,name,market):
 c,s,m=db
 c.execute(f'insert into {s}.securities(symbol,stock_name,market) values (%s,%s,%s)',('SSI',name,market))
 with pytest.raises(psycopg.Error,match='master merge conflicts'):c.execute(m('20261027_expand_symbols_master.sql'))
 c.execute('rollback')
 assert c.execute(f"select name,market,status,intraday_status from {s}.symbols where symbol='SSI'").fetchone()==('Existing','HOSE','inactive','active')
 assert c.execute('select count(*) from information_schema.columns where table_schema=%s and table_name=%s and column_name=%s',(s,'symbols','lot_size')).fetchone()==(0,)
