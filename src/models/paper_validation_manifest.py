"""Schema for paper-validator output manifests."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ValidationCheckResult(BaseModel):
    """Result for a single paper-validation check."""

    check_id: str
    title: str
    status: Literal["pass", "warn", "fail"]
    details: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    blocking: bool = False

    @model_validator(mode="after")
    def validate_blocking_status(self) -> "ValidationCheckResult":
        """Blocking failures are only valid for failed checks."""
        if self.blocking and self.status != "fail":
            raise ValueError("blocking can only be true when status is 'fail'")
        return self


class ManifestSummary(BaseModel):
    """Aggregated counts for validation results."""

    total_checks: int = Field(ge=0)
    pass_count: int = Field(ge=0)
    warn_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    blocking_failures: int = Field(ge=0)


class PaperValidationManifest(BaseModel):
    """Top-level manifest for paper-validator outputs."""

    schema_version: str = "1.0"
    document_id: str
    validator_mode: Literal["mode_1", "mode_2", "unknown"] = "unknown"
    checks: list[ValidationCheckResult] = Field(default_factory=list)
    summary: ManifestSummary | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def _build_summary(checks: list[ValidationCheckResult]) -> ManifestSummary:
        pass_count = sum(1 for check in checks if check.status == "pass")
        warn_count = sum(1 for check in checks if check.status == "warn")
        fail_count = sum(1 for check in checks if check.status == "fail")
        blocking_failures = sum(1 for check in checks if check.blocking)

        return ManifestSummary(
            total_checks=len(checks),
            pass_count=pass_count,
            warn_count=warn_count,
            fail_count=fail_count,
            blocking_failures=blocking_failures,
        )

    @model_validator(mode="after")
    def validate_summary(self) -> "PaperValidationManifest":
        """Ensure provided summary matches check-level facts."""
        computed_summary = self._build_summary(self.checks)
        if self.summary is None:
            self.summary = computed_summary
            return self

        if self.summary.model_dump() != computed_summary.model_dump():
            raise ValueError("summary does not match check-level status counts")
        return self

    def has_blocking_failures(self) -> bool:
        """Return True when manifest contains any blocking failure."""
        return bool(self.summary and self.summary.blocking_failures > 0)
