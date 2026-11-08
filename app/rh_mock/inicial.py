"""Petição inicial SINTÉTICA da reclamação trabalhista de demonstração.

Escrita como uma inicial real costuma ser: alegações exageradas misturadas com
verdades, para o agente ter o que confirmar e o que refutar com os documentos da empresa.
"""
from __future__ import annotations

from fpdf import FPDF

from app.rh_mock import dados as D

NUMERO = "0000123-45.2025.5.06.0001"

PEDIDOS = [
    ("horas_extras", "Horas extras e reflexos", 18500.00),
    ("intervalo", "Intervalo intrajornada suprimido (art. 71, § 4º, CLT)", 6200.00),
    ("multa_477", "Multa do art. 477, § 8º, da CLT", 1850.00),
    ("fgts", "Diferenças de FGTS + multa de 40%", 3900.00),
    ("insalubridade", "Adicional de insalubridade em grau médio e reflexos", 7300.00),
    ("dano_moral", "Indenização por danos morais", 20000.00),
]

_TEXTO = [
    ("EXCELENTÍSSIMO(A) SENHOR(A) JUIZ(A) DA 1ª VARA DO TRABALHO DE RECIFE/PE", None),
    (f"Processo nº {NUMERO}", None),
    (None, (
        f"{D.FUNCIONARIO['nome'].upper()}, brasileiro, solteiro, repositor, CPF {D.FUNCIONARIO['cpf']}, "
        "residente em Recife/PE, por seu advogado, vem propor a presente RECLAMAÇÃO TRABALHISTA, pelo rito "
        f"ordinário, em face de {D.EMPRESA['razao_social'].upper()}, CNPJ {D.EMPRESA['cnpj']}, com sede na "
        f"{D.EMPRESA['endereco']}, pelos fatos e fundamentos a seguir."
    )),
    ("I - DO CONTRATO DE TRABALHO", (
        "O reclamante foi admitido em 01/03/2023 para a função de repositor, lotado no setor de perecíveis, "
        "com salário de R$ 1.850,00, e dispensado sem justa causa em 28/02/2025."
    )),
    ("II - DA JORNADA DE TRABALHO E DAS HORAS EXTRAS", (
        "Durante todo o contrato, o reclamante laborava de segunda a sexta-feira das 8h às 19h e aos sábados "
        "das 8h às 14h, extrapolando habitualmente a jornada de 44 horas semanais. Jamais recebeu o pagamento "
        "das horas extras prestadas, nem os respectivos reflexos em DSR, férias + 1/3, 13º salário e FGTS. "
        "Os cartões de ponto, se existentes, não refletem a real jornada."
    )),
    ("III - DO INTERVALO INTRAJORNADA", (
        "O reclamante usufruía de apenas 20 (vinte) minutos de intervalo para refeição e descanso, em razão do "
        "volume de mercadorias a repor, fazendo jus ao pagamento do período suprimido com adicional de 50%, "
        "nos termos do art. 71, § 4º, da CLT."
    )),
    ("IV - DAS VERBAS RESCISÓRIAS E DA MULTA DO ART. 477 DA CLT", (
        "As verbas rescisórias somente foram quitadas em abril de 2025, muito após o prazo de 10 dias previsto "
        "no art. 477, § 6º, da CLT, sendo devida a multa do § 8º do mesmo artigo, no valor de um salário."
    )),
    ("V - DO FGTS", (
        "A reclamada não efetuou corretamente os depósitos do FGTS ao longo do contrato, havendo diversas "
        "competências em aberto, sendo devidas as diferenças acrescidas da multa de 40%."
    )),
    ("VI - DO ADICIONAL DE INSALUBRIDADE", (
        "O reclamante trabalhava diariamente no interior de câmara fria, exposto a baixas temperaturas, sem o "
        "fornecimento de equipamentos de proteção adequados, fazendo jus ao adicional de insalubridade em grau "
        "médio (20%), nos termos da NR-15, Anexo 9, com reflexos legais."
    )),
    ("VII - DOS DANOS MORAIS", (
        "O reclamante era constantemente humilhado pelo gerente Roberto Lima, que o chamava de \"lento\" e "
        "\"incompetente\" na frente de colegas e clientes. Os fatos foram levados ao conhecimento da empresa, "
        "que nada fez. Requer indenização por danos morais no valor de R$ 20.000,00."
    )),
]


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_pdf() -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(True, 20)
    pdf.add_page()
    for titulo, corpo in _TEXTO:
        if titulo:
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(0, 6, titulo, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        if corpo:
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, corpo, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(0, 6, "VIII - DOS PEDIDOS", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, "Diante do exposto, requer a condenação da reclamada ao pagamento de:",
                   new_x="LMARGIN", new_y="NEXT")
    for letra, (_, desc, valor) in zip("abcdefgh", PEDIDOS):
        pdf.multi_cell(0, 6, f"{letra}) {desc}: {_brl(valor)};", new_x="LMARGIN", new_y="NEXT")
    total = sum(v for *_, v in PEDIDOS)
    pdf.ln(2)
    pdf.multi_cell(0, 6, "Requer a juntada, pela reclamada, dos controles de jornada de todo o período "
                         "contratual, sob pena de aplicação da Súmula 338 do TST.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.multi_cell(0, 6, f"Dá-se à causa o valor de {_brl(total)}.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.multi_cell(0, 6, "Recife/PE, 10 de março de 2025.\nAdvogado(a) do reclamante - OAB/PE (fictício)",
                   new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
