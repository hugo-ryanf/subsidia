import { marked } from "marked";
import { useState } from "react";
import { useEffect } from "react";
import { Achado, api, brl, docUrl, Estrategia, Fonte, Pendencia, Processo, ResumoAFD, Subsidios, Triagem } from "./api";

export function Citacoes({ pid, fontes }: { pid: string; fontes: Fonte[] }) {
  if (!fontes?.length) return <span className="tag tag-warn">sem citação</span>;
  return (
    <span className="cits">
      {fontes.map((f) => (
        <a key={f.ref + f.documento_id} className="cit" href={docUrl(pid, f)} target="_blank" rel="noreferrer"
           title={`${f.documento}, p. ${f.pagina_inicio}`}>
          {f.documento.replace(".pdf", "")} p.{f.pagina_inicio}
        </a>
      ))}
    </span>
  );
}

/* ---------------- Triagem ---------------- */

export function VisaoTriagem({ pid, t }: { pid: string; t: Triagem }) {
  const p = t.processo;
  return (
    <div>
      {t.aviso && <div className="tag tag-warn">{t.aviso}</div>}
      <div className="grade-proc">
        <div><span>Processo</span><b>{p.numero ?? "—"}</b></div>
        <div><span>Reclamante</span><b>{p.reclamante ?? "—"}</b></div>
        <div><span>Cargo</span><b>{p.cargo ?? "—"}</b></div>
        <div><span>Contrato</span><b>{p.admissao ?? "?"} → {p.demissao ?? "?"}</b></div>
        <div><span>Valor da causa</span><b>{brl(p.valor_causa)}</b></div>
      </div>
      <table className="tabela">
        <thead><tr><th>Pedido</th><th>Categoria</th><th>Valor</th><th>Confiança</th><th>Fonte</th></tr></thead>
        <tbody>
          {t.pedidos.map((x) => (
            <tr key={x.id} className={x.requer_revisao ? "linha-rev" : ""}>
              <td><b>{x.titulo}</b><div className="muted small">{x.alegacao}</div>
                {x.requer_revisao && <div className="tag tag-warn">revisar: {x.motivos_revisao.join("; ")}</div>}</td>
              <td>{x.arquetipo_nome}</td>
              <td className="num">{brl(x.valor)}</td>
              <td className="num">{Math.round(x.confianca * 100)}%</td>
              <td><Citacoes pid={pid} fontes={x.fontes} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------------- Fonte do ponto (AFD) ---------------- */

export function FontePonto({ pid, coletaEm }: { pid: string; coletaEm?: string }) {
  const [resumo, setResumo] = useState<ResumoAFD | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => { api.afd(pid).then((r) => setResumo(r.importado)).catch(() => {}); }, [pid]);
  const importar = async (f: File | undefined) => {
    if (!f) return;
    setOcupado(true); setErro(null);
    try { setResumo(await api.importarAfd(pid, f)); } catch (e: any) { setErro(e.message); }
    setOcupado(false);
  };
  return (
    <div className="fonte">
      <div className="fonte-cab">
        <div>
          <b>Fonte do ponto:</b>{" "}
          {resumo ? <span className="tag tag-ok">AFD importado</span> : <span className="tag">sistema de ponto da empresa (simulado)</span>}
          <div className="muted small">O AFD é o arquivo que todo relógio de ponto é obrigado a exportar (Portarias 1510/2009 e 671/2021).
            Importado, o agente lê o ponto direto dele.</div>
        </div>
        <div className="acoes">
          <label className={`botao-arquivo ${ocupado ? "desab" : ""}`}>
            {ocupado ? "Lendo…" : "Importar AFD"}
            <input type="file" accept=".txt,.afd,text/plain" disabled={ocupado} onChange={(e) => importar(e.target.files?.[0])} />
          </label>
          <a className="small" href="/rh/demo/afd.txt">baixar AFD de exemplo</a>
        </div>
      </div>
      {erro && <div className="alerta">{erro}</div>}
      {resumo && (
        <div className="small fonte-res">
          <b>{resumo.arquivo}</b> · {resumo.layout} · CNPJ {resumo.cnpj ?? "—"} · {resumo.marcacoes.toLocaleString("pt-BR")} marcações de{" "}
          {resumo.empregados} empregado(s) · {resumo.periodo ? `${resumo.periodo[0]} a ${resumo.periodo[1]}` : "—"} · NSR {resumo.nsr[0]}–{resumo.nsr[1]}
          {resumo.dias_com_batida_impar > 0 && <> · <span className="warn-tx">{resumo.dias_com_batida_impar} dia(s) com batida faltando</span></>}
          {resumo.total_linhas_nao_lidas > 0 && <> · <span className="warn-tx">{resumo.total_linhas_nao_lidas} linha(s) não lidas</span></>}
          <span className="muted"> · CRC não validado nesta versão</span>
          {coletaEm && resumo.importado_em && coletaEm < resumo.importado_em && <div className="muted">A coleta já rodou com a fonte anterior: use “Rodar de novo” para refazer com o AFD.</div>}
        </div>
      )}
    </div>
  );
}

/* ---------------- Subsídios ---------------- */

const ROTULO: Record<Achado["tipo"], string> = { favoravel: "A favor", divergencia: "Risco", pendencia: "Pendência", cobertura: "Não verificado" };

export function VisaoSubsidios({ pid, s, tri, pendencias, aoMudar }: { pid: string; s: Subsidios; tri: Triagem; pendencias: Pendencia[]; aoMudar: () => void }) {
  if (s.bloqueado) return <div className="alerta">Coleta bloqueada: {s.motivo}</div>;
  const r = s.resumo;
  return (
    <div>
      <div className="kpis kpis-linha">
        <div><b>{r.documentos_coletados}</b><span>documentos coletados nos sistemas</span></div>
        <div className="ok"><b>{r.favoraveis}</b><span>provas a favor</span></div>
        <div className="bad"><b>{r.divergencias}</b><span>divergências (risco)</span></div>
        <div className="warn"><b>{r.pendencias}</b><span>pendências para humano</span></div>
        <div><b>{brl(r.exposicao_estimada)}</b><span>exposição estimada (principal)</span></div>
      </div>
      {tri.pedidos.map((p) => {
        const meus = s.achados.filter((a) => a.pedido_id === p.id);
        const col = s.coletas.find((c) => c.pedido_id === p.id);
        return (
          <div key={p.id} className="bloco-pedido">
            <h4>{p.titulo} <span className="muted">{brl(p.valor)}</span></h4>
            {col && (
              <div className="trilha">
                {col.passos.map((ps, i) => (
                  <span key={i} className="passo" title={`${ps.pensamento}\n→ ${ps.observacao}`}>{ps.acao}</span>
                ))}
                {!col.concluido && <span className="tag tag-warn">não concluído</span>}
                {col.modo === "playbook" && <span className="tag tag-warn" title={col.resumo ?? ""}>coletado pelo playbook (modelo indisponível)</span>}
              </div>
            )}
            {meus.map((a, i) => (
              <div key={i} className={`achado achado-${a.tipo}`}>
                <div className="achado-cab"><span className={`badge b-${a.tipo}`}>{ROTULO[a.tipo]}</span><b>{a.titulo}</b></div>
                <div className="small">{a.detalhe}</div>
                {a.evidencias.length > 0 && (
                  <div className="cits">
                    {a.evidencias.slice(0, 8).map((e) => (
                      <a key={e.documento_id} className="cit" href={docUrl(pid, e)} target="_blank" rel="noreferrer" title={e.sistema}>
                        {e.nome.replace(".pdf", "")}
                      </a>
                    ))}
                    {a.evidencias.length > 8 && <span className="muted small">+{a.evidencias.length - 8}</span>}
                  </div>
                )}
              </div>
            ))}
          </div>
        );
      })}
      <Pendencias pid={pid} pendencias={pendencias} aoMudar={aoMudar} />
      <details className="docs">
        <summary>Documentos coletados ({s.documentos.length})</summary>
        <ul>{s.documentos.map((d) => <li key={d.documento_id}><a href={docUrl(pid, d)} target="_blank" rel="noreferrer">{d.nome}</a> <span className="muted small">— {d.sistema}</span></li>)}</ul>
      </details>
    </div>
  );
}

function Pendencias({ pid, pendencias, aoMudar }: { pid: string; pendencias: Pendencia[]; aoMudar: () => void }) {
  const [texto, setTexto] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  if (!pendencias.length) return null;
  const agir = async (p: Pendencia, status: "resolvida" | "descartada") => {
    setErro(null);
    try { await api.resolver(pid, p.id, status, texto[p.id] ?? ""); aoMudar(); }
    catch (e: any) { setErro(e.message); }
  };
  return (
    <div className="card pend">
      <h4>Pendências escaladas para humano</h4>
      <p className="muted small">O agente não decide no seu lugar: resolva ou descarte com justificativa (nada some sem registro).</p>
      {erro && <div className="alerta">{erro}</div>}
      {pendencias.map((p) => (
        <div key={p.id} className={`pend-item st-${p.status}`}>
          <b>{p.titulo}</b>
          <div className="small muted">{p.contexto}</div>
          {p.status === "aberta" ? (
            <div className="pend-acoes">
              <input placeholder="O que foi feito / por que descartar" value={texto[p.id] ?? ""}
                     onChange={(e) => setTexto({ ...texto, [p.id]: e.target.value })} />
              <button onClick={() => agir(p, "resolvida")} disabled={!texto[p.id]?.trim()}>Resolver</button>
              <button className="sec" onClick={() => agir(p, "descartada")} disabled={!texto[p.id]?.trim()}>Descartar</button>
            </div>
          ) : <div className="small"><span className="tag">{p.status}</span> {p.resolucao}</div>}
        </div>
      ))}
    </div>
  );
}

/* ---------------- Estratégia ---------------- */

function renderMd(pid: string, md: string, cits: Fonte[]) {
  const mapa = new Map(cits.map((c) => [c.ref, c]));
  const seguro = md.replace(/</g, "&lt;");
  const comLinks = seguro.replace(/\[(D\d+(?:\s*,\s*D\d+)*)\]/g, (_, grupo: string) =>
    grupo.split(/\s*,\s*/).map((ref) => {
      const c = mapa.get(ref);
      return c ? `<a class="cit" target="_blank" rel="noreferrer" href="${docUrl(pid, c)}" title="${c.documento}, p. ${c.pagina_inicio}">${c.documento.replace(".pdf", "")} p.${c.pagina_inicio}</a>` : ref;
    }).join(" "));
  return { __html: marked.parse(comLinks, { async: false }) as string };
}

export function VisaoEstrategia({ pid, e }: { pid: string; e: Estrategia }) {
  return (
    <div>
      <div className="sintese">
        <div className="kpis kpis-linha">
          <div><b>{brl(e.valor_total_pleiteado)}</b><span>total pleiteado</span></div>
          <div className="bad"><b>{brl(e.valor_em_risco_alto)}</b><span>em pedidos de risco alto</span></div>
          <div className="warn"><b>{e.pendencias_abertas}</b><span>pendências abertas</span></div>
        </div>
        <p>{e.sintese}</p>
      </div>
      {e.secoes.map((s) => (
        <div key={s.pedido_id} className={`secao risco-${s.risco}`}>
          <div className="secao-cab">
            <h4>{s.titulo}</h4>
            <span className="muted">{brl(s.valor)}</span>
            <span className={`badge r-${s.risco}`}>risco {s.risco}</span>
            {s.exposicao_estimada ? <span className="muted small">exposição estimada {brl(s.exposicao_estimada)}</span> : null}
          </div>
          {s.requer_revisao && <div className="tag tag-warn">revisar: {s.motivos_revisao.join("; ")}</div>}
          <div className="md" dangerouslySetInnerHTML={renderMd(pid, s.markdown, s.citacoes)} />
        </div>
      ))}
    </div>
  );
}

export type { Processo };
