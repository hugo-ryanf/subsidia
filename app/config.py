"""Configuração única do app, lida do .env (fonte única)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


@dataclass(frozen=True)
class Config:
    llm_base_url: str
    llm_api_key: str
    model_pesado: str
    model_leve: str
    embed_model: str
    embed_dim: int
    db_path: Path
    custo_hora_manual: float
    # Chunking (em caracteres): janela e overlap atravessando página.
    chunk_chars: int = 1800
    chunk_overlap: int = 300
    # Página com menos texto que isto não é descartada: vira requer_revisao (regra #4).
    min_chars_pagina: int = 40


def carregar() -> Config:
    db = Path(os.getenv("DB_PATH", "./data/subsidia.db"))
    if not db.is_absolute():
        db = RAIZ / db
    return Config(
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.featherless.ai/v1"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        model_pesado=os.getenv("MODEL_PESADO", "zai-org/GLM-5.2"),
        model_leve=os.getenv("MODEL_LEVE", "google/gemma-4-31B-it"),
        embed_model=os.getenv("EMBED_MODEL", "Qwen/Qwen3-Embedding-4B"),
        embed_dim=int(os.getenv("EMBED_DIM", "2560")),
        db_path=db,
        custo_hora_manual=float(os.getenv("CUSTO_HORA_MANUAL", "80")),
    )


cfg = carregar()
