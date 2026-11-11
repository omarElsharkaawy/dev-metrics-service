"""Contract tests that every SourceAdapter must pass.

Usage: subclass `SourceContract` in a `test_*.py` file and override the
`source` fixture. The class name does not start with `Test`, so pytest
only collects it through subclasses (like an abstract test class in Kotlin).
"""

from dataclasses import dataclass

import pytest

from devmetrics.domain.models import Bug, PullRequest, Repository, ReviewComment
from devmetrics.sources.base import SourceAdapter


@dataclass(frozen=True)
class Snapshot:
    """Everything one full read of a source produced."""

    repositories: list[Repository]
    pull_requests: dict[str, list[PullRequest]]  # keyed by repository external_id
    review_comments: dict[str, list[ReviewComment]]
    bugs: dict[str, list[Bug]]

    def all_pull_requests(self) -> list[PullRequest]:
        return [pr for prs in self.pull_requests.values() for pr in prs]

    def all_review_comments(self) -> list[ReviewComment]:
        return [c for cs in self.review_comments.values() for c in cs]

    def all_bugs(self) -> list[Bug]:
        return [b for bs in self.bugs.values() for b in bs]


async def read_all(source: SourceAdapter) -> Snapshot:
    repositories = [repo async for repo in source.repositories()]
    return Snapshot(
        repositories=repositories,
        pull_requests={
            r.external_id: [pr async for pr in source.pull_requests(r)] for r in repositories
        },
        review_comments={
            r.external_id: [c async for c in source.review_comments(r)] for r in repositories
        },
        bugs={r.external_id: [b async for b in source.bugs(r)] for r in repositories},
    )


class SourceContract:
    @pytest.fixture
    def source(self) -> SourceAdapter:
        raise NotImplementedError("subclasses must provide a `source` fixture")

    @pytest.fixture
    async def snapshot(self, source: SourceAdapter) -> Snapshot:
        return await read_all(source)

    def test_has_a_name(self, source: SourceAdapter) -> None:
        assert source.name.strip()

    def test_yields_some_data(self, snapshot: Snapshot) -> None:
        assert snapshot.repositories
        assert snapshot.all_pull_requests()
        assert snapshot.all_review_comments()
        assert snapshot.all_bugs()

    def test_yields_domain_models(self, snapshot: Snapshot) -> None:
        assert all(isinstance(r, Repository) for r in snapshot.repositories)
        assert all(isinstance(pr, PullRequest) for pr in snapshot.all_pull_requests())
        assert all(isinstance(c, ReviewComment) for c in snapshot.all_review_comments())
        assert all(isinstance(b, Bug) for b in snapshot.all_bugs())

    def test_every_model_is_tagged_with_the_source_name(
        self, source: SourceAdapter, snapshot: Snapshot
    ) -> None:
        models: list[Repository | PullRequest | ReviewComment | Bug] = [
            *snapshot.repositories,
            *snapshot.all_pull_requests(),
            *snapshot.all_review_comments(),
            *snapshot.all_bugs(),
        ]
        assert {m.source for m in models} == {source.name}

    def test_external_ids_are_unique_per_type(self, snapshot: Snapshot) -> None:
        for items in (
            snapshot.repositories,
            snapshot.all_pull_requests(),
            snapshot.all_review_comments(),
            snapshot.all_bugs(),
        ):
            ids = [item.external_id for item in items]
            assert len(ids) == len(set(ids))

    def test_children_belong_to_the_repository_they_were_listed_under(
        self, snapshot: Snapshot
    ) -> None:
        for repo_id, prs in snapshot.pull_requests.items():
            assert all(pr.repository_external_id == repo_id for pr in prs)
        for repo_id, bugs in snapshot.bugs.items():
            assert all(bug.repository_external_id == repo_id for bug in bugs)

    def test_comments_point_at_a_pull_request_in_the_same_repository(
        self, snapshot: Snapshot
    ) -> None:
        for repo_id, comments in snapshot.review_comments.items():
            pr_ids = {pr.external_id for pr in snapshot.pull_requests[repo_id]}
            assert all(c.pull_request_external_id in pr_ids for c in comments)

    async def test_reading_twice_gives_the_same_data(
        self, source: SourceAdapter, snapshot: Snapshot
    ) -> None:
        assert await read_all(source) == snapshot
