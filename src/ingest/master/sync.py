"""Version-neutral, independently reported master dataset orchestration."""
from __future__ import annotations

from collections import Counter

from src.providers.ssi.master_contract import MASTER_DATASETS, MasterSnapshot, MasterSourceError
from src.providers.ssi.master_registry import MASTER_REGISTRY
from .contracts import canonical_record, compare, identity, FIELDS, KEYS
from .store import MasterStore


def _report(dataset, source, write):
    return dict(
        flow="sync-master-data", dataset=dataset, data_source=source,
        mode="WRITE" if write else "DRY_RUN", capability_status="UNSUPPORTED",
        requested_scope={"kind": "ALL"}, resolved_scope=None,
        pagination_complete=False, pagination={}, mapping_version=None,
        source_records_received=None, canonical_records_mapped=None,
        valid_records=0, invalid_records=0, duplicate_identities=0,
        new_records=None, changed_records=None, unchanged_records=None,
        source_missing_records=None, unsupported_records=None,
        unsupported_fields=[], unverified_fields=sorted(set(KEYS[dataset]) | FIELDS[dataset]),
        planned_inserts=None, planned_updates=None,
        actual_inserts=0, actual_updates=0, insert_counts_confirmed=True,
        readback_status="NOT_RUN", error_count=0, errors=[], warnings=[],
        classifications=[], status="BLOCKED", stage="PROVIDER_RESOLUTION",
        write_ready=False, recovery="Resolve the reported blocker and rerun DRY_RUN first.",
    )


def _dataset(dataset, source, write, registry, store_factory):
    report = _report(dataset, source, write)
    capability = registry.resolve(dataset, source)
    if capability is None:
        report["capability_status"] = "NO_READY_PROVIDER" if source is None else "UNSUPPORTED"
        report["errors"].append({"code": "NO_READY_MASTER_PROVIDER" if source is None else "UNSUPPORTED_DATASET"})
        report["available_capabilities"] = [
            {"source": c.source, "status": c.status, "verified": c.verified,
             "evidence": c.evidence, "note": c.note} for c in registry.capabilities(dataset)
        ]
        report["error_count"] = 1
        return report
    report.update(data_source=capability.source, capability_status=capability.status,
                  capability_verified=capability.verified, capability_evidence=capability.evidence)
    if not capability.verified or capability.status not in {"READY", "PREVIEW"} or (write and capability.status != "READY"):
        report.update(status="UNSUPPORTED" if capability.status == "UNSUPPORTED" else "BLOCKED",
                      errors=[{"code": "MASTER_CAPABILITY_NOT_READY"}], error_count=1,
                      warnings=[capability.note])
        return report
    try:
        report["stage"] = "SOURCE_FETCH"
        snapshot = capability.factory().fetch(dataset)
        if not isinstance(snapshot, MasterSnapshot) or snapshot.dataset != dataset:
            raise MasterSourceError("INVALID_ADAPTER_RESULT")
        report.update(
            source_records_received=snapshot.source_records,
            canonical_records_mapped=len(snapshot.records), pagination_complete=snapshot.complete,
            pagination=snapshot.pagination, resolved_scope=snapshot.resolved_scope,
            mapping_version=snapshot.mapping_version, unsupported_fields=list(snapshot.unsupported_fields),
        )
        # Adapters supply only safe codes/metadata, never raw source bodies.
        if snapshot.errors:
            report["errors"] = [{"code": e.get("code", "SOURCE_INVALID")} for e in snapshot.errors]
        if (snapshot.complete is not True or snapshot.errors or not snapshot.mapping_version
                or snapshot.resolved_scope != {"kind": "ALL"}
                or isinstance(snapshot.source_records, bool) or not isinstance(snapshot.source_records, int)
                or snapshot.source_records != len(snapshot.records)):
            raise MasterSourceError("SOURCE_COMPLETENESS_UNVERIFIED")
        report["stage"] = "CANONICAL_VALIDATION"
        report["unverified_fields"] = []
        canonical, seen = [], set()
        for row in snapshot.records:
            try:
                candidate = canonical_record(dataset, row)
            except (ValueError, TypeError):
                report["invalid_records"] += 1
                continue
            key = identity(dataset, candidate)
            if key in seen:
                report["duplicate_identities"] += 1
            seen.add(key)
            canonical.append(candidate)
        report["valid_records"] = len(canonical)
        if report["invalid_records"] or report["duplicate_identities"]:
            report["classifications"] = [{"classification": "INVALID"}] * report["invalid_records"] + [
                {"classification": "CONFLICT"}] * report["duplicate_identities"]
            raise MasterSourceError("INVALID_OR_DUPLICATE_CANONICAL_RECORDS")
        if not canonical:
            # No proof that an empty snapshot is the complete authoritative
            # universe; never allow mass missing classifications from this.
            raise MasterSourceError("SOURCE_EMPTY")
        report["stage"] = "DB_READ"
        store = store_factory()
        existing = store.read(dataset)
        report["stage"] = "DB_COMPARE"
        plan, classifications = compare(dataset, canonical, existing)
        report["classifications"] = classifications
        counts = Counter(item["classification"] for item in classifications)
        report.update(new_records=counts["NEW"], changed_records=counts["CHANGED"],
                      unchanged_records=counts["UNCHANGED"], source_missing_records=counts["SOURCE_MISSING"],
                      planned_inserts=counts["NEW"], planned_updates=counts["CHANGED"])
        if counts["SOURCE_MISSING"]:
            report["warnings"].append("SOURCE_MISSING is absence from this snapshot, not confirmed delisting; no mutation.")
        report["write_ready"] = capability.status == "READY"
        if not write:
            report.update(status="OK", stage="COMPLETE")
            return report
        for operation in plan:
            report["stage"] = "DB_WRITE"
            # A timeout may occur after commit. Keep counts acknowledged-only.
            report["insert_counts_confirmed"] = False
            acknowledged = store.apply(dataset, operation)
            if acknowledged != 1:
                raise MasterSourceError("DB_WRITE_UNACKNOWLEDGED")
            report["insert_counts_confirmed"] = True
            report["actual_inserts" if operation["classification"] == "NEW" else "actual_updates"] += 1
            report["stage"] = "READBACK"
            store.verify(dataset, operation)
        report.update(status="OK", stage="COMPLETE", readback_status="PASS" if plan else "NOT_NEEDED")
    except Exception as exc:
        stage = report["stage"]
        # Exception text can contain secrets in source/DB responses: type/code only.
        code = exc.code if isinstance(exc, MasterSourceError) else stage + "_ERROR"
        report["errors"].append({"code": code, "stage": stage})
        report["status"] = "PARTIAL" if (report["actual_inserts"] + report["actual_updates"] or
                                            not report["insert_counts_confirmed"]) else "FAILED"
        report["write_ready"] = False
        if stage == "READBACK":
            report["readback_status"] = "FAIL"
        if stage in {"DB_WRITE", "READBACK"}:
            report["recovery"] = "Stop; inspect affected identities read-only, then rerun DRY_RUN and the explicit dataset. No automatic rollback/retry."
    report["error_count"] = len(report["errors"])
    return report


def run_master_sync(dataset=None, *, data_source=None, write=False,
                    registry=None, store_factory=None):
    if not isinstance(write, bool):
        raise ValueError("write must be a boolean")
    if dataset not in (None, "all", *MASTER_DATASETS):
        raise ValueError("Unknown master dataset")
    if write and dataset not in MASTER_DATASETS:
        raise ValueError("--write requires one explicit --dataset; all is preview-only")
    registry = registry if registry is not None else MASTER_REGISTRY
    datasets = MASTER_DATASETS if dataset in (None, "all") else (dataset,)
    # Validate every source choice before any independently scoped work.
    for selected in datasets:
        registry.resolve(selected, data_source)
    reports = [_dataset(selected, data_source, write, registry, store_factory or MasterStore)
               for selected in datasets]
    statuses = [r["status"] for r in reports]
    status = "OK" if all(s == "OK" for s in statuses) else (
        "PARTIAL" if any(s in {"OK", "PARTIAL"} for s in statuses) else
        "BLOCKED" if all(s in {"BLOCKED", "UNSUPPORTED"} for s in statuses) else "FAILED")
    return {"flow": "sync-master-data", "dataset": dataset or "all",
            "mode": "WRITE" if write else "DRY_RUN", "data_source": data_source,
            "status": status, "datasets": reports,
            "actual_inserts": sum(r["actual_inserts"] for r in reports),
            "actual_updates": sum(r["actual_updates"] for r in reports),
            "error_count": sum(r["error_count"] for r in reports),
            "transaction_boundary": "one row/request; independent datasets, no cross-table atomicity"}
