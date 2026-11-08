"""Renderiza os documentos dos sistemas simulados em PDF (texto nativo → citável).

São esses PDFs que o worker de subsídios ingere na camada como `classe='subsidio'`.
"""
from __future__ import annotations

from fpdf import FPDF

from app.rh_mock import dados as D


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class _Doc(FPDF):
    def __init__(self, titulo: str, sistema: str, matricula: str = D.DEMO):
        super().__init__()
        self.titulo, self.sistema, self.empregado = titulo, sistema, D.funcionario(matricula)
        self.set_auto_page_break(True, 15)
        self.add_page()

    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 6, f"{D.EMPRESA['razao_social']} - CNPJ {D.EMPRESA['cnpj']}", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.cell(0, 4, f"Emitido pelo sistema: {self.sistema}", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 8, self.titulo, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        f = self.empregado
        self.cell(0, 5, f"Empregado: {f['nome']} - Matrícula {f['matricula']} - CPF {f['cpf']}",
                  new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, f"Cargo: {f['cargo']} - Setor: {f['setor']}", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def linha(self, texto: str, negrito: bool = False):
        self.set_font("Helvetica", "B" if negrito else "", 9)
        self.multi_cell(0, 5, texto, new_x="LMARGIN", new_y="NEXT")

    def tabela(self, cab: list[str], linhas: list[list[str]], larg: list[int]):
        self.set_font("Helvetica", "B", 8)
        for c, w in zip(cab, larg):
            self.cell(w, 6, c, border=1)
        self.ln()
        self.set_font("Helvetica", "", 8)
        for ln in linhas:
            for c, w in zip(ln, larg):
                self.cell(w, 5, c, border=1)
            self.ln()

    def bytes(self) -> bytes:
        return bytes(self.output())


def cartao_ponto(comp: str, marcacoes: list[dict] | None = None, sistema: str | None = None,
                 rodape: str | None = None, matricula: str = D.DEMO) -> bytes | None:
    marc = marcacoes if marcacoes is not None else D.ponto(comp, matricula)
    if marc is None:
        return None
    d = _Doc(f"Espelho de ponto - competência {comp}", sistema or "PontoFácil (registro eletrônico)", matricula)
    d.linha(f"Jornada contratual: {D.funcionario(matricula)['jornada_contratual']}")
    linhas = [[m["data"], m["entrada"], m["saida_intervalo"] or "-", m["retorno_intervalo"] or "-", m["saida"]]
              for m in marc]
    d.tabela(["Data", "Entrada", "Saída intervalo", "Retorno", "Saída"], linhas, [32, 28, 34, 28, 28])
    d.ln(2)
    d.linha(rodape or "Espelho assinado eletronicamente pelo empregado no fechamento do mês.")
    return d.bytes()


def holerite(comp: str, matricula: str = D.DEMO) -> bytes | None:
    h = D.holerite(comp, matricula)
    if h is None:
        return None
    d = _Doc(f"Recibo de pagamento (holerite) - competência {comp}", "FolhaPro (folha de pagamento)", matricula)
    linhas = [[r["codigo"], r["descricao"], r["ref"], _brl(r["valor"]), ""] for r in h["rubricas"]]
    linhas += [[x["codigo"], x["descricao"], "", "", _brl(x["valor"])] for x in h["descontos"]]
    d.tabela(["Cód.", "Descrição", "Referência", "Proventos", "Descontos"], linhas, [14, 70, 30, 34, 34])
    d.ln(2)
    d.linha(f"Total bruto: {_brl(h['bruto'])} - Líquido: {_brl(h['liquido'])} - "
            f"Base FGTS do mês: {_brl(h['fgts_mes'])} - Pago em {h['data_pagamento']}")
    return d.bytes()


def trct(matricula: str = D.DEMO) -> bytes:
    t = D.trct(matricula)
    d = _Doc("Termo de Rescisão do Contrato de Trabalho (TRCT)", "FolhaPro (folha de pagamento)", matricula)
    d.linha(f"Admissão: {D.funcionario(matricula)['admissao']} - Afastamento: {t['data_afastamento']}")
    d.linha(f"Causa do afastamento: {t['causa']}")
    d.tabela(["Verba rescisória", "Valor"], [[v["descricao"], _brl(v["valor"])] for v in t["verbas"]], [130, 40])
    d.ln(2)
    d.linha(f"Total bruto das verbas rescisórias: {_brl(t['total_bruto'])}", negrito=True)
    d.linha(f"Data do pagamento: {t['data_pagamento']} (prazo legal do art. 477, § 6º, da CLT: até {t['prazo_legal']}).")
    c = t["comprovante"]
    d.linha(f"Comprovante: {c['tipo']} {c['banco']}, autenticação {c['autenticacao']}, valor {_brl(c['valor'])}, em {c['data']}.")
    return d.bytes()


def extrato_fgts(matricula: str = D.DEMO) -> bytes:
    e = D.extrato_fgts(matricula)
    d = _Doc("Extrato analítico do FGTS", "Conectividade Social / FGTS Digital (simulado)", matricula)
    d.tabela(["Competência", "Depósito 8%"], [[x["competencia"], _brl(x["valor"])] for x in e["depositos"]], [60, 50])
    d.ln(2)
    d.linha(f"Saldo para fins rescisórios: {_brl(e['saldo_para_fins_rescisorios'])}", negrito=True)
    m = e["multa_40"]
    d.linha(f"Multa rescisória de 40% recolhida: {_brl(m['valor'])} em {m['data']} ({m['guia']}).")
    if len(e["depositos"]) == len(D.competencias(matricula)):
        d.linha("Todas as competências do contrato constam com depósito regular.")
    return d.bytes()


def ficha_epi(matricula: str = D.DEMO) -> bytes:
    d = _Doc("Ficha de entrega de EPI", "SSTNet (saúde e segurança do trabalho)", matricula)
    d.tabela(["Data", "Equipamento", "CA", "Qtd"],
             [[x["data"], x["item"], x["ca"] or "-", str(x["qtd"])] for x in D.fichas_epi(matricula)], [30, 90, 35, 15])
    d.ln(2)
    d.linha("Declaro ter recebido os EPIs acima e o treinamento sobre seu uso, guarda e conservação. "
            "(assinatura do empregado em cada entrega)")
    return d.bytes()


def ltcat(matricula: str = D.DEMO) -> bytes:
    l = D.ltcat(matricula)
    d = _Doc(l["documento"], "SSTNet (saúde e segurança do trabalho)", matricula)
    d.linha(f"Responsável técnico: {l['responsavel']}")
    d.linha(f"Setor avaliado: {l['setor']}")
    d.linha(f"Agente: {l['agente']}")
    d.linha(f"Conclusão: {l['conclusao']}", negrito=True)
    return d.bytes()


def ocorrencias(matricula: str = D.DEMO) -> bytes:
    d = _Doc("Ocorrências e denúncias registradas", "GenteRH (cadastro de pessoal)", matricula)
    for o in D.ocorrencias(matricula):
        d.linha(f"{o['data']} - {o['tipo']} - {o['situacao']}", negrito=True)
        d.linha(o["descricao"])
    return d.bytes()


def ficha_registro(matricula: str = D.DEMO) -> bytes:
    f = D.funcionario(matricula)
    d = _Doc("Ficha de registro de empregado", "GenteRH (cadastro de pessoal)", matricula)
    for k, rot in [("admissao", "Admissão"), ("demissao", "Desligamento"), ("motivo_desligamento", "Motivo"),
                   ("salario_base", "Salário base"), ("jornada_contratual", "Jornada"), ("gestor", "Gestor imediato")]:
        v = _brl(f[k]) if k == "salario_base" else f[k]
        d.linha(f"{rot}: {v}")
    d.linha(f"Ocorrências disciplinares / reclamações internas registradas: {len(D.ocorrencias(matricula)) or 'nenhuma'}.")
    return d.bytes()
