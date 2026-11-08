"""Regras determinísticas do cruzamento: sem LLM e sem banco."""
import pytest

from app.agentes.cruzamento import cruzar
from app.agentes.ferramentas import Caixa


def _caixa(**dados) -> Caixa:
    return Caixa("proc", "0042", ["2024-09"], dados=dados)


def _pedido(pid: str, arquetipo: str, titulo: str) -> dict:
    return {"id": pid, "arquetipo": arquetipo, "titulo": titulo}


@pytest.mark.parametrize("conclusao", [
    "O EPI não neutraliza o agente frio.",
    "EPI nao neutraliza o agente.",
    "Não se pode afirmar que o EPI neutraliza o agente.",
    "Não se pode afirmar, nos termos do art. 253 da CLT, que o EPI neutraliza o agente.",
    "Vestimenta insuficiente para neutralizar o frio.",
    "Sem neutralização do agente pelos EPIs fornecidos.",
    "O EPI neutraliza apenas parcialmente o agente.",
    "A neutralização do agente não foi comprovada.",
    "Neutralização insuficiente do agente.",
    "O agente foi neutralizado de forma insuficiente.",
    "A empresa deixou de neutralizar o agente.",
    "Exposição ao frio caracterizada como insalubre em grau médio.",
])
def test_ltcat_que_nao_atesta_neutralizacao_nao_favorece_a_empresa(conclusao):
    achados = cruzar(_caixa(ltcat={"conclusao": conclusao}), [_pedido("ins", "saude_acidente", "Insalubridade")])
    ltcat = [a for a in achados if "LTCAT" in a["titulo"]]
    assert [a["tipo"] for a in ltcat] == ["divergencia"]


@pytest.mark.parametrize("conclusao", [
    "O EPI neutraliza o agente.",
    "Agente neutralizado pelo EPI, não sendo devido o adicional.",
    "O EPI neutraliza o agente e não é devido o adicional.",
    # Texto real do LTCAT do caso de demonstração.
    "Exposição ao agente frio NEUTRALIZADA pelo uso regular de vestimenta térmica, luvas e botas forradas com "
    "CA válido, além de pausas de recuperação térmica (art. 253 da CLT). Atividade não caracterizada como "
    "insalubre enquanto mantido o fornecimento dos EPIs.",
])
def test_ltcat_que_atesta_neutralizacao_favorece_a_empresa(conclusao):
    achados = cruzar(_caixa(ltcat={"conclusao": conclusao}), [_pedido("ins", "saude_acidente", "Insalubridade")])
    ltcat = [a for a in achados if "LTCAT" in a["titulo"]]
    assert [a["tipo"] for a in ltcat] == ["favoravel"]


def _caixa_he_nao_paga() -> Caixa:
    """Setembro com 10h extras no ponto e nenhuma rubrica de extra no holerite."""
    return _caixa(**{
        "ponto:2024-09": {"minutos_extras": 600, "marcacoes": [], "dias_batida_impar": []},
        "holerite:2024-09": {"rubricas": []},
        "ficha_registro": {"salario_base": 2200.0},
    })


def _expostos(achados: list[dict]) -> list[dict]:
    return [a for a in achados if a["exposicao_estimada"]]


def test_exposicao_de_horas_extras_conta_uma_vez_e_fica_no_pedido_principal():
    pedidos = [_pedido("reflexos_dsr", "jornada", "Reflexos das horas extras em DSR"),
               _pedido("horas_extras", "jornada", "Horas extras")]
    achados = cruzar(_caixa_he_nao_paga(), pedidos)

    expostos = _expostos(achados)
    assert [a["pedido_id"] for a in expostos] == ["horas_extras"]
    assert expostos[0]["exposicao_estimada"] == pytest.approx(10 * (2200 / 220) * 1.5)

    # O outro pedido continua vendo a divergência, avisado de que o valor está no principal.
    dsr = [a for a in achados if a["pedido_id"] == "reflexos_dsr" and a["tipo"] == "divergencia"]
    assert len(dsr) == 1 and "Horas extras" in dsr[0]["detalhe"]


def test_exposicao_sem_pedido_principal_fica_no_primeiro():
    pedidos = [_pedido("dsr", "jornada", "Descanso semanal"), _pedido("noturno", "jornada", "Adicional noturno")]
    assert [a["pedido_id"] for a in _expostos(cruzar(_caixa_he_nao_paga(), pedidos))] == ["dsr"]


def test_exposicao_da_rescisao_tardia_conta_uma_vez():
    caixa = _caixa(trct={"data_pagamento": "2025-03-20", "prazo_legal": "2025-03-10"},
                   ficha_registro={"salario_base": 2200.0})
    pedidos = [_pedido("multa_477", "validade_rescisao", "Multa do art. 477"),
               _pedido("multa_467", "validade_rescisao", "Multa do art. 467")]
    assert [a["pedido_id"] for a in _expostos(cruzar(caixa, pedidos))] == ["multa_477"]


def test_pedido_unico_mantem_exposicao_e_detalhe():
    achados = cruzar(_caixa_he_nao_paga(), [_pedido("horas_extras", "jornada", "Horas extras")])
    assert len(_expostos(achados)) == 1
    assert "não somar" not in _expostos(achados)[0]["detalhe"]
