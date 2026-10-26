"""Explicit version/dataset registration, independent of price readiness."""
from src.providers.ssi.master_contract import MASTER_DATASETS, MasterCapability
from src.providers.ssi.adapters.master_v3 import SSIV3MasterAdapter


class MasterRegistry:
    def __init__(self, capabilities=()):
        self._capabilities = {}
        for capability in capabilities:
            self.register(capability)

    def register(self, capability: MasterCapability):
        if capability.dataset not in MASTER_DATASETS:
            raise ValueError("Unknown master dataset")
        if capability.status not in {"READY", "PREVIEW", "BLOCKED", "UNSUPPORTED"}:
            raise ValueError("Invalid master capability status")
        if capability.status in {"READY", "PREVIEW"} and not (
            capability.verified and capability.evidence and callable(capability.factory)
        ):
            raise ValueError("Usable master capabilities require verified evidence and factory")
        key = (capability.source, capability.dataset)
        if key in self._capabilities:
            raise ValueError("Master capability already registered")
        self._capabilities[key] = capability

    def capabilities(self, dataset):
        if dataset not in MASTER_DATASETS:
            raise ValueError("Unknown master dataset")
        return tuple(c for c in self._capabilities.values() if c.dataset == dataset)

    def resolve(self, dataset, requested=None):
        candidates = self.capabilities(dataset)
        if requested is not None:
            if not any(c.source == requested for c in self._capabilities.values()):
                raise ValueError(f"unsupported master data source: {requested}")
            return self._capabilities.get((requested, dataset))
        ready = [c for c in candidates if c.status == "READY" and c.verified]
        return max(ready, key=lambda c: c.order) if ready else None


MASTER_REGISTRY = MasterRegistry(
    MasterCapability(
        "ssi_v3", dataset, 3, "BLOCKED", False, SSIV3MasterAdapter,
        "scripts/inspectors/ssi_rest/endpoints.py: request candidates only; "
        "no verified v3 master response fixture in tests/fixtures",
        "Response fields, board/security-type semantics and complete snapshot "
        "pagination remain unverified; index membership is not inferred.",
    ) for dataset in MASTER_DATASETS
)
