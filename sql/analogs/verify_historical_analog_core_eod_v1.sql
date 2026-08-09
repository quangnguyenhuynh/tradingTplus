-- Read-only verification after manual migration.
select table_name from information_schema.tables where table_schema='public' and table_name in
('analog_profiles','analog_snapshots','analog_outcomes','analog_validation_runs','analog_profile_reviews','analog_queries','analog_query_matches') order by table_name;
select tablename,indexname,indexdef from pg_indexes where schemaname='public' and tablename like 'analog_%' order by tablename,indexname;
select tablename,rowsecurity from pg_tables where schemaname='public' and tablename like 'analog_%' order by tablename;
select grantee,table_name,privilege_type from information_schema.role_table_grants where table_schema='public' and table_name like 'analog_%' order by table_name,grantee,privilege_type;
