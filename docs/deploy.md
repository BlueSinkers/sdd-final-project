# Deploying

## How a change reaches production

1. A pull request runs **CI** (`.github/workflows/ci.yml`): lint, format check, tests against a
   real SQL Server with a 70% coverage gate, image build, and end-to-end checks on the compose
   stack, including both partial-failure cases.
2. A teammate approves and the PR is merged to `main`.
3. **CD** (`.github/workflows/cd.yml`) runs CI again on `main`, then:
   - builds both images and pushes them to GHCR as
     `ghcr.io/bluesinkers/sdd-final-project-<service>:<commit sha>` (and `:latest`)
   - rolls each Container App to the new image; the service applies its migrations as it
     starts, and CD waits until `GET /health` returns 200 **and** reports that commit as
     `version`, failing the run if it does not in time
   - writes the two service URLs into `ui/config.js` and publishes `ui/` to the Static Web App
   - runs a read-only smoke test against the public URLs (`tests/e2e/flow.py deployed`)

Nobody deploys from a laptop. CI never touches Azure.

## What runs where

Everything is in our group's resource group `rg-sdd-<class>-g<N>` and every name starts with
our group prefix `sdd-<class>-g<N>` (shown as `<prefix>` below).

| Piece | Azure resource | Name | Notes |
|---|---|---|---|
| UI | Static Web App (Free) | `<prefix>-ui` | static files only |
| Listings service | Container App | `<prefix>-listings` | Consumption, scales 0 to 1 replica |
| Swaps service | Container App | `<prefix>-swaps` | Consumption, scales 0 to 1 replica |
| Listings data | Azure SQL database | `<prefix>-listings-db` | serverless, pauses after 60 idle minutes |
| Swaps data | Azure SQL database | `<prefix>-swaps-db` | serverless, pauses after 60 idle minutes |
| SQL server | Azure SQL server | `<prefix>-sql` | hosts the two databases |
| Environment | Container Apps environment | `<prefix>-env` | |
| Logs | Log Analytics workspace | `<prefix>-logs` | the environment's workspace |

That is 2 Container Apps, 2 serverless databases and 1 Static Web App, the limit per group.

Each service connects with its own database user, which exists only inside its own database.

## One-time setup

1. Merge to `main` once so CD pushes the two images to GHCR. The deploy jobs are skipped
   until step 4, so this run is green.
2. Make both packages public (GitHub > the organisation or user > Packages > the package >
   Package settings > Change visibility). The images contain no secrets, and the Container
   Apps pull them without credentials.
3. Create the Azure resources:

   ```bash
   az login                          # your IE account has Contributor on the group's resource group
   export PREFIX=sdd-<class>-g<N>    # our group prefix; the resource group is rg-<PREFIX>
   ./infra/setup.sh
   ```

   The script is safe to run again. It prints the URLs and the exact values for step 4.
4. In GitHub > Settings > Secrets and variables > Actions, add:

   | Kind | Name | Value |
   |---|---|---|
   | Variable | `AZURE_RESOURCE_GROUP` | `rg-<PREFIX>` |
   | Variable | `LISTINGS_APP` | `<PREFIX>-listings` |
   | Variable | `SWAPS_APP` | `<PREFIX>-swaps` |
   | Variable | `STATIC_APP` | `<PREFIX>-ui` |
   | Secret | `AZURE_CREDENTIALS` | the JSON of our group's own service principal, sent by the professor (not the class one from Assignment 2) |
   | Secret | `AZURE_STATIC_WEB_APPS_API_TOKEN` | printed by the command the script shows |

5. Run CD by hand once (Actions > CD > Run workflow) to publish the UI.

## Secrets

- No secret is in the repository or in an image. `.env` and `.env.azure` are git-ignored.
- The database URL of each service is a Container App **secret**, referenced by the
  `DATABASE_URL` environment variable.
- CI generates throwaway database passwords on every run and masks them in the log.

## Rolling back

Every merged commit keeps its images in GHCR. To go back:

1. Actions > CD > Run workflow.
2. Keep the branch on `main`, put the full 40-character commit SHA of the last good version
   in **image_tag** and run it.

CD skips the build, rolls both Container Apps to those images, waits for `/health` to
report that SHA, and publishes the UI from that same commit. Then revert the bad commit with a normal PR so `main` matches production.

Migrations only ever add (a new file per change), so an older image keeps working against a
newer schema as long as a migration did not remove something the old code reads. A migration
that drops or renames a column must ship one release after the code stops using it.

## If the first deploy fails

Neither `infra/setup.sh` nor the CD workflow had been run against Azure when they were
written, so check these first:

| Symptom | Likely cause and fix |
|---|---|
| `az ... create` says the provider is not registered | The subscription needs `Microsoft.App`, `Microsoft.OperationalInsights`, `Microsoft.Sql` and `Microsoft.Web` registered (`az provider register --namespace <name>`), or ask the instructor |
| Container App cannot pull the image | The two GHCR packages are still private (step 2) |
| Service log shows `Login failed for user` | Azure SQL can want the user as `user@server`. Set the secret to `mssql://listings_user%40<prefix>-sql:<password>@<host>:1433/<prefix>-listings-db` (`%40` is `@`) |
| Service restarts in a loop right after an idle period | The database was still resuming while the service waited to start. Open the app URL again after a minute, or set `--min-replicas 1` for the demo |
| CD health check times out | Run `infra/monitoring/startup_and_errors.kql` to see why the new revision did not start |

## Cold starts

Both Container Apps scale to zero and both databases pause when idle, to stay inside the
budget. The first request after a quiet period can take from a few seconds (container start)
up to about a minute (database resume). The UI handles this: each request times out after 8
seconds, the page says the service is unavailable, retries every 10 seconds and recovers on
its own. See ADR-6 in [`decisions.md`](decisions.md) for how this affects the SLO.
