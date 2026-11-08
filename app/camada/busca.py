"""Busca híbrida (vetorial + full-text) fundida por RRF.

Regra #3: `processo_id` vai DENTRO das duas queries. Regra #1: sem resultado devolve
`status='no_results'` explícito, não lista vazia muda.
"""
from __future__ import annotations

import re

import numpy as np

from app import db, llm

_RRF_K = 60


def _fts_query(pergunta: str) -> str:
    termos = [t for t in re.findall(r"\w+", pergunta.lower()) if len(t) > 2]
    return " OR ".join(f'"{t}"' for t in termos[:24])


def _textual(processo_id: str, pergunta: str, limite: int, classe: str | None) -> list[str]:
    q = _fts_query(pergunta)
    if not q:
        return []
    sql = ("SELECT f.chunk_id FROM chunks_fts f JOIN chunks c ON c.id=f.chunk_id "
           "JOIN documentos d ON d.id=c.documento_id "
           "WHERE chunks_fts MATCH ? AND f.processo_id=? ")
    args: list = [q, processo_id]
    if classe:
        sql += "AND d.classe=? "
        args.append(classe)
    sql += "ORDER BY bm25(chunks_fts) LIMIT ?"
    args.append(limite)
    return [r["chunk_id"] for r in db.todos(sql, tuple(args))]


def _vetorial(processo_id: str, pergunta: str, limite: int, classe: str | None) -> list[str]:
    sql = ("SELECT c.id, c.embedding FROM chunks c JOIN documentos d ON d.id=c.documento_id "
           "WHERE c.processo_id=? AND c.embedding IS NOT NULL")
    args: list = [processo_id]
    if classe:
        sql += " AND d.classe=?"
        args.append(classe)
    linhas = db.conn().execute(sql, tuple(args)).fetchall()
    if not linhas:
        return []
    q = np.asarray(llm.embed([pergunta], etiqueta="embedding:pergunta")[0], dtype=np.float32)
    m = np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in linhas])
    sims = (m @ q) / (np.linalg.norm(m, axis=1) * np.linalg.norm(q) + 1e-9)
    ordem = np.argsort(-sims)[:limite]
    return [linhas[i]["id"] for i in ordem]


def buscar(processo_id: str, pergunta: str, top_k: int = 8, classe: str | None = None) -> dict:
    """Devolve chunks citáveis: texto + documento + páginas + origem da busca."""
    cand = top_k * 3
    textual = _textual(processo_id, pergunta, cand, classe)
    try:
        vetorial = _vetorial(processo_id, pergunta, cand, classe)
        aviso = None
    except llm.LLMError as e:
        vetorial, aviso = [], f"busca vetorial indisponível, só textual: {e}"

    score: dict[str, float] = {}
    origem: dict[str, set] = {}
    for nome, lista in (("vetorial", vetorial), ("textual", textual)):
        for pos, cid in enumerate(lista):
            score[cid] = score.get(cid, 0) + 1 / (_RRF_K + pos + 1)
            origem.setdefault(cid, set()).add(nome)
    escolhidos = sorted(score, key=score.get, reverse=True)[:top_k]
    if not escolhidos:
        return {"status": "no_results", "resultados": [], "aviso": aviso}

    marcas = ",".join("?" * len(escolhidos))
    linhas = {r["id"]: r for r in db.todos(
        f"SELECT c.id, c.texto, c.pagina_inicio, c.pagina_fim, c.requer_revisao, c.motivo, "
        f"d.id AS documento_id, d.nome AS documento, d.classe, d.origem "
        f"FROM chunks c JOIN documentos d ON d.id=c.documento_id "
        f"WHERE c.processo_id=? AND c.id IN ({marcas})", (processo_id, *escolhidos))}
    resultados = []
    for cid in escolhidos:
        r = linhas.get(cid)
        if r:
            r["score"] = round(score[cid], 5)
            r["origem_busca"] = sorted(origem[cid])
            r["requer_revisao"] = bool(r["requer_revisao"])
            resultados.append(r)
    return {"status": "ok", "resultados": resultados, "aviso": aviso}
