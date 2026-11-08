"""Extração página a página com PyMuPDF (texto nativo).

OCR fica fora do escopo do hackathon, mas a regra #4 continua: página sem texto
suficiente NÃO é descartada — entra marcada `requer_revisao` com o motivo.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

from app.config import cfg


@dataclass
class PaginaExtraida:
    numero: int
    texto: str
    confianca: float
    requer_revisao: bool
    motivo: str | None = None


def extrair(caminho: Path) -> list[PaginaExtraida]:
    paginas: list[PaginaExtraida] = []
    with fitz.open(caminho) as doc:
        for i, pag in enumerate(doc, start=1):
            texto = (pag.get_text("text") or "").strip()
            if len(texto) >= cfg.min_chars_pagina:
                paginas.append(PaginaExtraida(i, texto, 1.0, False))
            else:
                paginas.append(PaginaExtraida(
                    i, texto, 0.0, True,
                    "sem texto nativo (provável digitalização) — conferir a página no PDF",
                ))
    return paginas
