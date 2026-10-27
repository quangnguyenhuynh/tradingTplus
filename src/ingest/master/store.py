"""Bounded master reads and per-row guarded writes; no global upsert changes."""
from __future__ import annotations
import json

from src.database.client import SupabaseClient
from src.utils.time_utils import app_now_iso
from .contracts import KEYS, FIELDS, NUMERIC, equivalent, identity


class MasterStoreError(RuntimeError):
    pass


def checked_data(response):
    if getattr(response, "error", None) or not isinstance(getattr(response, "data", None), list):
        raise MasterStoreError("Database response unverified")
    return response.data


def select_columns(dataset):
    if dataset not in ('symbols', 'securities'):
        return '*'
    # PostgREST casts preserve exact numeric values through the SDK JSON decoder,
    # whose default floating-point parsing would round fractional NUMERICs.
    columns = set(KEYS[dataset]) | FIELDS[dataset] | {'updated_at'}
    if dataset == 'symbols':
        columns |= {'status', 'intraday_status', 'created_at'}
    return ','.join(column + '::text' if column in NUMERIC else column for column in sorted(columns))


class MasterStore:
    def __init__(self, client=None):
        self.client = client if client is not None else SupabaseClient().get()

    def read(self, dataset):
        if dataset == 'securities':
            raise MasterStoreError('DEPRECATED_DATASET: use canonical symbols pipeline')
        rows, expected, seen = [], None, set()
        # 100 rows avoids silently trusting a deployment's larger REST row cap.
        for offset in range(0, 100_000, 100):
            query = self.client.table(dataset).select(select_columns(dataset), count="exact")
            for key in KEYS[dataset]:
                query = query.order(key)
            try:
                response = query.range(offset, offset + 99).execute()
            except Exception as exc:
                if dataset == 'symbols':
                    from src.providers.ssi.master_contract import MasterSourceError
                    raise MasterSourceError('SYMBOLS_SCHEMA_REQUIRED_APPLY_STAGE_A_OR_CHECK_DB_ACCESS') from None
                raise
            page = checked_data(response)
            count = getattr(response, "count", None)
            if isinstance(count, bool) or not isinstance(count, int) or count < 0 or (expected is not None and count != expected):
                raise MasterStoreError("Database count unavailable or changed")
            expected = count
            for row in page:
                key = identity(dataset, row)
                if key in seen:
                    raise MasterStoreError("Database pagination repeated an identity")
                seen.add(key)
            rows.extend(page)
            if len(rows) > expected or len(page) > 100:
                raise MasterStoreError("Database pagination inconsistent")
            if len(rows) == expected:
                return rows
            if len(page) != 100:
                raise MasterStoreError("Database pagination truncated")
        raise MasterStoreError("Database row limit exceeded")

    def apply(self, dataset, operation):
        """One request/transaction; never retry an ambiguous write.

        Updates never send status columns. Insert conflicts do nothing rather than
        overwrite a concurrent operator insertion. Changed descriptive columns
        use compare-and-set to detect concurrent edits.
        """
        payload = dict(operation["payload"])
        if dataset == "symbols" and operation["classification"] == "NEW":
            payload["created_at"] = app_now_iso()
        elif dataset != "symbols":
            payload["updated_at"] = app_now_iso()
        if dataset == 'securities':
            raise MasterStoreError('DEPRECATED_DATASET: use symbols')
        if dataset == 'symbols':
            payload['updated_at'] = app_now_iso()
        table = self.client.table(dataset)
        if operation["classification"] == "NEW":
            query = table.upsert(payload, on_conflict=",".join(KEYS[dataset]), ignore_duplicates=True)
        else:
            query = table.update(payload)
            for key, value in operation["identity"].items():
                query = query.eq(key, value)
            for key in operation["payload"]:
                value = operation["before"].get(key)
                if key == "raw" and value is not None:
                    value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                query = query.is_(key, "null") if value is None else query.eq(key, value)
        if dataset in ('symbols', 'securities'):
            query = query.select(select_columns(dataset))
        acknowledged = checked_data(query.execute())
        if len(acknowledged) != 1:
            raise MasterStoreError("Write not acknowledged: conflict or unknown result")
        row = acknowledged[0]
        expected = {**operation["identity"], **operation["payload"]}
        if any(not equivalent(k, row.get(k), v) for k, v in expected.items()):
            raise MasterStoreError("Write acknowledgement differs from plan")
        return 1

    def verify(self, dataset, operation):
        if dataset == 'securities':
            raise MasterStoreError('DEPRECATED_DATASET: use symbols')
        query = self.client.table(dataset).select(select_columns(dataset))
        for key, value in operation["identity"].items():
            query = query.eq(key, value)
        rows = checked_data(query.limit(2).execute())
        expected = {**operation["identity"], **operation["payload"]}
        if len(rows) != 1 or any(not equivalent(k, rows[0].get(k), v) for k, v in expected.items()):
            raise MasterStoreError("Readback mismatch")
        # Existing operator controls were never included in the mutation. A
        # concurrent operator change is legitimate and must not be rolled back.
