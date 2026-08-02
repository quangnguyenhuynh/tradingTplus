"""Real PostgreSQL contract tests for the atomic feature replacement RPC."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")


@pytest.fixture()
def connection():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required locally; CI always provides PostgreSQL")
    conn = psycopg.connect(url, autocommit=True)
    with conn.cursor() as cursor:
        cursor.execute("drop schema if exists public cascade; create schema public")
        cursor.execute("do $$ begin create role anon; exception when duplicate_object then null; end $$")
        cursor.execute("do $$ begin create role authenticated; exception when duplicate_object then null; end $$")
        cursor.execute("do $$ begin create role service_role; exception when duplicate_object then null; end $$")
        cursor.execute("""
            create table public.features (
              symbol text not null, timeframe text not null, time timestamptz not null,
              close double precision, volume bigint,
              primary key(symbol, timeframe, time)
            )
        """)
        cursor.execute(Path("migrations/20260802_atomic_replace_features.sql").read_text())
    yield conn
    conn.close()


def _call(conn, symbol="SSI", timeframe="15m", start="2026-07-01T00:00:00Z",
          end="2026-07-02T00:00:00Z", rows=None):
    rows = rows if rows is not None else [{
        "symbol": symbol, "timeframe": timeframe,
        "time": "2026-07-01T10:00:00Z", "close": 20.0, "volume": 200,
    }]
    with conn.cursor() as cursor:
        cursor.execute(
            "select * from public.replace_features_atomic(%s,%s,%s,%s,%s::jsonb)",
            (symbol, timeframe, start, end, json.dumps(rows)),
        )
        return cursor.fetchone()


def test_atomic_function_security_privileges_exact_scope_and_counts(connection):
    with connection.cursor() as cursor:
        cursor.execute("""
          select p.prosecdef, p.proconfig,
            has_function_privilege('service_role', p.oid, 'execute'),
            has_function_privilege('anon', p.oid, 'execute'),
            has_function_privilege('authenticated', p.oid, 'execute'),
            has_function_privilege('public', p.oid, 'execute')
          from pg_proc p join pg_namespace n on n.oid=p.pronamespace
          where n.nspname='public' and p.proname='replace_features_atomic'
        """)
        assert cursor.fetchone() == (True, ["search_path=\"\""], True, False, False, False)
        cursor.execute("""
          insert into public.features values
          ('SSI','15m','2026-06-30T23:59:00Z',1,1),
          ('SSI','15m','2026-07-01T10:00:00Z',10,100),
          ('SSI','15m','2026-07-02T00:00:00Z',2,2),
          ('HPG','15m','2026-07-01T10:00:00Z',3,3),
          ('SSI','60m','2026-07-01T10:00:00Z',4,4)
        """)
    assert _call(connection) == (1, 1)
    with connection.cursor() as cursor:
        cursor.execute("select symbol,timeframe,close from public.features order by symbol,timeframe,time")
        values = cursor.fetchall()
    assert ("SSI", "15m", 20.0) in values
    assert len(values) == 5


@pytest.mark.parametrize("args", [
    {"symbol": "*"}, {"timeframe": "5m"},
    {"start": "2026-07-02T00:00:00Z", "end": "2026-07-01T00:00:00Z"},
    {"rows": []},
    {"rows": [
        {"symbol": "SSI", "timeframe": "15m", "time": "2026-07-01T10:00:00Z"},
        {"symbol": "SSI", "timeframe": "15m", "time": "2026-07-01T10:00:00Z"},
    ]},
])
def test_atomic_rejects_invalid_scopes_and_payloads(connection, args):
    with pytest.raises(psycopg.Error):
        _call(connection, **args)


def test_atomic_insert_failure_rolls_back_delete(connection):
    with connection.cursor() as cursor:
        cursor.execute("insert into public.features values ('SSI','15m','2026-07-01T10:00:00Z',10,100)")
    bad = [{"symbol": "SSI", "timeframe": "15m", "time": "2026-07-01T10:00:00Z", "volume": "not-a-bigint"}]
    with pytest.raises(psycopg.Error):
        _call(connection, rows=bad)
    with connection.cursor() as cursor:
        cursor.execute("select close,volume from public.features where symbol='SSI' and timeframe='15m'")
        assert cursor.fetchall() == [(10.0, 100)]
