"""Fila de jobs em processo (contrato assíncrono: 202 + status).

POST devolve 202 + job_id; o trabalho roda numa thread; GET /jobs/{id} mostra status.
Regra #1: TODO job termina em `concluido` ou `erro` com mensagem — nunca fica pendurado
por exceção engolida.
"""
from __future__ import annotations

import json
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from app import db, rastro

logger = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="job")


def criar(processo_id: str, tipo: str) -> str:
    jid = db.novo_id("job_")
    db.executar(
        "INSERT INTO jobs(id,processo_id,tipo,status,criado_em,atualizado_em) VALUES(?,?,?,?,?,?)",
        (jid, processo_id, tipo, "queued", db.agora(), db.agora()),
    )
    return jid


def etapa(job_id: str, texto: str) -> None:
    db.executar("UPDATE jobs SET etapa=?, atualizado_em=? WHERE id=?", (texto, db.agora(), job_id))


def _rodar(job_id: str, processo_id: str, fn: Callable[[str], dict | None]) -> None:
    token = rastro.entrar(processo_id, job_id)
    try:
        db.executar("UPDATE jobs SET status='processando', atualizado_em=? WHERE id=?", (db.agora(), job_id))
        resultado = fn(job_id) or {}
        db.executar(
            "UPDATE jobs SET status='concluido', etapa=NULL, resultado=?, atualizado_em=? WHERE id=?",
            (json.dumps(resultado, ensure_ascii=False), db.agora(), job_id),
        )
    except Exception as e:  # regra #1: falha vira status explícito
        logger.exception("job %s falhou", job_id)
        msg = f"{type(e).__name__}: {e}"
        db.executar("UPDATE jobs SET status='erro', erro=?, atualizado_em=? WHERE id=?",
                    (msg, db.agora(), job_id))
        rastro.registrar("erro", "job", {"erro": msg, "trace": traceback.format_exc()[-1500:]})
    finally:
        rastro.sair(token)


def disparar(processo_id: str, tipo: str, fn: Callable[[str], dict | None]) -> str:
    jid = criar(processo_id, tipo)
    _pool.submit(_rodar, jid, processo_id, fn)
    return jid


def obter(job_id: str) -> dict | None:
    j = db.um("SELECT * FROM jobs WHERE id=?", (job_id,))
    if j and j.get("resultado"):
        j["resultado"] = json.loads(j["resultado"])
    return j


def reconciliar_orfaos() -> None:
    """Na subida, job que ficou 'processando' (app caiu) vira erro explícito, não fantasma."""
    db.executar(
        "UPDATE jobs SET status='erro', erro='interrompido: o servidor reiniciou durante o job', "
        "atualizado_em=? WHERE status IN ('queued','processando')", (db.agora(),),
    )
