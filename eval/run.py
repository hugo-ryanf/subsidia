"""Eval ponta a ponta contra o gabarito do caso sintético (Featherless real).

Roda: ingestão → triagem → (aprovação) → subsídios → (aprovação) → estratégia, e mede:
recall de pedidos, problemas plantados detectados, citações válidas, custo e tempo.
Uso:  python -m eval.run        (grava eval/resultado.json)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("DB_PATH", str(Path(tempfile.mkdtemp()) / "eval.db"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

RAIZ = Path(__file__).resolve().parent
GAB = json.loads((RAIZ / "gabarito.json").read_text(encoding="utf-8"))


def esperar(c, jid, limite=900):
    for _ in range(limite):
        j = c.get(f"/jobs/{jid}").json()
        if j["status"] in ("concluido", "erro"):
            return j
        time.sleep(1)
    raise TimeoutError(jid)


def _pedido_do_gabarito(g, pedidos):
    for p in pedidos:
        if any(w in (p["titulo"] or "").lower() for w in g["palavras"]):
            return p
    return None


def main() -> int:
    t0 = time.time()
    rel: dict = {"checagens": []}

    def check(nome, ok, detalhe=""):
        rel["checagens"].append({"nome": nome, "ok": bool(ok), "detalhe": detalhe})
        print(f"[{'OK ' if ok else 'FALHA'}] {nome} {detalhe}")

    with TestClient(app) as c:
        r = c.post("/demo/processo").json()
        pid = r["processo_id"]
        check("ingestão da inicial", esperar(c, r["job_id"])["status"] == "concluido")
        j = esperar(c, c.post(f"/processos/{pid}/triagem").json()["job_id"])
        check("triagem concluída", j["status"] == "concluido", j.get("erro") or "")
        tri = c.get(f"/processos/{pid}").json()["artefatos"]["triagem"]["conteudo"]
        acertos = 0
        for g in GAB["pedidos"]:
            p = _pedido_do_gabarito(g, tri["pedidos"])
            ok = bool(p) and abs((p["valor"] or 0) - g["valor"]) < 1 and p["arquetipo"] == g["arquetipo"] \
                and bool(p["fontes"])
            acertos += ok
        check("pedidos extraídos (valor+categoria+citação)", acertos == len(GAB["pedidos"]),
              f"{acertos}/{len(GAB['pedidos'])}")
        rel["recall_pedidos"] = acertos / len(GAB["pedidos"])
        c.post(f"/processos/{pid}/aprovar/triagem", json={"observacao": "eval"})

        j = esperar(c, c.post(f"/processos/{pid}/subsidios").json()["job_id"])
        check("coleta de subsídios concluída", j["status"] == "concluido", j.get("erro") or "")
        sub = c.get(f"/processos/{pid}").json()["artefatos"]["subsidios"]["conteudo"]
        achados, pends = sub["achados"], sub["pendencias"]
        esperados = 0
        for g in GAB["pedidos"]:
            p = _pedido_do_gabarito(g, tri["pedidos"])
            pid_ped = p["id"] if p else None
            meus = [a for a in achados if a["pedido_id"] == pid_ped]
            exp = g["esperado"]
            if exp["tipo"] == "divergencia":
                ok = any(a["tipo"] == "divergencia" for a in meus)
            elif exp["tipo"] == "favoravel":
                ok = any(a["tipo"] == "favoravel" for a in meus) and not any(a["tipo"] == "divergencia" for a in meus)
            else:
                comps = exp.get("competencias") or []
                ok = any(a["tipo"] == "pendencia" for a in meus) and \
                    all(any(cpt in pd["titulo"] for pd in pends) for cpt in comps)
            esperados += ok
            check(f"  achado esperado: {g['id']} → {exp['tipo']}", ok,
                  "; ".join(f"{a['tipo']}: {a['titulo']}" for a in meus)[:160])
        rel["recall_achados"] = esperados / len(GAB["pedidos"])
        check("loops de coleta concluídos", all(col["concluido"] for col in sub["coletas"]),
              str([col["pedido_id"] for col in sub["coletas"] if not col["concluido"]]))
        c.post(f"/processos/{pid}/aprovar/subsidios", json={"observacao": "eval"})

        j = esperar(c, c.post(f"/processos/{pid}/estrategia").json()["job_id"])
        check("estratégia concluída", j["status"] == "concluido", j.get("erro") or "")
        est = c.get(f"/processos/{pid}").json()["artefatos"]["estrategia"]["conteudo"]
        com_cit = sum(bool(s["citacoes"]) for s in est["secoes"])
        check("seções da estratégia com citação válida", com_cit == len(est["secoes"]), f"{com_cit}/{len(est['secoes'])}")
        riscos = {s["pedido_id"]: s["risco"] for s in est["secoes"]}
        he = _pedido_do_gabarito(GAB["pedidos"][0], tri["pedidos"])
        check("horas extras classificadas como risco alto", he and riscos.get(he["id"]) == "alto", str(riscos))
        tot = c.get(f"/processos/{pid}/rastro").json()["totais"]

    rel.update({
        "processo_id": pid, "segundos_total": round(time.time() - t0, 1), "custo_usd": tot["custo_usd"],
        "chamadas_modelo": tot["chamadas_modelo"], "ferramentas": tot["ferramentas"],
        "tokens": tot["tokens_entrada"] + tot["tokens_saida"],
        "documentos_coletados": sub["resumo"]["documentos_coletados"],
        "minutos_manual_estimados": sub["resumo"]["minutos_manual_estimados"],
        "exposicao_estimada": sub["resumo"]["exposicao_estimada"],
        "aprovado": all(x["ok"] for x in rel["checagens"]),
    })
    (RAIZ / "resultado.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in rel.items() if k != "checagens"}, ensure_ascii=False, indent=2))
    print("\nSÍNTESE:", est["sintese"])
    print("\n--- seção de maior risco ---\n", est["secoes"][0]["markdown"][:1800])
    return 0 if rel["aprovado"] else 1


if __name__ == "__main__":
    sys.exit(main())
