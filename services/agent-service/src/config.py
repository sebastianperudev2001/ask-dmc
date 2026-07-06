from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv

# Loads services/agent-service/.env into os.environ if present — local dev convenience
# only. In PRODUCTION (Container Apps), env vars come from Container Apps secrets/env,
# not a .env file, and load_dotenv() is a no-op if no file is found.
load_dotenv()


class ENV(str, Enum):
    LOCAL = "local"
    PRODUCTION = "production"


@dataclass(frozen=True)
class AgentServiceConfig:
    env: ENV
    database_url: str
    azure_openai_endpoint: str
    azure_openai_embedding_deployment: str
    foundry_project_endpoint: str
    foundry_agent_model_deployment: str
    relax_confirmation_timeout_seconds: float
    retry_max_attempts: int
    retry_base_delay_seconds: float
    mercadopago_access_token: str
    mercadopago_webhook_secret: str
    mercadopago_base_url: str
    profile_data_timeout_seconds: float


def load_config() -> AgentServiceConfig:
    raw_env = os.environ.get("AGENT_SERVICE_ENV", "local").strip().lower()
    try:
        env = ENV(raw_env)
    except ValueError:
        raise ValueError(f"AGENT_SERVICE_ENV must be 'local' or 'production', got: {raw_env!r}")

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")

    return AgentServiceConfig(
        env=env,
        database_url=database_url,
        azure_openai_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        azure_openai_embedding_deployment=os.environ.get(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
        ),
        foundry_project_endpoint=os.environ.get("FOUNDRY_PROJECT_ENDPOINT", ""),
        foundry_agent_model_deployment=os.environ.get(
            "FOUNDRY_AGENT_MODEL_DEPLOYMENT", "gpt-5.4-nano"
        ),
        relax_confirmation_timeout_seconds=float(
            os.environ.get("RELAX_CONFIRMATION_TIMEOUT_SECONDS", "300")
        ),
        retry_max_attempts=int(os.environ.get("RETRY_MAX_ATTEMPTS", "3")),
        retry_base_delay_seconds=float(os.environ.get("RETRY_BASE_DELAY_SECONDS", "0.5")),
        mercadopago_access_token=os.environ.get("MERCADOPAGO_ACCESS_TOKEN", ""),
        mercadopago_webhook_secret=os.environ.get("MERCADOPAGO_WEBHOOK_SECRET", ""),
        mercadopago_base_url=os.environ.get("MERCADOPAGO_BASE_URL", "https://api.mercadopago.com"),
        # Found via real Build and Test verification: NFR Requirements originally decided
        # "no timeout — the WS disconnect is the natural limit" (Clarification Q1 = C).
        # That assumption was wrong in practice — a user who leaves the widget open
        # without disconnecting (e.g. clicking "Nueva conversación" instead of
        # submitting it) permanently deadlocks the whole connection, since the main
        # loop is blocked awaiting this exact future and never reaches the point where
        # a disconnect would be noticed. A bounded timeout is required after all.
        profile_data_timeout_seconds=float(
            os.environ.get("PROFILE_DATA_TIMEOUT_SECONDS", "300")
        ),
    )
