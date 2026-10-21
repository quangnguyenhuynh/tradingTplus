"""Unavailable integrations fail before constructing a provider or database client."""
class CapabilityUnavailableError(RuntimeError):
    error_type = "NOT_IMPLEMENTED"

    def __init__(self, dataset: str) -> None:
        self.dataset = dataset
        super().__init__(f"SSI v3 {dataset} ingestion adapter is not implemented")

    def as_summary(self) -> dict:
        return {"status": "FAILED", "error_type": self.error_type,
                "dataset": self.dataset, "reason": str(self)}
