"""Sem modelo disponível, a coleta acontece pelo playbook (e fica registrado). Offline."""
import os, tempfile
from pathlib import Path

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "teste.db")

from app import db, llm
from app.agentes import ferramentas as F, subsidios
from app.camada import ingestao
from app.rh_mock import sistemas as S


def test_playbook_quando_modelo_falha(monkeypatch):
    db.iniciar()
    db.executar("INSERT INTO processos(id,nome,criado_em) VALUES('p1','t',?)", (db.agora(),))

    def falha(*a, **k):
        raise llm.LLMError("resposta vazia")
    monkeypatch.setattr(llm, "chat_json", falha)
    monkeypatch.setattr(ingestao, "ingerir_bytes", lambda pid, nome, *a: {"documento_id": f"doc_{nome}"})
    caixa = F.Caixa("p1", "0042", S.competencias_contrato("0042"))
    r = subsidios._loop_pedido(caixa, {"id": "dano_moral", "titulo": "Danos morais", "arquetipo": "assedio",
                                       "arquetipo_nome": "Assédio", "valor": 1, "alegacao": "x"})
    assert r["modo"] == "playbook" and r["concluido"]
    assert [p["acao"] for p in r["passos"]] == ["obter_ocorrencias"]
    assert "ocorrencias" in caixa.dados
