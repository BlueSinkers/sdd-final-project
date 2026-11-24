# Architecture Decision Records

Seven records: architecture, stack and storage, the feature beyond CRUD, the frontend,
deployment and pipeline, monitoring, and the changes made after an independent review. Each lists the alternatives we considered and what the
choice costs us.

## ADR-1: Architecture: two services split by what the data is, layered inside
- **Status:** Accepted
- **Context:** The brief asks for exactly two services, each in its own container with its
  own database. Listings are catalog data that changes occasionally. Swaps are a log of
  proposals with their own lifecycle (proposed, accepted, declined) and hold our feature
  beyond CRUD.
- **Decision:** A Listings service and a Swaps service, each with its own database and its
  own database user. They never call each other: the browser calls both over HTTP and
  carries a snapshot of the listings to Swaps (ADR-3). Inside each service the code is
  layered: `routes.py` (HTTP only), `models.py` (shapes and validation), `repository.py`
  (all SQL), and in Swaps a pure `fairness.py` with no database or HTTP in it.
- **Alternatives:** (a) Swaps fetches the listings from Listings over HTTP: the score would
  use authoritative values, but Swaps would stop working whenever Listings is down or cold.
  (b) Split by technical role (an API service and a scoring service): the scoring service
  would have no data of its own. (c) Hexagonal structure inside each service: more
  indirection than two small tables justify.
- **Consequences:** Either service keeps working when the other is down, which CI proves on
  every pull request. The costs: the client is trusted to send honest snapshots (ADR-3),
  and anything that involves both services (accepting a swap marks two listings as swapped)
  is coordinated by the browser, so it can be left half done if the tab closes in between.

## ADR-2: Stack and storage: FastAPI, Azure SQL serverless, plain SQL, migrations on startup
- **Status:** Accepted
- **Context:** The stack is fixed to the one from Assignment 2 and the sprint is short.
  Each service needs its own Azure SQL serverless database, and the schema must come from
  versioned migration files applied on startup.
- **Decision:** Python and FastAPI, with pydantic models for validation. `pymssql` with
  hand-written, parameterised SQL in one `repository.py` per service, no ORM. Each service
  has `migrations/NNN_name.sql`; on startup it applies, in order, every file not yet
  recorded in its `schema_migrations` table, each in one transaction with the row that
  records it. Applied files are never edited. Money is `DECIMAL(10,2)`; check constraints
  repeat the API's rules.
- **Alternatives:** (a) Node and Express: our Assignment 2 experience is all in Python. (b) SQLAlchemy
  and Alembic: a real benefit with many tables, but for one table per service it hides the
  SQL we want to be able to read and explain. (c) SQLite for tests: faster, but then the
  tests would not run on the engine we deploy to.
- **Consequences:** The SQL that runs is the SQL we wrote. Tests run against a real SQL
  Server (a container locally and in CI, never the Azure database). A failing migration
  rolls back and stops the service from starting, so the deploy's health check fails and
  the previous revision keeps serving. Migrations on startup are safe only because each
  service runs at most one replica. We are tied to SQL Server.

## ADR-3: The feature beyond CRUD: a fairness score computed by Swaps from snapshots
- **Status:** Accepted
- **Context:** When a swap is proposed the app says how fair it is. The score needs both
  listings' value and condition, which live in the Listings database.
- **Decision:** `adjusted = value x (0.5 + condition / 10)`, `fairness = smaller / larger`;
  Fair trade at 0.8 or above, Lopsided from 0.5, Very uneven below. The caller sends a
  snapshot of both listings. Swaps validates it, computes the score and verdict itself in
  whole cents (cut to four decimals, never rounded up across a boundary) and stores the
  snapshot, both adjusted values, the score and the verdict. A caller cannot send a score.
- **Alternatives:** (a) Compute the score in the browser: no server-side rule to test, and
  nothing stored. (b) Swaps looks the listings up in Listings: see ADR-1. (c) Ask an LLM to
  judge the trade: a paid dependency and an answer we could not unit test.
- **Consequences:** The rule is one small module with 100% test coverage, including both
  boundaries. A proposal keeps showing what was actually compared even if a listing is
  edited or deleted later. A dishonest client can send a false value, so the verdict is
  advice to the two students, not something we enforce: accepting does not require a fair
  verdict.

## ADR-4: Frontend: plain static files that call both services, CORS limited to the UI
- **Status:** Accepted
- **Context:** The UI must be a static site on Azure Static Web Apps that calls the services
  from the browser, with CORS restricted to its origin. User accounts are out of scope.
- **Decision:** Plain HTML, CSS and JavaScript modules with no build step. Each service
  allows exactly one origin (`CORS_ORIGINS`). Every request has an 8 second timeout; when a
  service does not answer the page says so in plain words, keeps the other half working,
  retries every 10 seconds and recovers on its own. Text from the API is only ever inserted
  as text. There is no sign-in: a listing carries the name its owner typed.
- **Alternatives:** (a) React or Vue built to static files: a build step and a dependency
  tree for a page with two lists and two forms. (b) A gateway in front of both services: it
  would be a third container, which is out of scope. (c) A hard-coded demo user or API key:
  allowed by the brief, but it would add nothing a reviewer could see.
- **Consequences:** Nothing to build or bundle: the pipeline uploads the folder. The page
  handles a scaled-to-zero service waking up. The costs: no component framework if the UI
  grows, CORS is not access control, and without accounts anyone with the URL can edit or
  delete anything. That is acceptable for a class demo and the first thing to change after.

## ADR-5: Deployment and pipeline: GitHub Actions, GHCR, Container Apps, scripted setup
- **Status:** Accepted
- **Context:** Every change must reach production through a reviewed pull request and an
  automated pipeline, with nothing changed by hand after the initial setup.
- **Decision:** CI on every push and pull request: lint, format check, dependency audit and
  static security scan, tests on a real SQL Server with a 70% coverage gate, image build,
  and end-to-end checks on the compose stack including both partial-failure cases. CD on
  merge to `main`, only if CI passed: push both images to GHCR tagged with the commit SHA,
  roll each Container App to that image, wait until `/health` returns 200 and reports that
  SHA, publish the UI with the service URLs written into `config.js`, then run a read-only
  smoke test against the public URLs. Rollback is the same workflow run by hand with an
  older SHA. The Azure resources are created once by `infra/setup.sh` (Azure CLI), named
  with the group prefix, with database URLs stored as Container App secrets.
- **Alternatives:** (a) Bicep or Terraform for the setup: declarative and credited, but we
  could not test a template against Azure in the time we had; a re-runnable CLI script was
  the smaller risk. (b) The `latest` tag only: no way to say what is deployed or to roll
  back. (c) Blue-green or canary with traffic splitting between revisions: with at most one
  replica and no real traffic there is little to observe.
- **Consequences:** What is deployed is always a known commit, visible in `/health`.
  Container Apps starts the new revision next to the old one and moves traffic only when it
  is ready, so a deploy that fails to start does not take the product down. The costs: the
  setup script must be kept in step with the resources by hand, and a migration must stay
  compatible with the previous image for a rollback to work.

## ADR-6: Monitoring: one log line per request, an SLO measured at the service, scale to zero
- **Status:** Accepted
- **Context:** We must see request count, error rate and response time in Azure and state
  one SLO with the query that measures it. Both Container Apps scale to zero and both
  databases auto-pause, so the first request after an idle period is slow: a few seconds
  for the container, up to about a minute for the database.
- **Decision:** Each service writes one line per request to standard output
  (`service method path status duration_ms`) at INFO level, with no request bodies. The
  Container Apps environment sends it to its Log Analytics workspace. Saved KQL queries and
  an Azure Workbook built on them give request count, error rate (5xx only) and response
  time. The SLO is **99% of `POST /swaps` requests complete in under 500 ms over 7 days**,
  measured from those log lines.
- **Alternatives:** (a) Application Insights: richer, but another Azure service, which the
  brief does not allow. (b) Measure the SLO at the ingress, including cold starts: more
  honest about what a user feels, but with scale-to-zero required the number would mostly
  measure idle time, not our code. (c) An SLO on `GET /listings`: the more frequent request,
  but proposing a swap is the one a user waits on to learn something.
- **Consequences:** Log volume is one short line per request. The SLO says how fast the
  service is once a request reaches it; the wait for a container to start is not in it, and
  we say so wherever we show the number. A request that arrives while the database is still
  resuming can exceed 500 ms inside the service, and that does count. The UI is built for
  the cold start instead (ADR-4).

## ADR-7: Hardening after review: what we fixed, and what we chose to leave
- **Status:** Accepted
- **Context:** After the first complete version we reviewed the whole stack again. It found
  no failing behaviour, but several places where the design relied on luck: a database login
  on every request, an "item cannot be traded twice" rule that lived only in the browser, an
  unbounded list, no security headers, no test for the log line the monitoring depends on,
  and action versions that anyone could move.
- **Decision:** (1) A small connection pool in each service, with a rollback on return, a
  ping after a few idle seconds, an age limit, and no reuse after a database error.
  (2) Accepting a swap fails with 409 if another swap that shares an item was accepted after
  this proposal was made, serialized by an application lock. (3) `GET /listings` takes
  `limit` (default 200, at most 500) and `offset`. (4) A Content-Security-Policy and other
  headers for the static UI, UI unit tests in CI, a page that refreshes itself, and a
  "Mark as swapped" button for an accepted swap whose listings were never marked. (5) A test
  that the log line parses with the KQL queries. (6) GitHub Actions pinned to commit SHAs.
- **Alternatives:** (a) Have Swaps ask Listings whether an item is open: the correct answer,
  but it breaks ADR-1, and Swaps would fail whenever Listings is cold. We use the data Swaps
  already owns instead. (b) A cross-service transaction or an outbox to make "accept" atomic:
  far too heavy for two tables; the repair button covers the failure we can actually hit.
  (c) Sign-in (ADR-4 left it out of scope): the real fix for "anyone can edit any listing" and for trusting snapshots, but
  it is a feature, not a fix, and would need a third store.
- **Consequences:** Reuse of connections makes a stale connection possible, which the ping
  and the age limit handle. The guard cannot see a swap that the browser accepted but never
  recorded. The snapshots are still taken on trust (the score is only as honest as the
  caller), and a board over 200 listings shows the newest 200 until the UI pages. We left the
  Azure firewall rule and the lack of an approval on `production` as they are, and wrote down
  why in [`deploy.md`](deploy.md).
