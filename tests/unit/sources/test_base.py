"""Slice 2: the SourceAdapter protocol.

This file checks two things:
- at type-check time (mypy): a class with the right shape IS a SourceAdapter,
  without inheriting from it (structural typing).
- at runtime (pytest): code written against the protocol can consume any adapter.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from devmetrics.domain.models import (
    Bug,
    PullRequest,
    PullRequestState,
    Repository,
    ReviewComment,
)
from devmetrics.sources.base import SourceAdapter

T0 = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
REPO = Repository(source="tiny", external_id="r1", name="octo/tiny")


class TinySource:
    """Note: no `(SourceAdapter)` base class. Shape alone must be enough."""

    name = "tiny"

    async def repositories(self) -> AsyncIterator[Repository]:
        yield REPO

    async def pull_requests(self, repo: Repository) -> AsyncIterator[PullRequest]:
        yield PullRequest(
            source="tiny",
            external_id="pr-1",
            repository_external_id=repo.external_id,
            number=1,
            title="t",
            author="omar",
            state=PullRequestState.OPEN,
            created_at=T0,
        )

    async def review_comments(self, repo: Repository) -> AsyncIterator[ReviewComment]:
        return
        yield  # unreachable, but makes this an async generator that yields nothing

    async def bugs(self, repo: Repository) -> AsyncIterator[Bug]:
        return
        yield


async def count_pull_requests(source: SourceAdapter) -> int:
    """Stands in for future ingestion code: it only knows the protocol."""
    total = 0
    async for repo in source.repositories():
        async for _ in source.pull_requests(repo):
            total += 1
    return total


async def test_structural_class_satisfies_protocol() -> None:
    adapter: SourceAdapter = TinySource()  # mypy verifies the shape here

    assert adapter.name == "tiny"
    assert await count_pull_requests(adapter) == 1
