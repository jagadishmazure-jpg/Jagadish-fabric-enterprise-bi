-- Logical PostgreSQL schema for the Fabric HorizonDB source.
-- The offline mock stores this table in SQLite. Fabric mirroring would land the
-- same columns in OneLake as Delta. This file is not executed against PostgreSQL.

CREATE TABLE loyalty_redemptions (
    redemption_id text PRIMARY KEY,
    store_id text NOT NULL,
    region text NOT NULL,
    member_id text NOT NULL,
    points integer NOT NULL,
    redeemed_on text NOT NULL
);
