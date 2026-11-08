"""E2E da triagem contra a Featherless: o caso demo deve render os 6 pedidos do gabarito."""
import json, os, tempfile
from pathlib import Path

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "teste.db")

from fastapi.testclient import TestClient

from app.main import app
from tests.e2e_util import esperar

GAB = json.loads(Path(__file__).parent.parent.joinpath("eval/gabarito.json").read_text(encoding="utf-8"))


def test_triagem_caso_demo():
    with TestClient(app) as c:
        r = c.post("/demo/processo").json()
        assert esperar(c, r["job_id"])["status"] == "concluido"
        pid = r["processo_id"]
        j = esperar(c, c.post(f"/processos/{pid}/triagem").json()["job_id"])
        assert j["status"] == "concluido", j
        t = c.get(f"/processos/{pid}").json()["artefatos"]["triagem"]["conteudo"]
        print("\nPROCESSO:", json.dumps(t["processo"], ensure_ascii=False)[:400])
        for p in t["pedidos"]:
            print(f"- {p['id']:<16} {p['arquetipo']:<18} R$ {p['valor']} conf={p['confianca']} "
                  f"fontes={[f['ref'] for f in p['fontes']]} rev={p['motivos_revisao']}")
        achados = 0
        for g in GAB["pedidos"]:
            hit = [p for p in t["pedidos"] if any(w in (p["titulo"] or "").lower() for w in g["palavras"])]
            if hit and abs((hit[0]["valor"] or 0) - g["valor"]) < 1 and hit[0]["arquetipo"] == g["arquetipo"]:
                achados += 1
            else:
                print("NAO BATEU:", g["id"], [(p["titulo"], p["valor"], p["arquetipo"]) for p in hit])
        print("ACERTOS:", achados, "/", len(GAB["pedidos"]))
        print("RASTRO:", c.get(f"/processos/{pid}/rastro").json()["totais"])
        assert achados >= 5
