"""Conector AFD — Arquivo Fonte de Dados do registro eletrônico de ponto.

Todo REP no Brasil é obrigado a exportar o AFD com layout fixo (Portaria MTE 1510/2009 e,
depois, Portaria MTP 671/2021). Ler o AFD é ler o ponto de QUALQUER empresa, sem integração
com o sistema de cada fabricante.

Registro tipo 3 (marcação), o que importa aqui:
  - Portaria 671: NSR(9) + "3" + data/hora ISO (24, AAAA-MM-DDThh:mm:00-0300) + CPF(12) + CRC-16(4)
  - Portaria 1510: NSR(9) + "3" + data DDMMAAAA(8) + hora HHMM(4) + PIS(12)
Registro tipo 1 (cabeçalho): NSR(9) + "1" + tipo do identificador(1) + CNPJ/CPF(14) + ...

Limitações declaradas: o CRC-16 NÃO é validado nesta versão; registros que não são de
marcação (2, 4, 5, 6, 7) são contados, não interpretados. Linha que não se entende não some:
vai para `linhas_nao_lidas` no resumo (regra #4).
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from app import db
from app.rh_mock import dados as D
from app.rh_mock import pdfs as P

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")


@dataclass
class ResultadoAFD:
    layout: str = "desconhecido"
    cnpj: str | None = None
    marcacoes: dict = field(default_factory=lambda: defaultdict(list))   # identificador → [datetime]
    contagem_tipos: dict = field(default_factory=lambda: defaultdict(int))
    linhas_nao_lidas: list = field(default_factory=list)
    nsr_min: int | None = None
    nsr_max: int | None = None


def _so_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def ler(conteudo: bytes) -> ResultadoAFD:
    texto = conteudo.decode("latin-1", errors="replace")
    r = ResultadoAFD()
    layouts = set()
    for n, bruta in enumerate(texto.splitlines(), 1):
        linha = bruta.rstrip("\r\n")
        if not linha.strip():
            continue
        if len(linha) < 10 or not linha[:9].isdigit():
            r.linhas_nao_lidas.append({"linha": n, "motivo": "sem NSR/tipo no início", "trecho": linha[:60]})
            continue
        tipo = linha[9]
        r.contagem_tipos[tipo] += 1
        if tipo == "1" and len(linha) >= 25:
            r.cnpj = _so_digitos(linha[11:25]) or None
            continue
        if tipo != "3":
            continue
        nsr = int(linha[:9])
        try:
            if _ISO.match(linha[10:]) and len(linha) >= 46:
                quando = datetime.strptime(linha[10:26], "%Y-%m-%dT%H:%M")
                ident = _so_digitos(linha[34:46])
                layouts.add("Portaria 671/2021")
            elif len(linha) >= 34 and linha[10:22].isdigit():
                quando = datetime.strptime(linha[10:22], "%d%m%Y%H%M")
                ident = _so_digitos(linha[22:34])
                layouts.add("Portaria 1510/2009")
            else:
                raise ValueError("layout de marcação não reconhecido")
        except ValueError as e:
            r.linhas_nao_lidas.append({"linha": n, "motivo": str(e), "trecho": linha[:60]})
            continue
        r.marcacoes[ident.lstrip("0") or "0"].append(quando)
        r.nsr_min = nsr if r.nsr_min is None else min(r.nsr_min, nsr)
        r.nsr_max = nsr if r.nsr_max is None else max(r.nsr_max, nsr)
    r.layout = " + ".join(sorted(layouts)) or "nenhuma marcação reconhecida"
    return r


def _jornada(batidas: list[datetime]) -> tuple[dict, bool]:
    """Batidas de um dia → jornada. Número ímpar = batida faltando (exceção, não descarte)."""
    hs = sorted(b.strftime("%H:%M") for b in batidas)
    impar = len(hs) % 2 == 1
    if len(hs) >= 4:
        j = {"entrada": hs[0], "saida_intervalo": hs[1], "retorno_intervalo": hs[2], "saida": hs[-1]}
    elif len(hs) >= 2:
        j = {"entrada": hs[0], "saida_intervalo": None, "retorno_intervalo": None, "saida": hs[-1]}
    else:
        j = {"entrada": hs[0], "saida_intervalo": None, "retorno_intervalo": None, "saida": hs[0]}
    return j, impar


# --- importação por processo ------------------------------------------------------------

def importar(processo_id: str, nome: str, conteudo: bytes) -> dict:
    r = ler(conteudo)
    por_dia: dict[str, dict[str, list[datetime]]] = defaultdict(lambda: defaultdict(list))
    for ident, batidas in r.marcacoes.items():
        for b in batidas:
            por_dia[ident][b.date().isoformat()].append(b)
    c = db.conn()
    c.execute("DELETE FROM ponto_importado WHERE processo_id=?", (processo_id,))
    impares_total = 0
    for ident, dias in por_dia.items():
        for dia, batidas in dias.items():
            jornada, impar = _jornada(batidas)
            impares_total += impar
            c.execute("INSERT INTO ponto_importado(processo_id,identificador,data,jornada,impar) VALUES(?,?,?,?,?)",
                      (processo_id, ident, dia, json.dumps(jornada), int(impar)))
    todas = [b for bs in r.marcacoes.values() for b in bs]
    resumo = {
        "arquivo": nome, "layout": r.layout, "cnpj": r.cnpj,
        "registros_por_tipo": dict(r.contagem_tipos), "marcacoes": len(todas),
        "empregados": len(r.marcacoes), "dias_com_batida_impar": impares_total,
        "periodo": [min(todas).date().isoformat(), max(todas).date().isoformat()] if todas else None,
        "nsr": [r.nsr_min, r.nsr_max], "linhas_nao_lidas": r.linhas_nao_lidas[:20],
        "total_linhas_nao_lidas": len(r.linhas_nao_lidas),
        "crc_validado": False, "importado_em": db.agora(),
    }
    c.execute("INSERT INTO importacoes(processo_id,tipo,resumo,criado_em) VALUES(?,?,?,?) "
              "ON CONFLICT(processo_id,tipo) DO UPDATE SET resumo=excluded.resumo, criado_em=excluded.criado_em",
              (processo_id, "afd", json.dumps(resumo, ensure_ascii=False), db.agora()))
    c.commit()
    return resumo


def resumo_importado(processo_id: str) -> dict | None:
    r = db.um("SELECT resumo FROM importacoes WHERE processo_id=? AND tipo='afd'", (processo_id,))
    return json.loads(r["resumo"]) if r else None


def ponto(processo_id: str, cpf: str, competencia: str, pis: str | None = None) -> dict:
    """Mesma forma de resposta de `sistemas.ponto`, mas lida do AFD importado.
    Identifica o empregado pelo CPF (Portaria 671) ou pelo PIS (Portaria 1510)."""
    resumo = resumo_importado(processo_id) or {}
    sistema = f"AFD importado ({resumo.get('arquivo', 'arquivo')}, {resumo.get('layout', '')})"
    linhas = []
    for ident in filter(None, [_so_digitos(cpf).lstrip("0"), _so_digitos(pis or "").lstrip("0")]):
        linhas = db.todos("SELECT data, jornada, impar FROM ponto_importado WHERE processo_id=? AND identificador=? "
                          "AND substr(data,1,7)=? ORDER BY data", (processo_id, ident, competencia))
        if linhas:
            break
    if not linhas:
        motivo = (f"sem marcações no AFD para a competência {competencia}" if resumo.get("periodo") and
                  resumo["periodo"][0][:7] <= competencia <= resumo["periodo"][1][:7]
                  else f"competência {competencia} fora do período do AFD")
        return {"status": "sem_registros", "sistema": sistema, "dados": None, "pdf": None, "nome_pdf": None,
                "motivo": motivo}
    marc = [{"data": l["data"], **json.loads(l["jornada"])} for l in linhas]
    impares = [l["data"] for l in linhas if l["impar"]]
    dados = {"competencia": competencia, "marcacoes": marc, "minutos_extras": D.minutos_extras(marc),
             "dias_batida_impar": impares}
    rodape = (f"Espelho gerado a partir do AFD '{resumo.get('arquivo')}' ({resumo.get('layout')}), "
              f"NSR {resumo.get('nsr', ['?', '?'])[0]} a {resumo.get('nsr', ['?', '?'])[1]}."
              + (f" Dias com batida ímpar (incompleta): {', '.join(impares)}." if impares else ""))
    pdf = P.cartao_ponto(competencia, marcacoes=marc, sistema=sistema, rodape=rodape,
                         matricula=D.matricula_por_cpf(cpf))
    return {"status": "ok", "sistema": sistema, "dados": dados, "pdf": pdf,
            "nome_pdf": f"espelho_ponto_afd_{competencia}.pdf"}


# --- AFD de exemplo da empresa fictícia (layout Portaria 671) -------------------------------

OUTROS = [("98765432100", "Ana Paula Ribeiro"), ("11122233396", "Marcos Vinícius Teles")]
DIA_BATIDA_FALTANDO = "2024-03-12"


def _crc16(dados: str) -> str:
    """CRC-16/KERMIT do registro (usado no exemplo; a leitura não valida CRC)."""
    crc = 0
    for b in dados.encode("latin-1"):
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return f"{crc:04X}"


def gerar_exemplo() -> bytes:
    cpf = _so_digitos(D.FUNCIONARIO["cpf"]).zfill(12)
    eventos: list[tuple[str, str]] = []  # (iso, cpf)
    for comp in D.competencias():
        marc = D.ponto(comp)  # None em 2024-06: o mês some do AFD também
        for m in marc or []:
            hs = [m["entrada"], m["saida_intervalo"], m["retorno_intervalo"], m["saida"]]
            if m["data"] == DIA_BATIDA_FALTANDO:
                hs[3] = None  # esqueceu de bater a saída
            for h in filter(None, hs):
                eventos.append((f"{m['data']}T{h}:00-0300", cpf))
            for outro, _ in OUTROS:  # colegas de setor, jornada padrão
                for h in ("08:00", "12:00", "13:00", "17:00") if m["saida_intervalo"] else ("08:00", "12:00"):
                    eventos.append((f"{m['data']}T{h}:00-0300", outro.zfill(12)))
    eventos.sort()
    linhas = []
    cab = (f"{0:09d}1" + "1" + _so_digitos(D.EMPRESA["cnpj"]).zfill(14) + " " * 14
           + D.EMPRESA["razao_social"].ljust(150)[:150] + "00004004330012345"
           + D.ADMISSAO.isoformat() + D.DEMISSAO.isoformat()
           + datetime(2025, 3, 15, 9, 0).strftime("%Y-%m-%dT%H:%M:00-0300") + "003"
           + "1" + "12345678000199" + "REP-SIMULADO".ljust(30))
    linhas.append(cab + _crc16(cab))
    for i, (iso, ident) in enumerate(eventos, 1):
        reg = f"{i:09d}3{iso}{ident}"
        linhas.append(reg + _crc16(reg))
    linhas.append(f"999999999{0:09d}{len(eventos):09d}{0:09d}{0:09d}{0:09d}{0:09d}9")
    return ("\r\n".join(linhas) + "\r\n").encode("latin-1")


def gerar_exemplo_1510(limite: int = 40) -> bytes:
    """Trecho no layout antigo (Portaria 1510) — usado nos testes de compatibilidade."""
    pis = _so_digitos(D.FUNCIONARIO["pis"]).zfill(12)
    out = []
    for i, m in enumerate((D.ponto("2024-09") or [])[:limite // 4], 1):
        d = date.fromisoformat(m["data"]).strftime("%d%m%Y")
        for j, h in enumerate(filter(None, [m["entrada"], m["saida_intervalo"], m["retorno_intervalo"], m["saida"]])):
            out.append(f"{i * 10 + j:09d}3{d}{h.replace(':', '')}{pis}")
    return ("\r\n".join(out) + "\r\n").encode("latin-1")
