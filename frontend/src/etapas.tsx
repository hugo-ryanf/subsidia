import { marked } from "marked";
import { CSSProperties, ReactNode, useEffect, useState } from "react";
import { Achado, api, brl, docUrl, Estrategia, Fonte, Pendencia, Processo, ResumoAFD, semRotulos, Subsidios, Triagem } from "./api";
import { Barras, I } from "./icones";

/* ---------------- utilidades ---------------- */

const dataBR = (iso?: string | null) => (iso && /^\d{4}-\d{2}-\d{2}/.test(iso) ? iso.slice(0, 10).split("-").reverse().join("/") : iso ?? "—");
export const titulo = (s?: string | null) =>
  (s ?? "").toLowerCase().replace(/(^|\s)(\p{L})/gu, (_, a, b) => a + b.toUpperCase()).replace(/\b(Da|De|Do|Das|Dos|E)\b/g, (m) => m.toLowerCase());
const nomeDoc = (n: string) => n.replace(/\.pdf$/i, "");

function Ev({ pid, f, rotulo }: { pid: string; f: { documento_id: string; pagina_inicio?: number }; rotulo: string }) {
  return (
    <a className="ev" href={docUrl(pid, f)} target="_blank" rel="noreferrer" title="Abrir o PDF">
      <I n="doc" />{rotulo}
    </a>
  );
}

/** Cabeçalho de etapa (título, descrição, ações). */
export function CabEtapa({ nome, desc, children }: { nome: string; desc: string; children?: ReactNode }) {
  return (
    <div className="etapa-cab">
      <div style={{ flex: "1 1 360px", minWidth: 0, display: "flex", flexDirection: "column", gap: 4 }}>
        <h2 id="titulo-etapa" style={{ font: "600 20px/1.25 var(--f-sans)" }}>{nome}</h2>
        <p style={{ color: "var(--muted)", maxWidth: "70ch" }}>{desc}</p>
      </div>
      <div className="row" style={{ gap: 10 }}>{children}</div>
    </div>
  );
}

/* ---------------- Portão humano ---------------- */

export function Portao({ titulo: tit, selos, nota, aprovar, rodar, espera, textoAprovar = "Aprovar e seguir" }: {
  titulo: string; selos: ReactNode; nota: string; aprovar?: () => void; rodar?: () => void; espera?: boolean; textoAprovar?: string;
}) {
  return (
    <section id="portao" aria-labelledby="titulo-portao" className={`portao ${espera ? "espera" : ""}`}>
      <span aria-hidden="true" className="portao-ico"><I n="pessoaOk" style={{ width: 22, height: 22 }} /></span>
      <div style={{ flex: "1 1 380px", minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
        <span className="over" style={{ color: "var(--warn)" }}>Portão humano · {espera ? "aguardando o agente" : "sua decisão"}</span>
        <h3 id="titulo-portao" style={{ font: "600 19px/1.3 var(--f-sans)" }}>{tit}</h3>
        <div className="row" style={{ gap: 6, marginTop: 2 }}>{selos}</div>
        <p style={{ marginTop: 2, fontSize: 12.5, color: "var(--muted)" }}>{nota}</p>
      </div>
      <div className="row" style={{ gap: 10 }}>
        {rodar && !espera && <button type="button" className="btn btn-sec btn-lg" onClick={rodar}><I n="refresh" />Rodar de novo</button>}
        <button type="button" className="btn btn-acc btn-lg" disabled={espera || !aprovar} onClick={aprovar}>
          <I n="check" style={{ width: 18, height: 18 }} />{textoAprovar}
        </button>
      </div>
    </section>
  );
}

/* ---------------- Triagem ---------------- */

export function VisaoTriagem({ pid, t }: { pid: string; t: Triagem }) {
  const p = t.processo;
  const revisar = t.pedidos.filter((x) => x.requer_revisao).length;
  const caixa = (rot: string, val: ReactNode, flex: string, mono = false) => (
    <div className="sunk-box" style={{ flex, minWidth: 0 }}>
      <dt className="over">{rot}</dt>
      <dd className={mono ? "num" : ""} style={mono ? { font: "500 14px/1.35 var(--f-mono)", overflowWrap: "anywhere" } : { fontWeight: 600 }}>{val}</dd>
    </div>
  );
  return (
    <>
      {t.aviso && (
        <p className="row" role="status" style={{ gap: 10, padding: "12px 14px", borderRadius: 10, background: "var(--warn-bg)", border: "1px solid var(--warn-line)", fontSize: 13.5, flexWrap: "nowrap", alignItems: "flex-start" }}>
          <I n="alerta" style={{ color: "var(--warn)", marginTop: 2 }} />{t.aviso}
        </p>
      )}
      <dl className="row" style={{ gap: 12, alignItems: "stretch" }}>
        {caixa("Processo", p.numero ?? "—", "2 1 260px", true)}
        {caixa("Reclamante", titulo(p.reclamante) || "—", "1 1 170px")}
        {caixa("Cargo", p.cargo ? p.cargo[0].toUpperCase() + p.cargo.slice(1) : "—", "1 1 170px")}
        {caixa("Contrato", `${dataBR(p.admissao)} → ${dataBR(p.demissao)}`, "1 1 200px")}
        {caixa("Valor da causa", brl(p.valor_causa), "1 1 170px")}
      </dl>
      <div className="col" style={{ gap: 12 }}>
        <div className="row" style={{ justifyContent: "space-between", gap: "8px 16px" }}>
          <h3 style={{ font: "600 15px/1.3 var(--f-sans)" }}>Pedidos identificados <span className="num" style={{ color: "var(--muted)", fontWeight: 500 }}>({t.pedidos.length})</span></h3>
          <div className="row" style={{ gap: "8px 14px", fontSize: 12.5, color: "var(--muted)" }}>
            {revisar > 0 ? <span className="badge t-warn"><I n="alerta" />{revisar} pedido(s) para revisar</span>
              : <span className="badge t-ok"><I n="checkC" />nenhum pedido com confiança baixa</span>}
            <span>Clique numa fonte para abrir o PDF na página</span>
          </div>
        </div>
        <div style={{ overflowX: "auto", border: "1px solid var(--line)", borderRadius: 10 }}>
          <table className="tbl" style={{ minWidth: 820 }}>
            <thead><tr><th style={{ width: "40%" }}>Pedido</th><th>Categoria</th><th style={{ textAlign: "right" }}>Valor</th><th>Confiança</th><th>Fonte</th></tr></thead>
            <tbody>
              {t.pedidos.map((x) => {
                const pct = Math.round(x.confianca * 100);
                return (
                  <tr key={x.id} className={x.requer_revisao ? "row-rev" : ""}>
                    <td>
                      <div className="col" style={{ gap: 3 }}>
                        <span style={{ fontWeight: 600 }}>{x.titulo}</span>
                        {x.alegacao && <span style={{ fontSize: 13, lineHeight: 1.45, color: "var(--muted)" }}>{x.alegacao}</span>}
                        {x.requer_revisao && <span className="badge t-warn" style={{ alignSelf: "flex-start", marginTop: 6, background: "var(--surface)" }}><I n="alerta" />revisar: {x.motivos_revisao.join("; ")}</span>}
                      </div>
                    </td>
                    <td style={{ fontSize: 13.5, color: "var(--muted)" }}>{x.arquetipo_nome ?? "—"}</td>
                    <td className="num" style={{ textAlign: "right", fontWeight: 600, whiteSpace: "nowrap" }}>{brl(x.valor)}</td>
                    <td>
                      <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
                        <span aria-hidden="true" className="conf" style={x.requer_revisao ? { background: "var(--surface)" } : undefined}>
                          <span style={{ width: `${pct}%`, background: x.requer_revisao ? "var(--warn)" : undefined }} />
                        </span>
                        <span className="num" style={{ font: `${x.requer_revisao ? 600 : 500} 13px/1 var(--f-mono)`, color: x.requer_revisao ? "var(--warn)" : undefined }}>{pct}%</span>
                      </div>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 6 }}>
                        {x.fontes.length === 0 && <span className="badge t-warn">sem citação</span>}
                        {dedupFontes(x.fontes).map((f, i) => <Ev key={f.ref} pid={pid} f={f} rotulo={`${i === 0 ? nomeDoc(f.documento) + " " : ""}p.${f.pagina_inicio}`} />)}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

const dedupFontes = (fs: Fonte[]) => fs.filter((f, i) => fs.findIndex((g) => g.documento_id === f.documento_id && g.pagina_inicio === f.pagina_inicio) === i);

/* ---------------- Fonte do ponto (AFD) ---------------- */

export function FontePonto({ pid, coletaEm, aoImportar }: { pid: string; coletaEm?: string; aoImportar?: () => void }) {
  const [resumo, setResumo] = useState<ResumoAFD | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => { api.afd(pid).then((r) => setResumo(r.importado)).catch(() => {}); }, [pid]);
  const importar = async (f: File | undefined) => {
    if (!f) return;
    setOcupado(true); setErro(null);
    try { setResumo(await api.importarAfd(pid, f)); aoImportar?.(); } catch (e: any) { setErro(e.message); }
    setOcupado(false);
  };
  const cel = (rot: string, val: ReactNode, mono = false) => (
    <div style={{ flex: "1 1 150px", minWidth: 0, background: "var(--surface)", padding: "10px 14px", display: "flex", flexDirection: "column", gap: 3 }}>
      <dt className="over">{rot}</dt>
      <dd style={mono ? { font: "500 13px/1.35 var(--f-mono)", overflowWrap: "anywhere" } : { fontSize: 13.5, fontWeight: 500 }}>{val}</dd>
    </div>
  );
  const mes = (d: string) => `${d.slice(5, 7)}/${d.slice(0, 4)}`;
  return (
    <section aria-labelledby="titulo-afd" style={{ border: "1px solid var(--line)", borderRadius: 12, padding: "18px 20px", display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="row" style={{ justifyContent: "space-between", gap: 12 }}>
        <div className="row" style={{ gap: "10px 14px", minWidth: 0 }}>
          <h3 id="titulo-afd" style={{ font: "600 15px/1.3 var(--f-sans)" }}>Fonte do ponto</h3>
          <div aria-label="Fonte do ponto em uso" style={{ display: "inline-flex", flexWrap: "wrap", gap: 2, padding: 3, borderRadius: 9, background: "var(--sunk)", border: "1px solid var(--line)" }}>
            <span className={resumo ? "seg" : "seg seg-on"} style={{ display: "inline-flex", alignItems: "center" }}>Sistema de ponto da empresa (simulado)</span>
            <span className={resumo ? "seg seg-on" : "seg"} style={{ display: "inline-flex", alignItems: "center" }}>AFD importado</span>
          </div>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <a className="btn btn-ghost" href="/rh/demo/afd.txt" style={{ minHeight: 36, padding: "0 10px", fontSize: 13, fontWeight: 500 }}><I n="download" />baixar AFD de exemplo</a>
          <label className={`btn btn-sec botao-arquivo`} style={{ minHeight: 36 }} aria-disabled={ocupado}>
            {ocupado ? <><I n="arco" />Lendo…</> : <><I n="upload" />{resumo ? "Importar outro AFD" : "Importar AFD"}</>}
            <input type="file" accept=".txt,.afd,text/plain" disabled={ocupado} onChange={(e) => importar(e.target.files?.[0])} />
          </label>
        </div>
      </div>
      <p style={{ fontSize: 13.5, lineHeight: 1.55, color: "var(--muted)", maxWidth: "90ch" }}>
        O AFD é o arquivo que todo relógio de ponto é obrigado a exportar (Portarias 1510/2009 e 671/2021). Importado, o agente lê as marcações originais do relógio, sem integrar com o fabricante.
      </p>
      {erro && <div className="alerta" role="alert"><I n="xC" style={{ color: "var(--bad)" }} />{erro}</div>}
      {resumo ? (
        <>
          <dl style={{ display: "flex", flexWrap: "wrap", gap: 1, border: "1px solid var(--line)", borderRadius: 10, overflow: "hidden", background: "var(--line)" }}>
            {cel("Arquivo", resumo.arquivo, true)}
            {cel("Layout", resumo.layout)}
            {cel("CNPJ", resumo.cnpj ?? "—", true)}
            {cel("Marcações", `${resumo.marcacoes.toLocaleString("pt-BR")} de ${resumo.empregados} empregado(s)`)}
            {cel("Período", resumo.periodo ? `${mes(resumo.periodo[0])} → ${mes(resumo.periodo[1])}` : "—")}
            {cel("NSR", `${String(resumo.nsr[0]).padStart(9, "0")} → ${String(resumo.nsr[1]).padStart(9, "0")}`, true)}
          </dl>
          <div className="row" style={{ gap: 8 }}>
            {resumo.dias_com_batida_impar > 0 && <span className="badge t-warn"><I n="alerta" />{resumo.dias_com_batida_impar} dia(s) com batida faltando</span>}
            {resumo.total_linhas_nao_lidas > 0 && <span className="badge t-warn"><I n="alerta" />{resumo.total_linhas_nao_lidas} linha(s) não lidas</span>}
            <span className="badge t-neu"><I n="menosC" />CRC não validado nesta versão</span>
          </div>
          {coletaEm && resumo.importado_em && coletaEm < resumo.importado_em && (
            <p style={{ padding: "10px 14px", borderRadius: 10, background: "var(--warn-bg)", border: "1px solid var(--warn-line)", fontSize: 13.5 }}>
              A coleta abaixo rodou com a fonte anterior. Use <b>Rodar de novo</b> para refazer lendo o AFD.
            </p>
          )}
        </>
      ) : (
        <p style={{ padding: "12px 14px", borderRadius: 10, background: "var(--sunk)", fontSize: 13.5, color: "var(--muted)" }}>
          Usando os espelhos do sistema de ponto da empresa (simulado). Importe o AFD para o agente ler as marcações originais do relógio.
        </p>
      )}
    </section>
  );
}

/* ---------------- Coleta de subsídios ---------------- */

const TIPO_ACH: Record<string, { cls: string; badge: string; badgeCls: string; icon: "alerta" | "pessoa" | "checkC" | "menosC" | "pessoaOk" }> = {
  divergencia: { cls: "ach-risco", badge: "Risco", badgeCls: "t-solid-bad", icon: "alerta" },
  pendencia: { cls: "ach-pend", badge: "Pendência", badgeCls: "t-warn", icon: "pessoa" },
  favoravel: { cls: "ach-favor", badge: "A favor", badgeCls: "t-ok", icon: "checkC" },
  cobertura: { cls: "ach-nv", badge: "Não verificado", badgeCls: "t-neu", icon: "menosC" },
  resolvida: { cls: "ach-res", badge: "Pendência resolvida", badgeCls: "t-ok", icon: "pessoaOk" },
};
const PESO: Record<string, number> = { divergencia: 0, pendencia: 1, cobertura: 2, favoravel: 3, resolvida: 4 };

export function VisaoSubsidios({ pid, s, tri, pendencias, aoMudar }: {
  pid: string; s: Subsidios; tri: Triagem; pendencias: Pendencia[]; aoMudar: () => void;
}) {
  if (s.bloqueado) return <div className="alerta" role="alert"><I n="xC" style={{ color: "var(--bad)" }} />Coleta bloqueada: {s.motivo}</div>;
  const r = s.resumo;
  const abertas = pendencias.filter((p) => p.status === "aberta").length;
  const tipoDe = (a: Achado) => (a.tipo === "pendencia" && pendencias.some((p) => p.titulo === a.titulo && p.status !== "aberta") ? "resolvida" : a.tipo);
  const pedidos = tri.pedidos.map((p) => {
    const achs = s.achados.filter((a) => a.pedido_id === p.id).map((a) => ({ a, tipo: tipoDe(a) }))
      .sort((x, y) => PESO[x.tipo] - PESO[y.tipo]);
    const nota = Math.min(...achs.map((x) => PESO[x.tipo]), 9);
    return { p, achs, nota, col: s.coletas.find((c) => c.pedido_id === p.id) };
  }).sort((x, y) => x.nota - y.nota);

  const kpi = (n: ReactNode, l: ReactNode, cls: string, extra?: CSSProperties) => (
    <div className={`kpi ${cls}`} style={{ flex: "1 1 150px", minWidth: 0, ...extra }}><span className="kpi-n">{n}</span><span className="kpi-l">{l}</span></div>
  );
  return (
    <>
      <div className="row" style={{ gap: 12, alignItems: "stretch" }}>
        {kpi(<span style={{ color: "var(--ink)" }}>{r.documentos_coletados}</span>, "documentos coletados nos sistemas", "t-neu")}
        {kpi(r.favoraveis, <><I n="checkC" />provas a favor</>, "t-ok")}
        {kpi(r.divergencias, <><I n="alerta" />divergência(s) (risco)</>, "t-bad")}
        {kpi(r.pendencias, <><I n="pessoa" />pendências para humano · {abertas} aberta(s)</>, "t-warn")}
        <div className="kpi" style={{ flex: "1.5 1 220px", minWidth: 0, ["--t" as any]: "var(--bad)", ["--tb" as any]: "var(--surface)", ["--tl" as any]: "var(--bad-line)", borderWidth: 1.5 }}>
          <span className="kpi-n" style={{ fontSize: 30 }}>{brl(r.exposicao_estimada)}</span>
          <span className="kpi-l" style={{ fontWeight: 600 }}>exposição estimada (principal)</span>
        </div>
      </div>

      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", gap: "6px 16px", marginTop: 4 }}>
        <h3 style={{ font: "600 17px/1.3 var(--f-sans)" }}>Achados por pedido</h3>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>Ordenados por gravidade: risco e pendência primeiro</span>
      </div>

      {pedidos.map(({ p, achs, col }) => {
        const conta = (t: string) => achs.filter((x) => x.tipo === t).length;
        const tally: [string, string][] = [
          ["t-solid-bad", `${conta("divergencia")} risco`], ["t-warn", `${conta("pendencia")} pendência(s)`],
          ["t-neu", `${conta("cobertura")} não verificado`], ["t-ok", `${conta("favoravel")} a favor`],
          ["t-neu", `${conta("resolvida")} pendência resolvida`],
        ].filter(([, l]) => !l.startsWith("0 ")) as [string, string][];
        const passos = (col?.passos ?? []).filter((x) => x.acao !== "concluir");
        const playbook = col?.modo === "playbook";
        const pensa = col?.resumo && !col.resumo.startsWith("encerrado pelo guarda") && !playbook ? col.resumo
          : [...passos].reverse().find((x) => x.pensamento && !x.pensamento.startsWith("playbook"))?.pensamento;
        return (
          <article key={p.id} className="pedido">
            <header>
              <div className="row" style={{ alignItems: "baseline", gap: "4px 12px", minWidth: 0 }}>
                <h4 style={{ font: "600 17px/1.3 var(--f-sans)" }}>{p.titulo}</h4>
                <span className="num" style={{ font: "500 14px/1 var(--f-mono)", color: "var(--muted)" }}>{brl(p.valor)}</span>
              </div>
              <div className="row" style={{ gap: 6 }}>{tally.map(([c, l]) => <span key={l} className={`badge ${c}`}>{l}</span>)}</div>
            </header>
            {col && (
              <div className="trilha">
                <div className="row" style={{ gap: "6px 12px" }}>
                  <span className="over">Passos do agente</span>
                  {playbook && <span className="badge t-neu" style={{ background: "var(--surface)" }}>coletado pelo playbook (modelo indisponível)</span>}
                  {!col.concluido && <span className="badge t-warn" style={{ background: "var(--surface)" }}>não concluído</span>}
                </div>
                <div className="row" style={{ gap: 6, color: "var(--muted)" }}>
                  {passos.length === 0 && <span style={{ fontSize: 13 }}>nenhuma consulta: o agente concluiu com o que já tinha</span>}
                  {passos.map((ps, i) => {
                    const tom = ps.acao === "abrir_pendencia" ? "warn" : ps.observacao?.startsWith("SISTEMA INDISPONÍVEL") ? "bad" : playbook ? "neu" : "pri";
                    return (
                      <span key={i} className="row" style={{ gap: 6 }}>
                        <button type="button" className={`step t-${tom}`} style={{ cursor: "help" }}
                                title={`${ps.pensamento ? `Pensamento: ${ps.pensamento}\n` : ""}Resultado: ${ps.observacao}`}>{ps.acao}</button>
                        {i < passos.length - 1 && <I n="chevD" style={{ width: 13, height: 13 }} />}
                      </span>
                    );
                  })}
                </div>
                {pensa && <p className="pensa"><I n="placa" style={{ width: 14, height: 14, marginTop: 2 }} />“{pensa}”</p>}
              </div>
            )}
            <div className="col" style={{ gap: 10, padding: "16px 20px 20px" }}>
              {achs.length === 0 && <p style={{ fontSize: 13, color: "var(--muted)" }}>Nenhum achado do cruzamento para este pedido.</p>}
              {achs.map(({ a, tipo }, i) => {
                const T = TIPO_ACH[tipo];
                const pend = pendencias.find((q) => q.titulo === a.titulo);
                return (
                  <div key={i} className={`ach ${T.cls}`}>
                    <div className="row" style={{ alignItems: "flex-start", justifyContent: "space-between", gap: "8px 16px" }}>
                      <div className="row" style={{ flex: "1 1 360px", minWidth: 0, gap: "8px 10px" }}>
                        <span className={`badge ${T.badgeCls}`}><I n={T.icon} />{T.badge}</span>
                        <h5 className="ach-t">{a.titulo}</h5>
                      </div>
                      {a.exposicao_estimada ? (
                        <span className="col" style={{ alignItems: "flex-end", gap: 2 }}>
                          <span className="num" style={{ font: "600 19px/1.1 var(--f-sans)", color: "var(--bad)" }}>{brl(a.exposicao_estimada)}</span>
                          <span style={{ fontSize: 12, color: "var(--muted)" }}>exposição estimada</span>
                        </span>
                      ) : null}
                      {tipo === "pendencia" && (
                        <a href="#pendencias" className="btn btn-sec" style={{ minHeight: 32, padding: "0 10px", fontSize: 12.5 }}>Resolver<I n="setaB" style={{ width: 13, height: 13 }} /></a>
                      )}
                    </div>
                    <p className="ach-p">{tipo === "resolvida" && pend?.resolucao ? `Resolvida: ${pend.resolucao}` : a.detalhe}</p>
                    {a.evidencias.length > 0 && (
                      <div className="row" style={{ gap: 6 }}>
                        {a.evidencias.slice(0, 8).map((e) => <Ev key={e.documento_id} pid={pid} f={e} rotulo={nomeDoc(e.nome)} />)}
                        {a.evidencias.length > 8 && <span style={{ fontSize: 12.5, color: "var(--muted)" }}>+{a.evidencias.length - 8} documentos</span>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </article>
        );
      })}

      <Pendencias pid={pid} pendencias={pendencias} pedidos={tri.pedidos} aoMudar={aoMudar} />

      <details style={{ border: "1px solid var(--line)", borderRadius: 12, overflow: "hidden" }}>
        <summary className="row" style={{ justifyContent: "space-between", gap: 12, minHeight: 52, padding: "0 20px", cursor: "pointer", flexWrap: "nowrap" }}>
          <span className="row" style={{ gap: 10, fontWeight: 600 }}><I n="docLinhas" />Documentos coletados <span className="num" style={{ fontWeight: 500, color: "var(--muted)" }}>({s.documentos.length})</span></span>
          <span className="row" style={{ gap: 6, fontSize: 13, fontWeight: 500, color: "var(--pri)" }}>mostrar<I n="chevB" cls="chev" /></span>
        </summary>
        <ul className="docs-lista">
          {s.documentos.map((d) => (
            <li key={d.documento_id}>
              <a href={docUrl(pid, d)} target="_blank" rel="noreferrer" style={{ font: "500 12.5px/1.3 var(--f-mono)", overflowWrap: "anywhere", color: "var(--pri)" }}>{d.nome}</a>
              <span style={{ fontSize: 12.5, color: "var(--muted)" }}>{d.sistema}</span>
            </li>
          ))}
        </ul>
      </details>
    </>
  );
}

function Pendencias({ pid, pendencias, pedidos, aoMudar }: { pid: string; pendencias: Pendencia[]; pedidos: Triagem["pedidos"]; aoMudar: () => void }) {
  const [texto, setTexto] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  if (!pendencias.length) return null;
  const abertas = pendencias.filter((p) => p.status === "aberta");
  const feitas = pendencias.filter((p) => p.status !== "aberta");
  const agir = async (p: Pendencia, status: "resolvida" | "descartada") => {
    setErro(null);
    try { await api.resolver(pid, p.id, status, (texto[p.id] ?? "").trim()); aoMudar(); }
    catch (e: any) { setErro(e.message); }
  };
  const origem = (ctx: string) => ctx.match(/^\[(\w+)\]/)?.[1];
  const semOrigem = (ctx: string) => ctx.replace(/^\[\w+\]\s*/, "");
  const pedidoDe = (id: string | null) => pedidos.find((x) => x.id === id)?.titulo;
  return (
    <section id="pendencias" aria-labelledby="titulo-pend" className="pend-box">
      <div className="row" style={{ alignItems: "flex-start", gap: 14 }}>
        <span aria-hidden="true" style={{ width: 44, height: 44, flex: "none", borderRadius: 12, display: "grid", placeItems: "center", background: "var(--surface)", border: "1px solid var(--acc-line)", color: "var(--warn)" }}><I n="pessoa" style={{ width: 20, height: 20 }} /></span>
        <div style={{ flex: "1 1 360px", minWidth: 0, display: "flex", flexDirection: "column", gap: 3 }}>
          <span className="over" style={{ color: "var(--warn)" }}>Portão humano · {abertas.length} aberta(s)</span>
          <h3 id="titulo-pend" style={{ font: "600 18px/1.3 var(--f-sans)" }}>Pendências escaladas para humano</h3>
          <p style={{ fontSize: 13.5, lineHeight: 1.55, color: "var(--muted)" }}>O agente não decide no seu lugar: resolva ou descarte com justificativa (nada some sem registro).</p>
        </div>
      </div>
      {erro && <div className="alerta" role="alert"><I n="xC" style={{ color: "var(--bad)" }} />{erro}</div>}
      {abertas.length > 0 && (
        <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
          {abertas.map((p) => {
            const vazio = !(texto[p.id] ?? "").trim();
            return (
              <li key={p.id} className="pend-item">
                <div className="row" style={{ alignItems: "flex-start", justifyContent: "space-between", gap: "8px 16px" }}>
                  <div style={{ flex: "1 1 360px", minWidth: 0, display: "flex", flexDirection: "column", gap: 4 }}>
                    <h4 style={{ font: "600 15px/1.35 var(--f-sans)" }}>{p.titulo}</h4>
                    <p style={{ fontSize: 13.5, lineHeight: 1.55, color: "var(--muted)", maxWidth: "80ch" }}>{semOrigem(p.contexto)}</p>
                  </div>
                  <div className="row" style={{ gap: 6 }}>
                    {pedidoDe(p.pedido_id) && <span className="badge t-neu">{pedidoDe(p.pedido_id)}</span>}
                    {origem(p.contexto) && <span className="badge t-neu">origem: {origem(p.contexto)}</span>}
                  </div>
                </div>
                <div className="row" style={{ alignItems: "flex-end", gap: 10 }}>
                  <label htmlFor={`just-${p.id}`} style={{ flex: "1 1 380px", minWidth: 0, display: "flex", flexDirection: "column", gap: 6, fontSize: 12.5, fontWeight: 600 }}>
                    O que foi feito / por que descartar
                    <textarea id={`just-${p.id}`} className="inp" rows={2} placeholder="Ex.: folha de ponto manual de junho localizada e anexada"
                              value={texto[p.id] ?? ""} onChange={(e) => setTexto({ ...texto, [p.id]: e.target.value })} />
                  </label>
                  <div className="row" style={{ gap: 8 }}>
                    <button type="button" className="btn btn-pri" disabled={vazio} onClick={() => agir(p, "resolvida")}><I n="check" />Resolver</button>
                    <button type="button" className="btn btn-sec" disabled={vazio} onClick={() => agir(p, "descartada")}>Descartar</button>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {feitas.length > 0 && (
        <div className="col" style={{ gap: 8 }}>
          <span className="over">Resolvidas e descartadas</span>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
            {feitas.map((p) => (
              <li key={p.id} className="row" style={{ gap: "6px 12px", padding: "12px 16px", borderRadius: 10, border: "1px dashed var(--line-2)", background: "var(--surface)" }}>
                <span className={`badge ${p.status === "resolvida" ? "t-ok" : "t-neu"}`}>{p.status}</span>
                <span style={{ flex: "1 1 260px", minWidth: 0, fontWeight: 600, color: "var(--muted)" }}>{p.titulo}</span>
                <span style={{ flex: "1 1 100%", fontSize: 13, lineHeight: 1.5 }}>{p.resolucao}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/* ---------------- Estratégia ---------------- */

type Bloco = { chave: "tese" | "prova" | "fracos" | "rec" | "outro"; titulo: string; texto: string[]; itens: string[] };

function blocos(md: string): Bloco[] {
  const out: Bloco[] = [];
  let atual: Bloco | null = null;
  for (const bruta of md.split(/\r?\n/)) {
    const l = bruta.trim();
    const cab = l.match(/^(?:#{1,6}\s*(.+?)|\*\*(.+?)\*\*:?)\s*$/);
    if (cab) {
      const t = (cab[1] ?? cab[2]).replace(/[*:]/g, "").trim();
      const n = t.toLowerCase();
      const chave: Bloco["chave"] = n.includes("tese") ? "tese" : n.includes("fraco") || n.includes("vulnera") ? "fracos"
        : n.includes("prova") || n.includes("favor") ? "prova" : n.includes("recomenda") ? "rec" : "outro";
      atual = { chave, titulo: t, texto: [], itens: [] }; out.push(atual); continue;
    }
    if (!l) continue;
    if (!atual) { atual = { chave: "outro", titulo: "", texto: [], itens: [] }; out.push(atual); }
    const item = l.match(/^(?:[-*•]|\d+[.)])\s+(.*)$/);
    if (item) atual.itens.push(item[1]); else atual.texto.push(l);
  }
  return out;
}

const CIT = /\[(D\d+(?:\s*[,;]\s*D\d+)*)\]/g;

/** Numera as fontes na ordem em que aparecem e troca [D3, D5] por chips clicáveis. */
function citador(pid: string, md: string, cits: Fonte[]) {
  const mapa = new Map(cits.map((c) => [c.ref, c]));
  const ordem: Fonte[] = [];
  for (const m of md.matchAll(CIT)) for (const ref of m[1].split(/\s*[,;]\s*/)) {
    const c = mapa.get(ref);
    if (c && !ordem.includes(c)) ordem.push(c);
  }
  const html = (s: string) => {
    const seguro = semRotulos(s).replace(/</g, "&lt;");
    const comCit = seguro.replace(CIT, (_, g: string) => g.split(/\s*[,;]\s*/).map((ref) => {
      const c = mapa.get(ref);
      if (!c) return "";
      const n = ordem.indexOf(c) + 1;
      return `<a class="cite" href="${docUrl(pid, c)}" target="_blank" rel="noreferrer" title="${nomeDoc(c.documento)} · p.${c.pagina_inicio}" aria-label="Fonte ${n}: ${nomeDoc(c.documento)}, página ${c.pagina_inicio}">${n}</a>`;
    }).join(""));
    return { __html: marked.parseInline(comCit, { async: false }) as string };
  };
  return { ordem, html };
}

const RISCO = {
  alto: { cls: "t-solid-bad", rot: "Risco alto" }, medio: { cls: "t-warn", rot: "Risco médio" }, baixo: { cls: "t-ok", rot: "Risco baixo" },
} as const;
const PESO_RISCO = { alto: 0, medio: 1, baixo: 2 } as const;

const curta = (s: string) => {
  const limpa = semRotulos(s).replace(CIT, "").replace(/\*\*/g, "").replace(/\s+/g, " ").trim();
  const frase = limpa.split(/(?<=[.;])\s/)[0].replace(/[.;]$/, "");
  const r = frase.length > 150 ? frase.slice(0, 147).replace(/\s\S*$/, "") + "…" : frase;
  return r ? r[0].toLowerCase() + r.slice(1) + (r.endsWith("…") ? "" : ".") : "";
};

export function VisaoEstrategia({ pid, e, documentos }: { pid: string; e: Estrategia; documentos: number }) {
  const secoes = [...e.secoes].sort((a, b) => PESO_RISCO[a.risco] - PESO_RISCO[b.risco]);
  const temAlto = secoes.some((s) => s.risco === "alto");
  const sintese = semRotulos(e.sintese).split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  return (
    <>
      <div className="row" style={{ gap: 12, alignItems: "stretch" }}>
        <div className="kpi t-neu" style={{ flex: "1 1 180px", minWidth: 0 }}><span className="kpi-n" style={{ color: "var(--ink)" }}>{brl(e.valor_total_pleiteado)}</span><span className="kpi-l">total pleiteado</span></div>
        <div className="kpi t-bad" style={{ flex: "1 1 180px", minWidth: 0 }}><span className="kpi-n">{brl(e.valor_em_risco_alto)}</span><span className="kpi-l"><I n="alerta" />em pedidos de risco alto</span></div>
        <div className="kpi t-warn" style={{ flex: "1 1 180px", minWidth: 0 }}><span className="kpi-n">{e.pendencias_abertas}</span><span className="kpi-l"><I n="pessoa" />pendências abertas quando a estratégia foi escrita</span></div>
      </div>

      <section aria-labelledby="titulo-sintese" style={{ display: "flex", flexDirection: "column", gap: 10, padding: "22px 24px", borderRadius: 12, background: "var(--sunk)", border: "1px solid var(--line)" }}>
        <span id="titulo-sintese" className="over">Síntese executiva</span>
        {sintese.map((p, i) => <p key={i} style={{ font: "400 18px/1.7 var(--f-serif)", maxWidth: "72ch", textWrap: "pretty" } as CSSProperties}>{p}</p>)}
        <span style={{ fontSize: 12.5, color: "var(--muted)" }}>Escrita pelo agente a partir de {e.secoes.length} pedidos e {documentos} documentos. Cada número nas seções abre o PDF na página citada.</span>
      </section>

      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", gap: "6px 16px" }}>
        <h3 style={{ font: "600 17px/1.3 var(--f-sans)" }}>Por pedido</h3>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>Do maior para o menor risco</span>
      </div>

      <div className="col" style={{ gap: 12 }}>
        {secoes.map((s, i) => {
          const bs = blocos(s.markdown);
          const { ordem, html } = citador(pid, s.markdown, s.citacoes);
          const pega = (k: Bloco["chave"]) => bs.find((b) => b.chave === k);
          const tese = pega("tese"), prova = pega("prova"), fracos = pega("fracos"), rec = pega("rec");
          const estruturado = !!(tese || prova || fracos || rec);
          const recTexto = rec ? [...rec.texto, ...rec.itens].join(" ") : "";
          const R = RISCO[s.risco];
          const lista = (b?: Bloco) => (b ? [...b.texto, ...b.itens] : []);
          return (
            <details key={s.pedido_id} className="sec" open={s.risco === "alto" || (!temAlto && i === 0)}>
              <summary className="sec-h">
                <span style={{ flex: "1 1 420px", minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                  <span className="row" style={{ gap: "8px 12px" }}>
                    <span className={`badge ${R.cls}`}><Barras nivel={s.risco} />{R.rot}</span>
                    <span style={{ font: "600 18px/1.3 var(--f-sans)" }}>{s.titulo}</span>
                    <span className="num" style={{ font: "500 14px/1 var(--f-mono)", color: "var(--muted)" }}>{brl(s.valor)}</span>
                  </span>
                  {recTexto && <span style={{ fontSize: 13.5, lineHeight: 1.5, color: "var(--muted)" }}><strong style={{ fontWeight: 600, color: "var(--ink)" }}>Recomendação:</strong> {curta(recTexto)}</span>}
                </span>
                <span className="row" style={{ gap: 18, flexWrap: "nowrap" }}>
                  {s.exposicao_estimada ? (
                    <span className="col" style={{ alignItems: "flex-end", gap: 2 }}>
                      <span className="num" style={{ font: "600 19px/1.1 var(--f-sans)", color: "var(--bad)" }}>{brl(s.exposicao_estimada)}</span>
                      <span style={{ fontSize: 12, color: "var(--muted)" }}>exposição estimada</span>
                    </span>
                  ) : null}
                  <span aria-hidden="true" style={{ width: 32, height: 32, borderRadius: 8, display: "grid", placeItems: "center", border: "1px solid var(--line)", color: "var(--muted)" }}><I n="chevB" cls="chev" /></span>
                </span>
              </summary>
              <div className="sec-b">
                {s.requer_revisao && <span className="badge t-warn" style={{ alignSelf: "flex-start", height: "auto", minHeight: 24, whiteSpace: "normal", padding: "4px 9px" }}><I n="alerta" />revisar: {s.motivos_revisao.join("; ")}</span>}
                {!estruturado && <div className="lei" dangerouslySetInnerHTML={{ __html: marked.parse(semRotulos(s.markdown).replace(/</g, "&lt;"), { async: false }) as string }} />}
                {tese && (
                  <div className="col" style={{ gap: 8 }}>
                    <span className="over">Tese de defesa</span>
                    <div className="lei">{lista(tese).map((t, k) => <p key={k} dangerouslySetInnerHTML={html(t)} />)}</div>
                  </div>
                )}
                {(prova || fracos) && (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(300px,100%),1fr))", gap: 12 }}>
                    <div style={{ padding: "14px 16px 16px", borderRadius: 10, background: "var(--ok-bg)", border: "1px solid var(--ok-line)" }}>
                      <span className="over" style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--ok)" }}><I n="checkC" />Prova a favor</span>
                      <ul className="bul">{lista(prova).length ? lista(prova).map((t, k) => <li key={k} dangerouslySetInnerHTML={html(t)} />) : <li>Nenhuma prova documental a favor.</li>}</ul>
                    </div>
                    <div style={{ padding: "14px 16px 16px", borderRadius: 10, background: "var(--bad-bg)", border: "1px solid var(--bad-line)" }}>
                      <span className="over" style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--bad)" }}><I n="alerta" />Pontos fracos</span>
                      <ul className="bul">{lista(fracos).length ? lista(fracos).map((t, k) => <li key={k} dangerouslySetInnerHTML={html(t)} />) : <li>Nenhum identificado.</li>}</ul>
                    </div>
                  </div>
                )}
                {rec && (
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "16px 18px", borderRadius: 10, background: "var(--pri-soft)", border: "1px solid var(--pri-line)" }}>
                    <I n="placa" style={{ color: "var(--pri)", marginTop: 2 }} />
                    <div className="col" style={{ gap: 4, minWidth: 0 }}>
                      <span className="over" style={{ color: "var(--pri)" }}>Recomendação do agente</span>
                      {lista(rec).map((t, k) => <p key={k} style={{ font: "500 16px/1.6 var(--f-serif)", maxWidth: "74ch" }} dangerouslySetInnerHTML={html(t)} />)}
                      <span style={{ fontSize: 12.5, color: "var(--muted)" }}>A decisão final é do advogado.</span>
                    </div>
                  </div>
                )}
                {ordem.length > 0 && (
                  <div className="col" style={{ gap: 8 }}>
                    <span className="over">Fontes citadas</span>
                    <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(min(280px,100%),1fr))", gap: 6 }}>
                      {ordem.map((f, k) => (
                        <li key={f.ref}>
                          <a className="fonte" href={docUrl(pid, f)} target="_blank" rel="noreferrer">
                            <span className="cite" aria-hidden="true" style={{ marginLeft: 0, verticalAlign: 0 }}>{k + 1}</span>
                            <span style={{ font: "500 12.5px/1.3 var(--f-mono)" }}>{nomeDoc(f.documento)}</span>
                            <span style={{ color: "var(--muted)" }}>p.{f.pagina_inicio}{f.pagina_fim > f.pagina_inicio ? `–${f.pagina_fim}` : ""}</span>
                            <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12.5, fontWeight: 500, color: "var(--pri)" }}>abrir PDF<I n="externo" style={{ width: 13, height: 13 }} /></span>
                          </a>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            </details>
          );
        })}
      </div>
    </>
  );
}

export type { Processo };
