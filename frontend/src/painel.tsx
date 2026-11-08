import { useState } from "react";
import { Evento, hora, horaSeg, Job, num, Rastro } from "./api";
import { I, NomeIcone } from "./icones";

/* ---------------- Custo e ganho ---------------- */

export function Metricas({ rastro, segundosAgente, minutosManual, aoVivo }: {
  rastro: Rastro | null; segundosAgente?: number; minutosManual?: number; aoVivo?: boolean;
}) {
  const t = rastro?.totais;
  const temGanho = segundosAgente != null && minutosManual != null && !aoVivo;
  const minAgente = (segundosAgente ?? 0) / 60;
  const fator = temGanho && minAgente > 0 ? Math.round((minutosManual ?? 0) / minAgente) : null;
  const larg = temGanho && minutosManual ? Math.max(1.5, (minAgente / minutosManual) * 100) : 0;
  const item = (v: string, l: string) => (
    <div style={{ background: "var(--surface)", padding: "12px 14px", display: "flex", flexDirection: "column-reverse", gap: 2 }}>
      <dt style={{ fontSize: 12, color: "var(--muted)" }}>{l}</dt>
      <dd className="num" style={{ margin: 0, font: "600 18px/1.2 var(--f-sans)" }}>{v}</dd>
    </div>
  );
  return (
    <section className="card" aria-labelledby="titulo-custo" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
        <h2 id="titulo-custo" style={{ font: "600 15px/1.3 var(--f-sans)" }}>Custo e ganho</h2>
        {aoVivo
          ? <span className="row" style={{ gap: 6, fontSize: 12, color: "var(--ok)", fontWeight: 600 }}><span className="pulse" style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--ok)" }} />ao vivo</span>
          : <span style={{ fontSize: 12, color: "var(--muted)" }}>neste processo</span>}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: "16px 18px", borderRadius: 10, background: "var(--con)", border: "1px solid var(--con-line)", color: "var(--on-con)" }}>
        <span className="over" style={{ color: "var(--con-muted)" }}>Coleta de subsídios</span>
        {temGanho ? (
          <>
            <div className="col" style={{ gap: 6 }}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                <span className="num" style={{ font: "600 30px/1 var(--f-sans)", letterSpacing: "-0.02em" }}>{num(minAgente)} min</span>
                <span style={{ fontSize: 13, color: "var(--con-muted)" }}>pelo agente</span>
              </div>
              <span aria-hidden="true" style={{ display: "block", height: 8, borderRadius: 4, background: "rgba(255,255,255,.08)" }}>
                <span style={{ display: "block", width: `${larg}%`, minWidth: 6, height: "100%", borderRadius: 4, background: "var(--con-ok)" }} />
              </span>
            </div>
            <div className="col" style={{ gap: 6 }}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                <span className="num" style={{ font: "600 30px/1 var(--f-sans)", letterSpacing: "-0.02em" }}>~{num((minutosManual ?? 0) / 60)} h</span>
                <span style={{ fontSize: 13, color: "var(--con-muted)" }}>a mesma coleta à mão</span>
              </div>
              <span aria-hidden="true" style={{ display: "block", height: 8, borderRadius: 4, background: "var(--con-muted)" }} />
            </div>
            <span style={{ fontSize: 12.5, color: "var(--con-muted)" }}>
              {fator ? `≈ ${fator}× menos tempo de analista · ` : ""}estimativa: um analista abrindo cada sistema
            </span>
          </>
        ) : (
          <span style={{ fontSize: 13, color: "var(--con-muted)", lineHeight: 1.5 }}>
            {aoVivo ? "O agente está trabalhando: o tempo e a comparação com a coleta manual aparecem quando ele terminar."
              : "Aparece quando a coleta rodar: tempo do agente × a mesma coleta feita à mão."}
          </span>
        )}
      </div>
      <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 1, border: "1px solid var(--line)", borderRadius: 10, overflow: "hidden", background: "var(--line)" }}>
        {item(`US$ ${(t?.custo_usd ?? 0).toFixed(3).replace(".", ",")}`, aoVivo ? "custo de IA até agora" : "custo de IA no processo")}
        {item(t ? (t.tokens_entrada + t.tokens_saida).toLocaleString("pt-BR") : "0", "tokens")}
        {item(String(t?.chamadas_modelo ?? 0), "chamadas de modelo")}
        {item(String(t?.ferramentas ?? 0), "operações em sistemas")}
      </dl>
    </section>
  );
}

/* ---------------- Atividade do agente (rastro auditável) ---------------- */

type Tipo = "decisao" | "sistema" | "modelo" | "humano" | "pendencia" | "erro" | "recup";
type Etapa = "ingestao" | "triagem" | "subsidios" | "estrategia" | "outros";
export type Item = {
  id: number; k: Tipo; t: string; titulo: string; args?: string; detalhe?: string; pensa?: string;
  falha?: string; ok?: string; etapa: Etapa; quando: string;
  serie?: string; n?: number; docs?: number;   // consultas em série ao mesmo sistema viram uma linha
};

const KIND: Record<Tipo, { tone: string; icon: NomeIcone; mono: boolean }> = {
  decisao: { tone: "pri", icon: "placa", mono: true },
  sistema: { tone: "neu", icon: "banco", mono: false },
  modelo: { tone: "neu", icon: "faisca", mono: true },
  humano: { tone: "warn", icon: "pessoaOk", mono: false },
  pendencia: { tone: "warn", icon: "pessoa", mono: false },
  erro: { tone: "bad", icon: "xC", mono: false },
  recup: { tone: "ok", icon: "refresh", mono: false },
};
const NOME_ETAPA: Record<Etapa, string> = {
  estrategia: "Estratégia de defesa", subsidios: "Coleta de subsídios", triagem: "Triagem da inicial",
  ingestao: "Leitura da petição", outros: "Outros",
};
const ORDEM: Etapa[] = ["estrategia", "subsidios", "triagem", "ingestao", "outros"];
const ETAPAS = ["ingestao", "triagem", "subsidios", "estrategia"];
const APROVOU: Record<string, string> = { triagem: "a triagem", subsidios: "a coleta", estrategia: "a estratégia" };

function etapaDe(e: Evento, jobs: Record<string, Job>): Etapa {
  const porJob = Object.values(jobs).find((j) => j.id === e.job_id);
  if (porJob) return (ETAPAS.includes(porJob.tipo) ? porJob.tipo : "outros") as Etapa;
  const [pre, seg] = e.etiqueta.split(":");
  if (e.tipo === "humano") return pre === "aprovou" && ETAPAS.includes(seg) ? (seg as Etapa) : "subsidios";
  if (e.tipo === "embedding") return "ingestao";
  if (e.tipo === "ferramenta" || pre === "pendencia_aberta" || pre === "subsidios" || pre === "cruzamento") return "subsidios";
  if (pre === "triagem" || pre === "estrategia") return pre;
  return "outros";
}

/** Eventos crus do rastro → itens legíveis, na ordem em que aconteceram. */
export function itensDoRastro(eventos: Evento[], jobs: Record<string, Job>): Item[] {
  const out: Item[] = [];
  const serie = (chave: string, k: Tipo, base: Omit<Item, "k" | "titulo">, titulo: string, doc: boolean, rotulo: (n: number, d: number) => string) => {
    const ant = [...out].reverse().find((x) => x.serie === chave && x.etapa === base.etapa);
    if (ant && out.length - out.indexOf(ant) <= 6) {
      ant.n = (ant.n ?? 1) + 1; ant.docs = (ant.docs ?? 0) + (doc ? 1 : 0); ant.detalhe = rotulo(ant.n, ant.docs);
      return;
    }
    out.push({ ...base, k, titulo, serie: chave, n: 1, docs: doc ? 1 : 0, detalhe: rotulo(1, doc ? 1 : 0) });
  };
  for (const e of eventos) {
    const d = e.detalhe || {};
    const base = { id: e.id, t: horaSeg(e.criado_em), etapa: etapaDe(e, jobs), quando: e.criado_em };
    if (e.tipo === "embedding") {
      if (base.etapa !== "ingestao") continue;  // documentos coletados já aparecem como operação em sistema
      const doc = e.etiqueta.replace("embedding:", "");
      serie(`emb:${doc}`, "sistema", base, "Lendo e indexando a petição", false, (n) => `${doc} · ${n} lote(s) de trechos indexados`);
      continue;
    }
    if (e.tipo === "decisao") {
      if (d.acao === "concluir") {
        out.push({ ...base, k: "decisao", titulo: `${e.etiqueta.replace("subsidios:", "")} → concluir`, detalhe: d.args?.resumo || undefined, pensa: d.pensamento || undefined });
      } else if (e.etiqueta === "subsidios:concluido") {
        out.push({ ...base, k: "decisao", titulo: "Coleta concluída",
          detalhe: `${d.documentos_coletados} documentos · ${d.favoraveis} a favor · ${d.divergencias} divergência(s) · ${d.pendencias} pendência(s) · ${num(d.segundos_agente ?? 0)} s` });
      } else if (d.acao) {
        const args = d.args && Object.keys(d.args).length ? JSON.stringify(d.args) : undefined;
        out.push({ ...base, k: "decisao", titulo: `${e.etiqueta.replace("subsidios:", "")} → ${d.acao}`, args, pensa: d.pensamento || undefined });
      } else if (e.etiqueta === "pendencia_aberta") {
        out.push({ ...base, k: "pendencia", titulo: "Pendência escalada", detalhe: `${d.titulo}${d.origem ? ` · origem: ${d.origem}` : ""}` });
      } else if (e.etiqueta.endsWith(":playbook")) {
        out.push({ ...base, k: "erro", titulo: `${e.etiqueta.split(":")[1]} → playbook`, detalhe: "modelo indisponível: a coleta seguiu pelo playbook determinístico" });
      } else if (e.etiqueta.endsWith(":loop_interrompido")) {
        out.push({ ...base, k: "decisao", titulo: `${e.etiqueta.split(":")[1]} → encerrado`, detalhe: `guarda de repetição: ${d.acao ?? "ação"} já executada` });
      } else {
        const resumo = Object.entries(d).filter(([, v]) => v !== null && typeof v !== "object")
          .map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ");
        out.push({ ...base, k: "decisao", titulo: e.etiqueta.replace(":", " · "), detalhe: resumo || undefined });
      }
      continue;
    }
    if (e.tipo === "ferramenta") {
      const chave = e.etiqueta.split(":")[0];
      if (e.etiqueta.endsWith(":falhou")) {
        out.push({ ...base, k: "erro", titulo: `${chave} · sistema fora do ar`, detalhe: `tentativa ${d.tentativa} · ${d.erro ?? ""}` });
      } else if ((d.tentativas ?? 1) > 1 && d.status === "ok") {
        out.push({ ...base, k: "recup", titulo: d.sistema ?? chave, falha: `sistema fora do ar · ${d.tentativas - 1} tentativa(s) falharam`,
          ok: `recuperado na tentativa ${d.tentativas}${d.documento ? ` · ${d.documento.nome} anexado` : ""}` });
      } else if (e.etiqueta === "rh:buscar_funcionario") {
        out.push({ ...base, k: "sistema", titulo: "Cadastro de pessoal", detalhe: `empregado localizado: matrícula ${d.matricula}` });
      } else if (e.etiqueta.includes(":")) {
        serie(`f:${chave}`, "sistema", base, d.sistema ?? chave, !!d.documento,
          (n, docs) => `${chave} · ${n} competência(s) consultada(s) · ${docs} documento(s) anexado(s)`);
      } else {
        out.push({ ...base, k: "sistema", titulo: d.sistema ?? "Sistema",
          detalhe: d.status === "ok" ? (d.documento ? `${e.etiqueta} · documento anexado: ${d.documento.nome}` : `${e.etiqueta} · ok`)
            : `${e.etiqueta} · ${d.motivo ?? d.status}` });
      }
      continue;
    }
    if (e.tipo === "chat") {
      out.push({ ...base, k: "modelo", titulo: e.etiqueta,
        detalhe: `${e.modelo ?? ""} · ${(e.tokens_entrada + e.tokens_saida).toLocaleString("pt-BR")} tokens · US$ ${e.custo_usd.toFixed(4).replace(".", ",")} · ${num(e.segundos)} s` });
      continue;
    }
    if (e.tipo === "humano") {
      const [a, b] = e.etiqueta.split(":");
      if (a === "aprovou") out.push({ ...base, k: "humano", titulo: `Humano aprovou ${APROVOU[b] ?? b}`, detalhe: d.observacao || undefined });
      else if (a === "pendencia") out.push({ ...base, k: "humano", titulo: `Pendência ${b}`, detalhe: `${d.titulo ?? ""}${d.resolucao ? `: ${d.resolucao}` : ""}` });
      else if (a === "importou") out.push({ ...base, k: "humano", titulo: "AFD importado", detalhe: `${d.arquivo ?? ""} · ${d.layout ?? ""}` });
      else out.push({ ...base, k: "humano", titulo: `Humano: ${e.etiqueta}` });
      continue;
    }
    if (e.tipo === "erro") out.push({ ...base, k: "erro", titulo: `Erro em ${e.etiqueta}`, detalhe: d.erro });
  }
  return out;
}

const FILTROS: [string, string][] = [["tudo", "Tudo"], ["decisao", "Decisões"], ["sistema", "Sistemas"], ["modelo", "Modelo"], ["humano", "Humano"], ["falha", "Falhas"]];
const bate = (f: string, k: Tipo) => f === "tudo" || k === f || (f === "humano" && k === "pendencia") || (f === "falha" && (k === "erro" || k === "recup"));

export function Atividade({ rastro, jobs, aoVivo }: { rastro: Rastro | null; jobs: Record<string, Job>; aoVivo?: boolean }) {
  const [filtro, setFiltro] = useState("tudo");
  const todos = itensDoRastro(rastro?.eventos ?? [], jobs);
  const grupos = ORDEM.map((et) => {
    const evs = todos.filter((x) => x.etapa === et);
    const vis = evs.filter((x) => bate(filtro, x.k)).reverse().slice(0, 80);
    const meta = evs.length ? `${hora(evs[0].quando)} – ${hora(evs[evs.length - 1].quando)}` : "";
    return { et, vis, meta };
  }).filter((g) => g.vis.length);
  return (
    <section className="card" aria-labelledby="titulo-atividade" style={{ padding: 0, display: "flex", flexDirection: "column" }}>
      <div style={{ padding: "18px 20px 14px", display: "flex", flexDirection: "column", gap: 12, borderBottom: "1px solid var(--line)" }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
          <h2 id="titulo-atividade" style={{ font: "600 15px/1.3 var(--f-sans)" }}>Atividade do agente</h2>
          {aoVivo
            ? <span className="row" style={{ gap: 6, fontSize: 12, color: "var(--muted)" }}><span className="pulse" style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--pri)" }} />atualiza a cada 2 s</span>
            : <span className="over">rastro auditável</span>}
        </div>
        <div role="group" aria-label="Filtrar eventos por tipo" className="row" style={{ gap: 6 }}>
          {FILTROS.map(([id, nome]) => (
            <button key={id} type="button" className={filtro === id ? "fchip fchip-on" : "fchip"} aria-pressed={filtro === id} onClick={() => setFiltro(id)}>
              {nome}<span className="fc-n">{todos.filter((x) => bate(id, x.k)).length}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="feed">
        {grupos.length === 0 && <p className="muted" style={{ padding: "16px 0", fontSize: 13 }}>Nada ainda. Cada decisão, consulta a sistema e chamada de modelo aparece aqui.</p>}
        {grupos.map((g) => (
          <div key={g.et} className="col">
            <div className="row" style={{ justifyContent: "space-between", gap: 8, padding: "14px 0 10px" }}>
              <span style={{ fontSize: 12.5, fontWeight: 600 }}>{NOME_ETAPA[g.et]}</span>
              <span className="num" style={{ font: "11.5px/1 var(--f-mono)", color: "var(--muted)" }}>{g.meta}</span>
            </div>
            <ol className="tl" style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {g.vis.map((e) => {
                const k = KIND[e.k];
                return (
                  <li key={e.id} style={{ display: "grid", gridTemplateColumns: "28px minmax(0,1fr)", gap: 10, paddingBottom: 14 }}>
                    <span className={`tl-n t-${k.tone}`}><I n={k.icon} /></span>
                    <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 3, paddingTop: 4 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                        <span className={k.mono ? "ttl-mono" : "ttl"}>{e.titulo}</span>
                        <time className="num" style={{ flex: "none", font: "11.5px/1.4 var(--f-mono)", color: "var(--muted)" }}>{e.t}</time>
                      </div>
                      {e.args && <code style={{ font: "12px/1.45 var(--f-mono)", color: "var(--muted)", overflowWrap: "anywhere" }}>{e.args}</code>}
                      {e.detalhe && <span style={{ fontSize: 12.5, lineHeight: 1.45, color: "var(--muted)", overflowWrap: "anywhere" }}>{e.detalhe}</span>}
                      {e.pensa && <span style={{ fontSize: 12.5, lineHeight: 1.45, color: "var(--muted)", fontStyle: "italic" }}>“{e.pensa}”</span>}
                      {e.k === "recup" && (
                        <div className="recup">
                          <span style={{ display: "flex", gap: 6, fontSize: 12.5, color: "var(--bad)" }}><I n="xC" style={{ width: 13, height: 13, marginTop: 2 }} />{e.falha}</span>
                          <span style={{ display: "flex", gap: 6, fontSize: 12.5, color: "var(--ok)" }}><I n="check" style={{ width: 13, height: 13, marginTop: 2 }} />{e.ok}</span>
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        ))}
      </div>
    </section>
  );
}
