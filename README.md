# AlphaLens

**An AI research copilot for your Indian (NSE) stock portfolio.** Add the stocks you hold and AlphaLens keeps prices fresh during market hours, pulls and scores the news for every holding in the background, indexes the reports you upload, and answers questions about your portfolio with numbered, clickable citations: only from the sources it has stored, never from thin air. Saved "agents" run plain-English research instructions on demand or every morning, and a pgvector semantic cache answers repeat questions instantly.

> Portfolio/resume prototype. Built to show Django + DRF, React + TypeScript, PostgreSQL with pgvector, Redis, Celery workers + beat, Docker, CI and LLM integration working together end to end.

**Live demo:** https://alphalens.vercel.app _(placeholder)_ · **API:** https://alphalens-api.onrender.com/api/health/ _(placeholder)_
**Demo login:** `demo` / `demo12345` (or click **Use demo account**)

## Features

- **Portfolio dashboard**: holdings, live value, P&L, sector allocation donut, per-stock price charts (1M / 6M / 1Y). Prices refresh automatically every 15 minutes during NSE market hours.
- **News + documents per holding**: Google News headlines fetched by a scheduled job and scored for sentiment; PDFs (annual reports, call transcripts) uploaded and indexed asynchronously.
- **Ask AlphaLens**: chat answers grounded only in your stored documents, with `[n]` citation badges that highlight the matching source card.
- **Risk alerts**: holdings with clearly negative news in the last 7 days are flagged on the dashboard.
- **No-code agents**: save an instruction ("flag layoffs or guidance cuts in my IT stocks"), choose holdings and a schedule (manual or daily 8 AM), and every run's cited report is kept in a history.
- **Semantic cache**: a near-identical recent question returns the cached answer without calling the LLM; hit rate and cached vs. uncached latency are shown on the dashboard.

## Architecture

```mermaid
flowchart LR
    U[React + TS SPA<br/>Vercel] -->|JWT / HTTPS| API[Django REST API<br/>Render web service]
    API --> PG[(PostgreSQL 16<br/>+ pgvector)]
    API <-->|cache · throttle · locks| R[(Redis<br/>Render Key Value)]
    API -->|enqueue tasks| R
    B[Celery beat] -->|scheduled jobs| R
    R -->|broker| W[Celery worker]
    W --> PG
    W -->|locks · results| R
    W --> G[Gemini API<br/>chat + embeddings]
    W --> Y[yfinance<br/>NSE prices]
    W --> N[Google News RSS]
    API -->|/ask/ is synchronous| G
```

The API stays fast by pushing every slow, external call (prices, news, PDF embedding, agent runs) onto Celery. The only synchronous LLM path is `/ask/`, because the user is waiting for that answer; it is rate-limited and goes through the semantic cache first.

## Background jobs

Business logic lives in plain service functions (`services.py`, `ingest.py`, `rag.py`, `runner.py`). Celery tasks are thin wrappers, so everything is testable without a worker.

| Task | Triggered by | What it does | Retries |
|---|---|---|---|
| `portfolio.tasks.refresh_prices_task(user_id=None)` | `POST /holdings/refresh-prices/` (one user) · **beat** every 15 min, Mon–Fri 09:00–15:59 IST (all users) | Fetches the latest price per symbol; one bad ticker never breaks the batch; invalidates cached summaries | Network errors, exponential backoff, max 3 |
| `research.tasks.refresh_news_for_holding_task(holding_id)` | Holding created · `POST /holdings/{id}/refresh-news/` · fan-out below | Under a Redis lock: fetch RSS → embed new headlines → batch sentiment scoring | Network / Gemini 5xx errors, backoff, max 3 |
| `research.tasks.refresh_all_news_task()` | **beat** every 3 hours | Fans out one `refresh_news_for_holding_task` per holding with a Celery `group` | n/a (each child retries) |
| `research.tasks.ingest_document_task(document_id)` | `POST /documents/upload/` | Chunk → embed → store vectors; marks the document `ready` or `failed` | Network / Gemini 5xx errors, backoff, max 3 |
| `agents.tasks.run_agent_task(run_id)` | `POST /agents/{id}/run/` · scheduled job below | Refresh news, gather the last 7 days of documents, write a cited markdown report | Network / Gemini 5xx errors, backoff, max 3 |
| `agents.tasks.run_scheduled_agents_task()` | **beat** daily at 08:00 IST · `python manage.py run_agents` | Creates a `scheduled` run for every active daily agent and queues it | n/a |

Worker settings: `task_acks_late`, `worker_prefetch_multiplier=1`, 300s hard / 240s soft time limits, `task_track_started` (so `/api/tasks/{id}/` can report `STARTED`). Task start/finish is logged with task ids. Endpoints that enqueue work return **202 Accepted** with a `task_id`; the frontend polls it every 2 s and toasts when the job finishes.

## How Redis is used

1. **Celery broker + result backend**: every background job above goes through Redis.
2. **Django cache** (`django-redis`): price history (`price_history:{symbol}:{period}`, 15 min) and portfolio summaries (`summary:{user_id}`, 60 s, invalidated on any holding change or price refresh).
3. **Rate limiting**: `/ask/` uses a DRF `UserRateThrottle` (`ASK_RATE_LIMIT`, default 30/hour); DRF stores throttle history in the default cache, i.e. Redis.
4. **Distributed locks**: `core.locks.redis_lock` uses atomic `cache.add` (SET NX) with a timeout so the same holding's news is never refreshed by two workers at once (e.g. the 3-hourly fan-out overlapping a manual refresh or an agent run).

## RAG + semantic cache

1. The question is embedded with Gemini (`EMBEDDING_DIM` dimensions, matching the pgvector column).
2. **Cache check**: pgvector `CosineDistance` finds the user's most similar answered question from the last `SEMANTIC_CACHE_TTL_HOURS` with the same holding filter; if similarity ≥ `SEMANTIC_CACHE_THRESHOLD` (0.92) the stored answer is returned and logged as a cache hit.
3. **Retrieve**: the top 8 chunks by cosine distance, restricted to the user's `ready` documents (and selected holdings), using an HNSW index.
4. No chunks means a friendly "no documents yet" reply with no LLM call.
5. **Generate**: chunks go into the prompt as numbered sources `[1]..[n]` with title and date; the model must answer only from them and cite with `[n]`.
6. Only citations the answer actually references are returned, and every call is logged in `QueryLog` with its latency, which feeds the stats card.

## Tech stack

**Backend:** Python 3.11, Django 5.2, Django REST Framework, SimpleJWT, PostgreSQL 16 + pgvector, Redis, Celery 5 (+ beat, Flower), google-genai (Gemini), yfinance, feedparser, pypdf, whitenoise, gunicorn, pytest.
**Frontend:** Vite, React 19, TypeScript, Tailwind CSS 4, React Router, TanStack Query, axios, Recharts, react-markdown.
**Infra:** Docker Compose for local dev, GitHub Actions CI, Render (API + Postgres + Key Value), Vercel (frontend).

## Local setup

Prerequisites: Docker Desktop, Node 20+, and a free [Gemini API key](https://aistudio.google.com/apikey).

```bash
cp backend/.env.example backend/.env      # then set GEMINI_API_KEY
docker compose up --build                 # db, redis, backend :8000, worker, beat, flower :5555
docker compose exec backend python manage.py seed_demo
```

```bash
cd frontend
cp .env.example .env
npm install
npm run dev                               # http://localhost:5173
```

- API: http://localhost:8000/api/health/
- **Flower** (Celery monitoring): http://localhost:5555
- Django admin: create a user with `docker compose exec backend python manage.py createsuperuser`, then http://localhost:8000/admin/
- Trigger the daily agents now instead of waiting for 08:00: `docker compose exec backend python manage.py run_agents`

The Docker Postgres is published on host port **5433** so it doesn't clash with a locally installed Postgres. Inside Compose the services talk to `db:5432`. If another stack already holds 5433 or 6379 on the host, set `DB_HOST_PORT` / `REDIS_HOST_PORT` (e.g. `DB_HOST_PORT=5434 REDIS_HOST_PORT=6380 docker compose up --build`).

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | `change-me` | Django secret; use a long random value in production |
| `DEBUG` | `True` | `False` in production |
| `DATABASE_URL` | `postgres://alphalens:alphalens@localhost:5432/alphalens` | Postgres with pgvector |
| `REDIS_URL` | `redis://localhost:6379/0` | Broker, result backend, cache, throttle, locks |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Render's hostname is added automatically |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Frontend origin(s) |
| `GEMINI_API_KEY` | (none) | Required for embeddings, answers and sentiment |
| `GEMINI_CHAT_MODEL` | `gemini-2.5-flash` | Chat model (never hardcoded) |
| `GEMINI_EMBED_MODEL` | `gemini-embedding-001` | Embedding model |
| `EMBEDDING_DIM` | `768` | Requested output dimensionality; must match the vector columns |
| `SEMANTIC_CACHE_THRESHOLD` | `0.92` | Cosine similarity needed for a cache hit |
| `SEMANTIC_CACHE_TTL_HOURS` | `24` | How long answers stay cacheable |
| `ASK_RATE_LIMIT` | `30/hour` | Per-user `/ask/` throttle |
| `VITE_API_URL` (frontend) | `http://localhost:8000/api` | API base URL |

## Running tests

Tests use `alphalens.settings_test`: eager Celery, an in-memory cache (no Redis), and mocked Gemini, yfinance and RSS, so they never touch the network. They need a Postgres with pgvector:

```bash
docker compose up -d db
cd backend
DATABASE_URL=postgres://alphalens:alphalens@localhost:5433/alphalens pytest
```

Covered: auth; holdings CRUD, user isolation, summary math and cache invalidation; chunk overlap; async PDF ingest (ready and failed); the news lock; RAG scoping, citations and **cache hits that skip `generate`**; the 429 throttle; alerts; agent runs (success, failure, daily-only scheduling); and the beat schedule. CI runs the same suite against `pgvector/pgvector:pg16`, plus a lint and production build of the frontend.

## Deployment

**Backend → Render**
1. Create a **Key Value** (Redis) instance and a **Postgres** database in the same region. The first migration runs `CREATE EXTENSION vector` for you.
2. Create a **Web Service** from this repo with root directory `backend`, build command `./build.sh`, start command `./start.sh`, and health check path `/api/health/`. Or use the `render.yaml` blueprint.
3. Set the env vars from the table above, with `DEBUG=False`, `DATABASE_URL` from Render Postgres, `REDIS_URL` from Key Value's **internal** URL, and `CORS_ALLOWED_ORIGINS` set to your Vercel URL.
4. Seed the demo account: the free plan has no Shell tab, so set `SEED_DEMO_ON_START=true` (the blueprint does this) and `start.sh` runs `seed_demo` in the background on boot. Once "Use demo account" works, set it to `false` so later wake-ups don't re-seed. On a paid plan you can run `python manage.py seed_demo` in the Shell instead.

**Frontend → Vercel:** import the repo with root directory `frontend` and framework Vite, and set `VITE_API_URL=https://<your-render-app>.onrender.com/api`. `vercel.json` rewrites every route to `index.html` so deep links work.

### Free-tier worker note

Render background workers aren't free, so `start.sh` runs `celery worker -B` (worker + embedded beat, concurrency 1) in the background **inside the web service**, then `exec`s gunicorn. Set `RUN_WORKER_IN_WEB=false` to turn that off. `render.yaml` includes a commented-out separate `worker` service for paid plans, which is the production-correct layout.

- Render free web services **sleep when idle**. While asleep the embedded worker and beat sleep too, so scheduled jobs only run while the service is awake. Locally with Docker, the schedule runs normally. The frontend shows "Waking up the server…" when the first request takes more than 5 s.
- Render's free Postgres expires after a time limit; [Neon](https://neon.tech) supports pgvector and works by swapping `DATABASE_URL`.

## Screenshots

| | |
|---|---|
| Dashboard _(placeholder: `docs/dashboard.png`)_ | Ask with citations _(placeholder: `docs/ask.png`)_ |
| Agent run history _(placeholder: `docs/agents.png`)_ | Flower task monitor _(placeholder: `docs/flower.png`)_ |

## Notes and deviations from the original plan

- **Tata Motors**: the plan's example `TATAMOTORS.NS` stopped resolving on yfinance after the 2025 demerger. `seed_demo` tries candidates in order and uses `TMPV.NS` (Tata Motors Passenger Vehicles) instead.
- **Model names**: kept the plan's defaults (`gemini-2.5-flash`, `gemini-embedding-001`). Both come only from env vars, so switching to a newer model needs no code change.
- **`QueryLog.holding_ids`**: added so a cached answer is only reused for the same holding filter. Without it, an answer scoped to one stock could be replayed for a portfolio-wide question.
- Answers with no citations (e.g. "no documents yet") are never served from the cache, so newly added documents are used immediately.
- Gemini SDK retries are disabled (`HttpRetryOptions(attempts=1)`) because retries happen at the Celery task level, as the plan specifies.
- Docker publishes Postgres on host port 5433 (see Local setup).

## Future improvements

- Separate Render worker + beat services instead of running them inside the web dyno
- Streaming answers (server-sent events) for `/ask/`
- `django-celery-beat` so each agent can have its own custom schedule
- More data sources: exchange filings (NSE/BSE announcements), earnings call transcripts, broker research
