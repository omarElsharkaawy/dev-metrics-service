from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from devmetrics.domain.models import (
    Bug,
    BugSeverity,
    PullRequest,
    PullRequestState,
    Repository,
    ReviewComment,
)

T0 = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
CAIRO = timezone(timedelta(hours=2))


def make_repository(**overrides: object) -> Repository:
    data: dict[str, object] = {
        "source": "github",
        "external_id": "123",
        "name": "octo/hello",
    }
    return Repository.model_validate({**data, **overrides})


class TestRepository:
    def test_valid_input_builds_model(self) -> None:
        repo = make_repository()

        assert repo.source == "github"
        assert repo.name == "octo/hello"

    def test_is_immutable(self) -> None:
        repo = make_repository()

        with pytest.raises(ValidationError, match="frozen"):
            repo.name = "other"  # type: ignore[misc]

    def test_copy_with_update_returns_new_instance(self) -> None:
        repo = make_repository()

        renamed = repo.model_copy(update={"name": "octo/renamed"})

        assert renamed.name == "octo/renamed"
        assert repo.name == "octo/hello"

    @pytest.mark.parametrize("field", ["source", "external_id", "name"])
    def test_rejects_empty_strings(self, field: str) -> None:
        with pytest.raises(ValidationError):
            make_repository(**{field: ""})

    def test_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            make_repository(stars=5)


def make_pull_request(**overrides: object) -> PullRequest:
    data: dict[str, object] = {
        "source": "github",
        "external_id": "pr-1",
        "repository_external_id": "123",
        "number": 1,
        "title": "Add domain models",
        "author": "omar",
        "state": "open",
        "created_at": T0,
        "lines_changed": 42,
    }
    return PullRequest.model_validate({**data, **overrides})


class TestPullRequest:
    def test_valid_input_builds_model(self) -> None:
        pr = make_pull_request()

        assert pr.state is PullRequestState.OPEN
        assert pr.first_review_at is None
        assert pr.merged_at is None

    def test_parses_iso_string_with_offset(self) -> None:
        pr = make_pull_request(created_at="2026-11-02T09:00:00Z")

        assert pr.created_at == T0

    def test_normalizes_aware_datetimes_to_utc(self) -> None:
        pr = make_pull_request(created_at=datetime(2026, 11, 2, 11, 0, tzinfo=CAIRO))

        assert pr.created_at == T0
        assert pr.created_at.tzinfo is UTC

    @pytest.mark.parametrize("field", ["created_at", "first_review_at", "merged_at"])
    @pytest.mark.parametrize(
        "naive",
        [datetime(2026, 11, 2, 9, 0), "2026-11-02T09:00:00"],
        ids=["datetime", "iso-string"],
    )
    def test_rejects_naive_datetimes(self, field: str, naive: object) -> None:
        with pytest.raises(ValidationError, match="timezone"):
            make_pull_request(**{field: naive})

    def test_rejects_unknown_state(self) -> None:
        with pytest.raises(ValidationError):
            make_pull_request(state="draft")

    def test_rejects_negative_lines_changed(self) -> None:
        with pytest.raises(ValidationError):
            make_pull_request(lines_changed=-1)

    def test_merged_pull_request_requires_merged_at(self) -> None:
        with pytest.raises(ValidationError, match="merged_at is required"):
            make_pull_request(state="merged")

    @pytest.mark.parametrize("state", ["open", "closed"])
    def test_merged_at_only_allowed_when_merged(self, state: str) -> None:
        with pytest.raises(ValidationError, match="only allowed when state is 'merged'"):
            make_pull_request(state=state, merged_at=T0 + timedelta(hours=1))

    def test_valid_merged_pull_request(self) -> None:
        pr = make_pull_request(
            state="merged",
            first_review_at=T0 + timedelta(hours=2),
            merged_at=T0 + timedelta(hours=5),
        )

        assert pr.merged_at == T0 + timedelta(hours=5)

    @pytest.mark.parametrize("field", ["first_review_at", "merged_at"])
    def test_rejects_timestamps_before_created_at(self, field: str) -> None:
        with pytest.raises(ValidationError, match="before created_at"):
            make_pull_request(
                **{"state": "merged", "merged_at": T0, field: T0 - timedelta(seconds=1)}
            )

    def test_is_immutable(self) -> None:
        pr = make_pull_request()

        with pytest.raises(ValidationError, match="frozen"):
            pr.state = PullRequestState.MERGED  # type: ignore[misc]


def make_review_comment(**overrides: object) -> ReviewComment:
    data: dict[str, object] = {
        "source": "github",
        "external_id": "c-1",
        "pull_request_external_id": "pr-1",
        "reviewer": "reviewer-a",
        "body": "Consider a frozen model here.",
        "created_at": T0,
    }
    return ReviewComment.model_validate({**data, **overrides})


def make_bug(**overrides: object) -> Bug:
    data: dict[str, object] = {
        "source": "github",
        "external_id": "issue-9",
        "repository_external_id": "123",
        "title": "Crash on empty list",
        "severity": "high",
        "opened_at": T0,
    }
    return Bug.model_validate({**data, **overrides})


class TestReviewComment:
    def test_valid_input_builds_model(self) -> None:
        comment = make_review_comment()

        assert comment.reviewer == "reviewer-a"

    def test_rejects_naive_created_at(self) -> None:
        with pytest.raises(ValidationError, match="timezone"):
            make_review_comment(created_at=datetime(2026, 11, 2, 9, 0))

    def test_is_immutable(self) -> None:
        comment = make_review_comment()

        with pytest.raises(ValidationError, match="frozen"):
            comment.body = "edited"  # type: ignore[misc]


class TestBug:
    def test_valid_input_defaults_to_open_and_unlinked(self) -> None:
        bug = make_bug()

        assert bug.severity is BugSeverity.HIGH
        assert bug.closed_at is None
        assert bug.linked_pull_request_external_id is None
        assert bug.is_open

    def test_closed_bug_is_not_open(self) -> None:
        bug = make_bug(closed_at=T0 + timedelta(days=1))

        assert not bug.is_open

    def test_rejects_closed_before_opened(self) -> None:
        with pytest.raises(ValidationError, match="before opened_at"):
            make_bug(closed_at=T0 - timedelta(days=1))

    @pytest.mark.parametrize("field", ["opened_at", "closed_at"])
    def test_rejects_naive_datetimes(self, field: str) -> None:
        with pytest.raises(ValidationError, match="timezone"):
            make_bug(**{field: datetime(2026, 11, 2, 9, 0)})

    def test_is_immutable(self) -> None:
        bug = make_bug()

        with pytest.raises(ValidationError, match="frozen"):
            bug.severity = BugSeverity.LOW  # type: ignore[misc]
