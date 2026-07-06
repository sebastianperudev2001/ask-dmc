-- Persists the chat transcript so the frontend can rehydrate visible messages after a
-- page reload. Foundry Agent Memory remains the source of truth for the AGENT's actual
-- reasoning/context (PATTERN-20) — this table exists only because the installed SDK
-- (agent-framework-foundry) has no history-retrieval API, only create_session/get_session
-- for resuming a live agent.run() call. Keyed by `conversation_id` (stable per WS
-- connection, see chat_agent_client.py), not by Foundry's rotating service_session_id.

CREATE TABLE IF NOT EXISTS conversation_messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user', 'bot')),
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversation_messages_conversation_id_idx
    ON conversation_messages (conversation_id, created_at);
