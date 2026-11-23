-- Listings: what a student offers to swap. Applied once, never edited afterwards.
CREATE TABLE listings (
    id              INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_listings PRIMARY KEY,
    title           NVARCHAR(80)      NOT NULL,
    description     NVARCHAR(500)     NOT NULL CONSTRAINT df_listings_description DEFAULT '',
    category        NVARCHAR(20)      NOT NULL,
    condition       TINYINT           NOT NULL,
    estimated_value DECIMAL(10,2)     NOT NULL,
    owner_name      NVARCHAR(40)      NOT NULL,
    status          NVARCHAR(10)      NOT NULL CONSTRAINT df_listings_status DEFAULT 'open',
    created_at      DATETIME2(3)      NOT NULL CONSTRAINT df_listings_created_at DEFAULT SYSUTCDATETIME(),
    updated_at      DATETIME2(3)      NOT NULL CONSTRAINT df_listings_updated_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT ck_listings_category CHECK (category IN ('clothing', 'books', 'electronics', 'home', 'sports', 'other')),
    CONSTRAINT ck_listings_condition CHECK (condition BETWEEN 1 AND 5),
    CONSTRAINT ck_listings_value CHECK (estimated_value > 0),
    CONSTRAINT ck_listings_status CHECK (status IN ('open', 'swapped'))
);
GO

-- The board lists open listings, newest first.
CREATE INDEX ix_listings_status_created ON listings (status, created_at DESC);
