import { useEffect, useState } from "react";
import { Evento, Job, Rastro, Triagem } from "./api";
import { I } from "./icones";

/** Segundos desde `inicio`, atualizando a cada segundo. */
function useDecorrido(inicio?: string | null) {
  const [agora, setAgora] = useState(Date.now());
  useEffect(() => { const t = window.setInterval(() => setAgora(Date.now()), 1000); return () => window.clearInterval(t); }, []);
  return inicio ? Math.max(0, Math.round((agora - new Date(inicio).getTime()) / 1000)) : 0;
}
const mmss = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
const frase = (s?: string | null) => (s ? s[0].toUpperCase() + s.slice(1) : "");

/** Início do job: criado_em do job ou, na falta, o primeiro evento dele. */
function inicioDo(job: Job, eventos: Evento[]) {
  return job.criado_em ?? eventos.find((e) => e.job_id === job.id)?.criado_em ?? null;
}

const TEXTO: Record<string, string> = {
  ingestao: "Lendo e indexando a petição",
  triagem: "Lendo a reclamação e separando os pedidos",
  estrategia: "Escrevendo a estratégia por pedido",
};

/** Faixa compacta para triagem, leitura e estratégia (a coleta usa o console grande). */
export function FaixaProgresso({ job, rastro }: { job: Job; rastro: Rastro | null }) {
  const seg = useDecorrido(inicioDo(job, rastro?.eventos ?? []));
  return (
    <div className="faixa" role="status">
      <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
        <span className="row" style={{ gap: 10, fontWeight: 500 }}>
          <I n="arco" style={{ color: "var(--con-warn)" }} />Agente trabalhando: {frase(job.etapa) || TEXTO[job.tipo] || job.tipo}…
        </span>
        <span className="num" style={{ font: "500 13px/1 var(--f-mono)", color: "var(--con-muted)" }}>{mmss(seg)}</span>
      </div>
      <span aria-hidden="true" style={{ display: "block", height: 6, borderRadius: 3, background: "rgba(255,255,255,.1)", overflow: "hidden" }}>
        <span className="stripes" style={{ display: "block", width: "100%", height: "100%", backgroundColor: "var(--con-warn)", opacity: .7 }} />
      </span>
    </div>
  );
}

type Estado = "fila" | "rodando" | "feito";

/** Console da coleta ao vivo: tudo derivado do rastro do job em andamento. */
export function ConsoleAoVivo({ job, rastro, tri }: { job: Job; rastro: Rastro | null; tri: Triagem }) {
  const eventos = (rastro?.eventos ?? []).filter((e) => e.job_id === job.id);
  const seg = useDecorrido(inicioDo(job, rastro?.eventos ?? []));
  const cruzando = /cruzando/i.test(job.etapa ?? "");

  const pedidos = tri.pedidos.map((p) => {
    const meus = eventos.filter((e) => e.tipo === "decisao" && e.etiqueta.startsWith(`subsidios:${p.id}`));
    const passos = meus.filter((e) => e.detalhe?.acao && e.detalhe.acao !== "concluir");
    const fim = meus.some((e) => e.detalhe?.acao === "concluir" || /:(loop_interrompido|playbook)$/.test(e.etiqueta));
    const playbook = meus.some((e) => e.etiqueta.endsWith(":playbook"));
    const estado: Estado = fim || cruzando ? "feito" : passos.length ? "rodando" : "fila";
    const pend = eventos.filter((e) => e.etiqueta === "pendencia_aberta" && e.detalhe?.pedido === p.id).length;
    return { p, passos, estado, playbook, pend, ultimo: meus[meus.length - 1] };
  });
  const feitos = pedidos.filter((x) => x.estado === "feito").length;
  const atual = pedidos.filter((x) => x.estado === "rodando").sort((a, b) => (b.ultimo?.id ?? 0) - (a.ultimo?.id ?? 0))[0];
  const ultimaDecisao = [...eventos].reverse().find((e) => e.tipo === "decisao" && e.detalhe?.pensamento);
  const falhas = eventos.filter((e) => e.etiqueta.endsWith(":falhou"));
  const ultimaFalha = falhas[falhas.length - 1];
  const falhaRecente = ultimaFalha && (!ultimaDecisao || ultimaFalha.id > ultimaDecisao.id);
  const docs = eventos.filter((e) => e.tipo === "ferramenta" && e.detalhe?.documento).length;
  const n = tri.pedidos.length;

  return (
    <section aria-labelledby="titulo-live" className="console">
      <div className="row" style={{ alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
        <div className="col" style={{ gap: 10, minWidth: 0 }}>
          <span className="row" style={{ gap: 10, font: "600 11.5px/1 var(--f-mono)", letterSpacing: ".12em", textTransform: "uppercase", color: "var(--con-ok)" }}>
            <span className="ring" aria-hidden="true" style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--con-ok)" }} />Agente trabalhando
          </span>
          <h2 id="titulo-live" style={{ font: "600 22px/1.25 var(--f-sans)", color: "var(--on-con)" }}>
            Coleta de subsídios <span style={{ fontWeight: 500, color: "var(--con-muted)" }}>· {cruzando ? "cruzando os dados" : `${feitos} de ${n} pedidos`}</span>
          </h2>
        </div>
        <div className="col" style={{ alignItems: "flex-end", gap: 6 }}>
          <span className="num" aria-label="Tempo decorrido" style={{ font: "600 36px/1 var(--f-mono)", color: "var(--on-con)" }}>{mmss(seg)}</span>
          <span style={{ fontSize: 12.5, color: "var(--con-muted)" }}>decorrido · costuma levar 2 a 4 min</span>
        </div>
      </div>

      <div aria-live="polite" className="agora">
        <span className="over">Agora</span>
        <p style={{ font: "500 22px/1.35 var(--f-sans)", color: "var(--on-con)" }}>
          {atual && !cruzando ? `${atual.p.titulo} → ${atual.passos[atual.passos.length - 1]?.detalhe.acao ?? "decidindo"}` : frase(job.etapa) || "Preparando a coleta"}
          <span className="caret" aria-hidden="true" />
        </p>
        {falhaRecente ? (
          <p className="row" style={{ gap: 8, fontSize: 14, lineHeight: 1.5, color: "var(--con-bad)", flexWrap: "nowrap", alignItems: "flex-start" }}>
            <I n="xC" style={{ marginTop: 3 }} />{ultimaFalha.etiqueta.replace(":falhou", "")}: sistema fora do ar (tentativa {ultimaFalha.detalhe?.tentativa}). O agente tenta de novo antes de escalar para uma pessoa.
          </p>
        ) : ultimaDecisao ? (
          <p style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: 14, lineHeight: 1.5, fontStyle: "italic", color: "var(--con-muted)" }}>
            <I n="placa" style={{ marginTop: 3, flex: "none" }} />“{ultimaDecisao.detalhe.pensamento}”
          </p>
        ) : null}
      </div>

      <div className="col" style={{ gap: 8 }}>
        <div role="progressbar" aria-label="Pedidos concluídos" aria-valuemin={0} aria-valuemax={n} aria-valuenow={feitos} style={{ display: "flex", gap: 4, height: 10 }}>
          {pedidos.map((x) => (
            <span key={x.p.id} className={x.estado === "rodando" ? "stripes" : ""}
                  style={{ flex: "1 1 0", borderRadius: 3, background: x.estado === "feito" ? "var(--con-ok)" : x.estado === "rodando" ? "var(--con-warn)" : "rgba(255,255,255,.1)" }} />
          ))}
        </div>
        <div className="row" style={{ justifyContent: "space-between", gap: "4px 16px", fontSize: 12.5, color: "var(--con-muted)" }}>
          <span>{feitos} de {n} pedidos concluídos{cruzando ? " · cruzando ponto, folha, FGTS e SST" : ""}</span>
          <span className="num">{docs} documento(s) anexado(s) até agora</span>
        </div>
      </div>

      <ol aria-label="Passos do agente por pedido" style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", borderTop: "1px solid var(--con-line)" }}>
        {pedidos.map((x) => {
          const eAtual = x === atual && !cruzando;
          const sub = x.estado === "fila" ? "na fila" : eAtual ? "trabalhando agora"
            : x.estado === "rodando" ? `${x.passos.length} passo(s) · em paralelo`
            : `${x.passos.length} passo(s)${x.pend ? ` · ${x.pend} pendência(s)` : ""}${x.playbook ? " · seguiu pelo playbook" : ""}`;
          return (
            <li key={x.p.id} className={`cped ${eAtual ? "atual" : ""}`} style={x.estado === "fila" ? { color: "var(--con-muted)" } : undefined}>
              {x.estado === "feito" ? <I n="checkC" style={{ color: "var(--con-ok)" }} />
                : x.estado === "rodando" ? <I n="arco" style={{ color: "var(--con-warn)" }} />
                : <I n="circulo" style={{ color: "var(--con-muted)" }} />}
              <span className="nome">
                <span style={{ fontWeight: 600 }}>{x.p.titulo}</span>
                <span style={{ fontSize: 12, color: eAtual ? "var(--con-warn)" : "var(--con-muted)" }}>{sub}</span>
              </span>
              <span className="passos">
                {x.passos.length === 0 && <span className="cstep cstep-q">aguardando</span>}
                {x.passos.map((e, i) => {
                  const ultimo = i === x.passos.length - 1 && x.estado === "rodando";
                  const acao = e.detalhe.acao as string;
                  const cls = ultimo ? "cstep-run" : acao === "abrir_pendencia" ? "cstep-warn" : "cstep-ok";
                  return (
                    <span key={e.id} className="row" style={{ gap: 6 }}>
                      <span className={`cstep ${cls}`} title={e.detalhe.pensamento ?? ""}>
                        {ultimo ? <I n="arco" style={{ color: "var(--con-warn)" }} /> : acao === "abrir_pendencia" ? <I n="pessoa" /> : <I n="check" />}{acao}
                      </span>
                      {i < x.passos.length - 1 && <I n="chevD" style={{ width: 13, height: 13 }} />}
                    </span>
                  );
                })}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** Pendências que o agente escalou durante a coleta (os achados do cruzamento chegam no fim). */
export function AchadosAteAgora({ job, rastro, tri }: { job: Job; rastro: Rastro | null; tri: Triagem }) {
  const eventos = (rastro?.eventos ?? []).filter((e) => e.job_id === job.id);
  const pend = eventos.filter((e) => e.etiqueta === "pendencia_aberta");
  const falhas = eventos.filter((e) => e.etiqueta.endsWith(":falhou"));
  const nomePedido = (id?: string) => tri.pedidos.find((p) => p.id === id)?.titulo ?? "";
  return (
    <section className="card" aria-labelledby="titulo-achados" style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="col" style={{ gap: 2 }}>
        <h2 id="titulo-achados" style={{ font: "600 16px/1.3 var(--f-sans)" }}>Até agora</h2>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>Pendências escaladas e falhas de sistema aparecem na hora. Os achados (a favor, risco) saem do cruzamento, no fim da coleta.</span>
      </div>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
        {pend.length === 0 && falhas.length === 0 && (
          <li className="row" style={{ gap: 10, padding: "12px 14px", borderRadius: 10, border: "1px dashed var(--line-2)", color: "var(--muted)", fontSize: 13.5 }}>
            <span className="skel" style={{ width: 80 }} />nada escalado ainda
          </li>
        )}
        {falhas.map((e) => (
          <li key={e.id} className="fresh row" style={{ gap: "8px 12px", padding: "12px 14px", borderRadius: 10, background: "var(--sunk)", border: "1px solid var(--line)" }}>
            <span className="badge t-bad"><I n="refresh" />Sistema fora do ar</span>
            <span style={{ flex: "1 1 280px", minWidth: 0, fontWeight: 500 }}>{e.etiqueta.replace(":falhou", "")}: tentativa {e.detalhe?.tentativa} falhou, o agente tenta de novo</span>
          </li>
        ))}
        {pend.map((e) => (
          <li key={e.id} className="fresh row" style={{ gap: "8px 12px", padding: "12px 14px", borderRadius: 10, background: "var(--warn-bg)", border: "1px solid var(--warn-line)" }}>
            <span className="badge t-warn" style={{ background: "var(--surface)" }}><I n="pessoa" />Pendência</span>
            <span style={{ flex: "1 1 280px", minWidth: 0, fontWeight: 600 }}>{e.detalhe?.titulo}</span>
            <span style={{ fontSize: 12.5, color: "var(--muted)" }}>{nomePedido(e.detalhe?.pedido)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
