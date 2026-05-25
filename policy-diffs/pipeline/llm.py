# pipeline/llm.py
import json
from typing import Any

from openai import OpenAI

from pipeline.config import Config


class LLMClient:
    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._client = OpenAI(api_key=cfg.api_key)

    def complete_json(
        self,
        *,
        stage: str,
        system: str,
        user: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        model = self._cfg.model_for(stage)
        resp = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": stage, "schema": json_schema, "strict": True},
            },
        )
        return json.loads(resp.choices[0].message.content)
