-- Swap proposals. Each row keeps a snapshot of both listings as they were when
-- the swap was proposed, so this service never has to ask the Listings service.
-- Applied once, never edited afterwards.
CREATE TABLE swaps (
    id                   INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_swaps PRIMARY KEY,
    proposer_name        NVARCHAR(40)      NOT NULL,
    message              NVARCHAR(300)     NOT NULL CONSTRAINT df_swaps_message DEFAULT '',

    offered_listing_id   INT               NOT NULL,
    offered_title        NVARCHAR(80)      NOT NULL,
    offered_owner_name   NVARCHAR(40)      NOT NULL,
    offered_condition    TINYINT           NOT NULL,
    offered_value        DECIMAL(10,2)     NOT NULL,
    offered_adjusted     DECIMAL(10,2)     NOT NULL,

    requested_listing_id INT               NOT NULL,
    requested_title      NVARCHAR(80)      NOT NULL,
    requested_owner_name NVARCHAR(40)      NOT NULL,
    requested_condition  TINYINT           NOT NULL,
    requested_value      DECIMAL(10,2)     NOT NULL,
    requested_adjusted   DECIMAL(10,2)     NOT NULL,

    fairness_score       DECIMAL(5,4)      NOT NULL,
    verdict              NVARCHAR(20)      NOT NULL,
    status               NVARCHAR(10)      NOT NULL CONSTRAINT df_swaps_status DEFAULT 'proposed',
    created_at           DATETIME2(3)      NOT NULL CONSTRAINT df_swaps_created_at DEFAULT SYSUTCDATETIME(),
    updated_at           DATETIME2(3)      NOT NULL CONSTRAINT df_swaps_updated_at DEFAULT SYSUTCDATETIME(),

    CONSTRAINT ck_swaps_different_listings CHECK (offered_listing_id <> requested_listing_id),
    CONSTRAINT ck_swaps_conditions CHECK (offered_condition BETWEEN 1 AND 5 AND requested_condition BETWEEN 1 AND 5),
    CONSTRAINT ck_swaps_values CHECK (offered_value > 0 AND requested_value > 0),
    CONSTRAINT ck_swaps_score CHECK (fairness_score BETWEEN 0 AND 1),
    CONSTRAINT ck_swaps_verdict CHECK (verdict IN ('Fair trade', 'Lopsided', 'Very uneven')),
    CONSTRAINT ck_swaps_status CHECK (status IN ('proposed', 'accepted', 'declined'))
);
GO

-- The UI shows the most recent proposals first.
CREATE INDEX ix_swaps_created ON swaps (created_at DESC);
