"""Cruzamento DETERMINÍSTICO dos subsídios coletados — regras em Python, não LLM.

Conta não é tarefa para modelo de linguagem: aqui se compara ponto × holerite, prazo do
TRCT, competências do FGTS, cadência do EPI. Cada achado traz as evidências (documento
coletado) para o advogado conferir em segundos. O LLM depois só EXPLICA (estratégia).

Tipos: favoravel (prova a favor da empresa) · divergencia (prova contra / risco) ·
pendencia (falta algo; humano resolve) · cobertura (o agente não verificou tudo).
"""
from __future__ import annotations

from datetime import date

from app.agentes.ferramentas import Caixa, registrar_pendencia
from app.rh_mock.dados import DIVISOR


def _ev(caixa: Caixa, *chaves: str) -> list[dict]:
    return [caixa.documentos[k] | {"chave": k} for k in chaves if k in caixa.documentos]


def _achado(pedido: dict, tipo: str, titulo: str, detalhe: str, evidencias: list[dict],
            severidade: str = "media", exposicao: float | None = None) -> dict:
    return {"pedido_id": pedido["id"], "tipo": tipo, "severidade": severidade, "titulo": titulo,
            "detalhe": detalhe, "evidencias": evidencias, "exposicao_estimada": exposicao}


def _salario_hora(caixa: Caixa) -> float | None:
    f = caixa.dados.get("ficha_registro")
    return round(f["salario_base"] / DIVISOR, 4) if f else None


def _he_paga_min(h: dict) -> int:
    for r in h["rubricas"]:
        if "extra" in r["descricao"].lower():
            return int(round(float(r["ref"].rstrip("h")) * 60))
    return 0


def _jornada(caixa: Caixa, p: dict) -> list[dict]:
    out: list[dict] = []
    pontos = {k.split(":")[1]: v for k, v in caixa.dados.items() if k.startswith("ponto:")}
    hols = {k.split(":")[1]: v for k, v in caixa.dados.items() if k.startswith("holerite:")}
    if not pontos:
        return [_achado(p, "cobertura", "Ponto não consultado",
                        "O agente não trouxe espelhos de ponto para este pedido.", [], "alta")]
    sem_reg = sorted(c for c, v in pontos.items() if v is None)
    for c in sem_reg:
        titulo = f"Espelho de ponto de {c} ausente no sistema"
        registrar_pendencia(caixa, titulo, "Sem controle de jornada desta competência, presume-se verdadeira a "
                            "jornada alegada (Súmula 338 do TST). Localizar o espelho físico ou justificar.",
                            p["id"], "cruzamento")
        out.append(_achado(p, "pendencia", titulo, "Súmula 338 do TST: ausência injustificada dos controles "
                           "gera presunção da jornada da inicial nesse período.", [], "alta"))

    if p["arquetipo"] == "jornada" and "intervalo" in (p["id"] + (p.get("titulo") or "")).lower():
        dias = curtos = 0
        for c, v in pontos.items():
            for m in (v or {}).get("marcacoes", []):
                if m["saida_intervalo"]:
                    dias += 1
                    a, b = (int(x[:2]) * 60 + int(x[3:]) for x in (m["saida_intervalo"], m["retorno_intervalo"]))
                    curtos += (b - a) < 60
        evs = _ev(caixa, *[f"ponto:{c}" for c in sorted(pontos) if pontos[c]][:6])
        verificadas = sorted(c for c in pontos if pontos[c])
        cobertura = (f" Cobertura: {len(verificadas)} competências verificadas ({verificadas[0]} a {verificadas[-1]})"
                     + (f", exceto {', '.join(sem_reg)} (sem registro)" if sem_reg else "") + ".") if verificadas else ""
        if curtos:
            out.append(_achado(p, "divergencia", f"Intervalo inferior a 1h em {curtos} dia(s)",
                               f"De {dias} dias úteis com marcação, {curtos} têm intervalo < 60 min.{cobertura}",
                               evs, "media"))
        else:
            out.append(_achado(p, "favoravel", "Intervalo de 1h registrado em todos os dias",
                               f"{dias} dias úteis com intervalo ≥ 60 min marcado no ponto (a inicial alega 20 min)."
                               f"{cobertura}", evs, "alta"))
        return out

    sh = _salario_hora(caixa)
    nao_pagas, consistentes = [], []
    for c, v in sorted(pontos.items()):
        if not v or v["minutos_extras"] <= 60:
            continue
        h = hols.get(c)
        if h is None:
            out.append(_achado(p, "cobertura", f"Holerite de {c} não consultado",
                               "Há sobrejornada no ponto, mas o holerite do mês não foi trazido.", _ev(caixa, f"ponto:{c}")))
            continue
        pago = _he_paga_min(h)
        if v["minutos_extras"] - pago > 60:
            nao_pagas.append((c, v["minutos_extras"] - pago))
        else:
            consistentes.append(c)
    if nao_pagas:
        horas = sum(m for _, m in nao_pagas) / 60
        expo = round(horas * sh * 1.5, 2) if sh else None
        meses = ", ".join(f"{c} ({m / 60:.1f}h)" for c, m in nao_pagas)
        out.append(_achado(
            p, "divergencia", f"Horas extras registradas e NÃO pagas: {horas:.1f}h",
            f"O próprio ponto da empresa registra sobrejornada sem rubrica correspondente no holerite em: {meses}. "
            "Prova contra a defesa nesse período." + (f" Exposição estimada (principal, sem reflexos): R$ {expo:,.2f}."
                                                      if expo else ""),
            _ev(caixa, *[k for c, _ in nao_pagas for k in (f"ponto:{c}", f"holerite:{c}")]), "alta", expo))
    if consistentes:
        out.append(_achado(p, "favoravel", "Horas extras pagas corretamente quando prestadas",
                           f"Sobrejornada do ponto quitada no holerite em: {', '.join(consistentes)}.",
                           _ev(caixa, *[k for c in consistentes for k in (f"ponto:{c}", f"holerite:{c}")]), "media"))
    sabados_ate_12 = all(
        m["saida"] <= "12:15" for v in pontos.values() if v for m in v["marcacoes"]
        if date.fromisoformat(m["data"]).weekday() == 5)
    if sabados_ate_12:
        out.append(_achado(p, "favoravel", "Sábados encerrados às 12h no ponto",
                           "A inicial alega trabalho aos sábados até 14h; o ponto registra saída por volta das 12h.",
                           _ev(caixa, *[f"ponto:{c}" for c in sorted(pontos) if pontos[c]][:3]), "media"))
    faltando = [c for c in caixa.competencias if c not in pontos]
    if faltando:
        out.append(_achado(p, "cobertura", f"{len(faltando)} competência(s) não verificadas",
                           "O agente não consultou o ponto de: " + ", ".join(faltando), [], "media"))
    return out


def _rescisao(caixa: Caixa, p: dict) -> list[dict]:
    t = caixa.dados.get("trct")
    if not t:
        return [_achado(p, "cobertura", "TRCT não consultado", "", [], "alta")]
    if t["data_pagamento"] <= t["prazo_legal"]:
        return [_achado(p, "favoravel", "Rescisão paga dentro do prazo do art. 477",
                        f"Pagamento em {t['data_pagamento']} (prazo até {t['prazo_legal']}), comprovante "
                        f"{t['comprovante']['autenticacao']}. A inicial alega pagamento só em abril/2025.",
                        _ev(caixa, "trct"), "alta")]
    return [_achado(p, "divergencia", "Rescisão paga fora do prazo",
                    f"Pago em {t['data_pagamento']}, prazo era {t['prazo_legal']}.", _ev(caixa, "trct"), "alta",
                    caixa.dados.get("ficha_registro", {}).get("salario_base"))]


def _fgts(caixa: Caixa, p: dict) -> list[dict]:
    e = caixa.dados.get("fgts")
    if not e:
        return [_achado(p, "cobertura", "Extrato do FGTS não consultado", "", [], "alta")]
    deps = {d["competencia"] for d in e["depositos"]}
    faltam = [c for c in caixa.competencias if c not in deps]
    if faltam:
        return [_achado(p, "divergencia", f"FGTS sem depósito em {len(faltam)} competência(s)",
                        ", ".join(faltam), _ev(caixa, "fgts"), "alta")]
    return [_achado(p, "favoravel", "FGTS integral e multa de 40% recolhida",
                    f"{len(deps)}/{len(caixa.competencias)} competências depositadas; multa de 40% em "
                    f"{e['multa_40']['data']} ({e['multa_40']['guia']}).", _ev(caixa, "fgts"), "alta")]


def _sst(caixa: Caixa, p: dict) -> list[dict]:
    out = []
    epi, ltcat = caixa.dados.get("epi"), caixa.dados.get("ltcat")
    if epi:
        datas = sorted({date.fromisoformat(x["data"]) for x in epi["entregas"]})
        maior = max((b - a).days for a, b in zip(datas, datas[1:])) if len(datas) > 1 else 0
        sem_ca = [x for x in epi["entregas"] if not x.get("ca")]
        if sem_ca or maior > 200:
            out.append(_achado(p, "divergencia", "Falhas no fornecimento de EPI",
                               f"Maior intervalo entre entregas: {maior} dias; itens sem CA: {len(sem_ca)}.",
                               _ev(caixa, "epi"), "alta"))
        else:
            out.append(_achado(p, "favoravel", "EPI térmico fornecido com CA durante todo o contrato",
                               f"{len(datas)} entregas, intervalo máximo de {maior} dias, todos os itens com CA.",
                               _ev(caixa, "epi"), "alta"))
    else:
        out.append(_achado(p, "cobertura", "Ficha de EPI não consultada", "", [], "alta"))
    if ltcat:
        neutro = "neutraliz" in ltcat["conclusao"].lower()
        out.append(_achado(p, "favoravel" if neutro else "divergencia",
                           "LTCAT conclui que o EPI neutraliza o agente" if neutro else "LTCAT reconhece insalubridade",
                           ltcat["conclusao"], _ev(caixa, "ltcat"), "alta"))
    return out


def _assedio(caixa: Caixa, p: dict) -> list[dict]:
    if "ocorrencias" not in caixa.dados:
        return [_achado(p, "cobertura", "Ocorrências do RH não consultadas", "", [], "media")]
    if caixa.dados["ocorrencias"]:
        return [_achado(p, "pendencia", "Há ocorrências registradas — analisar",
                        f"{len(caixa.dados['ocorrencias'])} registro(s).", _ev(caixa, "ocorrencias"), "alta")]
    titulo = "Dano moral: sem prova documental — ouvir o gestor citado e indicar testemunhas"
    registrar_pendencia(caixa, titulo, "Nenhuma ocorrência/denúncia registrada no RH. A defesa depende de prova "
                        "oral: colher a versão do gestor citado na inicial e levantar testemunhas.", p["id"], "cruzamento")
    return [_achado(p, "pendencia", titulo, "A ausência de registro ajuda (não houve denúncia formal), mas não "
                    "basta: a prova será testemunhal.", _ev(caixa, "ficha_registro"), "media")]


REGRAS = {"jornada": _jornada, "validade_rescisao": _rescisao, "verbas_descontos": _fgts,
          "saude_acidente": _sst, "assedio": _assedio}


def cruzar(caixa: Caixa, pedidos: list[dict]) -> list[dict]:
    achados: list[dict] = []
    for p in pedidos:
        regra = REGRAS.get(p["arquetipo"])
        if regra is None:
            achados.append(_achado(p, "pendencia", "Sem regra de cruzamento para esta categoria",
                                   "Análise manual dos documentos coletados.", [], "media"))
            continue
        achados.extend(regra(caixa, p))
    return achados
