"""Rotas HTTP dos sistemas simulados — para a tela "Sistemas da empresa" e para os jurados
conferirem que o agente opera sobre dados reais da demo (não inventa)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.rh_mock import inicial, sistemas

router = APIRouter(prefix="/rh", tags=["sistemas da empresa (simulados)"])


def _json(r: dict) -> dict:
    return {k: v for k, v in r.items() if k != "pdf"}


def _pdf(r: dict) -> Response:
    if r["status"] != "ok" or not r["pdf"]:
        raise HTTPException(404, r.get("motivo", "sem documento"))
    return Response(r["pdf"], media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{r["nome_pdf"]}"'})


@router.get("/sistemas")
def listar() -> dict:
    return sistemas.SISTEMAS


@router.get("/funcionarios")
def funcionarios(termo: str) -> dict:
    return _json(sistemas.buscar_funcionario(termo))


@router.get("/ponto/{matricula}/{competencia}")
def ponto(matricula: str, competencia: str, pdf: bool = False):
    r = sistemas.ponto(matricula, competencia)
    return _pdf(r) if pdf else _json(r)


@router.get("/folha/{matricula}/holerite/{competencia}")
def holerite(matricula: str, competencia: str, pdf: bool = False):
    r = sistemas.holerite(matricula, competencia)
    return _pdf(r) if pdf else _json(r)


@router.get("/folha/{matricula}/trct")
def trct(matricula: str, pdf: bool = False):
    r = sistemas.trct(matricula)
    return _pdf(r) if pdf else _json(r)


@router.get("/sst/{matricula}/epi")
def epi(matricula: str, pdf: bool = False):
    r = sistemas.epi(matricula)
    return _pdf(r) if pdf else _json(r)


@router.get("/sst/ltcat")
def ltcat(pdf: bool = False):
    r = sistemas.laudo_ltcat()
    return _pdf(r) if pdf else _json(r)


@router.get("/demo/inicial.pdf")
def inicial_pdf() -> Response:
    return Response(inicial.gerar_pdf(), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="inicial_demo.pdf"'})


@router.get("/demo/afd.txt")
def afd_exemplo() -> Response:
    """AFD de exemplo da empresa fictícia (layout da Portaria 671), para testar a importação."""
    from app.conectores import afd
    return Response(afd.gerar_exemplo(), media_type="text/plain; charset=latin-1",
                    headers={"Content-Disposition": 'attachment; filename="AFD_mercado_exemplo.txt"'})
