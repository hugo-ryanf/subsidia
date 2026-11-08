"""Agente de Triagem: lê a inicial e separa CADA pedido, com valor, categoria, citação e
confiança. É a base que o humano aprova antes do worker sair buscando subsídios.

Recortada no que o processo trabalhista precisa.
"""
from __future__ import annotations

from app import db, llm, rastro
from app.agentes import catalogo, fontes

LIMIAR_CONFIANCA = 0.6
LIMITE_CHARS_POR_BLOCO = 60000  # tamanho de cada chamada ao modelo; autos maiores são lidos em vários blocos

SYSTEM = """Você é um advogado trabalhista sênior da DEFESA (empresa reclamada) fazendo a triagem
de uma reclamação trabalhista. Trabalhe SÓ com os trechos fornecidos, que vêm rotulados [D1], [D2]...
Nunca invente fato, valor, data ou nome. Se algo não estiver nos trechos, use null.
Responda SOMENTE um objeto JSON."""

USER = """TRECHOS DOS AUTOS:
{trechos}

CATEGORIAS POSSÍVEIS (campo "arquetipo"):
{menu}
{nota_bloco}
Extraia em JSON:
{{
  "processo": {{
    "numero": str|null, "vara": str|null, "reclamante": str|null, "cpf_reclamante": str|null,
    "reclamada": str|null, "cargo": str|null, "admissao": "AAAA-MM-DD"|null,
    "demissao": "AAAA-MM-DD"|null, "salario": number|null, "valor_causa": number|null,
    "fontes": ["D1", ...]
  }},
  "pedidos": [
    {{
      "id": "slug_curto_sem_acento",
      "titulo": "nome do pedido",
      "valor": number|null,
      "alegacao": "o que o reclamante alega para sustentar o pedido (fatos concretos: horários, datas, pessoas)",
      "periodo_alegado": "período a que o pedido se refere, se houver"|null,
      "arquetipo": "uma das categorias",
      "fontes": ["D2", ...],
      "confianca": 0.0-1.0
    }}
  ]
}}
Regras: um item por pedido da lista final de pedidos (normalmente "DOS PEDIDOS"), cruzando com a
fundamentação para preencher "alegacao". Cite em "fontes" os trechos de onde tirou o pedido E a
alegação. "confianca" baixa quando o pedido é ambíguo ou o valor não está claro."""


NOTA_BLOCO = """
ATENÇÃO: autos longos, lidos em partes. Este é o bloco {i} de {n}; os demais são analisados à parte.
Liste os pedidos que aparecerem NESTE bloco, na lista final ou na fundamentação. Campo que não estiver
aqui fica null. Se o bloco não tiver nenhum pedido, devolva "pedidos": [].
"""


def _mesmo_pedido(a: dict, b: dict) -> bool:
    if a.get("id") and a.get("id") == b.get("id"):
        return True
    titulo = catalogo._norm(a.get("titulo") or "").strip()
    return bool(titulo) and titulo == catalogo._norm(b.get("titulo") or "").strip()


def _consolidar(parciais: list[dict]) -> dict:
    """Junta as respostas dos blocos: o primeiro valor conhecido fica, as citações se somam."""
    proc: dict = {"fontes": []}
    pedidos: list[dict] = []
    for d in parciais:
        for k, v in (d.get("processo") or {}).items():
            if k == "fontes":
                proc["fontes"] += v or []
            elif proc.get(k) is None:
                proc[k] = v
        for p in d.get("pedidos") or []:
            igual = next((e for e in pedidos if _mesmo_pedido(e, p)), None)
            if igual is None:
                pedidos.append({**p, "fontes": list(p.get("fontes") or [])})
                continue
            confianca = min(float(igual.get("confianca") or 0), float(p.get("confianca") or 0))
            for k, v in p.items():
                if igual.get(k) is None:
                    igual[k] = v
            igual["fontes"] += p.get("fontes") or []
            igual["confianca"] = confianca
    return {"processo": proc, "pedidos": pedidos}


def _extrair(processo_id: str) -> tuple[dict, dict, int]:
    """Lê todos os autos, em quantos blocos forem precisos. Devolve (dados, refs, nº de blocos)."""
    chunks = fontes.chunks_do_processo(processo_id, classe="autos")
    if not chunks:
        raise ValueError("o processo não tem autos ingeridos — envie a petição inicial primeiro")
    blocos = fontes.em_blocos(chunks, LIMITE_CHARS_POR_BLOCO)
    n = len(blocos)
    refs: dict = {}
    parciais = []
    for i, bloco in enumerate(blocos, 1):
        texto, novas = fontes.rotular(bloco, inicio=len(refs))
        refs |= novas
        parciais.append(llm.chat_json(
            SYSTEM, USER.format(trechos=texto, menu=catalogo.menu_para_prompt(),
                                nota_bloco=NOTA_BLOCO.format(i=i, n=n) if n > 1 else ""),
            pesado=True, max_tokens=8000, etiqueta="triagem:pedidos" + (f" (bloco {i}/{n})" if n > 1 else "")))
    return (parciais[0] if n == 1 else _consolidar(parciais)), refs, n


def executar(processo_id: str, job_id: str | None = None) -> dict:
    dados, refs, n_blocos = _extrair(processo_id)

    pedidos = []
    for p in dados.get("pedidos") or []:
        citadas, invalidas = fontes.validar(p.get("fontes") or [], refs)
        motivos = []
        arq = p.get("arquetipo")
        por_gatilho = catalogo.arquetipo_por_gatilho(f"{p.get('titulo', '')} {p.get('alegacao', '')}")
        if arq not in catalogo.ARQUETIPOS:
            motivos.append(f"categoria '{arq}' desconhecida; usada a do catálogo ({por_gatilho})")
            arq = por_gatilho
        if not citadas:
            motivos.append("pedido sem citação válida nos autos")
        if invalidas:
            motivos.append(f"citações inexistentes descartadas: {', '.join(invalidas)}")
        conf = float(p.get("confianca") or 0)
        if invalidas or not citadas:
            conf = min(conf, 0.4)
        if conf < LIMIAR_CONFIANCA:
            motivos.append(f"confiança baixa ({conf:.2f})")
        if n_blocos > 1:
            motivos.append("autos lidos em partes: conferir se este pedido não está repetido com outro nome")
        pedidos.append({
            "id": p.get("id") or f"pedido_{len(pedidos) + 1}",
            "titulo": p.get("titulo"), "valor": p.get("valor"), "alegacao": p.get("alegacao"),
            "periodo_alegado": p.get("periodo_alegado"), "arquetipo": arq,
            "arquetipo_nome": catalogo.ARQUETIPOS.get(arq, {}).get("nome"),
            "fontes": citadas, "confianca": round(conf, 2),
            "requer_revisao": bool(motivos), "motivos_revisao": motivos,
        })

    proc = dados.get("processo") or {}
    proc_fontes, _ = fontes.validar(proc.get("fontes") or [], refs)
    proc["fontes"] = proc_fontes
    resultado = {"processo": proc, "pedidos": pedidos,
                 "total_pedidos": len(pedidos),
                 "valor_total_pedidos": round(sum(p["valor"] or 0 for p in pedidos), 2),
                 "requer_revisao": sum(p["requer_revisao"] for p in pedidos)}
    avisos = []
    if n_blocos > 1:
        avisos.append(f"Autos longos: lidos por inteiro em {n_blocos} blocos. Confira se há pedido repetido "
                      "com outro nome e se o valor e a alegação de cada um estão completos.")
    if not pedidos:
        avisos.append("Nenhum pedido identificado — revisar a inicial manualmente.")
    if avisos:
        resultado["aviso"] = " ".join(avisos)
    db.salvar_artefato(processo_id, "triagem", resultado, aprovado=False)
    rastro.registrar("decisao", "triagem:concluida",
                     {"pedidos": len(pedidos), "requer_revisao": resultado["requer_revisao"], "blocos": n_blocos})
    return {"pedidos": len(pedidos), "requer_revisao": resultado["requer_revisao"]}
