"""Rótulos de citação (D1, D2, ...) — a disciplina factual do sistema.

Todo trecho que entra no prompt ganha um rótulo; o modelo só pode citar rótulos que
recebeu. Citação desconhecida é detectada e vira `requer_revisao`, nunca passa calada.
"""
from __future__ import annotations

import re

from app import db

_REF = re.compile(r"\bD(\d+)\b")


def em_blocos(chunks: list[dict], limite_chars: int) -> list[list[dict]]:
    """Divide em blocos de até `limite_chars`, na ordem, sem perder nenhum chunk."""
    blocos: list[list[dict]] = []
    atual: list[dict] = []
    total = 0
    for c in chunks:
        if atual and total + len(c["texto"]) > limite_chars:
            blocos.append(atual)
            atual, total = [], 0
        atual.append(c)
        total += len(c["texto"])
    if atual:
        blocos.append(atual)
    return blocos


def rotular(chunks: list[dict], limite_chars: int | None = None, inicio: int = 0) -> tuple[str, dict[str, dict]]:
    """Rotula a partir de D{inicio + 1}. Com `limite_chars`, o excedente fica de fora: só use
    quando o texto for uma amostra declarada; para ler tudo, divida antes com `em_blocos`."""
    refs: dict[str, dict] = {}
    partes, total = [], 0
    for c in chunks:
        if limite_chars is not None and total + len(c["texto"]) > limite_chars:
            break
        rot = f"D{inicio + len(refs) + 1}"
        refs[rot] = {"chunk_id": c["id"], "documento_id": c["documento_id"], "documento": c["documento"],
                     "classe": c.get("classe"), "pagina_inicio": c["pagina_inicio"],
                     "pagina_fim": c["pagina_fim"], "requer_revisao": bool(c.get("requer_revisao"))}
        pag = c["pagina_inicio"] if c["pagina_inicio"] == c["pagina_fim"] else \
            f"{c['pagina_inicio']}-{c['pagina_fim']}"
        partes.append(f"[{rot}] ({c['documento']}, p. {pag})\n{c['texto']}")
        total += len(c["texto"])
    return "\n\n".join(partes), refs


def chunks_do_processo(processo_id: str, classe: str | None = None, documento_id: str | None = None) -> list[dict]:
    sql = ("SELECT c.id, c.texto, c.pagina_inicio, c.pagina_fim, c.requer_revisao, c.documento_id, "
           "d.nome AS documento, d.classe FROM chunks c JOIN documentos d ON d.id=c.documento_id "
           "WHERE c.processo_id=?")
    args: list = [processo_id]
    if classe:
        sql += " AND d.classe=?"
        args.append(classe)
    if documento_id:
        sql += " AND d.id=?"
        args.append(documento_id)
    sql += " ORDER BY d.criado_em, c.ordem"
    return db.todos(sql, tuple(args))


def validar(citadas: list[str], refs: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """Separa citações válidas (resolvidas para doc+página) das inválidas."""
    ok, ruins = [], []
    for c in citadas or []:
        m = _REF.search(str(c))
        rot = f"D{m.group(1)}" if m else str(c)
        if rot in refs:
            ok.append({"ref": rot, **refs[rot]})
        else:
            ruins.append(str(c))
    return ok, ruins


def refs_no_texto(texto: str) -> list[str]:
    return sorted({f"D{n}" for n in _REF.findall(texto)}, key=lambda r: int(r[1:]))
