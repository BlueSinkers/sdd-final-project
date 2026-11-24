# Definition of Done

A backlog item is **Done** only when all of these are true:

- [ ] Acceptance criteria are met.
- [ ] Merged to `main` through a PR approved by a teammate (no direct pushes).
- [ ] CI is green (lint, format check, tests, image build).
- [ ] New logic has unit tests; core logic stays at or above 70% coverage.
- [ ] Runs from a clean clone with `docker compose up`.
- [ ] Deployed by the pipeline and `GET /health` passes.
- [ ] No secrets, no stack traces shown to users, one log line per request.
- [ ] Docs updated if behaviour, data model or a decision changed.
- [ ] AI-assisted work is logged in `AI_USAGE.md`.
