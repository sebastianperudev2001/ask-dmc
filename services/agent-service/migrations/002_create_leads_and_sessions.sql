-- Incremento 2 — domain-entities.md: Lead reemplaza el diseño original de DynamoDB
-- (dmc-leads, dmc-conversations) — ver DIV-13. Mismo servidor Postgres que `courses`,
-- ninguna instancia nueva.

CREATE TABLE IF NOT EXISTS leads (
    id                      TEXT PRIMARY KEY,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    name                    TEXT,
    email                   TEXT,
    profile_summary         TEXT NOT NULL DEFAULT '',
    motivation              TEXT NOT NULL DEFAULT 'undefined'
                                CHECK (motivation IN ('growth', 'salary', 'company_requirement', 'academic', 'undefined')),
    motivation_detail       TEXT NOT NULL DEFAULT '',
    recommended_programs    TEXT[] NOT NULL DEFAULT '{}',
    payment_link_sent       BOOLEAN NOT NULL DEFAULT FALSE,
    payment_checkout_url    TEXT,
    payment_preference_id   TEXT,
    payment_confirmed       BOOLEAN NOT NULL DEFAULT FALSE,
    payment_confirmed_at    TIMESTAMPTZ,
    mercadopago_payment_id  TEXT,
    score                   TEXT NOT NULL DEFAULT 'cold'
                                CHECK (score IN ('hot', 'warm', 'cold')),
    score_justification     TEXT NOT NULL DEFAULT '',
    escalated_to_human      BOOLEAN NOT NULL DEFAULT FALSE,
    -- PATTERN-20: referencia al thread de Azure AI Foundry Agent Memory — la
    -- transcripción completa vive ahí, no se duplica aquí.
    service_session_id      TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS leads_service_session_id_idx ON leads (service_session_id);
CREATE INDEX IF NOT EXISTS leads_email_idx ON leads (email);

CREATE TABLE IF NOT EXISTS conversation_sessions (
    session_id          TEXT PRIMARY KEY,
    service_session_id  TEXT,
    lead_id             TEXT REFERENCES leads (id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
