# AI Usage Log

Log each significant piece of AI-assisted work: what was asked, what was used, and what
you checked or changed yourself.

| Date | Who | Tool | What it was used for | How it was verified |
|---|---|---|---|---|
| 2026-11-19 | _TBD_ | Claude Code | Sprint 0 docs and local skeleton | Reviewed in PR |
| 2026-11-23 | Serge Hagopian | Claude Code | CI workflow: lint, format check, tests with coverage gate, image build (#13) | CI run green on the PR |
| 2026-11-23 | Serge Hagopian | Claude Code | Listings service: database layer, migrations, CRUD endpoints and tests (#14, #15). The database and migration code follows the pattern from my Assignment 2 | 42 tests against SQL Server 2022 locally and in CI, 99% coverage |
| 2026-11-23 | Serge Hagopian | Claude Code | Swaps service: fairness functions, `POST /swaps`, accept/decline and tests (#16, #17) | 72 tests locally and in CI, including both verdict boundaries; worked example checked by hand (18.00 / 31.50 = 0.5714) |
| 2026-11-23 | Serge Hagopian | Claude Code | Static UI: listings board, swap proposal, partial-failure handling (#18, #19) | Used in a browser against both services: posted, proposed, accepted, then stopped each service in turn and watched the page degrade and recover |
| 2026-11-23 | Serge Hagopian | Claude Code | CD workflow, `infra/setup.sh`, end-to-end script (#20) | End-to-end script green in CI. **The CD workflow and the Azure script were not run against Azure when written**; see the PR |
| 2026-11-23 | Serge Hagopian | Claude Code | Log Analytics queries, workbook, SLO write-up, latency tool (#21) | Latency tool run locally (300 requests). **The queries and workbook were not run in Azure when written**; see the PR |
| 2026-11-23 | Serge Hagopian | Claude Code | README, decision records, data model, sprint files (#22) | Read against the code and the merged behaviour |
| 2026-11-23 | Serge Hagopian | Claude Code | Review of #1 and #2 | Read both diffs; #2's claim confirmed by the CI smoke run on top of it |
| 2026-11-23 | Serge Hagopian | Claude Code | Independent code review of the whole stack by a second AI reviewer, and the fixes that followed: fairness arithmetic in whole cents, input limits, error mapping, log-line safety, UI accept rules, SLO query, rollback and setup-script fixes | Every code fix has a test (138 tests pass); UI fixes checked in a browser; the SLO query fix could not be run in Azure |
| 2026-11-23 | Serge Hagopian | Claude Code | Check of the whole project against the assignment brief, and the changes that followed (#24): group naming in `infra/setup.sh`, CI on push, `pip-audit` and `bandit` in CI, FastAPI upgraded after the audit flagged the pinned version, deployed smoke test in CD, Definition of Done moved, sprint files matched to the brief's sprints, decision records rewritten with alternatives | 138 tests pass on the upgraded framework; audit and scan clean; smoke scenario run locally. The Azure parts are still unrun |
