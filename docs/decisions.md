# Architecture Decision Records

## ADR-1: Two services with separate databases
- **Status:** Accepted
- **Context:** Listings are catalog data that changes occasionally. Swaps are a log of
  proposals with their own lifecycle.
- **Decision:** Separate Listings and Swaps services, each with its own database. They
  never call each other; the UI sends listing snapshots to Swaps.
- **Consequences:** If Swaps is down, browsing and posting still work. The client is
  trusted to send honest snapshots, which is acceptable at this scope.

## ADR-2: Python, FastAPI and plain SQL
- **Status:** Accepted
- **Context:** Each of us already built FastAPI services on Azure SQL in Assignment 2. We
  have five days.
- **Decision:** Both services use FastAPI with pydantic models for validation and `pymssql`
  with hand-written, parameterised SQL in one `repository.py` per service. No ORM.
- **Consequences:** Two small tables do not need an ORM, and the SQL that runs is the SQL we
  wrote and can read. Validation errors come back as 422 with a field-level message for
  free. The cost is that we are tied to SQL Server: tests need a real SQL Server (a
  container locally and in CI) instead of an in-memory database. We accept that because it
  means the tests run against the same engine as production.

## ADR-3: The browser calls both services directly
- **Status:** Accepted
- **Context:** The UI needs data from both services. The alternatives were a gateway or
  backend-for-frontend in front of them, or one service proxying the other.
- **Decision:** The static UI calls each service directly. Each service has a CORS
  allow-list (`CORS_ORIGINS`) with exactly one entry: the UI's origin.
- **Consequences:** No third component to build, deploy and keep alive, and no hidden
  coupling: each part of the page depends on exactly one service, which is what makes the
  partial-failure behaviour simple. The cost is that the service URLs are public and CORS is
  not access control (any script outside a browser can call the API). With no accounts and
  no private data (ADR-7) that is acceptable here; with accounts we would add a gateway.

## ADR-4: The fairness score is computed in the Swaps service, from snapshots
- **Status:** Accepted
- **Context:** The score needs both listings' value and condition, which live in the
  Listings database. Swaps could fetch them from Listings, or the caller could send them.
- **Decision:** The caller sends a snapshot of both listings. The Swaps service validates the
  snapshot, computes the score and verdict itself (`fairness.py`, a pure module that works in
  whole cents and cuts the score to four decimals instead of rounding it up), and stores
  the snapshot, both adjusted values, the score and the verdict with the proposal. A caller
  can never send its own score.
- **Consequences:** Swaps works when Listings is down, and a proposal keeps showing what was
  actually compared even if the listing is edited or deleted later. The cost: a dishonest
  client can send a false value or condition, so the verdict is advice to the two students,
  not something to enforce. Accepting a swap does not require a fair verdict.

## ADR-5: Versioned SQL migrations, applied by the service on startup
- **Status:** Accepted
- **Context:** Schema changes must be repeatable from a clean clone and on Azure, without
  anyone running SQL by hand.
- **Decision:** Each service has `migrations/NNN_name.sql`. On startup it applies, in order,
  every file not yet recorded in its `schema_migrations` table, each in one transaction
  together with the row that records it. Applied files are never edited.
- **Consequences:** `docker compose up` on a clean clone and a deploy to Azure both end with
  the right schema. A failing migration rolls back and stops the service from starting, so
  the deploy's `/health` check fails and the old revision keeps serving. It is safe only
  because each service runs at most one replica (two replicas starting at once could race);
  if we scaled out we would move migrations to a separate deploy step. Migrations must stay
  compatible with the previous image so that a rollback works (see `deploy.md`).

## ADR-6: Scale to zero, and an SLO measured at the service
- **Status:** Accepted
- **Context:** The budget is small. Container Apps can scale to zero and Azure SQL serverless
  can pause, but then the first request after an idle period is slow: a few seconds for the
  container, up to about a minute for the database.
- **Decision:** Both services scale between 0 and 1 replica and both databases pause after
  60 idle minutes. The SLO is **99% of `POST /swaps` requests complete in under 500 ms over
  7 days**, measured from the service's own request log line, so the wait before a request
  reaches a starting container is not counted. The UI is built for the cold start: 8 second
  timeout, a clear "unavailable" state, automatic retry every 10 seconds.
- **Consequences:** Idle cost is close to zero and steady-state latency (tens of
  milliseconds locally) has a lot of room under 500 ms. The cost is honesty about what the
  number means: the first user after a quiet period waits longer than the SLO suggests. A
  request that arrives while the database is still resuming can take longer than 500 ms
  inside the service, and those do count against the SLO. If cold starts mattered to users
  we would set the minimum replicas to 1 and measure at the ingress instead.

## ADR-7: No user accounts
- **Status:** Accepted
- **Context:** The product is a small board for one class. Authentication would take a large
  share of five days and is not what the project is assessed on.
- **Decision:** No sign-in. A listing carries the name its owner typed. Anyone can edit,
  delete or accept.
- **Consequences:** The whole flow can be shown in one browser without setting up users. It
  is not safe for real use: anyone with the URL can change anything. Input is still
  validated on the server, the database enforces the same rules with check constraints, and
  the UI never inserts API text as HTML. Accounts and per-owner permissions are the first
  thing to add after the course.
