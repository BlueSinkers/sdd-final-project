-- Local only: creates one database and one login per service, idempotently, so it
-- is safe on every `docker compose up`. Run by the db-init service with sqlcmd,
-- which fills in $(LISTINGS_DB_PASSWORD) and $(SWAPS_DB_PASSWORD).
-- On Azure each service has its own Azure SQL database instead (see infra/).

IF DB_ID('listings') IS NULL CREATE DATABASE listings;
IF DB_ID('swaps') IS NULL CREATE DATABASE swaps;
GO

IF SUSER_ID('listings_user') IS NULL
    CREATE LOGIN listings_user WITH PASSWORD = '$(LISTINGS_DB_PASSWORD)', CHECK_POLICY = OFF;
IF SUSER_ID('swaps_user') IS NULL
    CREATE LOGIN swaps_user WITH PASSWORD = '$(SWAPS_DB_PASSWORD)', CHECK_POLICY = OFF;
GO

-- Each login is a user in its own database only, so the Listings service cannot
-- read the Swaps tables and the other way round. db_ddladmin lets a service run
-- its own migrations.
USE listings;
GO
IF USER_ID('listings_user') IS NULL CREATE USER listings_user FOR LOGIN listings_user;
ALTER ROLE db_ddladmin ADD MEMBER listings_user;
ALTER ROLE db_datareader ADD MEMBER listings_user;
ALTER ROLE db_datawriter ADD MEMBER listings_user;
GO

USE swaps;
GO
IF USER_ID('swaps_user') IS NULL CREATE USER swaps_user FOR LOGIN swaps_user;
ALTER ROLE db_ddladmin ADD MEMBER swaps_user;
ALTER ROLE db_datareader ADD MEMBER swaps_user;
ALTER ROLE db_datawriter ADD MEMBER swaps_user;
GO
