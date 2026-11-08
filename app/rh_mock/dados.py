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

Segundo empregado (matrícula 0107), com o quadro invertido: horas extras pagas, mas intervalo
reduzido, rescisão fora do prazo, FGTS com meses em aberto, EPI com falhas, LTCAT desfavorável e
denúncia registrada. Serve para mostrar que as regras leem os dados, não o caso de demonstração.
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
DEMO = FUNCIONARIO["matricula"]

SEGUNDA = {
    "matricula": "0107",
    "nome": "Juliana Ferreira Campos",
    "cpf": "111.444.777-35",
    "pis": "120.45678.90-3",
    "cargo": "Auxiliar de limpeza",
    "setor": "Limpeza e conservação",
    "admissao": "2023-08-14",
    "demissao": "2025-01-31",
    "motivo_desligamento": "Dispensa sem justa causa, aviso prévio indenizado",
    "salario_base": 1600.00,
    "jornada_contratual": "Seg a sex 07h-16h (1h de intervalo); sáb 07h-11h; 44h semanais",
    "gestor": "Márcia Tavares (supervisora de serviços)",
}

FUNCIONARIOS = {DEMO: FUNCIONARIO, SEGUNDA["matricula"]: SEGUNDA}

# O que muda de um empregado para outro. `verbas`: (descrição, numerador, denominador) do salário.
_PERFIS = {
    DEMO: {
        "admissao": ADMISSAO, "demissao": DEMISSAO, "entrada": 480, "semente": "ponto",
        "he_nao_paga": MESES_HE_NAO_PAGA, "he_paga": {MES_HE_PAGA}, "ponto_ausente": {MES_PONTO_AUSENTE},
        "intervalo_curto": set(), "sem_fgts": set(), "dias_pagto_rescisao": 7,
        "autenticacao": "TED-2025-0307-88421", "guia": "GRRF 2025/000731",
        "verbas": [("Saldo de salário (28 dias)", 28, 30), ("Aviso prévio indenizado (36 dias)", 36, 30),
                   ("13º salário proporcional (3/12)", 3, 12), ("Férias vencidas (2024/2025) + 1/3", 4, 3),
                   ("Férias proporcionais (1/12, projeção do aviso) + 1/3", 4, 36)],
    },
    SEGUNDA["matricula"]: {
        "admissao": date(2023, 8, 14), "demissao": date(2025, 1, 31), "entrada": 420, "semente": "ponto-0107",
        "he_nao_paga": set(), "he_paga": {"2024-03", "2024-04", "2024-11"}, "ponto_ausente": set(),
        "intervalo_curto": {"2024-05", "2024-06", "2024-07", "2024-08"}, "sem_fgts": {"2024-02", "2024-07"},
        "dias_pagto_rescisao": 23,
        "autenticacao": "TED-2025-0223-51907", "guia": "GRRF 2025/001284",
        "verbas": [("Saldo de salário (31 dias)", 31, 30), ("Aviso prévio indenizado (33 dias)", 33, 30),
                   ("13º salário proporcional (2/12)", 2, 12), ("Férias proporcionais (6/12) + 1/3", 8, 12)],
    },
}


def funcionario(matricula: str = DEMO) -> dict:
    return FUNCIONARIOS[matricula]


def matricula_por_cpf(cpf: str) -> str:
    alvo = "".join(c for c in cpf if c.isdigit()).lstrip("0")
    for m, f in FUNCIONARIOS.items():
        if "".join(c for c in f["cpf"] if c.isdigit()).lstrip("0") == alvo:
            return m
    return DEMO


def competencias(matricula: str = DEMO) -> list[str]:
    p = _PERFIS[matricula]
    out, d = [], p["admissao"].replace(day=1)
    while d <= p["demissao"]:
        out.append(f"{d.year}-{d.month:02d}")
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def _hm(minutos: int) -> str:
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


@lru_cache(maxsize=None)
def _ponto_mes(comp: str, matricula: str = DEMO) -> tuple:
    p = _PERFIS[matricula]
    ano, mes = map(int, comp.split("-"))
    base = p["entrada"]
    rnd = random.Random(f"{p['semente']}-{comp}")
    dias = []
    for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
        d = date(ano, mes, dia)
        if d < p["admissao"] or d > p["demissao"] or d.weekday() == 6:
            continue
        if d.weekday() == 5:  # sábado
            ent = base + rnd.randint(-4, 4)
            sai = base + 240 + rnd.randint(-3, 5)
            dias.append({"data": d.isoformat(), "entrada": _hm(ent), "saida_intervalo": None,
                         "retorno_intervalo": None, "saida": _hm(sai)})
            continue
        ent = base + rnd.randint(-5, 4)
        si = base + 240 + rnd.randint(-2, 3)
        ri = si + 60 + rnd.randint(0, 4)
        sai = base + 540 + rnd.randint(-3, 6)
        if comp in p["he_nao_paga"] and rnd.random() < 0.75:
            sai = base + 660 + rnd.randint(0, 20)    # +2h extras não pagas
        elif comp in p["he_paga"] and rnd.random() < 0.5:
            sai = base + 600 + rnd.randint(0, 10)    # +1h extra, paga no holerite
        if comp in p["intervalo_curto"] and rnd.random() < 0.7:
            folga = rnd.randint(30, 40)              # intervalo reduzido, compensado na saída
            ri, sai = si + folga, sai - (60 - folga)
        dias.append({"data": d.isoformat(), "entrada": _hm(ent), "saida_intervalo": _hm(si),
                     "retorno_intervalo": _hm(ri), "saida": _hm(sai)})
    return tuple(tuple(sorted(x.items())) for x in dias)


def ponto(comp: str, matricula: str = DEMO) -> list[dict] | None:
    """Marcações do mês, ou None quando o sistema não tem registro (lacuna plantada)."""
    if comp in _PERFIS[matricula]["ponto_ausente"] or comp not in competencias(matricula):
        return None
    return [dict(x) for x in _ponto_mes(comp, matricula)]


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


def holerite(comp: str, matricula: str = DEMO) -> dict | None:
    if comp not in competencias(matricula):
        return None
    base = FUNCIONARIOS[matricula]["salario_base"]
    rubricas = [{"codigo": "001", "descricao": "Salário base", "ref": "30 dias", "valor": base}]
    if comp in _PERFIS[matricula]["he_paga"]:
        horas = round(minutos_extras(ponto(comp, matricula)) / 60, 2)
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


def trct(matricula: str = DEMO) -> dict:
    f, p = FUNCIONARIOS[matricula], _PERFIS[matricula]
    base, demissao = f["salario_base"], p["demissao"]
    verbas = [{"descricao": d, "valor": round(base * n / q, 2)} for d, n, q in p["verbas"]]
    total = round(sum(v["valor"] for v in verbas), 2)
    pago_em = (demissao + timedelta(days=p["dias_pagto_rescisao"])).isoformat()
    return {
        "data_afastamento": demissao.isoformat(),
        "causa": f["motivo_desligamento"],
        "verbas": verbas, "total_bruto": total,
        "data_pagamento": pago_em,
        "prazo_legal": (demissao + timedelta(days=10)).isoformat(),
        "comprovante": {"tipo": "TED", "banco": "Banco Exemplo", "autenticacao": p["autenticacao"],
                        "valor": total, "data": pago_em},
    }


def extrato_fgts(matricula: str = DEMO) -> dict:
    p = _PERFIS[matricula]
    depositos = [{"competencia": c, "valor": holerite(c, matricula)["fgts_mes"]}
                 for c in competencias(matricula) if c not in p["sem_fgts"]]
    saldo = round(sum(d["valor"] for d in depositos), 2)
    return {
        "depositos": depositos, "saldo_para_fins_rescisorios": saldo,
        "multa_40": {"valor": round(saldo * 0.4, 2),
                     "data": (p["demissao"] + timedelta(days=p["dias_pagto_rescisao"])).isoformat(),
                     "guia": p["guia"]},
    }


def fichas_epi(matricula: str = DEMO) -> list[dict]:
    if matricula != DEMO:
        return [  # 269 dias sem reposição e um item sem CA: falhas plantadas
            {"data": "2023-08-14", "item": "Luva nitrílica", "ca": "CA 32.106", "qtd": 2},
            {"data": "2023-08-14", "item": "Bota de PVC", "ca": "CA 37.550", "qtd": 1},
            {"data": "2024-01-10", "item": "Luva nitrílica", "ca": "CA 32.106", "qtd": 2},
            {"data": "2024-10-05", "item": "Luva nitrílica", "ca": "CA 32.106", "qtd": 1},
            {"data": "2024-10-05", "item": "Avental de PVC", "ca": None, "qtd": 1},
        ]
    entregas, d = [], ADMISSAO
    while d <= DEMISSAO:
        entregas.append({"data": d.isoformat(), "item": "Jaqueta térmica para câmara fria", "ca": "CA 38.211", "qtd": 1})
        entregas.append({"data": d.isoformat(), "item": "Luva térmica", "ca": "CA 41.907", "qtd": 2})
        entregas.append({"data": d.isoformat(), "item": "Bota de PVC forrada", "ca": "CA 37.550", "qtd": 1})
        d += timedelta(days=180)
    return entregas


def ltcat(matricula: str = DEMO) -> dict:
    if matricula != DEMO:
        return {
            "documento": "LTCAT 2023 - Limpeza e conservação", "responsavel": "Eng. de Segurança (CREA fictício 000000)",
            "setor": "Limpeza e conservação",
            "agente": "Agentes químicos (produtos alcalinos de limpeza), contato habitual",
            "conclusao": ("Exposição habitual a produtos alcalinos sem neutralização comprovada do agente, em razão de "
                          "falhas na reposição de luvas. Atividade caracterizada como insalubre em grau médio."),
        }
    return {
        "documento": "LTCAT 2023 - Mercado Exemplo Ltda", "responsavel": "Eng. de Segurança (CREA fictício 000000)",
        "setor": "Perecíveis / câmara fria",
        "agente": "Frio (temperatura entre 0 °C e 4 °C), exposição intermitente",
        "conclusao": ("Exposição ao agente frio NEUTRALIZADA pelo uso regular de vestimenta térmica, luvas e botas "
                      "forradas com CA válido, além de pausas de recuperação térmica (art. 253 da CLT). "
                      "Atividade não caracterizada como insalubre enquanto mantido o fornecimento dos EPIs."),
    }


def ocorrencias(matricula: str = DEMO) -> list[dict]:
    if matricula != DEMO:
        return [{"data": "2024-06-18", "tipo": "Denúncia no canal interno",
                 "descricao": "Empregada relata cobranças em tom ofensivo da supervisora na frente de colegas.",
                 "situacao": "Encerrada sem apuração registrada"}]
    return []  # plantado: nada registrado sobre o gestor
