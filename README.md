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

See the "Run locally" section once the skeleton lands: `docker compose up`, then
`GET /health` on each service.

## Working agreement

- No direct pushes to `main`. Every change goes through a PR approved by a teammate.
- No secrets in the repo, ever. Use `.env` (git-ignored) locally and GitHub secrets in CI.
- Done means what [`docs/definition-of-done.md`](docs/definition-of-done.md) says.
- Log AI-assisted work in [`AI_USAGE.md`](AI_USAGE.md).
