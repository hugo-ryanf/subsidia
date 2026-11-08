"""Fachada dos "sistemas da empresa" — o que as ferramentas do agente chamam.

Cada consulta devolve `{"status", "sistema", "dados", "pdf"}`. Ausência é explícita
(`status='sem_registros'`), nunca lista vazia muda — o agente precisa distinguir "não
achei" de "não existe" para escalar certo.

`instavel`: o FGTS falha com 503 na 1ª chamada de cada processo (simula sistema legado
fora do ar), para a demo mostrar a retentativa — confiabilidade é critério da banca.
"""
from __future__ import annotations

import threading

from app.rh_mock import dados as D
from app.rh_mock import pdfs as P

SISTEMAS = {
    "rh": "GenteRH (cadastro de pessoal)",
    "ponto": "PontoFácil (registro eletrônico)",
    "folha": "FolhaPro (folha de pagamento)",
    "fgts": "FGTS Digital (simulado)",
    "sst": "SSTNet (saúde e segurança do trabalho)",
}

_falhou_uma_vez: set[str] = set()
_trava = threading.Lock()


class SistemaIndisponivel(RuntimeError):
    pass


def _ok(sistema: str, dados, pdf: bytes | None = None, nome_pdf: str | None = None) -> dict:
    return {"status": "ok", "sistema": SISTEMAS[sistema], "dados": dados, "pdf": pdf, "nome_pdf": nome_pdf}


def _vazio(sistema: str, motivo: str) -> dict:
    return {"status": "sem_registros", "sistema": SISTEMAS[sistema], "dados": None, "pdf": None,
            "nome_pdf": None, "motivo": motivo}


def _matricula(m: str) -> None:
    if m not in D.FUNCIONARIOS:
        raise KeyError(f"matrícula {m} não encontrada no cadastro")


def buscar_funcionario(termo: str) -> dict:
    t = termo.strip().lower().replace(".", "").replace("-", "")
    for f in D.FUNCIONARIOS.values():
        if t and (t in f["nome"].lower() or t == f["cpf"].replace(".", "").replace("-", "") or t == f["matricula"]):
            return _ok("rh", f, P.ficha_registro(f["matricula"]), f"ficha_registro_{f['matricula']}.pdf")
    return _vazio("rh", f"nenhum empregado encontrado para '{termo}'")


def ponto(matricula: str, competencia: str) -> dict:
    _matricula(matricula)
    marc = D.ponto(competencia, matricula)
    if marc is None:
        return _vazio("ponto", f"sem marcações de ponto para a competência {competencia}")
    return _ok("ponto", {"competencia": competencia, "marcacoes": marc,
                         "minutos_extras": D.minutos_extras(marc)},
               P.cartao_ponto(competencia, matricula=matricula), f"espelho_ponto_{competencia}.pdf")


def holerite(matricula: str, competencia: str) -> dict:
    _matricula(matricula)
    h = D.holerite(competencia, matricula)
    if h is None:
        return _vazio("folha", f"sem holerite para a competência {competencia}")
    return _ok("folha", h, P.holerite(competencia, matricula), f"holerite_{competencia}.pdf")


def trct(matricula: str) -> dict:
    _matricula(matricula)
    return _ok("folha", D.trct(matricula), P.trct(matricula), "trct.pdf")


def extrato_fgts(matricula: str, processo_id: str = "") -> dict:
    _matricula(matricula)
    with _trava:
        if processo_id not in _falhou_uma_vez:
            _falhou_uma_vez.add(processo_id)
            raise SistemaIndisponivel("FGTS Digital respondeu HTTP 503 (serviço temporariamente indisponível)")
    return _ok("fgts", D.extrato_fgts(matricula), P.extrato_fgts(matricula), "extrato_fgts.pdf")


def epi(matricula: str) -> dict:
    _matricula(matricula)
    return _ok("sst", {"entregas": D.fichas_epi(matricula)}, P.ficha_epi(matricula), "ficha_epi.pdf")


def laudo_ltcat(matricula: str = D.DEMO) -> dict:
    return _ok("sst", D.ltcat(matricula), P.ltcat(matricula), "ltcat.pdf")


def ocorrencias(matricula: str) -> dict:
    _matricula(matricula)
    o = D.ocorrencias(matricula)
    if not o:
        return _vazio("rh", "nenhuma ocorrência, advertência ou reclamação interna registrada")
    return _ok("rh", o, P.ocorrencias(matricula), f"ocorrencias_{matricula}.pdf")


def competencias_contrato(matricula: str) -> list[str]:
    _matricula(matricula)
    return D.competencias(matricula)
