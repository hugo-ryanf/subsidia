"""Chunking com overlap que atravessa a fronteira de página.

Páginas viram um fluxo único fatiado em janelas sobrepostas, para não cortar cláusula na
quebra de página. Cada chunk guarda a faixa de páginas (citação) e herda `requer_revisao`
de qualquer página coberta — a incerteza se propaga, não se perde (regra #4).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.camada.extracao import PaginaExtraida
from app.config import cfg


@dataclass
class Chunk:
    ordem: int
    texto: str
    pagina_inicio: int
    pagina_fim: int
    requer_revisao: bool
    motivo: str | None


def gerar(paginas: list[PaginaExtraida]) -> list[Chunk]:
    partes, intervalos, pos = [], [], 0
    for i, p in enumerate(paginas):
        if i:
            partes.append("\n")
            pos += 1
        partes.append(p.texto)
        intervalos.append((pos, pos + len(p.texto), p))
        pos += len(p.texto)
    full = "".join(partes)
    if not full.strip():
        return []

    tamanho = cfg.chunk_chars
    chunks: list[Chunk] = []
    i = 0
    while i < len(full):
        fim = min(i + tamanho, len(full))
        # Recua até um espaço para não cortar palavra (se houver um por perto).
        if fim < len(full):
            corte = full.rfind(" ", i + tamanho // 2, fim)
            fim = corte if corte > 0 else fim
        cobertas = [p for ini, f, p in intervalos if ini < fim and f > i] or \
                   [min(intervalos, key=lambda t: abs(t[0] - i))[2]]
        motivos = [f"p. {p.numero}: {p.motivo}" for p in cobertas if p.requer_revisao]
        texto = full[i:fim].strip()
        if texto:
            chunks.append(Chunk(len(chunks), texto, min(p.numero for p in cobertas),
                                max(p.numero for p in cobertas), bool(motivos),
                                "; ".join(motivos) or None))
        if fim >= len(full):
            break
        # A próxima janela começa `overlap` antes do fim real desta (que pode ter recuado
        # até um espaço) — garante sobreposição e sempre avança.
        i = max(i + 1, fim - cfg.chunk_overlap)
    return chunks
