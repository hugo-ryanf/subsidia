"""SQLite: dados, índice full-text (FTS5) e vetores (BLOB float32).

Toda tabela de conteúdo carrega `processo_id`, e as buscas
filtram por ele DENTRO do SQL (regra #3).
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from app.config import cfg

_local = threading.local()

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS processos (
  id TEXT PRIMARY KEY, nome TEXT NOT NULL, criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documentos (
  id TEXT PRIMARY KEY, processo_id TEXT NOT NULL REFERENCES processos(id),
  nome TEXT NOT NULL,
  classe TEXT NOT NULL CHECK (classe IN ('autos','subsidio')),
  origem TEXT NOT NULL,            -- 'upload' ou 'sistema:<nome>'
  sha256 TEXT, paginas INTEGER DEFAULT 0, chunks INTEGER DEFAULT 0,
  paginas_revisao INTEGER DEFAULT 0,
  status TEXT NOT NULL,            -- queued | processando | concluido | erro
  erro TEXT, criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paginas (
  documento_id TEXT NOT NULL, numero INTEGER NOT NULL, chars INTEGER NOT NULL,
  confianca REAL NOT NULL, requer_revisao INTEGER NOT NULL, motivo TEXT,
  PRIMARY KEY (documento_id, numero)
);
CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY, processo_id TEXT NOT NULL, documento_id TEXT NOT NULL,
  ordem INTEGER NOT NULL, texto TEXT NOT NULL,
  pagina_inicio INTEGER NOT NULL, pagina_fim INTEGER NOT NULL,
  requer_revisao INTEGER NOT NULL DEFAULT 0, motivo TEXT,
  embedding BLOB
);
CREATE INDEX IF NOT EXISTS ix_chunks_proc ON chunks(processo_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  texto, chunk_id UNINDEXED, processo_id UNINDEXED, tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, processo_id TEXT NOT NULL, tipo TEXT NOT NULL,
  status TEXT NOT NULL,            -- queued | processando | concluido | erro
  etapa TEXT, erro TEXT, resultado TEXT,
  criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS eventos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, processo_id TEXT, job_id TEXT,
  tipo TEXT NOT NULL,              -- chat | embedding | ferramenta | decisao | erro | humano
  etiqueta TEXT, modelo TEXT,
  tokens_entrada INTEGER DEFAULT 0, tokens_saida INTEGER DEFAULT 0,
  custo_usd REAL DEFAULT 0, segundos REAL DEFAULT 0,
  detalhe TEXT, criado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_eventos_proc ON eventos(processo_id);
CREATE TABLE IF NOT EXISTS artefatos (
  processo_id TEXT NOT NULL, tipo TEXT NOT NULL,   -- triagem | subsidios | estrategia
  conteudo TEXT NOT NULL, aprovado INTEGER NOT NULL DEFAULT 0,
  atualizado_em TEXT NOT NULL, PRIMARY KEY (processo_id, tipo)
);
CREATE TABLE IF NOT EXISTS pendencias (
  id TEXT PRIMARY KEY, processo_id TEXT NOT NULL, pedido_id TEXT,
  titulo TEXT NOT NULL, contexto TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'aberta',            -- aberta | resolvida | descartada
  resolucao TEXT, criado_em TEXT NOT NULL, resolvido_em TEXT
);
"""


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def novo_id(prefixo: str = "") -> str:
    return f"{prefixo}{uuid.uuid4().hex[:12]}"


def conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(cfg.db_path, timeout=60, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        _local.conn = c
    return c


def iniciar() -> None:
    conn().executescript(SCHEMA)
    conn().commit()


def um(sql: str, args: tuple = ()) -> dict | None:
    r = conn().execute(sql, args).fetchone()
    return dict(r) if r else None


def todos(sql: str, args: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn().execute(sql, args).fetchall()]


def executar(sql: str, args: tuple = ()) -> None:
    conn().execute(sql, args)
    conn().commit()


# --- artefatos (saída aprovável de cada etapa) -----------------------------------------

def salvar_artefato(processo_id: str, tipo: str, conteudo: dict, aprovado: bool = False) -> None:
    executar(
        "INSERT INTO artefatos(processo_id,tipo,conteudo,aprovado,atualizado_em) VALUES(?,?,?,?,?) "
        "ON CONFLICT(processo_id,tipo) DO UPDATE SET conteudo=excluded.conteudo, "
        "aprovado=excluded.aprovado, atualizado_em=excluded.atualizado_em",
        (processo_id, tipo, json.dumps(conteudo, ensure_ascii=False), int(aprovado), agora()),
    )


def artefato(processo_id: str, tipo: str) -> dict | None:
    r = um("SELECT * FROM artefatos WHERE processo_id=? AND tipo=?", (processo_id, tipo))
    if not r:
        return None
    return {"conteudo": json.loads(r["conteudo"]), "aprovado": bool(r["aprovado"]),
            "atualizado_em": r["atualizado_em"]}
