"""API do Subsídia — um app só (camada de documento + agentes + RH simulado)."""
from __future__ import annotations

import logging

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from app import db, jobs, rastro
from app.camada import busca, ingestao
from app.config import cfg
from app.rh_mock import api as rh_api

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Subsídia", version="0.1.0")
app.include_router(rh_api.router)


@app.on_event("startup")  # noqa: lifespan fica para depois
def _subir() -> None:
    db.iniciar()
    jobs.reconciliar_orfaos()


def _processo(processo_id: str) -> dict:
    p = db.um("SELECT * FROM processos WHERE id=?", (processo_id,))
    if not p:
        raise HTTPException(404, f"processo {processo_id} não existe")
    return p


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "modelos": {"pesado": cfg.model_pesado, "leve": cfg.model_leve,
                                        "embedding": cfg.embed_model},
            # Regra #2: a UI sinaliza que o processamento sai do perímetro local.
            "perimetro": "nuvem" if "localhost" not in cfg.llm_base_url else "local",
            "provedor": cfg.llm_base_url}


# --- processos -------------------------------------------------------------------------

class NovoProcesso(BaseModel):
    nome: str


@app.post("/processos", status_code=201)
def criar_processo(body: NovoProcesso) -> dict:
    pid = db.novo_id("proc_")
    db.executar("INSERT INTO processos(id,nome,criado_em) VALUES(?,?,?)", (pid, body.nome, db.agora()))
    return {"processo_id": pid, "nome": body.nome}


@app.get("/processos")
def listar_processos() -> list[dict]:
    return db.todos("SELECT * FROM processos ORDER BY criado_em DESC")


@app.get("/processos/{processo_id}")
def obter_processo(processo_id: str) -> dict:
    p = _processo(processo_id)
    p["documentos"] = db.todos(
        "SELECT id,nome,classe,origem,paginas,chunks,paginas_revisao,status,erro,criado_em "
        "FROM documentos WHERE processo_id=? ORDER BY criado_em", (processo_id,))
    p["pendencias"] = db.todos(
        "SELECT * FROM pendencias WHERE processo_id=? ORDER BY criado_em", (processo_id,))
    p["artefatos"] = {t: db.artefato(processo_id, t) for t in ("triagem", "subsidios", "estrategia")}
    return p


# --- documentos (autos) ------------------------------------------------------------------

@app.post("/processos/{processo_id}/documentos", status_code=202)
async def enviar_documento(processo_id: str, arquivo: UploadFile = File(...)) -> dict:
    _processo(processo_id)
    conteudo = await arquivo.read()
    if not conteudo.startswith(b"%PDF"):
        raise HTTPException(422, "o arquivo não é um PDF")
    caminho, sha = ingestao.guardar_arquivo(processo_id, arquivo.filename, conteudo)
    doc_id = ingestao.registrar_documento(processo_id, arquivo.filename, sha, "autos", "upload")
    job_id = jobs.disparar(processo_id, "ingestao", lambda jid: ingestao.processar(doc_id, caminho))
    return {"job_id": job_id, "documento_id": doc_id}


@app.get("/jobs/{job_id}")
def obter_job(job_id: str) -> dict:
    j = jobs.obter(job_id)
    if not j:
        raise HTTPException(404, "job não existe")
    return j


# --- busca -------------------------------------------------------------------------------

class Pergunta(BaseModel):
    pergunta: str
    top_k: int = 8
    classe: str | None = None


@app.post("/processos/{processo_id}/buscar")
def buscar(processo_id: str, body: Pergunta) -> dict:
    _processo(processo_id)
    token = rastro.entrar(processo_id)
    try:
        return busca.buscar(processo_id, body.pergunta, body.top_k, body.classe)
    finally:
        rastro.sair(token)


# --- rastro ------------------------------------------------------------------------------

@app.get("/processos/{processo_id}/rastro")
def obter_rastro(processo_id: str) -> dict:
    _processo(processo_id)
    return rastro.resumo(processo_id)


# --- demo ------------------------------------------------------------------------------

@app.post("/demo/processo", status_code=202)
def criar_processo_demo() -> dict:
    """Cria o processo de demonstração e ingere a petição inicial sintética."""
    from app.rh_mock import inicial
    pid = db.novo_id("proc_")
    db.executar("INSERT INTO processos(id,nome,criado_em) VALUES(?,?,?)",
                (pid, f"Reclamação {inicial.NUMERO} (demo)", db.agora()))
    conteudo = inicial.gerar_pdf()
    caminho, sha = ingestao.guardar_arquivo(pid, "peticao_inicial.pdf", conteudo)
    doc_id = ingestao.registrar_documento(pid, "peticao_inicial.pdf", sha, "autos", "upload")
    job_id = jobs.disparar(pid, "ingestao", lambda jid: ingestao.processar(doc_id, caminho))
    return {"processo_id": pid, "job_id": job_id}


# --- agentes ---------------------------------------------------------------------------

@app.post("/processos/{processo_id}/triagem", status_code=202)
def disparar_triagem(processo_id: str) -> dict:
    from app.agentes import triagem
    _processo(processo_id)
    return {"job_id": jobs.disparar(processo_id, "triagem", lambda jid: triagem.executar(processo_id, jid))}


class Aprovacao(BaseModel):
    conteudo: dict | None = None   # versão editada pelo humano (opcional)
    observacao: str | None = None


@app.post("/processos/{processo_id}/aprovar/{tipo}")
def aprovar(processo_id: str, tipo: str, body: Aprovacao) -> dict:
    """Portão humano entre etapas: o agente prepara, a pessoa aprova (e pode editar)."""
    _processo(processo_id)
    atual = db.artefato(processo_id, tipo)
    if not atual:
        raise HTTPException(409, f"não há {tipo} gerado para aprovar")
    conteudo = body.conteudo or atual["conteudo"]
    db.salvar_artefato(processo_id, tipo, conteudo, aprovado=True)
    rastro.registrar("humano", f"aprovou:{tipo}", {"editado": body.conteudo is not None,
                                                  "observacao": body.observacao}, processo_id=processo_id)
    return {"aprovado": True, "tipo": tipo}
