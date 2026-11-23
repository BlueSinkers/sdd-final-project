# Thrift-Swap Board

A web app where students post items they want to swap (jacket, textbook, desk lamp).
When someone proposes a swap, the app tells them how fair the trade is:
**Fair trade**, **Lopsided** or **Very uneven**.

**Live URL:** _TBD (added after first deploy)_

## Team and roles

| Member | GitHub | Area |
|---|---|---|
| _TBD_ | @BlueSinkers | _TBD_ |
| _TBD_ | @SergeGod | _TBD_ |

Scrum roles (Product Owner and Scrum Master) rotate each sprint. The current holders
and sprint outcomes are in [`docs/scrum/`](docs/scrum/).

Proposed work split (can rotate): Listings service, Swaps service + fairness function,
static UI, CI/CD + Azure, monitoring + docs. Everyone must understand the whole system.

## Architecture

- **Static UI** (HTML/JS) calls both services directly from the browser.
- **Listings service** (own database): CRUD for listings (title, category, condition 1-5,
  estimated value in euros, status open/swapped).
- **Swaps service** (own database): `POST /swaps` takes two listing snapshots, computes a
  fairness score, stores the proposal and returns the verdict.
- The services never call each other. See [`docs/decisions.md`](docs/decisions.md).

## Run locally

```bash
cp .env.example .env                # local passwords, git-ignored
docker compose up --build
curl http://localhost:8001/health   # listings
curl http://localhost:8002/health   # swaps
open http://localhost:8080          # the board
```

Each returns `{"status":"ok",...}`. Each request logs one line (service, method, path, status,
duration). The first start takes about a minute: SQL Server has to be healthy before the
services start. If a port is already in use on your machine, set `LISTINGS_PORT`, `SWAPS_PORT`,
`SQL_PORT` or `UI_PORT` in `.env`.

Each service applies its own versioned migrations (`<service>/migrations/NNN_name.sql`) on
startup. Applied files are never edited; a schema change is a new file.

## Tests

The tests run against a real SQL Server, never against Azure. With the compose stack up:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt -r listings/requirements.txt -r swaps/requirements.txt
SA="mssql://sa:<SA_PASSWORD from .env>@localhost:1433"
(cd listings && TEST_DATABASE_URL="$SA/listings_test" pytest --cov=app --cov-fail-under=70)
(cd swaps && TEST_DATABASE_URL="$SA/swaps_test" pytest --cov=app --cov-fail-under=70)
```

The database named in `TEST_DATABASE_URL` is dropped and recreated on every run, so its name
must end in `_test`. Lint and format: `ruff check .` and `ruff format --check .`.

## Working agreement

- No direct pushes to `main`. Every change goes through a PR approved by a teammate.
- No secrets in the repo, ever. Use `.env` (git-ignored) locally and GitHub secrets in CI.
- Done means what [`docs/definition-of-done.md`](docs/definition-of-done.md) says.
- Log AI-assisted work in [`AI_USAGE.md`](AI_USAGE.md).
