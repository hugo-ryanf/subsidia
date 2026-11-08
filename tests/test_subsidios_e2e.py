"""E2E do worker de subsídios contra a Featherless: precisa achar os problemas plantados."""
import json, os, tempfile
from pathlib import Path

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "teste.db")

from fastapi.testclient import TestClient

from app.main import app
from tests.e2e_util import esperar


def test_subsidios_caso_demo():
    with TestClient(app) as c:
        r = c.post("/demo/processo").json()
        pid = r["processo_id"]
        assert esperar(c, r["job_id"])["status"] == "concluido"
        assert esperar(c, c.post(f"/processos/{pid}/triagem").json()["job_id"])["status"] == "concluido"
        # sem aprovação humana, o worker não roda (portão)
        assert esperar(c, c.post(f"/processos/{pid}/subsidios").json()["job_id"])["status"] == "erro"
        c.post(f"/processos/{pid}/aprovar/triagem", json={})
        j = esperar(c, c.post(f"/processos/{pid}/subsidios").json()["job_id"])
        assert j["status"] == "concluido", j
        s = c.get(f"/processos/{pid}").json()["artefatos"]["subsidios"]["conteudo"]
        print("\nRESUMO:", s["resumo"])
        for col in s["coletas"]:
            print(f"- {col['pedido_id']}: concluido={col['concluido']} passos=" +
                  " > ".join(f"{p['acao']}{json.dumps(p['args'], ensure_ascii=False)[:40]}" for p in col["passos"]))
        for a in s["achados"]:
            print(f"  [{a['tipo']:<11}] {a['pedido_id'][:20]:<20} {a['titulo']}")
        for p in s["pendencias"]:
            print(f"  PEND [{p['origem']}] {p['pedido_id']}: {p['titulo']}")
        print("RASTRO:", c.get(f"/processos/{pid}/rastro").json()["totais"])
        tit = " | ".join(a["titulo"] for a in s["achados"])
        assert any(a["tipo"] == "divergencia" and "NÃO pagas" in a["titulo"] for a in s["achados"]), tit
        assert any("2024-06" in p["titulo"] for p in s["pendencias"])
        assert any("art. 477" in a["titulo"] and a["tipo"] == "favoravel" for a in s["achados"]), tit
        assert any("FGTS" in a["titulo"] and a["tipo"] == "favoravel" for a in s["achados"]), tit
        assert any("EPI" in a["titulo"] and a["tipo"] == "favoravel" for a in s["achados"]), tit
        assert any("Dano moral" in p["titulo"] for p in s["pendencias"])
