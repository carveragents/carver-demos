# pipeline/config.py
import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Config:
    provider: str
    default_model: str
    stage_models: dict[str, str]
    api_key: str

    def model_for(self, stage: str) -> str:
        return self.stage_models.get(stage, self.default_model)


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(path.read_text())
    api_key_env = raw.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing API key — set ${api_key_env}")
    stage_models = {
        name: stage["model"]
        for name, stage in (raw.get("stages") or {}).items()
        if isinstance(stage, dict) and "model" in stage
    }
    return Config(
        provider=raw["provider"],
        default_model=raw["default_model"],
        stage_models=stage_models,
        api_key=api_key,
    )
