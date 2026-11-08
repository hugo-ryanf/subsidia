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


@app.post("/demo/pronto", status_code=201)
def abrir_caso_pronto() -> dict:
    """Cópia nova e independente de um caso já processado (resultado na hora)."""
    from app import demo
    if not demo.disponivel():
        raise HTTPException(404, "caso pronto não disponível nesta instalação")
    return {"processo_id": demo.clonar()}


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


@app.post("/processos/{processo_id}/subsidios", status_code=202)
def disparar_subsidios(processo_id: str) -> dict:
    from app.agentes import subsidios
    _processo(processo_id)
    return {"job_id": jobs.disparar(processo_id, "subsidios", lambda jid: subsidios.executar(processo_id, jid))}


class Resolucao(BaseModel):
    status: str            # resolvida | descartada
    resolucao: str         # o que o humano fez/decidiu (obrigatório: descarte nunca é silencioso)


@app.post("/processos/{processo_id}/pendencias/{pendencia_id}")
def resolver_pendencia(processo_id: str, pendencia_id: str, body: Resolucao) -> dict:
    _processo(processo_id)
    if body.status not in ("resolvida", "descartada") or not body.resolucao.strip():
        raise HTTPException(422, "status deve ser resolvida|descartada e a resolução é obrigatória")
    p = db.um("SELECT * FROM pendencias WHERE id=? AND processo_id=?", (pendencia_id, processo_id))
    if not p:
        raise HTTPException(404, "pendência não existe")
    db.executar("UPDATE pendencias SET status=?, resolucao=?, resolvido_em=? WHERE id=?",
                (body.status, body.resolucao, db.agora(), pendencia_id))
    rastro.registrar("humano", f"pendencia:{body.status}", {"titulo": p["titulo"], "resolucao": body.resolucao},
                     processo_id=processo_id)
    return {"ok": True}


@app.post("/processos/{processo_id}/estrategia", status_code=202)
def disparar_estrategia(processo_id: str) -> dict:
    from app.agentes import estrategia
    _processo(processo_id)
    return {"job_id": jobs.disparar(processo_id, "estrategia", lambda jid: estrategia.executar(processo_id, jid))}


@app.get("/processos/{processo_id}/documentos/{documento_id}/arquivo")
def arquivo_documento(processo_id: str, documento_id: str):
    """PDF original de um documento citado (autos ou subsídio) — o advogado confere a fonte."""
    from fastapi.responses import FileResponse
    d = db.um("SELECT * FROM documentos WHERE id=? AND processo_id=?", (documento_id, processo_id))
    if not d:
        raise HTTPException(404, "documento não existe neste processo")
    caminho = ingestao.PASTA_ARQUIVOS / processo_id / f"{d['sha256'][:16]}_{d['nome']}"
    if not caminho.exists():
        raise HTTPException(404, "arquivo não encontrado no armazenamento")
    return FileResponse(caminho, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{d["nome"]}"'})


@app.get("/processos/{processo_id}/jobs")
def jobs_do_processo(processo_id: str) -> dict:
    """Último job de cada tipo — a UI retoma o acompanhamento depois de um reload."""
    _processo(processo_id)
    linhas = db.todos("SELECT id,tipo,status,etapa,erro,criado_em,atualizado_em FROM jobs "
                      "WHERE processo_id=? ORDER BY criado_em", (processo_id,))
    return {j["tipo"]: j for j in linhas}


# --- frontend (build do Vite servido pelo mesmo app: um serviço só no deploy) ---------
from pathlib import Path as _Path  # noqa: E402

from fastapi.responses import FileResponse as _FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles as _StaticFiles  # noqa: E402

_DIST = _Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", _StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def _index():
        return _FileResponse(_DIST / "index.html")


# --- conectores: AFD do ponto ------------------------------------------------------------

@app.post("/processos/{processo_id}/afd")
async def importar_afd(processo_id: str, arquivo: UploadFile = File(...)) -> dict:
    """Importa o AFD (Portarias 1510/671): a coleta passa a ler o ponto deste arquivo."""
    from app.conectores import afd
    _processo(processo_id)
    conteudo = await arquivo.read()
    if len(conteudo) > 50_000_000:
        raise HTTPException(413, "AFD acima de 50 MB")
    resumo = afd.importar(processo_id, arquivo.filename or "afd.txt", conteudo)
    if not resumo["marcacoes"]:
        raise HTTPException(422, f"nenhuma marcação de ponto reconhecida no arquivo ({resumo['total_linhas_nao_lidas']} "
                                 "linha(s) não lidas) — confira se é um AFD")
    rastro.registrar("humano", "importou:afd", {"arquivo": resumo["arquivo"], "layout": resumo["layout"],
                                                "marcacoes": resumo["marcacoes"], "empregados": resumo["empregados"]},
                     processo_id=processo_id)
    return resumo


@app.get("/processos/{processo_id}/afd")
def resumo_afd(processo_id: str) -> dict:
    from app.conectores import afd
    _processo(processo_id)
    return {"importado": afd.resumo_importado(processo_id)}
