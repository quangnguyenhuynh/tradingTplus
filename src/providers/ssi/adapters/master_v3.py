"""SSI v3 master adapter: explicitly blocked until source evidence exists.

Inspector request definitions are candidates, not response/membership contracts.
No successful master fixtures are fabricated, and no client is constructed here.
The existing SSIV3Client remains the authentication/retry boundary for a future
verified fetch implementation; its permissive paged() is NOT sufficient evidence
of a complete master universe.
"""
from src.providers.ssi.master_contract import MASTER_DATASETS, MasterSourceError, MasterSnapshot


class SSIV3MasterAdapter:
    source_id = "ssi_v3"
    mapping_version = "ssi_v3.master.unverified"

    # Audited candidates only. These are not claimed working mappings.
    candidates = {
        "symbols": ("/data/securitiesByBoard", "/data/masterdata"),
        "securities": ("/data/securitiesByBoard", "/data/masterdata"),
        "index_master": ("/data/indexList",),
        "index_components": ("/data/securitiesByBoard",),
    }

    def fetch(self, dataset: str) -> MasterSnapshot:
        if dataset not in MASTER_DATASETS:
            raise ValueError("Unknown master dataset")
        raise MasterSourceError("SSI_V3_MASTER_RESPONSE_UNVERIFIED")


def map_verified_record(dataset: str, payload: dict):
    """Compatibility mapping boundary: reject, rather than guess v2 aliases."""
    if dataset not in MASTER_DATASETS:
        raise ValueError("Unknown master dataset")
    raise MasterSourceError("SSI_V3_MASTER_MAPPING_UNVERIFIED")
