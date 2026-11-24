-- Accounts. A listing belongs to the account whose username equals its owner_name, so
-- the listings table needs no change. Passwords are stored only as salted scrypt hashes.
CREATE TABLE users (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_users PRIMARY KEY,
    username      NVARCHAR(40)      NOT NULL,
    password_hash NVARCHAR(200)     NOT NULL,
    created_at    DATETIME2(3)      NOT NULL CONSTRAINT df_users_created_at DEFAULT SYSUTCDATETIME(),
    -- The default collation ignores case, so "Lucia" and "lucia" are the same account.
    CONSTRAINT uq_users_username UNIQUE (username)
);
