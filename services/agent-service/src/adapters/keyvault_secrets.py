"""SecretsProvider — resolves secrets from Azure Key Vault (PATTERN-11). Never reads
credentials from plain environment variables in production; local dev may fall back to
.env (python-dotenv) for developer convenience only."""
from __future__ import annotations

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


class KeyVaultSecretsProvider:
    def __init__(self, vault_url: str, credential: DefaultAzureCredential) -> None:
        self._client = SecretClient(vault_url=vault_url, credential=credential)

    def get_secret(self, name: str) -> str:
        return self._client.get_secret(name).value
