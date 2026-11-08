"""Gera o snapshot do "caso pronto" (roda o fluxo inteiro de verdade, contra a Featherless).

Uso:  python -m seed.gerar_caso_pronto
Saída: seed/snapshot/subsidia.db + seed/snapshot/arquivos/ (vai para o repositório e a imagem).
Triagem e subsídios ficam aprovados; a estratégia fica aguardando aprovação (portão humano).
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

DESTINO = Path(__file__).resolve().parent / "snapshot"
shutil.rmtree(DESTINO, ignore_errors=True)
DESTINO.mkdir(parents=True)
# Gera num diretório temporário: no Windows as conexões das threads de job seguram o arquivo.
TEMP = Path(tempfile.mkdtemp(prefix="caso_pronto_"))
os.environ["DB_PATH"] = str(TEMP / "subsidia.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def esperar(c, jid):
    while True:
        j = c.get(f"/jobs/{jid}").json()
        if j["status"] in ("concluido", "erro"):
            if j["status"] == "erro":
                sys.exit(f"falhou: {j['tipo']}: {j['erro']}")
            return j
        time.sleep(1)


def main() -> None:
    with TestClient(app) as c:
        r = c.post("/demo/processo").json()
        pid = r["processo_id"]
        esperar(c, r["job_id"])
        esperar(c, c.post(f"/processos/{pid}/triagem").json()["job_id"])
        c.post(f"/processos/{pid}/aprovar/triagem", json={"observacao": "revisado pelo advogado"})
        esperar(c, c.post(f"/processos/{pid}/subsidios").json()["job_id"])
        c.post(f"/processos/{pid}/aprovar/subsidios", json={"observacao": "revisado pelo advogado"})
        esperar(c, c.post(f"/processos/{pid}/estrategia").json()["job_id"])
        est = c.get(f"/processos/{pid}").json()["artefatos"]["estrategia"]["conteudo"]
        assert all(s["citacoes"] for s in est["secoes"]), "estratégia com seção sem citação"
    src = sqlite3.connect(TEMP / "subsidia.db")
    dst = sqlite3.connect(DESTINO / "subsidia.db")
    src.backup(dst)
    dst.execute("PRAGMA journal_mode=DELETE")
    dst.execute("VACUUM")
    dst.close()
    src.close()
    shutil.copytree(TEMP / "arquivos", DESTINO / "arquivos")
    tam = sum(f.stat().st_size for f in DESTINO.rglob("*") if f.is_file())
    print(f"snapshot pronto: processo {pid}, {tam / 1e6:.1f} MB em {DESTINO}")


if __name__ == "__main__":
    main()
