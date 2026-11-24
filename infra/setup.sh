#!/usr/bin/env bash
# Creates everything the app needs on Azure, once. Safe to run again: every step
# either creates the resource or leaves the existing one alone.
#
#   az login                       # your IE account has Contributor on the group's resource group
#   export PREFIX=sdd-<class>-g<N> # our group prefix, e.g. sdd-3a-g3
#   ./infra/setup.sh
#
# Every resource name starts with the group prefix, and everything goes into the
# group's existing resource group rg-<PREFIX> (override with RESOURCE_GROUP). The
# script never creates a resource group.
#
# Needs: az CLI, docker (to run sqlcmd), openssl. The images must already be in
# GHCR and public (see docs/deploy.md), because the Container Apps pull them.
#
# What it creates in the resource group:
#   - <PREFIX>-logs  Log Analytics workspace
#   - <PREFIX>-env   Container Apps environment (Consumption) that logs to it
#   - <PREFIX>-sql   Azure SQL server with two serverless, auto-pausing databases,
#                    <PREFIX>-listings-db and <PREFIX>-swaps-db, each with its own
#                    database user that cannot see the other database
#   - <PREFIX>-listings and <PREFIX>-swaps  Container Apps (scale to zero, at most 1 replica)
#   - <PREFIX>-ui    Static Web App for the UI
#
# Passwords are generated here, stored only as Container App secrets and in
# .env.azure (git-ignored, readable only by you). Nothing secret is printed.
set -euo pipefail

: "${PREFIX:?set PREFIX to the group prefix sdd-<class>-g<N>, e.g. sdd-3a-g3}"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-${PREFIX}}"
LOCATION="${LOCATION:-westeurope}"
# Static Web Apps exist in only a few regions, so this is separate from LOCATION.
STATIC_LOCATION="${STATIC_LOCATION:-westeurope}"
GHCR_REPO="${GHCR_REPO:-ghcr.io/bluesinkers/sdd-final-project}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

if ! [[ "$PREFIX" =~ ^sdd-[a-z0-9]+-g[0-9]+$ ]]; then
  echo "PREFIX must be the group prefix sdd-<class>-g<N>, e.g. sdd-3a-g3" >&2
  exit 1
fi

WORKSPACE="${PREFIX}-logs"
ENVIRONMENT="${PREFIX}-env"
SQL_SERVER="${PREFIX}-sql"
SQL_HOST="${SQL_SERVER}.database.windows.net"
SQL_ADMIN="thriftadmin"
LISTINGS_APP="${PREFIX}-listings"
SWAPS_APP="${PREFIX}-swaps"
LISTINGS_DB="${PREFIX}-listings-db"
SWAPS_DB="${PREFIX}-swaps-db"
STATIC_APP="${PREFIX}-ui"
SECRETS_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env.azure"

say() { printf '\n==> %s\n' "$*"; }

# Letters and digits only (the value also goes inside a URL), and always with an
# upper case letter, a lower case letter and a digit, as Azure SQL requires.
new_password() { echo "Tw9$(openssl rand -hex 16)"; }

# Reuse the passwords from an earlier run so a re-run does not lock the apps out.
if [[ -f "$SECRETS_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
fi
SQL_ADMIN_PASSWORD="${SQL_ADMIN_PASSWORD:-$(new_password)}"
LISTINGS_DB_PASSWORD="${LISTINGS_DB_PASSWORD:-$(new_password)}"
SWAPS_DB_PASSWORD="${SWAPS_DB_PASSWORD:-$(new_password)}"
# Signs the sign-in tokens. Both apps get the same value, so Swaps can check a token
# that Listings issued without calling it.
AUTH_SECRET="${AUTH_SECRET:-$(openssl rand -hex 32)}"
# One-click demo accounts with no password. Run with DEMO_LOGIN=false to turn them off.
DEMO_LOGIN="${DEMO_LOGIN:-true}"
umask 077
cat > "$SECRETS_FILE" <<SECRETS
# Written by infra/setup.sh. Git-ignored. Do not commit or share.
SQL_ADMIN_PASSWORD=$SQL_ADMIN_PASSWORD
LISTINGS_DB_PASSWORD=$LISTINGS_DB_PASSWORD
SWAPS_DB_PASSWORD=$SWAPS_DB_PASSWORD
AUTH_SECRET=$AUTH_SECRET
SECRETS

say "Checking the resource group"
az group show --name "$RESOURCE_GROUP" --output none

say "Log Analytics workspace: $WORKSPACE"
az monitor log-analytics workspace create --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE" --location "$LOCATION" --retention-time 30 --output none
WORKSPACE_ID=$(az monitor log-analytics workspace show --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE" --query customerId --output tsv)
WORKSPACE_KEY=$(az monitor log-analytics workspace get-shared-keys --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE" --query primarySharedKey --output tsv)

say "Container Apps environment: $ENVIRONMENT"
if ! az containerapp env show --resource-group "$RESOURCE_GROUP" --name "$ENVIRONMENT" --output none 2>/dev/null; then
  az containerapp env create --resource-group "$RESOURCE_GROUP" --name "$ENVIRONMENT" --location "$LOCATION" \
    --logs-workspace-id "$WORKSPACE_ID" --logs-workspace-key "$WORKSPACE_KEY" --output none
fi

say "Azure SQL server: $SQL_SERVER"
if ! az sql server show --resource-group "$RESOURCE_GROUP" --name "$SQL_SERVER" --output none 2>/dev/null; then
  az sql server create --resource-group "$RESOURCE_GROUP" --name "$SQL_SERVER" --location "$LOCATION" \
    --admin-user "$SQL_ADMIN" --admin-password "$SQL_ADMIN_PASSWORD" --output none
else
  # The server exists already. If .env.azure was lost or this is another machine,
  # the admin password generated above is new, so make the server match it.
  az sql server update --resource-group "$RESOURCE_GROUP" --name "$SQL_SERVER" \
    --admin-password "$SQL_ADMIN_PASSWORD" --output none
fi
# 0.0.0.0 is Azure's way of saying "other Azure services", which is how the Container Apps reach it.
az sql server firewall-rule create --resource-group "$RESOURCE_GROUP" --server "$SQL_SERVER" \
  --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 --output none

for DATABASE in "$LISTINGS_DB" "$SWAPS_DB"; do
  say "Serverless database: $DATABASE"
  if ! az sql db show --resource-group "$RESOURCE_GROUP" --server "$SQL_SERVER" --name "$DATABASE" --output none 2>/dev/null; then
    # Serverless with auto-pause after 60 idle minutes: it costs nothing while paused.
    az sql db create --resource-group "$RESOURCE_GROUP" --server "$SQL_SERVER" --name "$DATABASE" \
      --edition GeneralPurpose --family Gen5 --capacity 1 --compute-model Serverless \
      --min-capacity 0.5 --auto-pause-delay 60 --backup-storage-redundancy Local --output none
  fi
done

say "One database user per service"
MY_IP=$(curl -fsS https://api.ipify.org)
az sql server firewall-rule create --resource-group "$RESOURCE_GROUP" --server "$SQL_SERVER" \
  --name setup-script --start-ip-address "$MY_IP" --end-ip-address "$MY_IP" --output none
remove_my_ip() {
  az sql server firewall-rule delete --resource-group "$RESOURCE_GROUP" --server "$SQL_SERVER" \
    --name setup-script --output none || true
}
trap remove_my_ip EXIT

create_user() { # database, user, password
  # A contained user exists only inside its own database, so the Listings user
  # cannot even connect to the Swaps database. db_ddladmin lets the service run
  # its own migrations.
  docker run --rm --platform linux/amd64 -e SQLCMDPASSWORD="$SQL_ADMIN_PASSWORD" \
    mcr.microsoft.com/mssql/server:2022-latest \
    /opt/mssql-tools18/bin/sqlcmd -b -l 120 -S "$SQL_HOST" -d "$1" -U "$SQL_ADMIN" -Q "
      IF USER_ID('$2') IS NULL CREATE USER [$2] WITH PASSWORD = '$3';
      ELSE ALTER USER [$2] WITH PASSWORD = '$3';
      ALTER ROLE db_ddladmin ADD MEMBER [$2];
      ALTER ROLE db_datareader ADD MEMBER [$2];
      ALTER ROLE db_datawriter ADD MEMBER [$2];"
}
# A new firewall rule or admin password takes a moment to apply, and a paused
# database needs up to a minute to resume, so try a few times before giving up.
create_user_with_retry() {
  local attempt
  for attempt in 1 2 3 4 5 6; do
    if create_user "$@"; then return 0; fi
    echo "    database $1 not reachable yet (attempt $attempt of 6), waiting 20 s"
    sleep 20
  done
  echo "could not create the database user in $1" >&2
  return 1
}
create_user_with_retry "$LISTINGS_DB" listings_user "$LISTINGS_DB_PASSWORD"
create_user_with_retry "$SWAPS_DB" swaps_user "$SWAPS_DB_PASSWORD"
remove_my_ip
trap - EXIT

say "Static Web App: $STATIC_APP"
if ! az staticwebapp show --resource-group "$RESOURCE_GROUP" --name "$STATIC_APP" --output none 2>/dev/null; then
  az staticwebapp create --resource-group "$RESOURCE_GROUP" --name "$STATIC_APP" --location "$STATIC_LOCATION" \
    --sku Free --output none
fi
UI_HOST=$(az staticwebapp show --resource-group "$RESOURCE_GROUP" --name "$STATIC_APP" \
  --query defaultHostname --output tsv)

create_app() { # app name, service, database, user, password
  say "Container App: $1"
  local database_url="mssql://$4:$5@${SQL_HOST}:1433/$3"
  if az containerapp show --resource-group "$RESOURCE_GROUP" --name "$1" --output none 2>/dev/null; then
    az containerapp secret set --resource-group "$RESOURCE_GROUP" --name "$1" \
      --secrets "database-url=$database_url" "auth-secret=$AUTH_SECRET" --output none
    az containerapp update --resource-group "$RESOURCE_GROUP" --name "$1" \
      --set-env-vars "DATABASE_URL=secretref:database-url" "AUTH_SECRET=secretref:auth-secret" \
      "DEMO_LOGIN=$DEMO_LOGIN" "CORS_ORIGINS=https://${UI_HOST}" --output none
  else
    # Only the browser origin of our own UI may call the API. The database URL
    # is a Container App secret, never a plain environment variable.
    az containerapp create --resource-group "$RESOURCE_GROUP" --name "$1" --environment "$ENVIRONMENT" \
      --image "${GHCR_REPO}-$2:${IMAGE_TAG}" --ingress external --target-port 8000 \
      --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
      --secrets "database-url=$database_url" "auth-secret=$AUTH_SECRET" \
      --env-vars "DATABASE_URL=secretref:database-url" "AUTH_SECRET=secretref:auth-secret" \
      "DEMO_LOGIN=$DEMO_LOGIN" "CORS_ORIGINS=https://${UI_HOST}" --output none
  fi
}
create_app "$LISTINGS_APP" listings "$LISTINGS_DB" listings_user "$LISTINGS_DB_PASSWORD"
create_app "$SWAPS_APP" swaps "$SWAPS_DB" swaps_user "$SWAPS_DB_PASSWORD"

fqdn() {
  az containerapp show --resource-group "$RESOURCE_GROUP" --name "$1" \
    --query properties.configuration.ingress.fqdn --output tsv
}

cat <<DONE

Done.

  UI:        https://${UI_HOST}
  Listings:  https://$(fqdn "$LISTINGS_APP")/health
  Swaps:     https://$(fqdn "$SWAPS_APP")/health

Now set these in GitHub (Settings > Secrets and variables > Actions), then run
the CD workflow once so it publishes the UI:

  Variables
    AZURE_RESOURCE_GROUP = $RESOURCE_GROUP
    LISTINGS_APP         = $LISTINGS_APP
    SWAPS_APP            = $SWAPS_APP
    STATIC_APP           = $STATIC_APP

  Secrets
    AZURE_CLIENT_ID                 = the output of:
      az identity show -g $RESOURCE_GROUP -n ${PREFIX}-github --query clientId -o tsv
    AZURE_TENANT_ID                 = 5ca2bc70-353c-4d1f-b7d7-7f2b2259df68
    AZURE_SUBSCRIPTION_ID           = e0b9cada-61bc-4b5a-bd7a-52c606726b3b
    AZURE_STATIC_WEB_APPS_API_TOKEN = the output of:
      az staticwebapp secrets list --resource-group $RESOURCE_GROUP --name $STATIC_APP --query properties.apiKey --output tsv

The database passwords and the sign-in secret are in .env.azure (git-ignored). Keep that file private.
DONE
