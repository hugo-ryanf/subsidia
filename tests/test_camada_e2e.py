"""E2E da camada contra a Featherless real: upload → job → busca escopada."""
import os, time, tempfile
from pathlib import Path

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "teste.db")

from fastapi.testclient import TestClient
from fpdf import FPDF

from app.main import app


def _pdf() -> bytes:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)
    pdf.add_page()
    pdf.multi_cell(0, 6, "RECLAMACAO TRABALHISTA. O reclamante laborava das 8h as 20h, de segunda a sabado, "
                         "sem intervalo intrajornada, e nunca recebeu horas extras. " * 8)
    pdf.add_page()  # pagina em branco: deve virar requer_revisao, nao sumir
    pdf.add_page()
    pdf.multi_cell(0, 6, "DOS PEDIDOS: a) horas extras com adicional de 50%; b) multa do art. 477 da CLT; "
                         "c) indenizacao por dano moral no valor de R$ 20.000,00. " * 4)
    return bytes(pdf.output())


def test_fluxo():
    with TestClient(app) as c:
        pa = c.post("/processos", json={"nome": "Teste A"}).json()["processo_id"]
        pb = c.post("/processos", json={"nome": "Teste B"}).json()["processo_id"]
        r = c.post(f"/processos/{pa}/documentos", files={"arquivo": ("inicial.pdf", _pdf(), "application/pdf")})
        assert r.status_code == 202
        jid = r.json()["job_id"]
        for _ in range(60):
            j = c.get(f"/jobs/{jid}").json()
            if j["status"] in ("concluido", "erro"):
                break
            time.sleep(1)
        assert j["status"] == "concluido", j
        assert j["resultado"]["paginas"] == 3
        assert j["resultado"]["paginas_requer_revisao"] == 1
        b = c.post(f"/processos/{pa}/buscar", json={"pergunta": "multa do artigo 477", "top_k": 3}).json()
        assert b["status"] == "ok" and b["resultados"], b
        top = b["resultados"][0]
        print("\nTOP:", top["documento"], "p.", top["pagina_inicio"], top["origem_busca"], top["texto"][:90])
        assert top["pagina_fim"] >= 3 and "477" in top["texto"]
        # Regra #3: outro processo não enxerga nada
        assert c.post(f"/processos/{pb}/buscar", json={"pergunta": "horas extras"}).json()["status"] == "no_results"
        t = c.get(f"/processos/{pa}/rastro").json()["totais"]
        print("RASTRO:", t)
        assert t["chamadas_modelo"] >= 2
        assert c.post(f"/processos/{pa}/documentos", files={"arquivo": ("x.txt", b"oi", "text/plain")}).status_code == 422
