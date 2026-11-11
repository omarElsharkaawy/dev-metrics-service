S1 | done | 2026-11-10 | Skeleton + gates. Gotcha: mypy errors if a path in `files` does not exist yet; fresh-clone check must use tracked files only.
S2 | done | 2026-11-10 | Frozen models + UtcDatetime. Gotchas: mypy needs pydantic.mypy plugin to see frozen; AwareDatetime keeps offset, so normalize to UTC.
S3 | done | 2026-11-11 | Protocol + FakeSource + contract suite. Gotchas: Protocol methods are plain def -> AsyncIterator (async def means coroutine); never inherit a Protocol (stubs return None); generate fake data once so reads are stable.
S4 | todo | | GitHub source adapter (3.5h)
S5 | todo | | Reference KPI functions (1.5h)
S6 | todo | | Postgres schema and migrations (3h)
S7 | todo | | Idempotent ingestion and sync runs (3h)
S8 | todo | | REST API for pull requests and comments (2.5h)
S9 | todo | | KPI endpoints in SQL (2.5h)
S10 | todo | | Auth, scheduler and logging (3h)
S11 | todo | | Docker and Compose (2h)
S12 | todo | | CI pipeline (2h)
S13 | todo | | Docs, demo data and release (3h)
