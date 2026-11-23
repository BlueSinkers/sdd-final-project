# Deploying

## How a change reaches production

1. A pull request runs **CI** (`.github/workflows/ci.yml`): lint, format check, tests against a
   real SQL Server with a 70% coverage gate, image build, and end-to-end checks on the compose
   stack, including both partial-failure cases.
2. A teammate approves and the PR is merged to `main`.
3. **CD** (`.github/workflows/cd.yml`) runs CI again on `main`, then:
   - builds both images and pushes them to GHCR as
     `ghcr.io/bluesinkers/sdd-final-project-<service>:<commit sha>` (and `:latest`)
   - rolls each Container App to the new image and waits until `GET /health` returns 200 **and**
     reports that commit as `version`
   - writes the two service URLs into `ui/config.js` and publishes `ui/` to the Static Web App

Nobody deploys from a laptop. CI never touches Azure.

## What runs where

| Piece | Azure resource | Notes |
|---|---|---|
| UI | Static Web App (Free) | static files only |
| Listings service | Container App | scales 0 to 1 replica, port 8000 |
| Swaps service | Container App | scales 0 to 1 replica, port 8000 |
| Listings data | Azure SQL database `listings` | serverless, pauses after 60 idle minutes |
| Swaps data | Azure SQL database `swaps` | serverless, pauses after 60 idle minutes |
| Logs | Log Analytics workspace | both Container Apps write their console logs here |

Each service connects with its own database user, which exists only inside its own database.

## One-time setup

1. Merge to `main` once so CD pushes the two images to GHCR. The deploy jobs are skipped
   until step 4, so this run is green.
2. Make both packages public (GitHub > the organisation or user > Packages > the package >
   Package settings > Change visibility). The images contain no secrets, and the Container
   Apps pull them without credentials.
3. Create the Azure resources:

   ```bash
   az login
   export RESOURCE_GROUP=<the resource group the class gave our group>
   export PREFIX=<short unique name, e.g. thriftswap3b2>
   ./infra/setup.sh
   ```

   The script is safe to run again. It prints the URLs and the exact values for step 4.
4. In GitHub > Settings > Secrets and variables > Actions, add:

   | Kind | Name | Value |
   |---|---|---|
   | Variable | `AZURE_RESOURCE_GROUP` | the resource group |
   | Variable | `LISTINGS_APP` | `<PREFIX>-listings` |
   | Variable | `SWAPS_APP` | `<PREFIX>-swaps` |
   | Secret | `AZURE_CREDENTIALS` | the JSON of the group's service principal |
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
2. Put the full commit SHA of the last good version in **image_tag** and run it.

CD skips the build, rolls both Container Apps to those images and waits for `/health` to
report that SHA. Then revert the bad commit with a normal PR so `main` matches production.

Migrations only ever add (a new file per change), so an older image keeps working against a
newer schema as long as a migration did not remove something the old code reads. A migration
that drops or renames a column must ship one release after the code stops using it.

## Cold starts

Both Container Apps scale to zero and both databases pause when idle, to stay inside the
budget. The first request after a quiet period can take from a few seconds (container start)
up to about a minute (database resume). The UI handles this: each request times out after 8
seconds, the page says the service is unavailable, retries every 10 seconds and recovers on
its own. See ADR-6 in [`decisions.md`](decisions.md) for how this affects the SLO.
