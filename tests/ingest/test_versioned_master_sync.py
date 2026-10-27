"""Offline CANONICAL contract fixtures, never evidence of SSI payload shapes."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import json
import socket

import pytest
import requests

from src.cli import main
from src.ingest.master.contracts import canonical_record, compare, DEFAULTS, KEYS
from src.ingest.master.store import MasterStore, MasterStoreError
from src.ingest.master.sync import run_master_sync
from src.providers.ssi.master_contract import MasterSnapshot, MasterCapability, MASTER_DATASETS, MasterSourceError
from src.providers.ssi.master_registry import MasterRegistry, MASTER_REGISTRY
from src.providers.ssi.adapters.master_v3 import SSIV3MasterAdapter, map_verified_record


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError("External service or downstream pipeline called")
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr("src.database.client.SupabaseClient._connect", forbidden)
    monkeypatch.setattr("src.providers.ssi.clients.rest_v3.SSIV3Client.__init__", forbidden)
    monkeypatch.setattr("src.ingest.stock_daily.daily.run_daily_ingest", forbidden)
    monkeypatch.setattr("src.ingest.stock_intraday.manual.run_manual_intraday", forbidden)
    monkeypatch.setattr("src.ingest.index_daily.index_daily.run_index_daily_ingest", forbidden)


ROWS = {
    "symbols": [{"symbol": "ssi", "market": "HOSE", "name": "Source confirmed name"}],
    "symbols": [{"symbol": "SSI", "name": "Source confirmed name", "lot_size": "100"}],
    "index_master": [{"index_code": "vnindex", "index_name": "Source confirmed index"}],
    "index_components": [{"index_code": "VNINDEX", "symbol": "ssi", "exchange": "HOSE"}],
}


def snapshot(dataset="symbols", **kwargs):
    return MasterSnapshot(dataset, deepcopy(ROWS[dataset]), 1, True, {"kind": "ALL"}, "test.canonical.1", **kwargs)


def registry_for(snap, *, source="test_provider", status="READY", order=1):
    class Provider:
        def fetch(self, dataset):
            assert dataset == snap.dataset
            return snap
    return MasterRegistry([MasterCapability(source, snap.dataset, order, status, True, Provider,
                                            "Synthetic canonical test data; NOT SSI evidence")])


class MemoryClient:
    def __init__(self, dataset, rows=()):
        self.tables = {dataset: deepcopy(list(rows))}
        self.writes = []
        self.fail_write = None
        self.fail_readback = False
        self.corrupt_readback = False

    def table(self, name):
        assert name in MASTER_DATASETS
        self.tables.setdefault(name, [])
        return Query(self, name)


class Query:
    def __init__(self, client, table):
        self.client, self.table = client, table
        self.filters, self.orders = [], []
        self.action, self.payload, self.bounds, self.cap = "read", None, None, None

    def select(self, *args, **kwargs): return self
    def order(self, key): self.orders.append(key); return self
    def range(self, start, end): self.bounds = (start, end); return self
    def limit(self, cap): self.cap = cap; return self
    def eq(self, key, value):
        self.filters.append((key, json.loads(value) if key == "raw" and isinstance(value, str) else value))
        return self
    def is_(self, key, value): assert value == "null"; return self.eq(key, None)
    def update(self, payload): self.action, self.payload = "update", payload; return self
    def upsert(self, payload, on_conflict, ignore_duplicates):
        assert ignore_duplicates is True and on_conflict == ",".join(KEYS[self.table])
        self.action, self.payload = "insert", payload
        return self

    def execute(self):
        client = self.client
        table = client.tables[self.table]
        rows = [r for r in table if all(r.get(k) == v for k, v in self.filters)]
        if self.action != "read":
            assert not ({"status", "intraday_status"} & self.payload.keys()) or self.action == "insert"
            client.writes.append((self.action, deepcopy(self.payload)))
            if client.fail_write:
                raise client.fail_write
            if self.action == "insert":
                if any(all(r[k] == self.payload[k] for k in KEYS[self.table]) for r in table):
                    rows = []
                else:
                    table.append(deepcopy(self.payload)); rows = [table[-1]]
            else:
                for r in rows: r.update(self.payload)
        elif self.cap is not None and client.writes:
            if client.fail_readback: raise RuntimeError("secret response")
            if client.corrupt_readback: rows = []
        count = len(rows)
        for key in reversed(self.orders): rows.sort(key=lambda r: r[key])
        if self.bounds: rows = rows[self.bounds[0]:self.bounds[1]+1]
        if self.cap: rows = rows[:self.cap]
        return SimpleNamespace(data=deepcopy(rows), count=count)


def execute(snap, *, rows=(), write=False, client=None, status="READY"):
    client = client or MemoryClient(snap.dataset, rows)
    result = run_master_sync(snap.dataset, registry=registry_for(snap, status=status), write=write,
                             store_factory=lambda: MasterStore(client))
    return result["datasets"][0], client


@pytest.mark.parametrize("dataset", ["index_master", "index_components"])
def test_real_v3_explicitly_blocked_without_services(dataset):
    for write in (False, True):
        report = run_master_sync(dataset, data_source="ssi_v3", write=write)
        assert report["status"] == "BLOCKED"
        assert report["datasets"][0]["planned_inserts"] is None
    with pytest.raises(MasterSourceError): SSIV3MasterAdapter().fetch(dataset)
    with pytest.raises(MasterSourceError): map_verified_record(dataset, {"Symbol": "SSI"})


def test_only_verified_security_capabilities_promoted():
    for dataset in ("symbols", "symbols"):
        assert MASTER_REGISTRY.resolve(dataset).status == "READY"
    for dataset in ("index_master", "index_components"):
        assert MASTER_REGISTRY.resolve(dataset) is None
        assert MASTER_REGISTRY.resolve(dataset, "ssi_v3").status == "BLOCKED"


@pytest.mark.parametrize("source", ["ssi_v2", "ssi_v4", "ssi_v5", "auto"])
def test_unknown_version_never_guessed(source):
    with pytest.raises(ValueError): run_master_sync("symbols", data_source=source)


def test_registry_version_selection_and_independent_capabilities():
    reg = registry_for(snapshot())
    cap = reg.resolve("symbols")
    reg.register(replace(cap, source="future_test", order=99, status="PREVIEW"))
    assert reg.resolve("symbols").source == "test_provider"
    assert reg.resolve("symbols", "future_test").status == "PREVIEW"
    assert reg.resolve("index_master", "test_provider") is None
    with pytest.raises(ValueError): reg.register(cap)
    with pytest.raises(ValueError): MasterRegistry([replace(cap, verified=False)])
    with pytest.raises(ValueError): MasterRegistry([replace(cap, evidence="")])
    reg.register(replace(cap, source="verified_future_test", order=100))
    assert reg.resolve("symbols").source == "verified_future_test"


@pytest.mark.parametrize("dataset", ("symbols", "index_master", "index_components"))
def test_dry_run_write_and_idempotency(dataset):
    snap = snapshot(dataset)
    preview, client = execute(snap)
    assert preview["status"] == "OK" and preview["planned_inserts"] == 1
    assert client.writes == []
    result, client = execute(snap, write=True, client=client)
    assert result["actual_inserts"] == 1 and result["readback_status"] == "PASS"
    for k, v in DEFAULTS.get(dataset, {}).items(): assert client.tables[dataset][0][k] == v
    result, client = execute(snap, write=True, client=client)
    assert result["unchanged_records"] == 1 and result["actual_inserts"] == 0
    assert len(client.writes) == 1


@pytest.mark.parametrize("status,intraday", [("inactive", "active"), ("active", "inactive"), ("inactive", "inactive")])
def test_status_and_nonnull_fields_preserved(status, intraday):
    old = {"symbol": "SSI", "name": "old", "market": "operator market", "status": status,
           "intraday_status": intraday, "created_at": "original"}
    snap = replace(snapshot(), records=[{"symbol": "SSI", "name": "new", "market": None}])
    report, client = execute(snap, rows=[old], write=True)
    assert report["actual_updates"] == 1
    assert {k:client.tables["symbols"][0][k] for k in old} == {**old, "name": "new"}
    assert client.writes[0][1]["name"] == "new"


def test_existing_index_status_preserved_and_missing_members_not_deleted():
    report, client = execute(snapshot("index_master"), rows=[{"index_code": "VNINDEX", "status": "active"}], write=True)
    assert report["status"] == "OK" and client.tables["index_master"][0]["status"] == "active"
    rows = [{"index_code": "OTHER", "symbol": "HPG"}]
    report, client = execute(snapshot("index_components"), rows=rows, write=True)
    assert report["source_missing_records"] == 1 and rows[0] in client.tables["index_components"]
    assert {c["classification"] for c in report["classifications"]} == {"NEW", "SOURCE_MISSING"}


@pytest.mark.parametrize("row", [{}, {"symbol": ""}, {"symbol": None}, {"symbol": "*"},
                                 {"symbol": "SSI", "status": "active"},
                                 {"symbol": "SSI", "intraday_status": "active"},
                                 {"symbol": "SSI", "name": ""}])
def test_invalid_canonical_no_database_access(row):
    report, client = execute(replace(snapshot(), records=[row]))
    assert report["invalid_records"] == 1 and report["status"] == "FAILED" and not client.writes


def test_duplicate_normalized_identity_blocks_whole_dataset():
    snap = replace(snapshot(), records=[{"symbol": "SSI"}, {"symbol": " ssi ", "name": "conflict"}], source_records=2)
    report, client = execute(snap, write=True)
    assert report["duplicate_identities"] == 1 and report["status"] == "FAILED" and not client.writes


@pytest.mark.parametrize("changes", [dict(complete=False), dict(records=[], source_records=0),
    dict(source_records=2), dict(errors=[{"code": "PAGINATION_TRUNCATED"}]),
    dict(resolved_scope={"board": "UNVERIFIED"}), dict(mapping_version="")])
def test_incomplete_empty_scope_and_errors_block_before_db(changes):
    report, client = execute(replace(snapshot(), **changes), write=True)
    assert report["status"] == "FAILED" and not client.writes


def test_preview_provider_never_written_or_default_selected():
    report, client = execute(snapshot(), write=True, status="PREVIEW")
    assert report["status"] == "BLOCKED" and not client.writes
    report, _ = execute(snapshot(), status="PREVIEW")  # omitted source only selects READY
    assert report["status"] == "BLOCKED"


@pytest.mark.parametrize("code", ["SSI_AUTH", "SSI_HTTP", "SSI_RATE_LIMIT", "SSI_TIMEOUT", "MALFORMED_ENVELOPE", "INCOMPLETE_PAGINATION", "UNSUPPORTED_ENDPOINT"])
def test_safe_adapter_errors_no_fallback(code):
    class Bad:
        def fetch(self, dataset): raise MasterSourceError(code)
    cap = replace(registry_for(snapshot()).resolve("symbols"), factory=Bad)
    result = run_master_sync("symbols", registry=MasterRegistry([cap]))
    assert result["datasets"][0]["errors"] == [{"code": code, "stage": "SOURCE_FETCH"}]


def test_database_read_and_compare_errors_sanitized():
    class Bad:
        def read(self, dataset): raise RuntimeError("secret response body")
    result = run_master_sync("symbols", registry=registry_for(snapshot()), store_factory=Bad)
    assert result["status"] == "FAILED" and "secret" not in json.dumps(result)
    report, _ = execute(snapshot(), rows=[{"symbol": "ssi"}])
    assert report["errors"][0]["code"] == "DB_COMPARE_ERROR"


@pytest.mark.parametrize("failure", ["write", "readback_error", "readback_mismatch"])
def test_partial_and_ambiguous_database_write_recovery(failure):
    client = MemoryClient("symbols")
    if failure == "write": client.fail_write = TimeoutError("secret in db response")
    if failure == "readback_error": client.fail_readback = True
    if failure == "readback_mismatch": client.corrupt_readback = True
    report, client = execute(snapshot(), write=True, client=client)
    assert report["status"] == "PARTIAL" and len(client.writes) == 1
    assert report["actual_inserts"] == (0 if failure == "write" else 1)
    assert report["insert_counts_confirmed"] is (failure != "write")
    assert "secret" not in json.dumps(report)
    client.fail_write = None; client.fail_readback = client.corrupt_readback = False
    rerun, _ = execute(snapshot(), write=True, client=client)
    assert rerun["status"] == "OK" and rerun["readback_status"] in {"PASS", "NOT_NEEDED"}


def test_completed_dataset_evidence_survives_later_blocker():
    reg = registry_for(snapshot())
    result = run_master_sync(registry=reg, store_factory=lambda: MasterStore(MemoryClient("symbols")))
    assert result["status"] == "PARTIAL" and result["datasets"][0]["planned_inserts"] == 1
    assert len(result["datasets"]) == 3


@pytest.mark.parametrize("dataset", [None, "all"])
def test_broad_write_rejected(dataset):
    with pytest.raises(ValueError): run_master_sync(dataset, write=True)


@pytest.mark.parametrize("command", ["sync-master-data", "init"])
def test_cli_alias_and_blocked_json(command, capsys):
    assert main([command, "--dataset", "index_master", "--data-source", "ssi_v3"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["flow"] == "sync-master-data" and report["mode"] == "DRY_RUN"
    assert main([command, "--write"]) == 2
    assert main([command, "--dry-run", "--write"]) == 2
    assert main([command, "--dataset", "symbols", "--data-source", "ssi_v4"]) == 2


@pytest.mark.parametrize("dataset", ("symbols", "index_master", "index_components"))
def test_database_read_pagination_exact_and_bounded(dataset):
    rows = [{**dict(zip(KEYS[dataset], (f"K{n}",) * len(KEYS[dataset])))} for n in range(205)]
    store = MasterStore(MemoryClient(dataset, rows))
    assert len(store.read(dataset)) == 205


def test_concurrent_insert_and_update_never_overwrite_operator_controls():
    client = MemoryClient("symbols")
    store = MasterStore(client)
    plan, _ = compare("symbols", [{"symbol": "SSI", "name": "source"}], [])
    client.tables["symbols"] = [{"symbol": "SSI", "status": "active", "intraday_status": "active", "name": "operator"}]
    with pytest.raises(MasterStoreError): store.apply("symbols", plan[0])
    assert client.tables["symbols"][0]["name"] == "operator"
    plan, _ = compare("symbols", [{"symbol": "SSI", "name": "source"}], client.tables["symbols"])
    client.tables["symbols"][0]["name"] = "concurrent edit"
    with pytest.raises(MasterStoreError): store.apply("symbols", plan[0])
    assert client.tables["symbols"][0]["name"] == "concurrent edit"


@pytest.mark.parametrize("value", [True, 1.5, "NaN", "Infinity", "-1", "invalid"])
def test_numeric_contract_rejects_non_exact_or_invalid(value):
    with pytest.raises(ValueError): canonical_record("symbols", {"symbol": "SSI", "lot_size": value})


def test_decimal_and_dates_exact_without_version_specific_names():
    row = canonical_record("symbols", {"symbol": "ssi", "listed_share": "9007199254740993", "issue_date": "2026-10-20"})
    assert row["listed_share"] == "9007199254740993" and row["symbol"] == "SSI"
    plan, _ = compare("symbols", [row], [{**row, "listed_share": 9007199254740993}])
    assert not plan
    with pytest.raises(ValueError): canonical_record("symbols", {"symbol": "SSI", "issue_date": "20/10/2026"})


@pytest.mark.parametrize("fault", ["no_count", "count_change", "short_page", "duplicate", "error"])
def test_database_pagination_faults_fail_closed(fault):
    class BadClient:
        def table(self, dataset): return self
        def select(self, *a, **kw): return self
        def order(self, *a): return self
        def range(self, start, end): self.start = start; return self
        def execute(self):
            rows = [{"symbol": f"K{n}"} for n in range(self.start, self.start+100)]
            if fault == "duplicate": rows[-1] = rows[0]
            if fault == "short_page": rows = rows[:1]
            return SimpleNamespace(data=rows, count=None if fault == "no_count" else (201 if fault == "count_change" and self.start else 200),
                                   error="safe failure" if fault == "error" else None)
    with pytest.raises(MasterStoreError): MasterStore(BadClient()).read("symbols")


def test_actual_sdk_queries_with_http_mock_transport():
    import httpx
    from postgrest import SyncPostgrestClient
    requests_seen = []
    def handle(request):
        requests_seen.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=[{"symbol": "SSI", "name": "new"}], headers={"content-range": "0-0/1"})
        return httpx.Response(201 if request.method == "POST" else 200,
                              json=[json.loads(request.content) | {"symbol": "SSI"}])
    http = httpx.Client(base_url="https://master.invalid", transport=httpx.MockTransport(handle))
    client = SyncPostgrestClient("https://master.invalid", http_client=http)
    store = MasterStore(client)
    assert store.read("symbols") == [{"symbol": "SSI", "name": "new"}]
    assert "count=exact" in requests_seen[-1].headers["prefer"]
    plan, _ = compare("symbols", [{"symbol": "SSI", "name": "new"}], [])
    assert store.apply("symbols", plan[0]) == 1
    request = requests_seen[-1]
    assert request.url.params["on_conflict"] == "symbol"
    assert "resolution=ignore-duplicates" in request.headers["prefer"]
    assert json.loads(request.content)["status"] == "inactive"
    plan, _ = compare("symbols", [{"symbol": "SSI", "raw": {"source": "new"}}],
                      [{"symbol": "SSI", "raw": {"source": "old"}}])
    assert store.apply("symbols", plan[0]) == 1
    request = requests_seen[-1]
    assert request.method == "PATCH" and request.url.params["symbol"] == "eq.SSI"
    assert request.url.params["raw"] == 'eq.{"source":"old"}'
    store.verify("symbols", {"identity": {"symbol": "SSI"}, "payload": {"name": "new"}})
    http.close()


def test_partial_counts_survive_later_row_failure():
    snap = replace(snapshot(), records=[{"symbol": "AAA"}, {"symbol": "BBB"}], source_records=2)
    client = MemoryClient("symbols")
    class SecondFails(MasterStore):
        def apply(self, dataset, operation):
            if operation["identity"]["symbol"] == "BBB": raise TimeoutError("secret")
            return super().apply(dataset, operation)
    result = run_master_sync("symbols", write=True, registry=registry_for(snap),
                             store_factory=lambda: SecondFails(client))["datasets"][0]
    assert result["status"] == "PARTIAL" and result["actual_inserts"] == 1
    assert not result["insert_counts_confirmed"] and result["planned_inserts"] == 2
    assert len(client.tables["symbols"]) == 1
