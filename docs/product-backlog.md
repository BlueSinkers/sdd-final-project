# Initial Product Backlog

Ordered by priority. Size: S / M / L. Each story has a GitHub issue, closed by the pull
requests that deliver it. The live backlog and its status are in the repository's GitHub
Project; this file is the initial version.

| # | Story | Acceptance criteria | Size | Issue | Pull requests |
|---|---|---|---|---|---|
| 1 | As a team, we have a runnable skeleton so we can build on it. | `docker compose up` starts both services; `GET /health` returns 200 on each. | S | - | #2 |
| 2 | As a student, I can post a listing so others can see what I offer. | `POST /listings` validates title, category, condition 1-5, value > 0 and returns 201. | M | #3 | #15, #18 |
| 3 | As a student, I can browse all listings. | `GET /listings` returns listings; UI shows them. | M | #4 | #15, #18 |
| 4 | As a student, I can edit or delete my listing. | `PUT` and `DELETE /listings/{id}` work; 404 for unknown ids. | S | #5 | #15, #18 |
| 5 | As a student, I can mark a listing swapped. | Status changes open -> swapped and shows in the UI. | S | #6 | #15, #18 |
| 6 | As a student, I can propose a swap and see how fair it is. | `POST /swaps` with two snapshots returns a verdict and stores the proposal. | M | #7 | #17, #19 |
| 7 | As a developer, the fairness rule is correct and tested. | Pure function; boundaries and zero value covered by unit tests. | S | #8 | #16 |
| 8 | As a student, I still browse when the swap checker is down. | UI shows "swap checker unavailable"; requests time out cleanly. | M | #9 | #19, #20 |
| 9 | As a developer, schema changes are versioned. | Migration files applied on startup for each service. | M | #10 | #14, #17 |
| 10 | As a team, CI/CD builds, tests and deploys on merge. | GitHub Actions to GHCR to Azure Container Apps; `/health` checked. | L | #11 | #13, #20 |
| 11 | As an operator, I can see health and the SLO. | Log Analytics queries and dashboard: request count, error rate, latency. | M | #12 | #21 |

## Fairness rule

`adjusted = estimated_value * (0.5 + condition / 10)`, `fairness = min(a, b) / max(a, b)`.
Fair at 0.8 or above, Lopsided from 0.5 up to 0.8, Very uneven below 0.5.
