-- Read-only verification after manual migration.
select table_name from information_schema.tables where table_schema='public' and table_name in
('analog_profiles','analog_snapshots','analog_outcomes','analog_validation_runs','analog_profile_reviews','analog_queries','analog_query_matches') order by table_name;
select tablename,indexname,indexdef from pg_indexes where schemaname='public' and tablename like 'analog_%' order by tablename,indexname;
select tablename,rowsecurity from pg_tables where schemaname='public' and tablename like 'analog_%' order by tablename;
select grantee,table_name,privilege_type from information_schema.role_table_grants where table_schema='public' and table_name like 'analog_%' order by table_name,grantee,privilege_type;
select routine_name,security_type from information_schema.routines where routine_schema='public' and routine_name in ('analog_jsonb_object_size','persist_analog_query_v1') order by routine_name;
select conrelid::regclass as table_name,conname,pg_get_constraintdef(oid) as definition from pg_constraint where connamespace='public'::regnamespace and conrelid::regclass::text like 'analog_%' order by 1,2;
