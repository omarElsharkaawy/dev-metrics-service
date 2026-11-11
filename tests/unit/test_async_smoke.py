from collections.abc import AsyncIterator


async def count_to(n: int) -> AsyncIterator[int]:
    for i in range(1, n + 1):
        yield i


async def test_async_generator_runs_under_pytest() -> None:
    assert [i async for i in count_to(3)] == [1, 2, 3]
