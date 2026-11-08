"""Caso pronto: cada clique gera uma cópia independente e íntegra do snapshot. Offline."""
import os, tempfile
from pathlib import Path

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "teste.db")

from fastapi.testclient import TestClient

from app.main import app


def test_clones_independentes_e_integros():
    with TestClient(app) as c:
        a = c.post("/demo/pronto").json()["processo_id"]
        b = c.post("/demo/pronto").json()["processo_id"]
        assert a != b
        pa = c.get(f"/processos/{a}").json()
        docs = {d["id"] for d in pa["documentos"]}
        assert len(docs) >= 50
        art = pa["artefatos"]
        assert art["triagem"]["aprovado"] and art["subsidios"]["aprovado"] and not art["estrategia"]["aprovado"]
        evid = {e["documento_id"] for x in art["subsidios"]["conteudo"]["achados"] for e in x["evidencias"]}
        cits = {f["documento_id"] for s in art["estrategia"]["conteudo"]["secoes"] for f in s["citacoes"]}
        assert evid and evid <= docs and cits and cits <= docs     # tudo aponta para o PRÓPRIO clone
        doc = next(iter(cits))
        r = c.get(f"/processos/{a}/documentos/{doc}/arquivo")
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        assert c.get(f"/processos/{a}/rastro").json()["totais"]["chamadas_modelo"] > 20
        assert "caso pronto" in pa["nome"]
        # o que um jurado faz num clone não aparece no outro
        pend = next(p for p in pa["pendencias"] if p["status"] == "aberta")
        assert c.post(f"/processos/{a}/pendencias/{pend['id']}",
                      json={"status": "resolvida", "resolucao": "teste"}).status_code == 200
        pb = c.get(f"/processos/{b}").json()
        assert all(p["status"] == "aberta" for p in pb["pendencias"])
        assert not ({d["id"] for d in pb["documentos"]} & docs)
