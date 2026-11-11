"""FakeSource-specific behaviour (the contract suite covers the shared rules)."""

from devmetrics.sources.fake import FakeSource
from tests.contract.source_contract import read_all


async def test_same_seed_gives_identical_data() -> None:
    first = await read_all(FakeSource(seed=7))
    second = await read_all(FakeSource(seed=7))

    assert first == second


async def test_different_seeds_give_different_data() -> None:
    first = await read_all(FakeSource(seed=7))
    second = await read_all(FakeSource(seed=8))

    assert first != second


async def test_size_follows_constructor_arguments() -> None:
    snapshot = await read_all(FakeSource(repositories=3, pull_requests_per_repo=4))

    assert len(snapshot.repositories) == 3
    assert len(snapshot.all_pull_requests()) == 12
    assert all(len(prs) == 4 for prs in snapshot.pull_requests.values())
