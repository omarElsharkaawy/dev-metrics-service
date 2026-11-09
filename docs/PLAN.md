# Engineering Metrics Service: Build Plan

Nov 9, 2026 · @Omar Elsharkawy

A 3-week plan of 13 steps (about 31 hours) to build `devmetrics`, a Python service that ingests pull requests, review comments and bugs, stores them in Postgres, and serves engineering KPIs through a tested, Dockerized FastAPI API with CI.

## Goal, scope and stack

The goal is to replace the monthly reporting you do by hand with a service you can run, test and demo. The public version runs on GitHub and fake data; Takaful's Bitbucket and Jira stay in a separate private adapter (see the last section but one).

**In scope:** ingesting pull requests, review comments and bug issues; Postgres storage; KPI endpoints; scheduled sync; Docker; CI.

**Out of scope until Week 4:** embeddings, LLM calls and any UI. A dashboard can call the API later.

| Layer | Choice | Why |
| --- | --- | --- |
| Language and tooling | Python 3.12, uv, Ruff, mypy (strict), pytest | Typed, fast feedback, the habits postings ask for |
| API | FastAPI, Pydantic v2 | Typed contracts and a free OpenAPI page |
| Data | PostgreSQL 16 (pgvector image), SQLAlchemy 2.0 async, Alembic | Production default; pgvector is ready for Week 4 |
| HTTP client | httpx (async), tenacity | Async calls with testable transports and retries |
| Scheduling | APScheduler with a Postgres advisory lock | No extra infrastructure |
| Delivery | Docker multi-stage, Compose, GitHub Actions | Shows you can ship, not only code |

### The 13 steps at a glance

| Week | Step | What you build | Hours |
| --- | --- | --- | --- |
| 1 | S1 | Project skeleton and quality gates | 1.5 |
| 1 | S2 | Domain models with Pydantic | 2 |
| 1 | S3 | Source interface and fake source | 1.5 |
| 1 | S4 | GitHub source adapter | 3.5 |
| 1 | S5 | Reference KPI functions | 1.5 |
| 2 | S6 | Postgres schema and migrations | 3 |
| 2 | S7 | Idempotent ingestion and sync runs | 3 |
| 2 | S8 | REST API for pull requests and comments | 2.5 |
| 2 | S9 | KPI endpoints in SQL | 2.5 |
| 3 | S10 | Auth, scheduler and logging | 3 |
| 3 | S11 | Docker and Compose | 2 |
| 3 | S12 | CI pipeline | 2 |
| 3 | S13 | Docs, demo data and release | 3 |

## Architecture

&#91;embedded content: architecture · 3 sources, 5 layers\]

Sources plug in behind one interface, so the rest of the service never knows whether data came from GitHub, the fake source or a private system. Only the ingestion service writes to Postgres, and only the services layer reads from it.

## Data model and API

Five tables are enough. Every row from outside carries a `source` and an `external_id`, and the pair is unique. That unique pair is what makes re-running a sync safe.

| Table | Key columns | Notes |
| --- | --- | --- |
| `repositories` | id, source, external\_id, name | One row per repo or project |
| `pull_requests` | id, repository\_id, author, state, created\_at, first\_review\_at, merged\_at, lines\_changed | Unique (source, external\_id); index (repository\_id, created\_at) |
| `review_comments` | id, pull\_request\_id, reviewer, body, created\_at, search\_vector | Full-text search column; later an embedding column |
| `bugs` | id, repository\_id, severity, opened\_at, closed\_at, linked\_pull\_request\_id | Powers the bug-rate KPI |
| `sync_runs` | id, source, started\_at, finished\_at, status, items\_seen, watermark | The audit trail and the incremental-sync cursor |

### Endpoints

| Method and path | Purpose | Step |
| --- | --- | --- |
| `GET /health` | Liveness and database check | S8 |
| `GET /pull-requests` | Filter by repo, author, state and date range; cursor pagination | S8 |
| `GET /pull-requests/{id}` | One pull request with its comments | S8 |
| `GET /comments/search?q=` | Full-text search over review comments | S8 |
| `GET /kpis/cycle-time` | Median and 90th percentile time to merge, by week | S9 |
| `GET /kpis/review-latency` | Time to first review, by reviewer and by week | S9 |
| `GET /kpis/bug-rate` | Bugs per merged pull request, by month | S9 |
| `GET /kpis/reviewer-load` | Reviews done per reviewer in a period | S9 |
| `POST /sync` | Start a sync in the background; returns 202 and a run id | S10 |
| `GET /sync/runs` | Recent sync runs and their status | S10 |

Every `GET` returns typed Pydantic models, so the OpenAPI page at `/docs` doubles as your API reference. Everything except `/health` needs an API key from S10 onward.

## Week 1: Python foundations and the data layer

By the end of the week you can fetch real pull requests from GitHub, turn them into typed objects and compute KPIs on them, all without a database. Every step ends with `make check` green (lint, types, tests).

### S1. Project skeleton and quality gates (1.5 h)

**Build:** a `devmetrics` repo with `pyproject.toml`, a `src/` layout, uv for dependencies, Ruff, mypy in strict mode, pytest, and a `Makefile` with `check`, `test` and `fmt` targets. One trivial test that passes.

**Learn first:**

- [uv documentation](https://docs.astral.sh/uv/): projects, lockfile, `uv run`
- [Writing your pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [Ruff](https://docs.astral.sh/ruff/) and [mypy getting started](https://mypy.readthedocs.io/en/stable/getting_started.html)

**Done when:** a fresh clone runs `uv sync && make check` without any manual step.

### S2. Domain models with Pydantic (2 h)

**Build:** frozen models for `Repository`, `PullRequest`, `ReviewComment` and `Bug`, in `domain/models.py`. Timestamps must be timezone-aware, and a validator rejects naive datetimes.

**Learn first:**

- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/) and [validators](https://docs.pydantic.dev/latest/concepts/validators/)
- [Aware and naive datetimes](https://docs.python.org/3/library/datetime.html#aware-and-naive-objects)
- [pytest parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html)

**Done when:** tests cover valid input, a naive datetime being rejected, and a model being immutable.

### S3. Source interface and fake source (1.5 h)

**Build:** a `SourceAdapter` protocol in `sources/base.py` with async iterators for pull requests, comments and bugs, plus a `FakeSource` that generates a repeatable data set from a seed. Write contract tests that any adapter must pass.

**Learn first:**

- [mypy protocols](https://mypy.readthedocs.io/en/stable/protocols.html): the Python version of a Dart interface
- [Async generators, PEP 525](https://peps.python.org/pep-0525/) and [asyncio tasks](https://docs.python.org/3/library/asyncio-task.html)
- [Cosmic Python, the repository pattern](https://www.cosmicpython.com/book/chapter_02_repository.html)

**Done when:** the same contract test suite runs against `FakeSource` and will later run against the GitHub adapter.

### S4. GitHub source adapter (3.5 h)

**Build:** `GitHubSource` using httpx. It follows `Link` header pagination, waits when the rate limit is hit (`X-RateLimit-Reset`), and retries transient errors with tenacity. Configuration comes from pydantic-settings, with the token read from the environment.

**Learn first:**

- [httpx async client](https://www.python-httpx.org/async/) and [custom transports](https://www.python-httpx.org/advanced/transports/) for tests
- [GitHub: pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api) and [rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [tenacity](https://tenacity.readthedocs.io/en/latest/) and [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

**Done when:** tests run against recorded JSON through `httpx.MockTransport` (no network), including a rate-limit response and a two-page result.

### S5. Reference KPI functions (1.5 h)

**Build:** pure functions in `domain/kpi.py` for cycle time, review latency, bug rate and reviewer load, working on lists of models. These are your oracle: in S9 the SQL must give the same answers.

**Learn first:**

- [`statistics` module](https://docs.python.org/3/library/statistics.html): median and quantiles
- [Hypothesis quickstart](https://hypothesis.readthedocs.io/en/latest/quickstart.html): property-based tests

**Done when:** tests pin the results for a small hand-checked data set, and one Hypothesis test proves the median never exceeds the maximum.

## Week 2: Postgres and the API

The in-memory pipeline becomes a real service. By Friday you can sync data into Postgres twice and see no duplicates, then ask the API for pull requests and KPIs.

### S6. Postgres schema and migrations (3 h)

**Build:** a Compose file running `pgvector/pgvector:pg16`, SQLAlchemy 2.0 models using `Mapped[...]` annotations, an async engine and session factory, and an Alembic setup that works with the async driver. First migration creates the five tables with the unique `(source, external_id)` constraints and the `(repository_id, created_at)` index.

**Learn first:**

- [SQLAlchemy 2.0 quickstart](https://docs.sqlalchemy.org/en/20/orm/quickstart.html) and [asyncio support](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html) and [cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html)
- [Postgres indexes](https://www.postgresql.org/docs/current/indexes.html)

**Done when:** `alembic upgrade head` and `alembic downgrade base` both work on an empty database.

### S7. Idempotent ingestion and sync runs (3 h)

**Build:** an ingestion service that pulls from any `SourceAdapter` and writes with `INSERT ... ON CONFLICT DO UPDATE`. Each run creates a `sync_runs` row and stores a watermark, so the next run only asks the source for what changed.

**Learn first:**

- [Postgres INSERT and ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html)
- [SQLAlchemy PostgreSQL dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html): the `insert().on_conflict_do_update()` construct
- [pytest fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html), [pytest-asyncio](https://pytest-asyncio.readthedocs.io/en/latest/) and [Testcontainers for Python](https://testcontainers-python.readthedocs.io/en/latest/)

**Done when:** an integration test on a real Postgres runs the sync twice and the row counts do not change.

### S8. REST API for pull requests and comments (2.5 h)

**Build:** an app factory with a lifespan hook that owns the database engine, a session dependency, and routers for `/health`, `/pull-requests`, `/pull-requests/{id}` and `/comments/search`. Pagination uses a cursor, not page numbers. Search uses a Postgres full-text index.

**Learn first:**

- [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/), then [dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) and [bigger applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Testing FastAPI](https://fastapi.tiangolo.com/tutorial/testing/) and [async tests](https://fastapi.tiangolo.com/advanced/async-tests/)
- [Postgres full-text search](https://www.postgresql.org/docs/current/textsearch-intro.html)

**Done when:** API tests cover filters, the last page of a cursor, a 404, and a search that finds a known comment.

### S9. KPI endpoints in SQL (2.5 h)

**Build:** a `services/metrics.py` module with one query per KPI, using `date_trunc`, `percentile_cont` and window functions, exposed under `/kpis/...`. Check the slowest query with `EXPLAIN ANALYZE`, add an index if it helps, and record the decision in your first ADR.

**Learn first:**

- [Postgres window functions](https://www.postgresql.org/docs/current/tutorial-window.html) and [aggregate functions](https://www.postgresql.org/docs/current/functions-aggregate.html)
- [Using EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html) and [Use The Index, Luke](https://use-the-index-luke.com/)
- [Architecture Decision Records](https://adr.github.io/)

**Done when:** a test loads the same fake data, runs the S5 Python functions and the S9 SQL, and the numbers match.

## Week 3: Ship it

The service becomes something another person could run and trust: protected, scheduled, containerised, tested on every push and documented.

### S10. Auth, scheduler and logging (3 h)

**Build:** an API-key dependency for every route except `/health`. `POST /sync` starts a run in the background and returns 202 with a run id. APScheduler runs a nightly sync, guarded by a Postgres advisory lock so two instances never sync at once. structlog writes JSON logs with a request ID on every line.

**Learn first:**

- [FastAPI security reference](https://fastapi.tiangolo.com/reference/security/) and [background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [APScheduler 3.x](https://apscheduler.readthedocs.io/en/3.x/) and [Postgres explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- [structlog](https://www.structlog.org/en/stable/) and [The Twelve-Factor App: config](https://12factor.net/config)

**Done when:** tests show a missing key gives 401, and a second concurrent sync is refused while the first holds the lock.

### S11. Docker and Compose (2 h)

**Build:** a multi-stage Dockerfile that installs dependencies with uv, runs as a non-root user and has a health check. Compose starts Postgres, a one-shot migration job and the API, in that order.

**Learn first:**

- [Multi-stage builds](https://docs.docker.com/build/building/multi-stage/) and [build best practices](https://docs.docker.com/build/building/best-practices/)
- [uv in Docker](https://docs.astral.sh/uv/guides/integration/docker/)
- [Compose getting started](https://docs.docker.com/compose/gettingstarted/)

**Done when:** `docker compose up` on a clean machine gives a working `/docs` page, and the image is small enough that you can explain why.

### S12. CI pipeline (2 h)

**Build:** a GitHub Actions workflow with jobs for lint, type check, tests (with a Postgres service container) and a Docker build, using the uv cache to keep runs fast.

**Learn first:**

- [GitHub Actions overview](https://docs.github.com/en/actions) and [building and testing Python](https://docs.github.com/en/actions/use-cases-and-examples/building-and-testing/building-and-testing-python)
- [PostgreSQL service containers](https://docs.github.com/en/actions/using-containerized-services/creating-postgresql-service-containers)
- [uv with GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/)

**Done when:** a pull request with a deliberate type error fails the pipeline, and the fixed version passes.

### S13. Docs, demo data and release (3 h)

**Build:** a README with the architecture diagram, a quick start and example `curl` calls; a `seed` command that fills the database from `FakeSource`; three ADRs (source adapter, idempotent upserts, SQL for KPIs); a changelog; and a `v0.1.0` tag. Write a two-minute demo script for interviews.

**Learn first:**

- [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/)
- [Cosmic Python](https://www.cosmicpython.com/): the whole book is a good reference for how you explain your design choices

**Done when:** someone who has never seen the repo can run the demo from the README alone in under ten minutes.

## Built for what comes next

The design leaves three doors open, so Weeks 4 to 13 extend this project instead of starting new ones.

| Plan weeks | Extension | Hook already in place |
| --- | --- | --- |
| 4 to 7 | RAG over review comments | pgvector image from S6, `review_comments` table, full-text search as the baseline to beat |
| 8 to 10 | An agent that answers questions about team health | Services-layer functions from S9 become the agent's tools |
| 11 to 13 | Flutter screen with an AI feature | Typed OpenAPI contract from S8 and S9 |

### Private adapters for Takaful data

Bitbucket and Jira belong in a separate private repository that depends on this package and implements `SourceAdapter`. Keep that code, real data and credentials out of the public repo, and check with your employer before using work data in anything you show publicly. The public demo should only ever use GitHub and the fake source.

### Further reading

- [Cosmic Python](https://www.cosmicpython.com/): architecture patterns in Python, which matches the adapter and service layers here
- [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/) and [SQLAlchemy 2.0 quickstart](https://docs.sqlalchemy.org/en/20/orm/quickstart.html): worth rereading once the project exists
- [pgvector](https://github.com/pgvector/pgvector): preview before Week 4

The links in this plan point to official documentation, but they have not been opened or checked from here. If one has moved, search the page title.

## Working with the instructor skill

The `devmetrics-instructor` skill for Claude Code turns this plan into a step-by-step course. Save it from the review card, export this doc as `docs/PLAN.md` in your repo, then open Claude Code in the repo and ask for a step by name.

| You say | What happens |
| --- | --- |
| `status` | Reads `docs/PROGRESS.md`, shows done and next steps with hours |
| `start S4` | Goal and a short lesson linking the concepts to Dart or Kotlin ideas you know, then the first small slice |
| `teach S4` | The lesson only, with no code written |
| `coach S4` | You write the code; Claude gives hints one level at a time, then reviews |
| `pair S4` | You and Claude alternate slices, tests first |
| `build S4` | Claude implements the step and explains each decision as it goes |
| `hint` | The next hint level for where you are stuck |
| `review` | Reads your diff against the step's "Done when" and gives a short review |
| `quiz S4` | Three questions on the step, to check you understood |
| `done S4` | Runs `make check`, confirms the criteria, updates the progress file |

**Progress file:** `docs/PROGRESS.md` holds one line per step with its status, date and a note on what you found hard. The skill updates it, so you can stop and resume on any day or any machine.

**Ground rules the skill follows:** one small slice at a time; test first when the step allows; nothing is marked done until `make check` passes; and if `docs/PLAN.md` exists it wins over the plan baked into the skill.
