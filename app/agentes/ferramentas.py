"""Ferramentas do digital worker: operam os sistemas da empresa e ingerem o que trazem.

Cada chamada:
  - vai ao sistema (com retentativa se ele estiver fora do ar);
  - ingere o PDF devolvido na camada como `subsidio` (fica citável por documento+página);
  - guarda os DADOS estruturados na `Caixa` (o cruzamento determinístico usa isso);
  - grava um evento `ferramenta` no rastro (o quê, com quais args, resultado, tempo);
  - devolve ao LLM uma OBSERVAÇÃO curta em texto (nunca o dump inteiro).
Falha que persiste vira pendência — nunca some (regras #1 e #4).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from app import db, rastro
from app.camada import busca, ingestao
from app.rh_mock import sistemas as S

MAX_TENTATIVAS = 3


@dataclass
class Caixa:
    """Estado compartilhado da coleta de um processo (todas as threads de pedido)."""
    processo_id: str
    matricula: str
    competencias: list[str]
    dados: dict = field(default_factory=dict)        # chave → dados estruturados
    documentos: dict = field(default_factory=dict)   # chave → {documento_id, nome, sistema}
    pendencias: list = field(default_factory=list)
    trava: threading.Lock = field(default_factory=threading.Lock)
    travas: dict = field(default_factory=dict)       # chave → Lock (busca em andamento)


def _h(minutos: int) -> str:
    return f"{minutos / 60:.1f}h".replace(".", ",")


def _chamar_sistema(caixa: Caixa, chave: str, fn, *args) -> dict:
    """Chama o sistema com retentativa; ingere o PDF; cacheia por chave (idempotente).
    Um lock por chave impede duas threads de pedido buscarem/ingerirem o mesmo documento."""
    with caixa.trava:
        trava_chave = caixa.travas.setdefault(chave, threading.Lock())
    with trava_chave:
        with caixa.trava:
            if chave in caixa.dados:
                d = caixa.dados[chave]
                return {"status": "ok" if d is not None else "sem_registros", "dados": d, "cache": True,
                        "motivo": None if d is not None else "sem registros (consulta anterior)"}
        return _chamar_sem_cache(caixa, chave, fn, *args)


def _chamar_sem_cache(caixa: Caixa, chave: str, fn, *args) -> dict:
    ultimo_erro = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        t0 = time.time()
        try:
            r = fn(*args)
        except S.SistemaIndisponivel as e:
            ultimo_erro = str(e)
            rastro.registrar("ferramenta", f"{chave}:falhou", {"tentativa": tentativa, "erro": ultimo_erro},
                             segundos=round(time.time() - t0, 2))
            time.sleep(0.5 * tentativa)
            continue
        doc = None
        if r["status"] == "ok" and r.get("pdf"):
            ing = ingestao.ingerir_bytes(caixa.processo_id, r["nome_pdf"], r["pdf"], "subsidio",
                                         f"sistema:{r['sistema']}")
            doc = {"documento_id": ing["documento_id"], "nome": r["nome_pdf"], "sistema": r["sistema"]}
        with caixa.trava:
            caixa.dados[chave] = r["dados"] if r["status"] == "ok" else None
            if doc:
                caixa.documentos[chave] = doc
        rastro.registrar("ferramenta", chave, {"sistema": r["sistema"], "status": r["status"],
                                               "motivo": r.get("motivo"), "documento": doc,
                                               "tentativas": tentativa},
                         segundos=round(time.time() - t0, 2))
        return r
    raise S.SistemaIndisponivel(f"{ultimo_erro} (após {MAX_TENTATIVAS} tentativas)")


def _lista_comp(caixa: Caixa, competencias) -> list[str]:
    if competencias in (None, "todas", ["todas"]):
        return list(caixa.competencias)
    if isinstance(competencias, str):
        competencias = [competencias]
    return [c for c in competencias if c in caixa.competencias] or []


def _fonte_ponto(caixa: Caixa):
    """AFD importado para o processo tem prioridade sobre o sistema de ponto."""
    from app.conectores import afd
    if afd.resumo_importado(caixa.processo_id):
        f = S.buscar_funcionario(caixa.matricula)["dados"] or {}
        return "AFD importado", lambda c: afd.ponto(caixa.processo_id, f.get("cpf", ""), c, f.get("pis"))
    return "sistema de ponto", lambda c: S.ponto(caixa.matricula, c)


def obter_ponto(caixa: Caixa, competencias="todas") -> str:
    comps = _lista_comp(caixa, competencias)
    if not comps:
        return "nenhuma competência válida pedida (o contrato vai de " \
               f"{caixa.competencias[0]} a {caixa.competencias[-1]})"
    nome_fonte, fonte = _fonte_ponto(caixa)
    com_extra, sem_reg, impares, normais = [], [], [], 0
    for c in comps:
        r = _chamar_sistema(caixa, f"ponto:{c}", fonte, c)
        if r["status"] != "ok":
            sem_reg.append(c)
            continue
        impares += (r["dados"] or {}).get("dias_batida_impar") or []
        if r["dados"]["minutos_extras"] > 0:
            com_extra.append(f"{c} ({_h(r['dados']['minutos_extras'])} além da jornada)")
        else:
            normais += 1
    partes = [f"Ponto consultado em {len(comps)} competência(s) (fonte: {nome_fonte})."]
    if impares:
        partes.append(f"Batida faltando (marcação ímpar) em: {', '.join(impares)}.")
    if com_extra:
        partes.append("Com sobrejornada registrada: " + "; ".join(com_extra) + ".")
    if sem_reg:
        partes.append("SEM REGISTRO no sistema de ponto: " + ", ".join(sem_reg) + ".")
    partes.append(f"{normais} competência(s) dentro da jornada contratual.")
    return " ".join(partes)


def obter_holerite(caixa: Caixa, competencias="todas") -> str:
    comps = _lista_comp(caixa, competencias)
    pagos, faltam = [], []
    for c in comps:
        r = _chamar_sistema(caixa, f"holerite:{c}", S.holerite, caixa.matricula, c)
        if r["status"] != "ok":
            faltam.append(c)
            continue
        he = [x for x in r["dados"]["rubricas"] if "extra" in x["descricao"].lower()]
        if he:
            pagos.append(f"{c} ({he[0]['ref']}, R$ {he[0]['valor']:.2f})")
    txt = f"Holerites consultados em {len(comps)} competência(s). "
    txt += ("Horas extras PAGAS em: " + "; ".join(pagos) + ". ") if pagos else "Nenhuma hora extra paga. "
    if faltam:
        txt += "Sem holerite: " + ", ".join(faltam) + "."
    return txt


def obter_trct(caixa: Caixa) -> str:
    t = _chamar_sistema(caixa, "trct", S.trct, caixa.matricula)["dados"]
    return (f"TRCT: afastamento {t['data_afastamento']}, verbas R$ {t['total_bruto']:.2f}, pagas em "
            f"{t['data_pagamento']} (prazo legal até {t['prazo_legal']}), comprovante {t['comprovante']['autenticacao']}.")


def obter_extrato_fgts(caixa: Caixa) -> str:
    e = _chamar_sistema(caixa, "fgts", S.extrato_fgts, caixa.matricula, caixa.processo_id)["dados"]
    deps = {d["competencia"] for d in e["depositos"]}
    faltam = [c for c in caixa.competencias if c not in deps]
    return (f"Extrato FGTS: {len(deps)}/{len(caixa.competencias)} competências depositadas"
            + (f" (faltam {', '.join(faltam)})" if faltam else "")
            + f"; multa de 40% recolhida em {e['multa_40']['data']} ({e['multa_40']['guia']}).")


def obter_epi(caixa: Caixa) -> str:
    ent = _chamar_sistema(caixa, "epi", S.epi, caixa.matricula)["dados"]["entregas"]
    itens = sorted({f"{x['item']} ({x['ca']})" for x in ent})
    datas = sorted({x["data"] for x in ent})
    return f"Ficha de EPI: {len(datas)} entregas ({datas[0]} a {datas[-1]}) de: {'; '.join(itens)}."


def obter_ltcat(caixa: Caixa) -> str:
    l = _chamar_sistema(caixa, "ltcat", lambda: S.laudo_ltcat())["dados"]
    return f"LTCAT ({l['setor']}): agente {l['agente']}. Conclusão: {l['conclusao']}"


def obter_ocorrencias(caixa: Caixa) -> str:
    r = _chamar_sistema(caixa, "ocorrencias", S.ocorrencias, caixa.matricula)
    return "Ocorrências: " + (r.get("motivo") or f"{len(r['dados'])} registro(s)") + "."


def obter_ficha_registro(caixa: Caixa) -> str:
    _chamar_sistema(caixa, "ficha_registro", S.buscar_funcionario, caixa.matricula)
    return "Ficha de registro anexada."


def buscar_autos(caixa: Caixa, pergunta: str = "") -> str:
    r = busca.buscar(caixa.processo_id, pergunta, top_k=3, classe="autos")
    if r["status"] != "ok":
        return "Nada encontrado nos autos para essa pergunta."
    return " | ".join(f"({x['documento']} p.{x['pagina_inicio']}) {x['texto'][:300]}" for x in r["resultados"])


def abrir_pendencia(caixa: Caixa, titulo: str = "", contexto: str = "", pedido_id: str | None = None) -> str:
    registrar_pendencia(caixa, titulo or "Pendência sem título", contexto or "", pedido_id, origem="agente")
    return "Pendência registrada para revisão humana."


def registrar_pendencia(caixa: Caixa, titulo: str, contexto: str, pedido_id: str | None, origem: str) -> None:
    with caixa.trava:
        # Mesma pendência vinda de outro pedido (ex.: ponto ausente afeta HE e intervalo) não duplica.
        if any(p["titulo"] == titulo for p in caixa.pendencias):
            return
        pid = db.novo_id("pend_")
        caixa.pendencias.append({"id": pid, "titulo": titulo, "contexto": contexto, "pedido_id": pedido_id,
                                 "origem": origem})
    db.executar("INSERT INTO pendencias(id,processo_id,pedido_id,titulo,contexto,criado_em) VALUES(?,?,?,?,?,?)",
                (pid, caixa.processo_id, pedido_id, titulo, f"[{origem}] {contexto}", db.agora()))
    rastro.registrar("decisao", "pendencia_aberta", {"titulo": titulo, "pedido": pedido_id, "origem": origem})


FERRAMENTAS = {
    "obter_ponto": (obter_ponto, '{"competencias": ["AAAA-MM", ...] ou "todas"}',
                    "espelhos de ponto (marcações diárias) do sistema de ponto"),
    "obter_holerite": (obter_holerite, '{"competencias": ["AAAA-MM", ...] ou "todas"}',
                       "holerites (rubricas pagas) da folha"),
    "obter_trct": (obter_trct, "{}", "termo de rescisão e comprovante de pagamento"),
    "obter_extrato_fgts": (obter_extrato_fgts, "{}", "extrato analítico do FGTS e guia da multa de 40%"),
    "obter_epi": (obter_epi, "{}", "fichas de entrega de EPI com CA"),
    "obter_ltcat": (obter_ltcat, "{}", "laudo técnico (LTCAT) do setor"),
    "obter_ocorrencias": (obter_ocorrencias, "{}", "ocorrências, denúncias e medidas disciplinares no RH"),
    "obter_ficha_registro": (obter_ficha_registro, "{}", "ficha de registro do empregado"),
    "buscar_autos": (buscar_autos, '{"pergunta": "..."}', "busca trechos na petição/autos"),
    "abrir_pendencia": (abrir_pendencia, '{"titulo": "...", "contexto": "..."}',
                        "escala algo que só um humano resolve (falta documento, ambiguidade, depoimento)"),
}


def descricao_para_prompt() -> str:
    return "\n".join(f"- {n}({args}): {d}" for n, (_, args, d) in FERRAMENTAS.items())
