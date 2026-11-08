"""Cruzamento DETERMINÍSTICO dos subsídios coletados — regras em Python, não LLM.

Conta não é tarefa para modelo de linguagem: aqui se compara ponto × holerite, prazo do
TRCT, competências do FGTS, cadência do EPI. Cada achado traz as evidências (documento
coletado) para o advogado conferir em segundos. O LLM depois só EXPLICA (estratégia).

Tipos: favoravel (prova a favor da empresa) · divergencia (prova contra / risco) ·
pendencia (falta algo; humano resolve) · cobertura (o agente não verificou tudo).
"""
from __future__ import annotations

import re
from datetime import date

from app.agentes.ferramentas import Caixa, registrar_pendencia
from app.rh_mock.dados import DIVISOR

_SABADO_ATE = re.compile(r"s[áa]bados?\b[^.;]*?\b(?:at[ée]|[àa]s|a)\s+(?:[àa]s\s+)?(\d{1,2})\s*h", re.I)
_FRASE = re.compile(r"(?<=[.;!?])\s+(?=[A-ZÀ-Ý])")
_NEUTRALIZ = re.compile(r"neutraliz\w*", re.I)
_RESSALVA = (r"insuficiente\w*|parcial\w*|incomplet\w*|inexistente\w*|ineficaz\w*|inadequad\w*")
# Termo negativo em qualquer ponto ANTES da menção, na mesma frase.
_NEGA_ANTES = re.compile(
    rf"\b(?:n[ãa]o|nem|nunca|jamais|sem|nenhum\w*|incapaz\w*|imposs[íi]vel|invi[áa]vel|deix\w+ de|falh\w+|"
    rf"aus[êe]ncia|{_RESSALVA})\b", re.I)
# Depois da menção só vale o que nega a própria neutralização: "neutralização não foi comprovada"
# nega; "neutraliza o agente, não sendo devido o adicional" e "neutraliza e não é devido" não negam.
_NEGA_DEPOIS = re.compile(
    r"^(?:\s+(?!e\b)[\w-]+){0,4}?\s+(?:"
    r"n[ãa]o\s+(?:foi|foram|é|são|est[áa]|restou|ficou|houve|ocorre\w*|se\b|comprovad\w*|demonstrad\w*|"
    rf"atingid\w*|alcan[çc]ad\w*)|{_RESSALVA})\b", re.I)


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
        titulo = f"Ponto de {c} sem nenhuma marcação"
        registrar_pendencia(caixa, titulo, "Sem controle de jornada desta competência, presume-se verdadeira a "
                            "jornada alegada (Súmula 338 do TST). Localizar o espelho físico ou justificar.",
                            p["id"], "cruzamento")
        out.append(_achado(p, "pendencia", titulo, "Súmula 338 do TST: ausência injustificada dos controles "
                           "gera presunção da jornada da inicial nesse período.", [], "alta"))

    impares = sorted({d for v in pontos.values() if v for d in v.get("dias_batida_impar") or []})
    if impares:
        titulo = f"Batida faltando no ponto em {len(impares)} dia(s)"
        registrar_pendencia(caixa, titulo, f"Marcação ímpar no registro de ponto em: {', '.join(impares)}. "
                            "Conferir com o gestor e registrar o tratamento do ponto (justificativa assinada).",
                            p["id"], "cruzamento")
        out.append(_achado(p, "pendencia", titulo, f"Dias: {', '.join(impares)}. Sem tratamento, a jornada desses "
                           "dias fica sem prova completa.", _ev(caixa, *[f"ponto:{d[:7]}" for d in impares]), "media"))

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
                               f"{dias} dias úteis com intervalo ≥ 60 min marcado no ponto."
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
    alegado = _SABADO_ATE.search(p.get("alegacao") or "")
    sabados = [m["saida"] for v in pontos.values() if v for m in v["marcacoes"]
               if date.fromisoformat(m["data"]).weekday() == 5]
    if alegado and sabados and max(sabados) < f"{int(alegado.group(1)) - 1:02d}:30":
        out.append(_achado(p, "favoravel", f"Saída aos sábados até {max(sabados)} no ponto",
                           f"A alegação fala em trabalho aos sábados até {alegado.group(1)}h; o ponto registra saída "
                           f"no máximo às {max(sabados)}.",
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
                        f"{t['comprovante']['autenticacao']}.",
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


def _ltcat_atesta_neutralizacao(conclusao: str) -> bool:
    """Só é prova a favor se o laudo afirma a neutralização e nenhuma menção a nega ou ressalva.
    Na dúvida conta contra: alarme falso aparece para o advogado, prova a favor indevida inverte o risco."""
    mencoes = 0
    for frase in _FRASE.split(conclusao):
        for m in _NEUTRALIZ.finditer(frase):
            mencoes += 1
            if _NEGA_ANTES.search(frase[:m.start()]) or _NEGA_DEPOIS.search(frase[m.end():]):
                return False
    return mencoes > 0


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
            out.append(_achado(p, "favoravel", "EPI fornecido com CA durante todo o contrato",
                               f"{len(datas)} entregas, intervalo máximo de {maior} dias, todos os itens com CA.",
                               _ev(caixa, "epi"), "alta"))
    else:
        out.append(_achado(p, "cobertura", "Ficha de EPI não consultada", "", [], "alta"))
    if ltcat:
        neutro = _ltcat_atesta_neutralizacao(ltcat["conclusao"])
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


def _sem_exposicao_repetida(achados: list[dict], pedidos: list[dict]) -> None:
    """Pedidos da mesma categoria leem a mesma caixa e geram o mesmo achado (ex.: horas extras e DSR).
    Cada pedido mantém a prova, mas o valor fica em um só, para o total não somar o mesmo dinheiro."""
    rotulos = {p["id"]: f"{p['id']} {p.get('titulo') or ''}".lower() for p in pedidos}
    titulos = {p["id"]: p.get("titulo") or p["id"] for p in pedidos}

    def principal(a: dict) -> bool:
        r = rotulos[a["pedido_id"]]
        return "extra" in r and "dsr" not in r and "reflexo" not in r

    grupos: dict[tuple, list[dict]] = {}
    for a in achados:
        if a["exposicao_estimada"]:
            grupos.setdefault((a["tipo"], a["titulo"]), []).append(a)
    for grupo in grupos.values():
        titular = next(filter(principal, grupo), grupo[0])
        for a in grupo:
            if a is not titular:
                a["exposicao_estimada"] = None
                a["detalhe"] += f" Valor já computado no pedido '{titulos[titular['pedido_id']]}'; não somar de novo."


def cruzar(caixa: Caixa, pedidos: list[dict]) -> list[dict]:
    achados: list[dict] = []
    for p in pedidos:
        regra = REGRAS.get(p["arquetipo"])
        if regra is None:
            achados.append(_achado(p, "pendencia", "Sem regra de cruzamento para esta categoria",
                                   "Análise manual dos documentos coletados.", [], "media"))
            continue
        achados.extend(regra(caixa, p))
    _sem_exposicao_repetida(achados, pedidos)
    return achados
