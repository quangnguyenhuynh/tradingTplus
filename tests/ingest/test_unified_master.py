"""Unified scope, compatibility, source exceptions and migration safeguards."""
from pathlib import Path
from dataclasses import replace
import runpy
import pytest
from src.providers.ssi.adapters.master_v3 import map_verified_record,SSIV3MasterAdapter
from src.providers.ssi.master_contract import MasterSourceError
from src.providers.ssi.master_registry import MasterRegistry,MASTER_REGISTRY
from src.ingest.master.sync import run_master_sync
from src.ingest.master.store import MasterStore

fixtures=runpy.run_path('tests/ingest/test_ssi_v3_master_adapter.py')
MemoryClient=fixtures['MemoryClient']

def test_derivatives_exact_exception_only():
 row={'symbol':'41I1GC000','board':'DERIVATIVES','stockType':'Future'}
 mapped=map_verified_record('symbols',row,requested_board='HNX')
 assert mapped['market']=='DERIVATIVES' and mapped['sec_type']=='Future'
 for board,kind in [('HOSE','Future'),('HNX','Stock')]:
  with pytest.raises(MasterSourceError):
   map_verified_record('symbols',{**row,'stockType':kind},requested_board=board)
 with pytest.raises(MasterSourceError):map_verified_record('symbols',{'symbol':'VN50 GROWTH','board':'HOSE'})

def test_counted_index_exclusion_and_derivative_provenance():
 class Source:
  token=None
  def securities_by_board(self,board):
   if board=='HOSE':return [{'symbol':'SSI','board':'HOSE'},{'symbol':'VN50 GROWTH','board':'HOSE','stockType':None}]
   if board=='HNX':return [{'symbol':'41I1GC000','board':'DERIVATIVES','stockType':'Future'}]
   return [{'symbol':'UPC','board':'UPCOM'}]
 a=SSIV3MasterAdapter(Source(),reference={'counts':{}})
 snap=a.fetch('symbols')
 assert snap.complete and snap.source_records==4 and len(snap.records)==3 and len(snap.excluded_records)==1
 assert snap.excluded_records[0]['symbol']=='VN50 GROWTH'
 assert snap.pagination['boards'][1]['actual_markets']=={'DERIVATIVES':1}
 memory=MemoryClient('symbols');reg=MasterRegistry([replace(MASTER_REGISTRY.resolve('symbols'),factory=lambda:a)])
 report=run_master_sync('securities',write=True,registry=reg,store_factory=lambda:MasterStore(memory))
 assert report['dataset']==report['canonical_dataset']=='symbols'
 assert report['requested_dataset']=='securities' and report['warnings']
 assert report['actual_inserts']==3 and set(memory.tables)=={'symbols'}
 assert all(r['status']==r['intraday_status']=='inactive' for r in memory.tables['symbols'])
 assert report['datasets'][0]['excluded_records']==1
 memory.writes.clear()
 report=run_master_sync(registry=reg,store_factory=lambda:MasterStore(memory))
 assert len(report['datasets'])==3 and report['datasets'][0]['unchanged_records']==3 and not memory.writes

def test_missing_expansion_actionable_and_no_write():
 class Query:
  def table(self,*a):return self
  def select(self,*a,**k):return self
  def order(self,*a):return self
  def range(self,*a):return self
  def execute(self):raise RuntimeError('42703 column missing')
 with pytest.raises(MasterSourceError,match='APPLY_STAGE_A'):
  MasterStore(Query()).read('symbols')

def test_stage_a_structural_preservation_and_conflict_gate():
 sql=Path('migrations/20261027_expand_symbols_master.sql').read_text()
 assert sql.index('RAISE EXCEPTION')<sql.index('INSERT INTO public.symbols')
 assert 'IS DISTINCT FROM' in sql and 'COALESCE(symbols.' in sql
 assert "'inactive','inactive',NULL" in sql
 assert 'status=EXCLUDED' not in sql and 'created_at=EXCLUDED' not in sql
 assert 'DROP TABLE' not in sql and 'CASCADE' not in sql
 assert 'stock_name' in sql and 'ADD COLUMN IF NOT EXISTS stock_name' not in sql
 assert 'raw jsonb' in sql and 'listed_share numeric' in sql and 'LOCK TABLE' in sql
 assert sql.count('BEGIN;')==1 and sql.rstrip().endswith('rollback.')

def test_stage_b_opt_in_and_restrict():
 sql=Path('migrations/20261027_retire_securities_optional.sql').read_text()
 assert sql.index('app.approve_retire_securities')<sql.index('DROP TABLE public.securities RESTRICT')
 assert 'CASCADE;' not in sql and 'Unmigrated legacy identities' in sql
