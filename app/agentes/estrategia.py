"""Agente de Estratégia: memorando de defesa POR PEDIDO, com risco e prova citada.

Estratégia por pedido com disciplina factual, e uma regra importante:
o RISCO não é opinião do modelo — sai dos achados determinísticos do cruzamento. O LLM
argumenta e explica; a régua de risco é auditável. Citação inválida é marcada, nunca aceita.
"""
from __future__ import annotations

import contextvars
import re
from concurrent.futures import ThreadPoolExecutor

from app import db, llm, rastro
from app.agentes import fontes

CONCORRENCIA = 4
_ORDEM_RISCO = {"baixo": 0, "medio": 1, "alto": 2}

SYSTEM = """Você é advogado(a) trabalhista sênior da DEFESA da empresa reclamada. Escreva o trecho do
memorando estratégico de UM pedido. Use SOMENTE os trechos rotulados [D1], [D2]... e os achados
fornecidos. Toda afirmação de fato termina com a citação entre colchetes, ex.: [D3]. Não invente
documento, data, valor, jurisprudência ou fato. Se a prova é desfavorável, diga com franqueza:
o advogado precisa saber onde a empresa perde. Português jurídico claro e direto."""

USER = """PEDIDO: {titulo} — valor pleiteado R$ {valor}
ALEGAÇÃO: {alegacao}

ACHADOS DO CRUZAMENTO (calculados pelo sistema, confiáveis):
{achados}

RISCO CALCULADO: {risco}

TRECHOS (autos e documentos coletados nos sistemas da empresa):
{trechos}

Escreva em markdown, exatamente com estas seções (sem título de pedido):
**Tese de defesa** — 2 a 4 frases.
**Prova a favor** — bullets com citação [D#]. Se não houver, diga.
**Pontos fracos** — bullets com citação [D#]. Se não houver, diga.
**Recomendação** — 1 a 2 frases (ex.: contestar integralmente, contestar e avaliar acordo neste pedido,
produzir prova testemunhal). A decisão final é do advogado."""


def _risco(achados: list[dict]) -> str:
    if any(a["tipo"] == "divergencia" and a["severidade"] == "alta" for a in achados):
        return "alto"
    if any(a["tipo"] in ("divergencia", "pendencia", "cobertura") for a in achados):
        return "medio"
    return "baixo"


def _fmt_achados(achados: list[dict], label_doc: dict[str, list[str]]) -> str:
    linhas = []
    for a in achados:
        refs = sorted({r for e in a["evidencias"] for r in label_doc.get(e["documento_id"], [])[:1]})
        linhas.append(f"- [{a['tipo'].upper()}] {a['titulo']}: {a['detalhe']}"
                      + (f" (evidência: {', '.join(refs)})" if refs else ""))
    return "\n".join(linhas) or "- (nenhum achado — pedido sem documento nos sistemas)"


def _contexto(processo_id: str, pedido: dict, achados: list[dict]) -> tuple[str, dict, dict]:
    chunks: list[dict] = []
    vistos: set[str] = set()
    for f in pedido.get("fontes") or []:          # trechos da inicial que sustentam o pedido
        for c in fontes.chunks_do_processo(processo_id, documento_id=f["documento_id"]):
            if c["id"] == f["chunk_id"] and c["id"] not in vistos:
                chunks.append(c)
                vistos.add(c["id"])
    docs_evid: list[str] = []
    for a in achados:
        for e in a["evidencias"]:
            if e["documento_id"] not in docs_evid:
                docs_evid.append(e["documento_id"])
    for doc_id in docs_evid[:8]:                   # documentos coletados que embasam os achados
        for c in fontes.chunks_do_processo(processo_id, documento_id=doc_id)[:2]:
            if c["id"] not in vistos:
                chunks.append(c)
                vistos.add(c["id"])
    texto, refs = fontes.rotular(chunks, limite_chars=30000)
    label_doc: dict[str, list[str]] = {}
    for rot, r in refs.items():
        label_doc.setdefault(r["documento_id"], []).append(rot)
    return texto, refs, label_doc


def _validar_citacoes(md: str, refs: dict) -> tuple[str, list[str], list[dict]]:
    usadas = fontes.refs_no_texto(md)
    invalidas = [r for r in usadas if r not in refs]
    for r in invalidas:
        md = re.sub(rf"\[{r}\]", "[fonte não verificada]", md)
    citacoes = [{"ref": r, **refs[r]} for r in usadas if r in refs]
    return md, invalidas, citacoes


def _pedido(processo_id: str, pedido: dict, achados: list[dict]) -> dict:
    risco = _risco(achados)
    texto, refs, label_doc = _contexto(processo_id, pedido, achados)
    md = llm.chat(SYSTEM, USER.format(titulo=pedido["titulo"], valor=pedido.get("valor"),
                                      alegacao=pedido.get("alegacao"), achados=_fmt_achados(achados, label_doc),
                                      risco=risco.upper(), trechos=texto),
                  pesado=True, max_tokens=6000, etiqueta=f"estrategia:{pedido['id']}")
    md, invalidas, citacoes = _validar_citacoes(md, refs)
    motivos = []
    if invalidas:
        motivos.append(f"citações inexistentes removidas: {', '.join(invalidas)}")
    if not citacoes:
        motivos.append("texto sem nenhuma citação válida")
    return {"pedido_id": pedido["id"], "titulo": pedido["titulo"], "valor": pedido.get("valor"),
            "risco": risco, "exposicao_estimada": round(sum(a["exposicao_estimada"] or 0 for a in achados), 2) or None,
            "markdown": md, "citacoes": citacoes, "requer_revisao": bool(motivos), "motivos_revisao": motivos}


def executar(processo_id: str, job_id: str | None = None) -> dict:
    tri, sub = db.artefato(processo_id, "triagem"), db.artefato(processo_id, "subsidios")
    if not sub or sub["conteudo"].get("bloqueado"):
        raise ValueError("rode a coleta de subsídios antes da estratégia")
    if not sub["aprovado"]:
        raise ValueError("os subsídios precisam ser aprovados por um humano antes da estratégia")
    pedidos = tri["conteudo"]["pedidos"]
    achados = sub["conteudo"]["achados"]

    def um(p):
        try:
            return _pedido(processo_id, p, [a for a in achados if a["pedido_id"] == p["id"]])
        except llm.LLMError as e:  # um pedido falhar não derruba o memorando; fica marcado
            return {"pedido_id": p["id"], "titulo": p["titulo"], "valor": p.get("valor"), "risco": "medio",
                    "exposicao_estimada": None, "markdown": f"_Falha ao gerar este pedido: {e}_",
                    "citacoes": [], "requer_revisao": True, "motivos_revisao": [str(e)]}

    with ThreadPoolExecutor(CONCORRENCIA) as pool:
        secoes = list(pool.map(lambda p: contextvars.copy_context().run(um, p), pedidos))

    total = round(sum(s["valor"] or 0 for s in secoes), 2)
    em_risco = round(sum(s["valor"] or 0 for s in secoes if s["risco"] == "alto"), 2)
    tabela = "\n".join(f"- {s['titulo']}: R$ {s['valor'] or 0:,.2f} — risco {s['risco']}" for s in secoes)
    pend = db.todos("SELECT titulo FROM pendencias WHERE processo_id=? AND status='aberta'", (processo_id,))
    try:
        sintese = llm.chat(
            "Você é advogado(a) trabalhista sênior da defesa. Escreva uma síntese executiva de 3 a 5 frases, "
            "sem inventar nada além do que foi dado. Termine lembrando que a decisão é do advogado.",
            f"Pedidos e risco calculado:\n{tabela}\n\nValor total pleiteado: R$ {total:,.2f}. "
            f"Valor em pedidos de risco alto: R$ {em_risco:,.2f}.\n"
            f"Pendências abertas: {'; '.join(p['titulo'] for p in pend) or 'nenhuma'}.",
            pesado=False, max_tokens=600, etiqueta="estrategia:sintese")
    except llm.LLMError as e:
        sintese = f"_Síntese indisponível: {e}_"

    resultado = {"sintese": sintese, "secoes": sorted(secoes, key=lambda s: -_ORDEM_RISCO[s["risco"]]),
                 "valor_total_pleiteado": total, "valor_em_risco_alto": em_risco,
                 "pendencias_abertas": len(pend),
                 "requer_revisao": sum(s["requer_revisao"] for s in secoes)}
    db.salvar_artefato(processo_id, "estrategia", resultado)
    rastro.registrar("decisao", "estrategia:concluida",
                     {"riscos": {s["pedido_id"]: s["risco"] for s in secoes}, "requer_revisao": resultado["requer_revisao"]})
    return {"secoes": len(secoes), "requer_revisao": resultado["requer_revisao"]}
