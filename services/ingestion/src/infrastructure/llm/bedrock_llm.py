from __future__ import annotations

import json

import boto3


class BedrockLLMProvider:
    def __init__(self, model_id: str) -> None:
        self._model_id = model_id
        self._client = boto3.client("bedrock-runtime")

    def complete(self, prompt: str, format: dict | None = None) -> str:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 256,
            "messages": [{"role": "user", "content": prompt}],
        })
        response = self._client.invoke_model(
            modelId=self._model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
