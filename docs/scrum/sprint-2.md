# Sprint 2: a usable board

- **Planned window:** Sun 22 Nov 2026
- **Product Owner:** _TBD (rotates from Sprint 1)_
- **Scrum Master:** _TBD (rotates from Sprint 1)_
- **Sprint goal:** A student can do everything from the browser, and the page stays useful
  when one service is down.

## Sprint backlog

| Story | Issue | Pull requests |
|---|---|---|
| 2-5. Post, browse, edit, delete, mark swapped (UI) | #3, #4, #5, #6 | #18 |
| 6. Propose a swap and see the verdict (UI) | #7 | #19 |
| 8. Browse still works when the swap checker is down | #9 | #19 |

## Increment

- Static UI served at `http://localhost:8080`: listings board, post/edit dialog, swap
  proposal with verdict, accept/decline.
- Partial failure handled both ways, with an 8 second timeout and automatic recovery.
- Checked by hand in a browser with each service stopped in turn.

## Outcome
_Filled in at the Sprint Review: what was accepted, what was not, and why._

## Retrospective
_Filled in by the Scrum Master: one thing to keep, one thing to change next sprint._
