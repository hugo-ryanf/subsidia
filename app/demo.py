"""Caso pronto: clona o snapshot de um caso já processado para um processo NOVO.

Cada clique gera uma cópia independente (ids novos, arquivos copiados), então quem
testa vê o resultado completo na hora — e o que um jurado aprova ou resolve não
aparece para o próximo. O snapshot vive dentro da imagem (`seed/snapshot/`), por isso
sobrevive ao disco efêmero do plano gratuito.
"""
from __future__ import annotations

import shutil
import sqlite3

from app import db
from app.camada import ingestao
from app.config import RAIZ

SNAPSHOT = RAIZ / "seed" / "snapshot"
SNAPSHOT_DB = SNAPSHOT / "subsidia.db"


def disponivel() -> bool:
    return SNAPSHOT_DB.exists()


def _ler(con: sqlite3.Connection, sql: str, args: tuple = ()) -> list[dict]:
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def clonar() -> str:
    if not disponivel():
        raise FileNotFoundError("snapshot do caso pronto não está nesta instalação")
    src = sqlite3.connect(f"file:{SNAPSHOT_DB.as_posix()}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    try:
        proc = _ler(src, "SELECT * FROM processos LIMIT 1")[0]
        velho = proc["id"]
        docs = _ler(src, "SELECT * FROM documentos WHERE processo_id=?", (velho,))
        chunks = _ler(src, "SELECT * FROM chunks WHERE processo_id=?", (velho,))
        paginas = _ler(src, "SELECT p.* FROM paginas p JOIN documentos d ON d.id=p.documento_id "
                            "WHERE d.processo_id=?", (velho,))
        jobs_ = _ler(src, "SELECT * FROM jobs WHERE processo_id=?", (velho,))
        eventos = _ler(src, "SELECT * FROM eventos WHERE processo_id=? ORDER BY id", (velho,))
        artefatos = _ler(src, "SELECT * FROM artefatos WHERE processo_id=?", (velho,))
        pendencias = _ler(src, "SELECT * FROM pendencias WHERE processo_id=?", (velho,))
    finally:
        src.close()

    novo = db.novo_id("proc_")
    mapa = {velho: novo}
    mapa.update({d["id"]: db.novo_id("doc_") for d in docs})
    mapa.update({c["id"]: db.novo_id("chk_") for c in chunks})
    mapa.update({j["id"]: db.novo_id("job_") for j in jobs_})
    mapa.update({p["id"]: db.novo_id("pend_") for p in pendencias})

    def troca(txt: str | None) -> str | None:
        if not txt:
            return txt
        for a, b in mapa.items():
            txt = txt.replace(a, b)
        return txt

    c = db.conn()
    try:
        c.execute("INSERT INTO processos(id,nome,criado_em) VALUES(?,?,?)",
                  (novo, proc["nome"].replace("(demo)", "(caso pronto)"), db.agora()))
        for d in docs:
            c.execute("INSERT INTO documentos(id,processo_id,nome,classe,origem,sha256,paginas,chunks,"
                      "paginas_revisao,status,erro,criado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (mapa[d["id"]], novo, d["nome"], d["classe"], d["origem"], d["sha256"], d["paginas"],
                       d["chunks"], d["paginas_revisao"], d["status"], d["erro"], d["criado_em"]))
        for p in paginas:
            c.execute("INSERT INTO paginas VALUES(?,?,?,?,?,?)",
                      (mapa[p["documento_id"]], p["numero"], p["chars"], p["confianca"], p["requer_revisao"],
                       p["motivo"]))
        for ch in chunks:
            nid = mapa[ch["id"]]
            c.execute("INSERT INTO chunks(id,processo_id,documento_id,ordem,texto,pagina_inicio,pagina_fim,"
                      "requer_revisao,motivo,embedding) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (nid, novo, mapa[ch["documento_id"]], ch["ordem"], ch["texto"], ch["pagina_inicio"],
                       ch["pagina_fim"], ch["requer_revisao"], ch["motivo"], ch["embedding"]))
            c.execute("INSERT INTO chunks_fts(texto,chunk_id,processo_id) VALUES(?,?,?)", (ch["texto"], nid, novo))
        for j in jobs_:
            c.execute("INSERT INTO jobs(id,processo_id,tipo,status,etapa,erro,resultado,criado_em,atualizado_em) "
                      "VALUES(?,?,?,?,?,?,?,?,?)",
                      (mapa[j["id"]], novo, j["tipo"], j["status"], j["etapa"], j["erro"], troca(j["resultado"]),
                       j["criado_em"], j["atualizado_em"]))
        for e in eventos:
            c.execute("INSERT INTO eventos(processo_id,job_id,tipo,etiqueta,modelo,tokens_entrada,tokens_saida,"
                      "custo_usd,segundos,detalhe,criado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                      (novo, mapa.get(e["job_id"], e["job_id"]), e["tipo"], e["etiqueta"], e["modelo"],
                       e["tokens_entrada"], e["tokens_saida"], e["custo_usd"], e["segundos"], troca(e["detalhe"]),
                       e["criado_em"]))
        for a in artefatos:
            c.execute("INSERT INTO artefatos(processo_id,tipo,conteudo,aprovado,atualizado_em) VALUES(?,?,?,?,?)",
                      (novo, a["tipo"], troca(a["conteudo"]), a["aprovado"], a["atualizado_em"]))
        for p in pendencias:
            c.execute("INSERT INTO pendencias(id,processo_id,pedido_id,titulo,contexto,status,resolucao,criado_em,"
                      "resolvido_em) VALUES(?,?,?,?,?,?,?,?,?)",
                      (mapa[p["id"]], novo, p["pedido_id"], p["titulo"], p["contexto"], p["status"], p["resolucao"],
                       p["criado_em"], p["resolvido_em"]))
        origem = SNAPSHOT / "arquivos" / velho
        if origem.exists():
            shutil.copytree(origem, ingestao.PASTA_ARQUIVOS / novo, dirs_exist_ok=True)
        c.commit()
    except Exception:
        c.rollback()
        shutil.rmtree(ingestao.PASTA_ARQUIVOS / novo, ignore_errors=True)
        raise
    return novo
