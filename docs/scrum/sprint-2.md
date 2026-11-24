# Sprint 2 (19-24 Nov 2026): MVP complete, monitoring, documentation

- **Product Owner:** Serge Hagopian
- **Scrum Master:** Abhiram Kidambi
- **Sprint Goal:** A working two-service product that deploys itself to Azure and can be
  monitored, with its documentation, by Tue 24 Nov 23:59.

## Items selected

Everything in the Product Backlog, including the items carried over from Sprints 0 and 1.
Story numbers are from [`../product-backlog.md`](../product-backlog.md).

| Item | Issue | Pull requests | Status |
|---|---|---|---|
| Sprint 0 carry-over: backlog, Definition of Done, roles, decisions | - | #1 | Done (merged) |
| 1. Runnable skeleton | - | #2 | Done (merged) |
| CI on every push and pull request (first half of story 10) | #11 | #13 | Done (merged) |
| 9. Versioned migrations | #10 | #14, #17 | Done (merged) |
| 2-5. Post, browse, edit, delete, mark swapped (API) | #3, #4, #5, #6 | #15 | Done (merged) |
| 7. Fairness rule correct and tested | #8 | #16 | Done (merged) |
| 6. Propose a swap and get a verdict (API) | #7 | #17 | Done (merged) |
| 2-5. Listings in the UI | #3, #4, #5, #6 | #18 | Done (merged) |
| 6. Propose a swap in the UI; 8. swap checker down | #7, #9 | #19 | Done (merged) |
| 10. CD: build, push, deploy, health check; end-to-end checks | #11 | #20, #35 | Done (merged; OIDC in #35) |
| 11. Health, dashboard and SLO | #12 | #21 | Done in repo (workbook/KQL); install on Azure at Review |
| Documentation | - | #22 | Done (merged) |
| Fixes from an independent code review | - | #23 | Done (merged) |
| Alignment with the assignment brief | - | #24 | Done (merged) |
| Review follow-ups (pooling, CSP, paging, accept guard, docs) | - | #25–#34 | Done (merged via #34) |

## Done means deployed

By our Definition of Done an item is Done only when it is merged to `main` and deployed.

- [x] Merge the pull requests into `main`, lowest number first, with merge commits.
- [x] Run `infra/setup.sh` and set the GitHub variables and secrets (`docs/deploy.md`).
- [x] First deploy green; live URL in the README.
- [ ] Each query in `infra/monitoring/` run against real logs; dashboard installed (do before / during Sprint Review).
- [x] Roles, reviews and retrospective agreements filled in for all three sprints.
- [ ] `main` tagged `submission`; URL and SHA submitted on Blackboard.

## Items not done

- GitHub Projects board was not created during the sprint (issues + `product-backlog.md` used instead). Create the board before the Review (commands in the README).
- Log Analytics workbook not yet imported into the Azure portal; KQL files are in the repo and ready to paste.
- `submission` tag and Blackboard URL/SHA still outstanding at the time of writing.

## Review (25-26 Nov)

_Filled in after the Sprint Review: what was demonstrated and the feedback received._

## Retrospective agreements

- Get Azure access (tenant invite, federated credentials, secrets) working early in the sprint, not on the last day.
- Prefer merging a stacked series of small PRs over one giant PR; after a stack lands, re-approve the PR into `main`.
- Next sprint: add a simple identity check so a person can only offer their own listings, and run the monitoring workbook on real traffic from day one.
