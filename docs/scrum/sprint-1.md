# Sprint 1: two working services

- **Planned window:** Thu 19 - Sat 21 Nov 2026
- **Product Owner:** _TBD_
- **Scrum Master:** _TBD_
- **Sprint goal:** Both services run from a clean clone, store their own data, and the
  fairness rule is correct and tested.

## Sprint backlog

| Story | Issue | Pull requests |
|---|---|---|
| 1. Runnable skeleton | - | #1, #2 |
| 2. Post a listing (API) | #3 | #15 |
| 3. Browse listings (API) | #4 | #15 |
| 4. Edit or delete a listing (API) | #5 | #15 |
| 5. Mark a listing swapped (API) | #6 | #15 |
| 6. Propose a swap and get a verdict (API) | #7 | #17 |
| 7. Fairness rule correct and tested | #8 | #16 |
| 9. Versioned migrations | #10 | #14, #17 |
| CI on every pull request (first half of story 10) | #11 | #13 |

## Increment

- `docker compose up` starts SQL Server, both services and their databases.
- Listings: full CRUD with validation, 42 tests. Swaps: scoring, storing, accept/decline,
  72 tests. Both at 99% coverage, against a real SQL Server.
- CI runs lint, format check, tests with a 70% coverage gate and image builds on every PR.

## Outcome
_Filled in at the Sprint Review: what was accepted, what was not, and why._

## Retrospective
_Filled in by the Scrum Master: one thing to keep, one thing to change next sprint._
