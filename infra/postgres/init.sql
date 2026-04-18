-- Postgres bootstrap script for the AI Fraud Intelligence Console.
--
-- PURPOSE
--   This script is a safety net for fresh environments (Docker first-start,
--   CI pipelines, local resets). It is mounted into the Postgres container at:
--     /docker-entrypoint-initdb.d/01_init.sql
--   Postgres only executes files in that directory when the data volume is empty.
--
-- RELATIONSHIP TO ALEMBIC
--   Alembic is the authoritative migration path. This script stamps the
--   alembic_version table (see bottom) so that if `alembic upgrade head` is run
--   after a fresh init, Alembic recognises the schema is already at revision 0001
--   and skips re-creating the table.
--
-- SCHEMA SOURCE
--   Mirrors src/db/postgres_logger.py and alembic/versions/0001_initial_predictions_table.py
--   exactly. Any future schema change must go through a new Alembic revision first,
--   then be reflected here.

-- ---------------------------------------------------------------------------
-- predictions table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS predictions (

    -- Primary key
    id               SERIAL          PRIMARY KEY,

    -- Transaction identity
    transaction_id   VARCHAR(64),

    -- NUMERIC(12, 4): exact decimal precision for financial amounts.
    -- Avoids floating-point rounding errors present in FLOAT / REAL.
    amount           NUMERIC(12, 4),

    -- Stored as ISO-8601 string (e.g. "2024-03-15T14:32:07Z")
    -- to match the existing application behaviour.
    timestamp        VARCHAR(32),

    -- Deterministic scoring outputs
    rule_flag        SMALLINT,           -- 0 or 1
    model_prediction SMALLINT,           -- 0 or 1
    risk_score       NUMERIC(6, 4),      -- 0.0000 – 1.0000
    decision         VARCHAR(10),        -- APPROVE | REVIEW | BLOCK

    -- Pipe-delimited reason strings written by /predict
    -- e.g. "High transaction amount|Unusual transaction time"
    reasons          TEXT,

    -- Analyst review fields — populated after human review, always nullable
    analyst_status   VARCHAR(20),        -- CONFIRMED_FRAUD | FALSE_POSITIVE | APPROVED
    analyst_notes    TEXT,
    reviewed_at      VARCHAR(32)         -- ISO-8601 string

);

-- ---------------------------------------------------------------------------
-- Indexes
-- Matches the indexes created in the Alembic migration.
-- ---------------------------------------------------------------------------

-- Used by GET /review-queue (WHERE decision IN ('REVIEW','BLOCK'))
-- and GET /stats (COUNT WHERE decision = ...)
CREATE INDEX IF NOT EXISTS ix_predictions_decision
    ON predictions (decision);

-- Used by future lookups by external transaction identifier
CREATE INDEX IF NOT EXISTS ix_predictions_transaction_id
    ON predictions (transaction_id);

-- ---------------------------------------------------------------------------
-- Alembic version stamp
--
-- Inserting revision 0001 prevents `alembic upgrade head` from trying to
-- re-create a table that this script already built.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

INSERT INTO alembic_version (version_num)
VALUES ('0001')
ON CONFLICT DO NOTHING;
