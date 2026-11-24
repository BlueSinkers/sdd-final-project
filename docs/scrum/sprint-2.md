# Sprint 2 (19-24 Nov 2026): MVP complete, monitoring, documentation

- **Product Owner:** _TBD (rotates from Sprint 1)_
- **Scrum Master:** _TBD (rotates from Sprint 1)_
- **Sprint Goal:** A working two-service product that deploys itself to Azure and can be
  monitored, with its documentation, by Tue 24 Nov 23:59.

## Items selected

Everything in the Product Backlog, including the items carried over from Sprints 0 and 1.
Story numbers are from [`../product-backlog.md`](../product-backlog.md).

| Item | Issue | Pull requests | Status |
|---|---|---|---|
| Sprint 0 carry-over: backlog, Definition of Done, roles, decisions | - | #1 | Approved, waiting to merge |
| 1. Runnable skeleton | - | #2 | Approved, waiting to merge |
| CI on every push and pull request (first half of story 10) | #11 | #13 | In review |
| 9. Versioned migrations | #10 | #14, #17 | In review |
| 2-5. Post, browse, edit, delete, mark swapped (API) | #3, #4, #5, #6 | #15 | In review |
| 7. Fairness rule correct and tested | #8 | #16 | In review |
| 6. Propose a swap and get a verdict (API) | #7 | #17 | In review |
| 2-5. Listings in the UI | #3, #4, #5, #6 | #18 | In review |
| 6. Propose a swap in the UI; 8. swap checker down | #7, #9 | #19 | In review |
| 10. CD: build, push, deploy, health check; end-to-end checks | #11 | #20 | In review |
| 11. Health, dashboard and SLO | #12 | #21 | In review |
| Documentation | - | #22 | In review |
| Fixes from an independent code review | - | #23 | In review |
| Alignment with the assignment brief | - | #24 | In review |

## Done means deployed

By our Definition of Done an item is Done only when it is merged to `main` and deployed.
Update the Status column as that happens.

- [ ] Merge the pull requests into `main`, lowest number first, with merge commits.
- [ ] Run `infra/setup.sh` and set the GitHub variables and secrets (`docs/deploy.md`).
- [ ] First deploy green; live URL in the README.
- [ ] Each query in `infra/monitoring/` run against real logs; dashboard installed.
- [ ] Roles, reviews and retrospective agreements filled in for all three sprints.
- [ ] `main` tagged `submission`; URL and SHA submitted on Blackboard.

## Items not done
_Filled in at the Sprint Review: anything above that did not reach Done, and why._

## Review (25-26 Nov)
_Filled in after the Sprint Review: what was demonstrated and the feedback received._

## Retrospective agreements
_Filled in by the Scrum Master: the main agreement, and what the team would do next sprint._
