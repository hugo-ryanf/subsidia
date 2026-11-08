"""Digital worker de subsídios: para cada pedido, DECIDE o que buscar, OPERA os sistemas,
observa o resultado e decide o próximo passo — até concluir ou escalar.

No fluxo tradicional esta etapa é: checklist → humano pede ao RH → upload manual. Aqui o agente
faz a coleta sozinho. O loop é próprio (o modelo responde JSON com a próxima ação), então
não depende de function calling nativo do provedor. Depois, o cruzamento determinístico
transforma o que foi coletado em achados com evidência.
"""
from __future__ import annotations

import contextvars
import json
import time
from concurrent.futures import ThreadPoolExecutor

from app import db, jobs, llm, rastro
from app.agentes import catalogo, cruzamento
from app.agentes import ferramentas as F
from app.rh_mock import sistemas as S

MAX_PASSOS = 7
CONCORRENCIA = 4
# Base do "tempo vs. manual" (estimativa declarada, ajustável): localizar e conferir cada
# documento num sistema + cruzar cada pedido à mão.
MIN_MANUAL_POR_DOCUMENTO = 6
MIN_MANUAL_POR_PEDIDO = 25

SYSTEM = """Você é um digital worker do Departamento Pessoal que reúne SUBSÍDIOS para a defesa da
empresa numa reclamação trabalhista. Você opera os sistemas da empresa por ferramentas.

FERRAMENTAS:
{ferramentas}
- concluir({{"resumo": "..."}}): encerra quando os documentos necessários para ESTE pedido foram obtidos.

Regras:
- Traga a prova que confirma OU refuta a alegação. Não julgue o mérito; colete.
- Se a alegação cobre todo o contrato, consulte TODAS as competências ("todas").
- Documento AUSENTE num sistema já é registrado automaticamente — não abra pendência por isso.
  Use abrir_pendencia só para o que depende de PESSOAS (depoimento, gestor, testemunha, decisão).
- Assim que tiver os documentos do playbook para este pedido, use concluir. Nunca invente dados.
- Uma ação por resposta. Responda SOMENTE JSON: {{"pensamento": "frase curta", "acao": "nome", "args": {{}}}}"""

USER = """PEDIDO: {titulo} (valor R$ {valor})
ALEGAÇÃO DO RECLAMANTE: {alegacao}
PERÍODO ALEGADO: {periodo}
CATEGORIA: {arquetipo_nome}
CONTRATO: matrícula {matricula}, competências de {ini} a {fim}.
SUGESTÃO DO PLAYBOOK: documentos {docs}; ferramentas {ferr}.

HISTÓRICO DESTE PEDIDO:
{historico}

Qual a próxima ação?"""


def _historico(passos: list[dict]) -> str:
    if not passos:
        return "(nenhuma ação ainda)"
    return "\n".join(f"{i}. {p['acao']}({json.dumps(p['args'], ensure_ascii=False)}) → {p['observacao']}"
                     for i, p in enumerate(passos, 1))


def _executar_acao(caixa: F.Caixa, pedido: dict, acao: str, args: dict) -> str:
    fn = F.FERRAMENTAS.get(acao, (None,))[0]
    if fn is None:
        return f"ferramenta '{acao}' não existe. Use uma da lista."
    args = dict(args or {})
    if acao == "abrir_pendencia":
        args["pedido_id"] = pedido["id"]
    try:
        return fn(caixa, **args)
    except TypeError as e:
        return f"argumentos inválidos para {acao}: {e}"
    except S.SistemaIndisponivel as e:
        F.registrar_pendencia(caixa, f"Sistema indisponível ao executar {acao}", str(e), pedido["id"], "ferramenta")
        return f"SISTEMA INDISPONÍVEL: {e}. Pendência aberta."
    except KeyError as e:
        return f"erro do sistema: {e}"


def _loop_pedido(caixa: F.Caixa, pedido: dict) -> dict:
    arq = catalogo.ARQUETIPOS.get(pedido["arquetipo"], {})
    passos: list[dict] = []
    concluido, resumo = False, None
    for _ in range(MAX_PASSOS):
        prompt = USER.format(
            titulo=pedido["titulo"], valor=pedido.get("valor"), alegacao=pedido.get("alegacao"),
            periodo=pedido.get("periodo_alegado") or "não especificado",
            arquetipo_nome=pedido.get("arquetipo_nome"), matricula=caixa.matricula,
            ini=caixa.competencias[0], fim=caixa.competencias[-1],
            docs="; ".join(arq.get("documentos", [])), ferr=", ".join(arq.get("ferramentas", [])),
            historico=_historico(passos))
        try:
            dec = llm.chat_json(SYSTEM.format(ferramentas=F.descricao_para_prompt()), prompt,
                                max_tokens=800, etiqueta=f"subsidios:{pedido['id']}")
        except llm.LLMError as e:
            F.registrar_pendencia(caixa, f"Agente não conseguiu decidir a coleta de '{pedido['titulo']}'",
                                  str(e), pedido["id"], "agente")
            break
        acao, args = str(dec.get("acao", "")).strip(), dec.get("args") or {}
        rastro.registrar("decisao", f"subsidios:{pedido['id']}",
                         {"pensamento": dec.get("pensamento"), "acao": acao, "args": args})
        if acao == "concluir":
            concluido, resumo = True, (args.get("resumo") if isinstance(args, dict) else None)
            break
        assinatura = (acao, json.dumps(args, sort_keys=True, ensure_ascii=False))
        repetidas = sum((p["acao"], json.dumps(p["args"], sort_keys=True, ensure_ascii=False)) == assinatura
                        for p in passos)
        if repetidas >= 2:
            # Guarda contra loop: o modelo insiste numa ação já feita → encerra com o que tem.
            rastro.registrar("decisao", f"subsidios:{pedido['id']}:loop_interrompido", {"acao": acao})
            concluido, resumo = True, "encerrado pelo guarda de repetição (coleta já feita)"
            break
        if repetidas:
            obs = "Você JÁ executou essa ação (veja o histórico). Se já tem o necessário, use concluir."
        else:
            obs = _executar_acao(caixa, pedido, acao, args)
        passos.append({"acao": acao, "args": args, "pensamento": dec.get("pensamento"), "observacao": obs})
    if not concluido:
        F.registrar_pendencia(caixa, f"Coleta de '{pedido['titulo']}' não concluída pelo agente",
                              f"Encerrada após {len(passos)} passos sem 'concluir'. Conferir os documentos.",
                              pedido["id"], "agente")
    return {"pedido_id": pedido["id"], "passos": passos, "concluido": concluido, "resumo": resumo}


def executar(processo_id: str, job_id: str) -> dict:
    t0 = time.time()
    tri = db.artefato(processo_id, "triagem")
    if not tri:
        raise ValueError("rode a triagem antes da coleta de subsídios")
    if not tri["aprovado"]:
        raise ValueError("a triagem precisa ser aprovada por um humano antes da coleta")
    proc, pedidos = tri["conteudo"]["processo"], tri["conteudo"]["pedidos"]

    jobs.etapa(job_id, "identificando o empregado no cadastro")
    termo = proc.get("cpf_reclamante") or proc.get("reclamante") or ""
    achado = S.buscar_funcionario(termo)
    if achado["status"] != "ok" and proc.get("reclamante"):
        achado = S.buscar_funcionario(proc["reclamante"])
    if achado["status"] != "ok":
        db.executar("INSERT INTO pendencias(id,processo_id,titulo,contexto,criado_em) VALUES(?,?,?,?,?)",
                    (db.novo_id("pend_"), processo_id, "Reclamante não localizado no cadastro de pessoal",
                     f"Busca por '{termo}' sem resultado. Informar a matrícula.", db.agora()))
        resultado = {"bloqueado": True, "motivo": "reclamante não localizado no cadastro"}
        db.salvar_artefato(processo_id, "subsidios", resultado)
        return resultado
    matricula = achado["dados"]["matricula"]
    caixa = F.Caixa(processo_id, matricula, S.competencias_contrato(matricula))
    rastro.registrar("ferramenta", "rh:buscar_funcionario", {"termo": termo, "matricula": matricula})

    jobs.etapa(job_id, "anexando documentos de praxe")
    for item in catalogo.PRAXE:
        _executar_acao(caixa, {"id": "praxe"}, item["ferramenta"], {})

    jobs.etapa(job_id, f"coletando subsídios de {len(pedidos)} pedidos")
    with ThreadPoolExecutor(CONCORRENCIA) as pool:
        futuros = [pool.submit(contextvars.copy_context().run, _loop_pedido, caixa, p) for p in pedidos]
        coletas = [f.result() for f in futuros]

    jobs.etapa(job_id, "cruzando ponto, folha, FGTS e SST")
    achados = cruzamento.cruzar(caixa, pedidos)

    docs = list(caixa.documentos.values())
    min_manual = len(docs) * MIN_MANUAL_POR_DOCUMENTO + len(pedidos) * MIN_MANUAL_POR_PEDIDO
    resultado = {
        "matricula": matricula, "funcionario": achado["dados"]["nome"],
        "documentos": [d | {"chave": k} for k, d in caixa.documentos.items()],
        "coletas": coletas, "achados": achados,
        "pendencias": caixa.pendencias,
        "resumo": {
            "documentos_coletados": len(docs),
            "favoraveis": sum(a["tipo"] == "favoravel" for a in achados),
            "divergencias": sum(a["tipo"] == "divergencia" for a in achados),
            "pendencias": len(caixa.pendencias),
            "exposicao_estimada": round(sum(a["exposicao_estimada"] or 0 for a in achados), 2),
            "segundos_agente": round(time.time() - t0, 1),
            "minutos_manual_estimados": min_manual,
        },
    }
    db.salvar_artefato(processo_id, "subsidios", resultado)
    rastro.registrar("decisao", "subsidios:concluido", resultado["resumo"])
    return resultado["resumo"]
