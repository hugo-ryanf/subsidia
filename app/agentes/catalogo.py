"""Playbook da defesa trabalhista — ligado aos SISTEMAS da empresa.

Um checklist comum diz QUE documento pedir ao cliente. Este também diz ONDE buscar
(qual ferramenta) — é isso que transforma o checklist em trabalho feito pelo agente.
`gatilhos` servem de rede de segurança determinística para a classificação do LLM.
"""
from __future__ import annotations

import unicodedata

PRAXE = [  # entram em todo caso trabalhista
    {"documento": "Ficha de registro do empregado", "ferramenta": "obter_ficha_registro"},
    {"documento": "TRCT e comprovante de pagamento da rescisão", "ferramenta": "obter_trct"},
]

ARQUETIPOS = {
    "jornada": {
        "nome": "Jornada, horas extras e intervalos",
        "gatilhos": ["hora extra", "horas extras", "jornada", "sobrejornada", "intervalo", "intrajornada",
                     "interjornada", "adicional noturno", "dsr", "domingos", "feriados", "cargo de confianca"],
        "documentos": ["Espelhos de ponto das competências alegadas", "Holerites das mesmas competências"],
        "ferramentas": ["obter_ponto", "obter_holerite"],
        "perguntas": ["O ponto registrava a jornada real?", "Havia banco de horas ou acordo de compensação?"],
    },
    "validade_rescisao": {
        "nome": "Rescisão: prazo, validade e multa do art. 477",
        "gatilhos": ["477", "verbas rescisorias", "rescisao", "justa causa", "pedido de demissao", "467"],
        "documentos": ["TRCT", "Comprovante de pagamento da rescisão"],
        "ferramentas": ["obter_trct"],
        "perguntas": ["As verbas foram pagas em até 10 dias do afastamento?"],
    },
    "verbas_descontos": {
        "nome": "FGTS, verbas e descontos",
        "gatilhos": ["fgts", "40%", "deposito", "desconto", "seguro-desemprego"],
        "documentos": ["Extrato analítico do FGTS", "Guia da multa de 40%"],
        "ferramentas": ["obter_extrato_fgts"],
        "perguntas": ["Todas as competências foram depositadas?"],
    },
    "saude_acidente": {
        "nome": "Saúde, segurança, insalubridade e acidente",
        "gatilhos": ["insalubridade", "periculosidade", "epi", "acidente", "doenca ocupacional", "frio",
                     "ruido", "camara fria", "cat"],
        "documentos": ["Fichas de entrega de EPI com CA", "LTCAT / laudo técnico do setor"],
        "ferramentas": ["obter_epi", "obter_ltcat"],
        "perguntas": ["O EPI neutralizava o agente? Havia CA válido e registro de entrega?"],
    },
    "assedio": {
        "nome": "Assédio moral e danos morais",
        "gatilhos": ["dano moral", "danos morais", "assedio", "humilha", "constrangimento", "ofensa"],
        "documentos": ["Ocorrências, denúncias e medidas disciplinares", "Ficha funcional da chefia citada"],
        "ferramentas": ["obter_ocorrencias"],
        "perguntas": ["Houve registro em canal de denúncia?", "O que o gestor citado diz sobre os fatos?"],
    },
    "remuneracao": {
        "nome": "Remuneração, comissões e benefícios",
        "gatilhos": ["comissao", "premio", "equiparacao", "diferenca salarial", "salario por fora", "beneficio"],
        "documentos": ["Holerites do período", "Plano de cargos e salários"],
        "ferramentas": ["obter_holerite"],
        "perguntas": ["Como era calculada a remuneração variável?"],
    },
}


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def arquetipo_por_gatilho(texto: str) -> str | None:
    t = _norm(texto)
    melhor, n = None, 0
    for aid, a in ARQUETIPOS.items():
        hits = sum(1 for g in a["gatilhos"] if g in t)
        if hits > n:
            melhor, n = aid, hits
    return melhor


def menu_para_prompt() -> str:
    return "\n".join(f"- {aid}: {a['nome']}" for aid, a in ARQUETIPOS.items())
