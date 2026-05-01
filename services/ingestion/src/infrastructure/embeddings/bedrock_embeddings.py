import json

import boto3


class BedrockEmbeddingsProvider:
    def __init__(self, model_id: str) -> None:
        self._model_id = model_id
        self._client = boto3.client("bedrock-runtime")

    def embed(self, text: str) -> list[float]:
        body = json.dumps({"inputText": text})
        response = self._client.invoke_model(
            modelId=self._model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["embedding"]
