"""Rastro auditável: cada chamada de modelo, ferramenta, decisão e intervenção humana.

O processo/job corrente vive num ContextVar, então qualquer código chamado dentro de um
job (agente, ferramenta, llm) grava no lugar certo sem passar ids adiante.
"""
from __future__ import annotations

import contextvars
import json

from app import db, llm
from app.config import cfg

_ctx: contextvars.ContextVar[tuple[str | None, str | None]] = contextvars.ContextVar(
    "rastro_ctx", default=(None, None)
)


def entrar(processo_id: str | None, job_id: str | None = None):
    return _ctx.set((processo_id, job_id))


def sair(token) -> None:
    _ctx.reset(token)


def registrar(tipo: str, etiqueta: str, detalhe: dict | None = None, *, modelo: str | None = None,
              tokens_entrada: int = 0, tokens_saida: int = 0, custo_usd: float = 0.0,
              segundos: float = 0.0, processo_id: str | None = None) -> None:
    proc, job = _ctx.get()
    db.executar(
        "INSERT INTO eventos(processo_id,job_id,tipo,etiqueta,modelo,tokens_entrada,tokens_saida,"
        "custo_usd,segundos,detalhe,criado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (processo_id or proc, job, tipo, etiqueta, modelo, tokens_entrada, tokens_saida,
         custo_usd, segundos, json.dumps(detalhe or {}, ensure_ascii=False), db.agora()),
    )


def _de_llm(info: dict) -> None:
    registrar(info["tipo"], info["etiqueta"], modelo=info["modelo"],
              tokens_entrada=info["tokens_entrada"], tokens_saida=info["tokens_saida"],
              custo_usd=info["custo_usd"], segundos=info["segundos"])


llm.registrar_chamada = _de_llm


def resumo(processo_id: str) -> dict:
    eventos = db.todos("SELECT * FROM eventos WHERE processo_id=? ORDER BY id", (processo_id,))
    for e in eventos:
        e["detalhe"] = json.loads(e["detalhe"] or "{}")
    custo = sum(e["custo_usd"] or 0 for e in eventos)
    segundos_modelo = sum(e["segundos"] or 0 for e in eventos if e["tipo"] in ("chat", "embedding"))
    return {
        "eventos": eventos,
        "totais": {
            "chamadas_modelo": sum(1 for e in eventos if e["tipo"] in ("chat", "embedding")),
            "ferramentas": sum(1 for e in eventos if e["tipo"] == "ferramenta"),
            "tokens_entrada": sum(e["tokens_entrada"] or 0 for e in eventos),
            "tokens_saida": sum(e["tokens_saida"] or 0 for e in eventos),
            "custo_usd": round(custo, 4),
            "segundos_modelo": round(segundos_modelo, 1),
            "custo_hora_manual_brl": cfg.custo_hora_manual,
        },
    }
