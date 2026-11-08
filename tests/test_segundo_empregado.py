"""Segundo empregado: as regras leem os dados de cada um, sem frase fixa do caso de demonstração. Offline."""
import json

import fitz
import pytest

from app.agentes.cruzamento import cruzar
from app.agentes.estrategia import _risco
from app.agentes.ferramentas import Caixa
from app.rh_mock import dados as D, inicial, sistemas as S

M = "0107"
PEDIDOS = {
    "horas_extras": "jornada", "intervalo": "jornada", "multa_477": "validade_rescisao",
    "fgts": "verbas_descontos", "insalubridade": "saude_acidente", "assedio_moral": "assedio",
}
ALEGA = "De segunda a sexta das 7h às 18h e aos sábados das 7h às 15h, sem pagamento de horas extras."


def _texto(pdf: bytes) -> str:
    with fitz.open(stream=pdf, filetype="pdf") as d:
        return "\n".join(p.get_text() for p in d)


def _extrato() -> dict:
    S._falhou_uma_vez.add("proc")   # pula a queda simulada do FGTS
    return S.extrato_fgts(M, "proc")


def _caixa() -> Caixa:
    comps = S.competencias_contrato(M)
    c = Caixa("proc", M, comps)
    c.dados["ficha_registro"] = S.buscar_funcionario(M)["dados"]
    for comp in comps:
        c.dados[f"ponto:{comp}"] = S.ponto(M, comp)["dados"]
        c.dados[f"holerite:{comp}"] = S.holerite(M, comp)["dados"]
    c.dados["trct"] = S.trct(M)["dados"]
    c.dados["fgts"] = _extrato()["dados"]
    c.dados["epi"] = S.epi(M)["dados"]
    c.dados["ltcat"] = S.laudo_ltcat(M)["dados"]
    c.dados["ocorrencias"] = S.ocorrencias(M)["dados"]
    return c


@pytest.fixture
def achados():
    pedidos = [{"id": i, "arquetipo": a, "titulo": i, "alegacao": ALEGA if i == "horas_extras" else ""}
               for i, a in PEDIDOS.items()]
    todos = cruzar(_caixa(), pedidos)
    return {i: [a for a in todos if a["pedido_id"] == i] for i in PEDIDOS}


def _tipos(lista):
    return {a["tipo"] for a in lista}


def test_cadastro_acha_cada_empregado_e_nao_casa_termo_vazio():
    assert S.buscar_funcionario("111.444.777-35")["dados"]["matricula"] == M
    assert S.buscar_funcionario("JULIANA FERREIRA CAMPOS")["dados"]["matricula"] == M
    assert S.buscar_funcionario("Carlos Eduardo Nogueira")["dados"]["matricula"] == "0042"
    assert S.buscar_funcionario("")["status"] == "sem_registros"


def test_horas_extras_pagas_e_sabado_refutado(achados):
    he = achados["horas_extras"]
    assert "divergencia" not in _tipos(he)
    assert any(a["titulo"] == "Horas extras pagas corretamente quando prestadas" for a in he)
    sab = [a for a in he if "sábados" in a["titulo"]]
    assert len(sab) == 1 and "até 15h" in sab[0]["detalhe"]


def test_quadro_desfavoravel_e_risco_calculado(achados):
    assert any("Intervalo inferior" in a["titulo"] for a in achados["intervalo"])
    multa = achados["multa_477"][0]
    assert multa["tipo"] == "divergencia" and multa["exposicao_estimada"] == 1600.00
    assert "2 competência" in achados["fgts"][0]["titulo"]
    ins = achados["insalubridade"]
    assert {a["titulo"] for a in ins} == {"Falhas no fornecimento de EPI", "LTCAT reconhece insalubridade"}
    assert achados["assedio_moral"][0]["titulo"] == "Há ocorrências registradas — analisar"
    assert [_risco(achados[i]) for i in ("multa_477", "fgts", "insalubridade")] == ["alto"] * 3
    assert _risco(achados["assedio_moral"]) == "medio"


def test_nenhum_achado_traz_frase_do_caso_de_demonstracao(achados):
    txt = json.dumps(achados, ensure_ascii=False)
    for frase in ("20 min", "14h", "abril/2025", "térmico", "12h"):
        assert frase not in txt


def test_sem_alegacao_de_sabado_nao_gera_achado():
    p = {"id": "horas_extras", "arquetipo": "jornada", "titulo": "Horas extras", "alegacao": "Fazia horas extras."}
    assert not [a for a in cruzar(_caixa(), [p]) if "sábados" in a["titulo"]]


def test_documentos_trazem_a_empregada_certa():
    for pdf in (S.ponto(M, "2024-05")["pdf"], S.holerite(M, "2024-05")["pdf"], S.trct(M)["pdf"], S.epi(M)["pdf"],
                S.laudo_ltcat(M)["pdf"], S.ocorrencias(M)["pdf"], S.buscar_funcionario(M)["pdf"]):
        t = _texto(pdf)
        assert D.SEGUNDA["nome"] in t and D.FUNCIONARIO["nome"] not in t
    assert "Todas as competências" not in _texto(_extrato()["pdf"])


def test_inicial_da_segunda_reclamante():
    t = _texto(inicial.gerar_pdf(M))
    assert D.SEGUNDA["cpf"] in t and inicial.NUMERO_2 in t and "Carlos" not in t
    assert "R$ 45.100,00" in t
    assert D.FUNCIONARIO["nome"].upper() in _texto(inicial.gerar_pdf())
