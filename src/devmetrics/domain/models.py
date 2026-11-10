"""Domain models: the typed, immutable shapes every layer speaks.

Sources produce these, ingestion stores them, KPIs are computed from them.
They know nothing about HTTP, SQL or any specific source.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _require_aware_utc(value: datetime) -> datetime:
    """Reject naive datetimes and normalize aware ones to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware (e.g. end with 'Z' or '+02:00')")
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_require_aware_utc)]


class DomainModel(BaseModel):
    """Base for all domain models: immutable and strict about unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Repository(DomainModel):
    source: NonEmptyStr
    external_id: NonEmptyStr
    name: NonEmptyStr


class PullRequestState(StrEnum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


class PullRequest(DomainModel):
    source: NonEmptyStr
    external_id: NonEmptyStr
    repository_external_id: NonEmptyStr
    number: int = Field(gt=0)
    title: str
    author: NonEmptyStr
    state: PullRequestState
    created_at: UtcDatetime
    first_review_at: UtcDatetime | None = None
    merged_at: UtcDatetime | None = None
    lines_changed: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _check_timeline(self) -> Self:
        if self.state is PullRequestState.MERGED and self.merged_at is None:
            raise ValueError("merged_at is required when state is 'merged'")
        if self.state is not PullRequestState.MERGED and self.merged_at is not None:
            raise ValueError("merged_at is only allowed when state is 'merged'")
        for name in ("first_review_at", "merged_at"):
            value: datetime | None = getattr(self, name)
            if value is not None and value < self.created_at:
                raise ValueError(f"{name} cannot be before created_at")
        return self


class ReviewComment(DomainModel):
    source: NonEmptyStr
    external_id: NonEmptyStr
    pull_request_external_id: NonEmptyStr
    reviewer: NonEmptyStr
    body: str
    created_at: UtcDatetime


class BugSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Bug(DomainModel):
    source: NonEmptyStr
    external_id: NonEmptyStr
    repository_external_id: NonEmptyStr
    title: str
    severity: BugSeverity
    opened_at: UtcDatetime
    closed_at: UtcDatetime | None = None
    linked_pull_request_external_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _check_timeline(self) -> Self:
        if self.closed_at is not None and self.closed_at < self.opened_at:
            raise ValueError("closed_at cannot be before opened_at")
        return self

    @property
    def is_open(self) -> bool:
        return self.closed_at is None
