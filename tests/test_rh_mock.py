"""Os sistemas simulados precisam bater com o gabarito — senão o eval mede ruído."""
import json
from pathlib import Path

import fitz
import pytest

from app.rh_mock import dados as D, inicial, sistemas as S

GAB = json.loads(Path(__file__).parent.parent.joinpath("eval/gabarito.json").read_text(encoding="utf-8"))


def _texto(pdf: bytes) -> str:
    with fitz.open(stream=pdf, filetype="pdf") as d:
        return "\n".join(p.get_text() for p in d)


def test_he_plantada_nao_paga_e_he_paga_consistente():
    for comp in ["2024-09", "2024-10", "2024-11"]:
        p = S.ponto("0042", comp)
        assert p["dados"]["minutos_extras"] > 600, comp          # > 10h extras no mês
        assert not any("extra" in r["descricao"].lower() for r in S.holerite("0042", comp)["dados"]["rubricas"])
    pago = S.holerite("0042", D.MES_HE_PAGA)["dados"]["rubricas"]
    assert any("extra" in r["descricao"].lower() for r in pago)
    assert S.ponto("0042", "2024-03")["dados"]["minutos_extras"] == 0  # mês normal: nada


def test_lacunas_explicitas():
    assert S.ponto("0042", "2024-06")["status"] == "sem_registros"
    assert S.ocorrencias("0042")["status"] == "sem_registros"
    with pytest.raises(KeyError):
        S.ponto("9999", "2024-03")


def test_fgts_instavel_na_primeira_chamada():
    with pytest.raises(S.SistemaIndisponivel):
        S.extrato_fgts("0042", "proc_x")
    e = S.extrato_fgts("0042", "proc_x")["dados"]
    assert len(e["depositos"]) == len(D.competencias()) == 24


def test_trct_no_prazo():
    t = S.trct("0042")["dados"]
    assert t["data_pagamento"] <= t["prazo_legal"]


def test_pdfs_tem_texto_citavel():
    assert "PONTO" in _texto(S.ponto("0042", "2024-09")["pdf"]).upper()
    assert "art. 477" in _texto(S.trct("0042")["pdf"])
    assert "NEUTRALIZADA" in _texto(S.laudo_ltcat()["pdf"])
    txt = _texto(inicial.gerar_pdf())
    for ped in GAB["pedidos"]:
        assert any(w.lower() in txt.lower() for w in ped["palavras"]), ped["id"]
