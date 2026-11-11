"""A deterministic, in-memory source for tests, demos and local development.

The whole data set is generated once in `__init__` from `random.Random(seed)`,
so the same seed always gives the same data, and reading twice is stable.
"""

import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from devmetrics.domain.models import (
    Bug,
    BugSeverity,
    PullRequest,
    PullRequestState,
    Repository,
    ReviewComment,
)

# Fixed, not datetime.now(): "now" would make every run produce different data.
BASE_TIME = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
DEVELOPERS = ("amira", "omar", "karim", "lina", "youssef", "sara")
WINDOW_HOURS = 24 * 60  # PRs and bugs are spread over ~60 days


class FakeSource:
    name = "fake"

    def __init__(
        self, seed: int = 0, repositories: int = 2, pull_requests_per_repo: int = 10
    ) -> None:
        rng = random.Random(seed)  # local: used only here, never shared across reads
        self._repositories: list[Repository] = []
        self._pull_requests: dict[str, list[PullRequest]] = {}
        self._review_comments: dict[str, list[ReviewComment]] = {}
        self._bugs: dict[str, list[Bug]] = {}

        for index in range(1, repositories + 1):
            repo = Repository(
                source=self.name, external_id=f"repo-{index}", name=f"fake-org/service-{index}"
            )
            prs = [
                self._make_pull_request(rng, repo, n) for n in range(1, pull_requests_per_repo + 1)
            ]
            self._repositories.append(repo)
            self._pull_requests[repo.external_id] = prs
            self._review_comments[repo.external_id] = [
                comment for pr in prs for comment in self._make_comments(rng, pr)
            ]
            self._bugs[repo.external_id] = self._make_bugs(rng, repo, prs)

    # --- SourceAdapter ---------------------------------------------------

    async def repositories(self) -> AsyncIterator[Repository]:
        for repo in self._repositories:
            yield repo

    async def pull_requests(self, repo: Repository) -> AsyncIterator[PullRequest]:
        for pr in self._pull_requests.get(repo.external_id, []):
            yield pr

    async def review_comments(self, repo: Repository) -> AsyncIterator[ReviewComment]:
        for comment in self._review_comments.get(repo.external_id, []):
            yield comment

    async def bugs(self, repo: Repository) -> AsyncIterator[Bug]:
        for bug in self._bugs.get(repo.external_id, []):
            yield bug

    # --- generation ------------------------------------------------------

    def _make_pull_request(self, rng: random.Random, repo: Repository, number: int) -> PullRequest:
        created_at = BASE_TIME + timedelta(hours=rng.randint(0, WINDOW_HOURS))
        state = rng.choices(
            [PullRequestState.MERGED, PullRequestState.OPEN, PullRequestState.CLOSED],
            weights=[60, 25, 15],
        )[0]
        reviewed = state is PullRequestState.MERGED or rng.random() < 0.6
        first_review_at = created_at + timedelta(hours=rng.randint(1, 48)) if reviewed else None
        merged_at = (
            (first_review_at or created_at) + timedelta(hours=rng.randint(1, 72))
            if state is PullRequestState.MERGED
            else None
        )
        return PullRequest(
            source=self.name,
            external_id=f"{repo.external_id}-pr-{number}",
            repository_external_id=repo.external_id,
            number=number,
            title=f"Change #{number} in {repo.name}",
            author=rng.choice(DEVELOPERS),
            state=state,
            created_at=created_at,
            first_review_at=first_review_at,
            merged_at=merged_at,
            lines_changed=rng.randint(5, 800),
        )

    def _make_comments(self, rng: random.Random, pr: PullRequest) -> list[ReviewComment]:
        if pr.first_review_at is None:
            return []
        reviewers = [dev for dev in DEVELOPERS if dev != pr.author]
        comments: list[ReviewComment] = []
        at = pr.first_review_at
        for k in range(1, rng.randint(1, 4) + 1):
            comments.append(
                ReviewComment(
                    source=self.name,
                    external_id=f"{pr.external_id}-c-{k}",
                    pull_request_external_id=pr.external_id,
                    reviewer=rng.choice(reviewers),
                    body=rng.choice(_COMMENT_BODIES),
                    created_at=at,
                )
            )
            at += timedelta(minutes=rng.randint(5, 240))
        return comments

    def _make_bugs(self, rng: random.Random, repo: Repository, prs: list[PullRequest]) -> list[Bug]:
        merged = [pr for pr in prs if pr.state is PullRequestState.MERGED]
        bugs: list[Bug] = []
        for k in range(1, rng.randint(3, 6) + 1):
            opened_at = BASE_TIME + timedelta(hours=rng.randint(0, WINDOW_HOURS))
            closed_at = (
                opened_at + timedelta(hours=rng.randint(1, 240)) if rng.random() < 0.7 else None
            )
            linked = rng.choice(merged).external_id if merged and rng.random() < 0.5 else None
            bugs.append(
                Bug(
                    source=self.name,
                    external_id=f"{repo.external_id}-bug-{k}",
                    repository_external_id=repo.external_id,
                    title=f"Bug {k} in {repo.name}",
                    severity=rng.choice(list(BugSeverity)),
                    opened_at=opened_at,
                    closed_at=closed_at,
                    linked_pull_request_external_id=linked,
                )
            )
        return bugs


_COMMENT_BODIES = (
    "Can we add a test for the empty case?",
    "Nit: rename this to something more specific.",
    "This query runs inside a loop; consider batching.",
    "Looks good to me.",
    "Should this handle a timeout?",
    "Please extract this into a helper.",
)
