# Architecture Decision Records

## ADR-1: Two services with separate databases
- **Status:** Accepted
- **Context:** Listings are catalog data that changes occasionally. Swaps are a log of
  proposals with their own lifecycle.
- **Decision:** Separate Listings and Swaps services, each with its own database. They
  never call each other; the UI sends listing snapshots to Swaps.
- **Consequences:** If Swaps is down, browsing and posting still work. The client is
  trusted to send honest snapshots, which is acceptable at this scope.

_More records (stack, CORS, SLO and cold starts, migrations) are added as decided._
