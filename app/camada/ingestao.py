"""Ingestão: PDF → páginas → chunks → embeddings → SQLite (+FTS5).

Usada para os AUTOS (upload) e para os SUBSÍDIOS que o worker puxa dos sistemas de RH
(`classe='subsidio'`, `origem='sistema:<nome>'`) — os dois ficam citáveis do mesmo jeito.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from app import db, llm, rastro
from app.camada import chunking, extracao
from app.config import RAIZ

PASTA_ARQUIVOS = RAIZ / "data" / "arquivos"


def guardar_arquivo(processo_id: str, nome: str, conteudo: bytes) -> tuple[Path, str]:
    sha = hashlib.sha256(conteudo).hexdigest()
    destino = PASTA_ARQUIVOS / processo_id / f"{sha[:16]}_{Path(nome).name}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)
    return destino, sha


def registrar_documento(processo_id: str, nome: str, sha: str, classe: str, origem: str) -> str:
    doc_id = db.novo_id("doc_")
    db.executar(
        "INSERT INTO documentos(id,processo_id,nome,classe,origem,sha256,status,criado_em) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (doc_id, processo_id, nome, classe, origem, sha, "queued", db.agora()),
    )
    return doc_id


def processar(doc_id: str, caminho: Path) -> dict:
    """Processa um documento já registrado. Levanta exceção em falha total (o job vira
    `erro`); falha parcial (embedding) vira chunks `requer_revisao`, nunca descarte."""
    doc = db.um("SELECT * FROM documentos WHERE id=?", (doc_id,))
    processo_id = doc["processo_id"]
    db.executar("UPDATE documentos SET status='processando' WHERE id=?", (doc_id,))
    try:
        paginas = extracao.extrair(caminho)
        for p in paginas:
            db.conn().execute(
                "INSERT OR REPLACE INTO paginas VALUES(?,?,?,?,?,?)",
                (doc_id, p.numero, len(p.texto), p.confianca, int(p.requer_revisao), p.motivo),
            )
        chunks = chunking.gerar(paginas)

        vetores: list[list[float] | None]
        try:
            vetores = llm.embed([c.texto for c in chunks], etiqueta=f"embedding:{doc['nome']}")
        except llm.LLMError as e:
            # Sem vetor o chunk continua achável pelo full-text; fica marcado para revisão.
            vetores = [None] * len(chunks)
            rastro.registrar("erro", "embedding", {"documento": doc["nome"], "erro": str(e)})

        c = db.conn()
        for ch, vet in zip(chunks, vetores):
            cid = db.novo_id("chk_")
            motivo = ch.motivo
            revisao = ch.requer_revisao
            if vet is None:
                revisao, motivo = True, "; ".join(filter(None, [motivo, "sem embedding (só busca textual)"]))
            blob = np.asarray(vet, dtype=np.float32).tobytes() if vet is not None else None
            c.execute(
                "INSERT INTO chunks(id,processo_id,documento_id,ordem,texto,pagina_inicio,pagina_fim,"
                "requer_revisao,motivo,embedding) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (cid, processo_id, doc_id, ch.ordem, ch.texto, ch.pagina_inicio, ch.pagina_fim,
                 int(revisao), motivo, blob),
            )
            c.execute("INSERT INTO chunks_fts(texto,chunk_id,processo_id) VALUES(?,?,?)",
                      (ch.texto, cid, processo_id))
        revisao_pags = sum(p.requer_revisao for p in paginas)
        c.execute(
            "UPDATE documentos SET status='concluido', paginas=?, chunks=?, paginas_revisao=? WHERE id=?",
            (len(paginas), len(chunks), revisao_pags, doc_id),
        )
        c.commit()
        return {"documento_id": doc_id, "paginas": len(paginas), "chunks": len(chunks),
                "paginas_requer_revisao": revisao_pags}
    except Exception as e:
        db.conn().rollback()
        db.executar("UPDATE documentos SET status='erro', erro=? WHERE id=?",
                    (f"{type(e).__name__}: {e}", doc_id))
        raise


def ingerir_bytes(processo_id: str, nome: str, conteudo: bytes, classe: str, origem: str) -> dict:
    """Atalho síncrono (usado pelas ferramentas do worker de subsídios)."""
    caminho, sha = guardar_arquivo(processo_id, nome, conteudo)
    existente = db.um("SELECT id FROM documentos WHERE processo_id=? AND sha256=? AND status='concluido'",
                      (processo_id, sha))
    if existente:
        return {"documento_id": existente["id"], "reaproveitado": True}
    doc_id = registrar_documento(processo_id, nome, sha, classe, origem)
    return processar(doc_id, caminho)
