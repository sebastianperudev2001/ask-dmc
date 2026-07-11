-- Incremento 3 — BackOffice: OutreachDraft (domain-entities.md). Ciclo de vida
-- independiente de `leads` (BR-22). Mismo servidor Postgres, ninguna instancia nueva.

CREATE TABLE IF NOT EXISTS outreach_drafts (
    draft_id    TEXT PRIMARY KEY,
    lead_id     TEXT NOT NULL REFERENCES leads (id),
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'sent', 'discarded')),
    trigger     TEXT NOT NULL
                    CHECK (trigger IN ('auto', 'on_demand')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS outreach_drafts_lead_id_idx ON outreach_drafts (lead_id);

-- BR-22: "activo" = a lo sumo un draft `pending` por lead. Enforced aquí como
-- defensa-en-profundidad (belt-and-suspenders) además del dedupe a nivel de aplicación
-- en OutreachAgentService.generate_draft — un índice único parcial es la forma idiomática
-- de Postgres de expresar esta restricción sin bloquear filas `sent`/`discarded`.
CREATE UNIQUE INDEX IF NOT EXISTS outreach_drafts_one_pending_per_lead_idx
    ON outreach_drafts (lead_id)
    WHERE status = 'pending';
