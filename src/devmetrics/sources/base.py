"""The contract every data source (fake, GitHub, ...) must satisfy.

Ingestion depends only on this protocol, never on a concrete source.
"""

from collections.abc import AsyncIterator
from typing import Protocol

from devmetrics.domain.models import Bug, PullRequest, Repository, ReviewComment


class SourceAdapter(Protocol):
    """A read-only stream of domain models from one external system.

    Methods are declared with plain `def` returning `AsyncIterator[...]`:
    implementations write `async def ... yield`, which is an async generator,
    and calling one returns an AsyncIterator directly (no `await` needed).
    """

    name: str

    def repositories(self) -> AsyncIterator[Repository]: ...

    def pull_requests(self, repo: Repository) -> AsyncIterator[PullRequest]: ...

    def review_comments(self, repo: Repository) -> AsyncIterator[ReviewComment]: ...

    def bugs(self, repo: Repository) -> AsyncIterator[Bug]: ...
