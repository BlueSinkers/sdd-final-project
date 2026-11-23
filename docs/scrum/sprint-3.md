# Sprint 3: shipped and observable

- **Planned window:** Mon 23 - Tue 24 Nov 2026 (submission Tue 24 Nov, 23:59)
- **Product Owner:** _TBD (rotates from Sprint 2)_
- **Scrum Master:** _TBD (rotates from Sprint 2)_
- **Sprint goal:** Every merge deploys itself to Azure, we can see how the system behaves,
  and someone new can understand it from the docs.

## Sprint backlog

| Story | Issue | Pull requests |
|---|---|---|
| 10. CD: build, push, deploy, health check | #11 | #20 |
| 8. Partial failure proven in CI (end-to-end job) | #9 | #20 |
| 11. Health, dashboard and SLO | #12 | #21 |
| Documentation: README, decisions, data model, sprint files | - | #22 |

## Increment

- CD pipeline to GHCR, Azure Container Apps and Static Web Apps, with rollback by commit SHA.
- One re-runnable script that creates all Azure resources.
- Log Analytics queries, a workbook dashboard and the SLO definition.
- README, seven decision records, data model, deploy and monitoring guides.

## Still to do before submission

- [ ] Merge the pull request stack into `main` (bottom up).
- [ ] Run `infra/setup.sh` and set the GitHub variables and secrets (`docs/deploy.md`).
- [ ] Confirm the first deploy is green and put the live URL in the README.
- [ ] Run each query in `infra/monitoring/` against real logs and install the dashboard.
- [ ] Fill in the roles and outcomes in these sprint files, and the team table in the README.
- [ ] Tag the submission and record the tag and SHA.

## Outcome
_Filled in at the Sprint Review: what was accepted, what was not, and why._

## Retrospective
_Filled in by the Scrum Master: one thing to keep, one thing to change next time._
