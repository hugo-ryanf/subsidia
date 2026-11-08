"""Base sintética dos "sistemas da empresa" (Mercado Exemplo Ltda — fictícia).

Determinística (semente fixa): a mesma base sempre gera os mesmos documentos, e o
gabarito do eval depende disso. PROBLEMAS PLANTADOS (o agente precisa achar sozinho):

  1. Ponto de 2024-09 a 2024-11 com saída ~19h em vários dias úteis, e os holerites
     desses meses SEM hora extra paga  → divergência de risco alto.
  2. Ponto de 2024-06 AUSENTE no sistema de ponto → lacuna (Súmula 338 do TST).
  3. Nenhuma ocorrência registrada sobre o gerente → dano moral sem prova documental.

E o que está em ordem (defesa forte): TRCT pago em 7 dias, FGTS completo + 40%,
EPI térmico entregue com CA e LTCAT dizendo que o EPI neutraliza o frio. Em 2023-12
há hora extra feita E paga — caso consistente, para o cruzamento não "achar" tudo.
"""
from __future__ import annotations

import calendar
import random
from datetime import date, timedelta
from functools import lru_cache

EMPRESA = {
    "razao_social": "Mercado Exemplo Ltda",
    "cnpj": "12.345.678/0001-90",
    "endereco": "Rua das Palmeiras, 100, Recife/PE",
}

FUNCIONARIO = {
    "matricula": "0042",
    "nome": "Carlos Eduardo Nogueira",
    "cpf": "123.456.789-09",
    "pis": "012.34567.89-01",
    "cargo": "Repositor de câmara fria",
    "setor": "Perecíveis / câmara fria",
    "admissao": "2023-03-01",
    "demissao": "2025-02-28",
    "motivo_desligamento": "Dispensa sem justa causa, aviso prévio indenizado",
    "salario_base": 1850.00,
    "jornada_contratual": "Seg a sex 08h-17h (1h de intervalo); sáb 08h-12h; 44h semanais",
    "gestor": "Roberto Lima (gerente de loja)",
}

ADMISSAO = date(2023, 3, 1)
DEMISSAO = date(2025, 2, 28)
DIVISOR = 220
MESES_HE_NAO_PAGA = {"2024-09", "2024-10", "2024-11"}
MES_PONTO_AUSENTE = "2024-06"
MES_HE_PAGA = "2023-12"


def competencias() -> list[str]:
    out, d = [], ADMISSAO.replace(day=1)
    while d <= DEMISSAO:
        out.append(f"{d.year}-{d.month:02d}")
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def _hm(minutos: int) -> str:
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


@lru_cache(maxsize=None)
def _ponto_mes(comp: str) -> tuple:
    ano, mes = map(int, comp.split("-"))
    rnd = random.Random(f"ponto-{comp}")
    dias = []
    for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
        d = date(ano, mes, dia)
        if d < ADMISSAO or d > DEMISSAO or d.weekday() == 6:
            continue
        if d.weekday() == 5:  # sábado
            ent = 480 + rnd.randint(-4, 4)
            sai = 720 + rnd.randint(-3, 5)
            dias.append({"data": d.isoformat(), "entrada": _hm(ent), "saida_intervalo": None,
                         "retorno_intervalo": None, "saida": _hm(sai)})
            continue
        ent = 480 + rnd.randint(-5, 4)
        si = 720 + rnd.randint(-2, 3)
        ri = si + 60 + rnd.randint(0, 4)
        sai = 1020 + rnd.randint(-3, 6)
        if comp in MESES_HE_NAO_PAGA and rnd.random() < 0.75:
            sai = 1140 + rnd.randint(0, 20)          # ~19h: 2h extras não pagas
        elif comp == MES_HE_PAGA and rnd.random() < 0.5:
            sai = 1080 + rnd.randint(0, 10)          # ~18h: 1h extra, paga no holerite
        dias.append({"data": d.isoformat(), "entrada": _hm(ent), "saida_intervalo": _hm(si),
                     "retorno_intervalo": _hm(ri), "saida": _hm(sai)})
    return tuple(tuple(sorted(x.items())) for x in dias)


def ponto(comp: str) -> list[dict] | None:
    """Marcações do mês, ou None quando o sistema não tem registro (lacuna plantada)."""
    if comp == MES_PONTO_AUSENTE or comp not in competencias():
        return None
    return [dict(x) for x in _ponto_mes(comp)]


def _min(h: str | None) -> int:
    if not h:
        return 0
    a, b = h.split(":")
    return int(a) * 60 + int(b)


def minutos_extras(marcacoes: list[dict]) -> int:
    """Minutos além da jornada contratual, com a tolerância de 10 min/dia (art. 58 §1º CLT)."""
    total = 0
    for m in marcacoes:
        trabalhado = _min(m["saida"]) - _min(m["entrada"])
        if m["saida_intervalo"]:
            trabalhado -= _min(m["retorno_intervalo"]) - _min(m["saida_intervalo"])
        contratual = 240 if date.fromisoformat(m["data"]).weekday() == 5 else 480
        excesso = trabalhado - contratual
        if excesso > 10:
            total += excesso
    return total


def holerite(comp: str) -> dict | None:
    if comp not in competencias():
        return None
    base = FUNCIONARIO["salario_base"]
    rubricas = [{"codigo": "001", "descricao": "Salário base", "ref": "30 dias", "valor": base}]
    if comp == MES_HE_PAGA:
        horas = round(minutos_extras(ponto(comp)) / 60, 2)
        valor = round(horas * base / DIVISOR * 1.5, 2)
        rubricas.append({"codigo": "050", "descricao": "Horas extras 50%", "ref": f"{horas}h", "valor": valor})
    bruto = round(sum(r["valor"] for r in rubricas), 2)
    inss = round(bruto * 0.09, 2)
    return {
        "competencia": comp, "rubricas": rubricas,
        "descontos": [{"codigo": "901", "descricao": "INSS", "valor": inss}],
        "bruto": bruto, "liquido": round(bruto - inss, 2),
        "fgts_mes": round(bruto * 0.08, 2), "data_pagamento": f"{_proximo_mes(comp)}-05",
    }


def _proximo_mes(comp: str) -> str:
    ano, mes = map(int, comp.split("-"))
    return f"{ano + (mes == 12)}-{(mes % 12) + 1:02d}"


def trct() -> dict:
    base = FUNCIONARIO["salario_base"]
    verbas = [
        {"descricao": "Saldo de salário (28 dias)", "valor": round(base / 30 * 28, 2)},
        {"descricao": "Aviso prévio indenizado (36 dias)", "valor": round(base / 30 * 36, 2)},
        {"descricao": "13º salário proporcional (3/12)", "valor": round(base * 3 / 12, 2)},
        {"descricao": "Férias vencidas (2024/2025) + 1/3", "valor": round(base * 4 / 3, 2)},
        {"descricao": "Férias proporcionais (1/12, projeção do aviso) + 1/3", "valor": round(base / 12 * 4 / 3, 2)},
    ]
    total = round(sum(v["valor"] for v in verbas), 2)
    return {
        "data_afastamento": DEMISSAO.isoformat(),
        "causa": FUNCIONARIO["motivo_desligamento"],
        "verbas": verbas, "total_bruto": total,
        "data_pagamento": (DEMISSAO + timedelta(days=7)).isoformat(),
        "prazo_legal": (DEMISSAO + timedelta(days=10)).isoformat(),
        "comprovante": {"tipo": "TED", "banco": "Banco Exemplo", "autenticacao": "TED-2025-0307-88421",
                        "valor": total, "data": (DEMISSAO + timedelta(days=7)).isoformat()},
    }


def extrato_fgts() -> dict:
    depositos = [{"competencia": c, "valor": holerite(c)["fgts_mes"]} for c in competencias()]
    saldo = round(sum(d["valor"] for d in depositos), 2)
    return {
        "depositos": depositos, "saldo_para_fins_rescisorios": saldo,
        "multa_40": {"valor": round(saldo * 0.4, 2), "data": (DEMISSAO + timedelta(days=7)).isoformat(),
                     "guia": "GRRF 2025/000731"},
    }


def fichas_epi() -> list[dict]:
    entregas, d = [], ADMISSAO
    while d <= DEMISSAO:
        entregas.append({"data": d.isoformat(), "item": "Jaqueta térmica para câmara fria", "ca": "CA 38.211", "qtd": 1})
        entregas.append({"data": d.isoformat(), "item": "Luva térmica", "ca": "CA 41.907", "qtd": 2})
        entregas.append({"data": d.isoformat(), "item": "Bota de PVC forrada", "ca": "CA 37.550", "qtd": 1})
        d += timedelta(days=180)
    return entregas


def ltcat() -> dict:
    return {
        "documento": "LTCAT 2023 - Mercado Exemplo Ltda", "responsavel": "Eng. de Segurança (CREA fictício 000000)",
        "setor": "Perecíveis / câmara fria",
        "agente": "Frio (temperatura entre 0 °C e 4 °C), exposição intermitente",
        "conclusao": ("Exposição ao agente frio NEUTRALIZADA pelo uso regular de vestimenta térmica, luvas e botas "
                      "forradas com CA válido, além de pausas de recuperação térmica (art. 253 da CLT). "
                      "Atividade não caracterizada como insalubre enquanto mantido o fornecimento dos EPIs."),
    }


def ocorrencias() -> list[dict]:
    return []  # plantado: nada registrado sobre o gestor
