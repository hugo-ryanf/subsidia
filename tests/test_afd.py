"""Conector AFD: lê os dois layouts, filtra por empregado, aponta batida ímpar. Offline."""
import os, tempfile
from pathlib import Path

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "teste.db")

from app import db
from app.agentes import cruzamento, ferramentas as F
from app.camada import ingestao
from app.conectores import afd
from app.rh_mock import dados as D, sistemas as S


def _proc(pid):
    db.iniciar()
    db.executar("INSERT OR IGNORE INTO processos(id,nome,criado_em) VALUES(?,?,?)", (pid, "t", db.agora()))


def test_le_layout_671_e_filtra_empregado():
    r = afd.ler(afd.gerar_exemplo())
    assert r.layout == "Portaria 671/2021" and r.cnpj == "12345678000190"
    assert len(r.marcacoes) == 3 and not r.linhas_nao_lidas            # reclamante + 2 colegas


def test_le_layout_1510():
    r = afd.ler(afd.gerar_exemplo_1510())
    assert r.layout == "Portaria 1510/2009" and len(r.marcacoes) == 1


def test_linha_estranha_nao_some():
    r = afd.ler(afd.gerar_exemplo_1510() + b"lixo sem nsr\r\n0000000993xx\r\n")
    assert len(r.linhas_nao_lidas) == 2


def test_ponto_do_afd_bate_com_o_sistema_e_aponta_impar():
    _proc("pa")
    res = afd.importar("pa", "AFD.txt", afd.gerar_exemplo())
    assert res["empregados"] == 3 and res["dias_com_batida_impar"] == 1 and res["crc_validado"] is False
    cpf = D.FUNCIONARIO["cpf"]
    assert afd.ponto("pa", cpf, "2024-06")["status"] == "sem_registros"       # lacuna preservada
    for comp in ("2024-09", "2023-12"):
        assert afd.ponto("pa", cpf, comp)["dados"]["minutos_extras"] == S.ponto("0042", comp)["dados"]["minutos_extras"]
    mar = afd.ponto("pa", cpf, "2024-03")
    assert mar["dados"]["dias_batida_impar"] == [afd.DIA_BATIDA_FALTANDO] and mar["pdf"][:4] == b"%PDF"


def test_agente_usa_o_afd_quando_importado(monkeypatch):
    _proc("pb")
    afd.importar("pb", "AFD.txt", afd.gerar_exemplo())
    monkeypatch.setattr(ingestao, "ingerir_bytes", lambda pid, nome, *a: {"documento_id": f"doc_{nome}"})
    caixa = F.Caixa("pb", "0042", S.competencias_contrato("0042"))
    obs = F.obter_ponto(caixa, "todas")
    assert "fonte: AFD importado" in obs and afd.DIA_BATIDA_FALTANDO in obs and "2024-06" in obs
    achados = cruzamento.cruzar(caixa, [{"id": "he", "titulo": "Horas extras", "arquetipo": "jornada"}])
    assert any("Batida faltando" in a["titulo"] for a in achados)
    assert any(p["titulo"].startswith("Batida faltando") for p in caixa.pendencias)
