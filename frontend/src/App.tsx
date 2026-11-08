import { CSSProperties, useCallback, useEffect, useState } from "react";
import { api, brl, hora, Job, Processo, Rastro } from "./api";
import { AchadosAteAgora, ConsoleAoVivo, FaixaProgresso } from "./aovivo";
import { CabEtapa, FontePonto, Portao, titulo, VisaoEstrategia, VisaoSubsidios, VisaoTriagem } from "./etapas";
import { useJob, usePolling } from "./hooks";
import { I } from "./icones";
import { Atividade, Metricas } from "./painel";

type Etapa = "triagem" | "subsidios" | "estrategia";
const ETAPAS: { id: Etapa; nome: string; desc: string }[] = [
  { id: "triagem", nome: "Triagem da inicial", desc: "O agente lê a reclamação e separa cada pedido, com valor, categoria e a página de onde tirou." },
  { id: "subsidios", nome: "Coleta de subsídios", desc: "O digital worker opera ponto, folha, FGTS e SST, anexa os documentos e cruza os dados." },
  { id: "estrategia", nome: "Estratégia de defesa", desc: "Tese, prova citada, pontos fracos e risco por pedido. A decisão final é do advogado." },
];

function useEscuro() {
  const mq = typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  const [escuro, setEscuro] = useState(!!mq?.matches);
  useEffect(() => {
    if (!mq) return;
    const f = (e: MediaQueryListEvent) => setEscuro(e.matches);
    mq.addEventListener("change", f);
    return () => mq.removeEventListener("change", f);
  }, [mq]);
  return escuro;
}

export default function App() {
  const escuro = useEscuro();
  const [pid, setPid] = useState<string | null>(() => new URLSearchParams(location.search).get("p"));
  const [health, setHealth] = useState<{ perimetro: string; provedor: string; modelos: Record<string, string> } | null>(null);
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, []);
  const abrir = (id: string | null) => {
    setPid(id);
    history.replaceState(null, "", id ? `?p=${id}` : location.pathname);
    window.scrollTo(0, 0);
  };
  return (
    <div className={`sb ${escuro ? "escuro" : ""}`}>
      <header className="topo">
        <div className="wrap topo-in">
          <button type="button" className="marca" onClick={() => abrir(null)} aria-label="Subsídia, voltar ao início">
            <span aria-hidden="true" className="logo">§</span>
            <span className="col" style={{ gap: 2 }}>
              <span style={{ font: "700 17px/1.1 var(--f-sans)", letterSpacing: "-0.01em" }}>Subsídia</span>
              <span style={{ fontSize: 12, lineHeight: 1.2, color: "var(--muted)" }}>digital worker de contencioso trabalhista</span>
            </span>
          </button>
          {health && (health.perimetro === "nuvem" ? (
            <span className="badge t-warn perim" tabIndex={0}
                  title={`Provedor: ${health.provedor}. Modelos: ${Object.values(health.modelos).join(", ")}. Os dados saem do seu ambiente para a nuvem; nesta demo eles são sintéticos.`}>
              <I n="nuvem" /><span>IA em nuvem · Featherless</span><span aria-hidden="true" className="sep" /><span>dados sintéticos</span>
            </span>
          ) : (
            <span className="badge t-ok perim"><I n="cadeado" />IA local · os dados não saem daqui</span>
          ))}
        </div>
      </header>
      {pid ? <TelaProcesso key={pid} pid={pid} voltar={() => abrir(null)} /> : <Inicio abrir={abrir} />}
    </div>
  );
}

/* ================= Início ================= */

function Inicio({ abrir }: { abrir: (id: string) => void }) {
  const [lista, setLista] = useState<{ id: string; nome: string; criado_em: string }[]>([]);
  const [ocupado, setOcupado] = useState<null | "pronto" | "demo" | "enviar">(null);
  const [erro, setErro] = useState<string | null>(null);
  const [nome, setNome] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  useEffect(() => { api.processos().then(setLista).catch((e) => setErro(e.message)); }, []);
  const rodar = async (qual: "pronto" | "demo" | "enviar", fn: () => Promise<string>) => {
    setOcupado(qual); setErro(null);
    try { abrir(await fn()); } catch (e: any) { setErro(e.message); setOcupado(null); }
  };
  const pronto = () => rodar("pronto", async () => (await api.pronto()).processo_id);
  const demo = () => rodar("demo", async () => (await api.demo()).processo_id);
  const enviar = () => arquivo && rodar("enviar", async () => {
    const r = await api.criar(nome || arquivo.name.replace(/\.pdf$/i, ""));
    await api.upload(r.processo_id, arquivo);
    return r.processo_id;
  });
  const leg = (cor: string, txt: string) => <span className="leg"><i style={{ background: cor }} />{txt}</span>;
  return (
    <main>
      <section className="hero">
        <div className="wrap ruled hero-in">
          <div style={{ flex: "1 1 520px", minWidth: 0, display: "flex", flexDirection: "column", gap: 24 }}>
            <h1 style={{ font: "600 clamp(34px,3.7vw,54px)/1.1 var(--f-serif)", letterSpacing: "-0.02em", maxWidth: "17ch", textWrap: "balance" } as CSSProperties}>
              Da reclamação trabalhista à defesa pronta, com prova tirada dos sistemas de RH
            </h1>
            <p style={{ fontSize: 18, lineHeight: 1.6, color: "var(--muted)", maxWidth: "56ch" }}>
              O agente lê a petição, busca sozinho ponto, holerites, TRCT, FGTS e EPI, cruza os dados e mostra onde a empresa ganha e onde perde, sempre citando o documento. O que não fecha vai para uma pessoa decidir.
            </p>
            <div className="row" style={{ gap: 12 }}>
              <button type="button" className="btn btn-acc btn-lg" onClick={pronto} disabled={!!ocupado}>
                {ocupado === "pronto" ? <I n="arco" style={{ width: 18, height: 18 }} /> : <I n="raio" style={{ width: 18, height: 18 }} />}Ver caso já analisado
              </button>
              <button type="button" className="btn btn-sec btn-lg" onClick={demo} disabled={!!ocupado}>
                {ocupado === "demo" ? <I n="arco" /> : <I n="play" />}Rodar o agente ao vivo
                <span className="num" style={{ font: "500 12px/1 var(--f-mono)", color: "var(--muted)", padding: "5px 7px", borderRadius: 5, background: "var(--sunk)" }}>~6 min</span>
              </button>
            </div>
            <p className="row" style={{ gap: 8, fontSize: 13, color: "var(--muted)" }}>
              <I n="docLinhas" />Mercado Exemplo Ltda × ex-repositor de câmara fria · dados 100% sintéticos
            </p>
            {erro && <div className="alerta" role="alert"><I n="xC" style={{ color: "var(--bad)" }} />{erro}</div>}
          </div>

          <figure style={{ margin: 0, flex: "1 1 460px", minWidth: 0, maxWidth: 620, position: "relative", padding: "0 18px 18px 0" }}>
            <div aria-hidden="true" style={{ position: "absolute", top: 22, left: 22, right: 0, bottom: 0, borderRadius: 14, background: "var(--sunk)", border: "1px solid var(--line)" }} />
            <div className="card" style={{ position: "relative", padding: "22px 22px 18px", display: "flex", flexDirection: "column", gap: 18, boxShadow: "var(--shadow-lg)" }}>
              <div className="row" style={{ alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                <div className="col" style={{ gap: 4, minWidth: 0 }}>
                  <span className="over">Caso pronto · Mercado Exemplo Ltda</span>
                  <span style={{ font: "600 17px/1.3 var(--f-serif)" }}>Reclamação 0000123-45.2025.5.06.0001</span>
                </div>
                <span className="badge t-ok"><I n="pessoaOk" />analisado e revisado</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: "14px 16px", borderRadius: 10, background: "var(--sunk)" }}>
                <div className="row" style={{ alignItems: "baseline", justifyContent: "space-between", gap: 12 }}>
                  <span style={{ fontSize: 13, color: "var(--muted)" }}>Em jogo</span>
                  <span className="num" style={{ font: "600 22px/1 var(--f-sans)" }}>R$ 57.750,00</span>
                </div>
                <div aria-hidden="true" className="barra" style={{ height: 10, borderRadius: 5 }}>
                  <span style={{ flex: "18.5 1 0", background: "var(--hi-fill)" }} />
                  <span style={{ flex: "20 1 0", background: "var(--mid-fill)" }} />
                  <span style={{ flex: "6.2 1 0", background: "var(--mid-fill)" }} />
                  <span style={{ flex: "7.3 1 0", background: "var(--lo-fill)" }} />
                  <span style={{ flex: "3.9 1 0", background: "var(--lo-fill)" }} />
                  <span style={{ flex: "1.85 1 0", background: "var(--lo-fill)" }} />
                </div>
                <div className="row" style={{ gap: "6px 16px", fontSize: 12, color: "var(--muted)" }}>
                  {leg("var(--hi-fill)", "risco alto R$ 18.500")}{leg("var(--mid-fill)", "médio R$ 26.200")}{leg("var(--lo-fill)", "baixo R$ 13.050")}
                </div>
              </div>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 12 }}>
                {([
                  ["t-solid-bad", "alerta", "Risco", "Horas extras registradas e não pagas: 99,2 h", "espelho_ponto_2024-09"],
                  ["t-ok", "checkC", "A favor", "Rescisão paga dentro do prazo do art. 477", "trct"],
                  ["t-warn", "pessoa", "Pendência", "Ponto de 2024-06 sem nenhuma marcação", "Súmula 338"],
                ] as const).map(([c, ic, b, t, ev]) => (
                  <li key={t} className="row" style={{ gap: "10px 12px" }}>
                    <span className={`badge ${c}`}><I n={ic} />{b}</span>
                    <span style={{ flex: "1 1 220px", fontWeight: 500 }}>{t}</span>
                    <span className="ev" style={{ cursor: "default" }}><I n="doc" />{ev}</span>
                  </li>
                ))}
              </ul>
              <div className="row" style={{ justifyContent: "space-between", gap: 12, paddingTop: 14, borderTop: "1px solid var(--line)" }}>
                <div aria-label="Passos do agente" className="row" style={{ gap: 6, color: "var(--muted)" }}>
                  <span className="step t-pri">obter_ponto</span><I n="chevD" style={{ width: 13, height: 13 }} />
                  <span className="step t-pri">obter_holerite</span><I n="chevD" style={{ width: 13, height: 13 }} />
                  <span className="step t-warn">abrir_pendencia</span>
                </div>
                <span style={{ fontSize: 12.5, color: "var(--muted)" }}><strong className="num" style={{ color: "var(--ink)" }}>1,6 min</strong> pelo agente × ~7,7 h à mão</span>
              </div>
            </div>
          </figure>
        </div>
      </section>

      <section className="wrap" style={{ paddingTop: 48, paddingBottom: 72, display: "flex", flexWrap: "wrap", alignItems: "flex-start", gap: 24 }}>
        <form className="card" onSubmit={(e) => { e.preventDefault(); enviar(); }} style={{ flex: "1 1 420px", minWidth: 0, padding: 24, display: "flex", flexDirection: "column", gap: 18 }}>
          <div className="col" style={{ gap: 4 }}>
            <h2 style={{ font: "600 18px/1.3 var(--f-sans)" }}>Nova reclamação</h2>
            <p style={{ fontSize: 13.5, color: "var(--muted)" }}>Envie a petição inicial em PDF. O agente começa pela triagem.</p>
          </div>
          <label htmlFor="nome-processo" style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, fontWeight: 600 }}>
            Nome do processo
            <input id="nome-processo" className="inp" type="text" placeholder="Ex.: Reclamação 0000456-78.2025.5.06.0002" value={nome} onChange={(e) => setNome(e.target.value)} />
          </label>
          <label htmlFor="pdf-peticao" className="drop">
            <span aria-hidden="true" className="ico-box"><I n={arquivo ? "doc" : "upload"} /></span>
            <span className="col" style={{ gap: 2, minWidth: 0 }}>
              <span style={{ fontSize: 14, fontWeight: 600, overflowWrap: "anywhere" }}>{arquivo ? arquivo.name : "Selecionar PDF da petição"}</span>
              <span style={{ fontSize: 12.5, color: "var(--muted)" }}>{arquivo ? `${(arquivo.size / 1024).toFixed(0)} KB · clique para trocar` : "PDF com texto (o agente lê página por página)"}</span>
            </span>
            <input id="pdf-peticao" type="file" accept="application/pdf" onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
          </label>
          <div className="row" style={{ gap: 12 }}>
            <button type="submit" className="btn btn-pri" disabled={!arquivo || !!ocupado}>{ocupado === "enviar" && <I n="arco" />}Enviar petição</button>
            <a className="btn btn-ghost" href="/rh/demo/inicial.pdf" style={{ fontSize: 13, fontWeight: 500 }}><I n="download" />petição de exemplo</a>
          </div>
          <p className="row" style={{ alignItems: "flex-start", gap: 8, fontSize: 12.5, lineHeight: 1.5, color: "var(--muted)", flexWrap: "nowrap" }}>
            <I n="info" style={{ marginTop: 1 }} />Os sistemas de RH desta demo são simulados: a coleta funciona para o empregado da empresa fictícia.
          </p>
        </form>

        <section className="card" aria-labelledby="titulo-processos" style={{ flex: "1 1 520px", minWidth: 0, padding: 0, overflow: "hidden" }}>
          <div className="row" style={{ alignItems: "baseline", justifyContent: "space-between", gap: 12, padding: "20px 24px 14px" }}>
            <h2 id="titulo-processos" style={{ font: "600 18px/1.3 var(--f-sans)" }}>Processos</h2>
            <span className="num" style={{ fontSize: 13, color: "var(--muted)" }}>{lista.length} processo(s)</span>
          </div>
          {lista.length === 0 && <p style={{ padding: "14px 24px 22px", borderTop: "1px solid var(--line)", fontSize: 13.5, color: "var(--muted)" }}>Nenhum processo ainda. Abra o caso pronto ou rode o agente ao vivo.</p>}
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {lista.map((p) => {
              const pronto = /caso pronto/i.test(p.nome), vivo = /\(demo\)|ao vivo/i.test(p.nome);
              return (
                <li key={p.id}>
                  <button type="button" className="row-link" onClick={() => abrir(p.id)}>
                    <span aria-hidden="true" style={{ width: 36, height: 36, borderRadius: 8, display: "grid", placeItems: "center", flex: "none", background: "var(--pri-soft)", color: "var(--pri)" }}><I n="docLinhas" /></span>
                    <span style={{ flex: "1 1 auto", minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                      <span style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.nome}</span>
                      <span className="num" style={{ font: "12px/1.3 var(--f-mono)", color: "var(--muted)" }}>{new Date(p.criado_em).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</span>
                    </span>
                    {pronto && <span className="badge t-pri">Caso pronto</span>}
                    {vivo && <span className="badge t-neu">Ao vivo</span>}
                    <I n="chevD" style={{ color: "var(--muted)" }} />
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      </section>
    </main>
  );
}

/* ================= Processo ================= */

function TelaProcesso({ pid, voltar }: { pid: string; voltar: () => void }) {
  const [proc, setProc] = useState<Processo | null>(null);
  const [rastro, setRastro] = useState<Rastro | null>(null);
  const [jobs, setJobs] = useState<Record<string, Job>>({});
  const [jobId, setJobId] = useState<string | null>(null);
  const [aba, setAbaEstado] = useState<Etapa>("triagem");
  const [erro, setErro] = useState<string | null>(null);

  const setAba = (e: Etapa) => {
    setAbaEstado(e);
    const u = new URLSearchParams(location.search); u.set("aba", e);
    history.replaceState(null, "", `?${u}`);
  };

  const carregar = useCallback(async () => {
    try {
      const [p, r, js] = await Promise.all([api.processo(pid), api.rastro(pid), api.jobs(pid).catch(() => ({} as Record<string, Job>))]);
      setProc(p); setRastro(r); setJobs(js);
      return p;
    } catch (e: any) { setErro(e.message); return null; }
  }, [pid]);

  const rodar = useCallback(async (etapa: Etapa) => {
    setErro(null);
    try { const r = await api.rodar(pid, etapa); setJobId(r.job_id); setAba(etapa); window.scrollTo({ top: 0, behavior: "smooth" }); }
    catch (e: any) { setErro(e.message); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  // Retoma um job em andamento depois de reload; abre a aba pedida ou a etapa mais avançada.
  useEffect(() => {
    (async () => {
      const p = await carregar();
      const js = await api.jobs(pid).catch(() => ({} as Record<string, Job>));
      const andamento = Object.values(js).find((j) => j.status === "queued" || j.status === "processando");
      if (andamento) setJobId(andamento.id);
      const pedida = new URLSearchParams(location.search).get("aba") as Etapa | null;
      if (pedida && ETAPAS.some((e) => e.id === pedida)) setAbaEstado(pedida);
      else if (andamento && ETAPAS.some((e) => e.id === andamento.tipo)) setAbaEstado(andamento.tipo as Etapa);
      else if (p?.artefatos.estrategia) setAbaEstado("estrategia");
      else if (p?.artefatos.subsidios) setAbaEstado("subsidios");
    })();
  }, [pid, carregar]);

  const job = useJob(jobId, async (j) => {
    setJobId(null);
    if (j.status === "erro") setErro(`Não foi possível concluir (${j.tipo}): ${j.erro}`);
    const p = await carregar();
    if (j.status === "concluido" && j.tipo !== "ingestao") setAba(j.tipo as Etapa);
    // Petição indexada → a triagem começa sozinha (o humano aprova depois).
    if (j.status === "concluido" && j.tipo === "ingestao" && p && !p.artefatos.triagem) rodar("triagem");
  });
  // Durante o job: rastro a cada 2 s (console ao vivo) e o processo inteiro a cada 6 s (contadores, pendências).
  usePolling(() => { api.rastro(pid).then(setRastro).catch(() => {}); }, 2000, !!jobId);
  usePolling(() => { api.processo(pid).then(setProc).catch(() => {}); }, 6000, !!jobId);

  const aprovar = async (tipo: Etapa, proxima?: Etapa) => {
    setErro(null);
    try { await api.aprovar(pid, tipo); await carregar(); if (proxima) rodar(proxima); } catch (e: any) { setErro(e.message); }
  };

  if (!proc) return (
    <main className="wrap" style={{ paddingTop: 24 }}>
      {erro ? <div className="alerta" role="alert"><I n="xC" style={{ color: "var(--bad)" }} />{erro}</div>
        : <p className="row" style={{ gap: 8, color: "var(--muted)" }}><I n="arco" />Carregando o processo…</p>}
    </main>
  );

  const a = proc.artefatos;
  const rodando = !!job && (job.status === "queued" || job.status === "processando") ? job : null;
  const abertas = proc.pendencias.filter((p) => p.status === "aberta").length;
  const tri = a.triagem?.conteudo;
  const aprovadoEm = (t: Etapa) => [...(rastro?.eventos ?? [])].reverse().find((e) => e.tipo === "humano" && e.etiqueta === `aprovou:${t}`)?.criado_em;
  type Est = "rodando" | "aprovado" | "aguarda" | "pronta" | "travada";
  const estado = (e: Etapa): Est => {
    if (rodando?.tipo === e || (e === "triagem" && rodando?.tipo === "ingestao")) return "rodando";
    if (a[e]) return a[e]!.aprovado ? "aprovado" : "aguarda";
    const anterior = e === "subsidios" ? a.triagem : e === "estrategia" ? a.subsidios : null;
    return e === "triagem" || anterior?.aprovado ? "pronta" : "travada";
  };
  const aguardando = ETAPAS.some((e) => estado(e.id) === "aguarda");
  const partes = tri ? [titulo(tri.processo.reclamada), titulo(tri.processo.reclamante)].filter(Boolean).join(" × ") : "";

  const irPendencias = () => {
    setAba("subsidios");
    window.setTimeout(() => document.getElementById("pendencias")?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
  };

  return (
    <main className="wrap" style={{ paddingTop: 20, paddingBottom: 72, display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="col" style={{ gap: 6, minWidth: 0 }}>
        <button type="button" className="btn btn-ghost" onClick={voltar} style={{ alignSelf: "flex-start", minHeight: 32, padding: "0 10px 0 6px", marginLeft: -6, fontSize: 13, fontWeight: 500 }}>
          <I n="voltar" />Processos
        </button>
        <div className="row" style={{ gap: "10px 14px" }}>
          <h1 style={{ font: "600 28px/1.2 var(--f-serif)", letterSpacing: "-0.01em" }}>{tri?.processo.numero ? `Reclamação ${tri.processo.numero}` : proc.nome}</h1>
          {rodando ? <span className="badge t-pri"><I n="arco" />Agente trabalhando</span>
            : aguardando ? <span className="badge t-warn"><I n="pessoa" />Aguarda sua aprovação</span>
            : /caso pronto/i.test(proc.nome) ? <span className="badge t-pri">Caso pronto</span> : null}
        </div>
        <div className="row" style={{ gap: "4px 18px", fontSize: 13.5, color: "var(--muted)" }}>
          {partes && <span>{partes}</span>}
          <span className="num">{proc.documentos.length} documento(s)</span>
          <span className="num">{abertas} pendência(s) aberta(s)</span>
        </div>
      </div>

      {erro && (
        <div className="alerta" role="alert">
          <I n="xC" style={{ width: 18, height: 18, marginTop: 1, color: "var(--bad)" }} />
          <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}><strong style={{ fontWeight: 600, color: "var(--bad)" }}>Algo não saiu como esperado</strong><code style={{ font: "12.5px/1.45 var(--f-mono)", color: "var(--muted)" }}>{erro}</code></span>
          <button type="button" className="btn btn-ghost" aria-label="Fechar alerta" onClick={() => setErro(null)} style={{ minHeight: 32, minWidth: 32, padding: 0, color: "var(--muted)" }}><I n="x" /></button>
        </div>
      )}

      {tri && <ResumoRisco proc={proc} cruzando={rodando?.tipo === "subsidios"} irPendencias={irPendencias} />}

      <nav className="stpr" aria-label="Etapas do processo">
        {ETAPAS.map((e, i) => {
          const st = estado(e.id);
          const ant = i > 0 ? estado(ETAPAS[i - 1].id) : null;
          return (
            <span key={e.id} style={{ display: "contents" }}>
              {i > 0 && (
                <span className={`gate ${ant === "aprovado" ? "t-ok" : ant === "aguarda" ? "t-warn" : "t-neu"}`}>
                  <span className="gate-n"><I n={ant === "aprovado" ? "pessoaOk" : "pessoa"} /></span>
                  <span className="sr">{ant === "aprovado" ? "Portão humano aprovado" : ant === "aguarda" ? "Portão humano aguardando você" : "Portão humano ainda não alcançado"}</span>
                </span>
              )}
              <button type="button" className={`stp ${aba === e.id ? "stp-on" : ""} ${st === "travada" ? "stp-lock" : ""}`}
                      aria-current={aba === e.id ? "step" : undefined} onClick={() => setAba(e.id)}>
                <span className={`stp-n ${{ rodando: "t-pri", aprovado: "t-ok", aguarda: "t-warn", pronta: "t-neu", travada: "t-neu" }[st]}`}>
                  {st === "rodando" ? <I n="arco" /> : st === "aprovado" ? <I n="check" /> : st === "aguarda" ? <I n="pessoa" /> : st === "travada" ? <I n="cadeado" /> : i + 1}
                </span>
                <span className="col" style={{ gap: 2, minWidth: 0 }}>
                  <span style={{ fontSize: 12, color: "var(--muted)" }}>Etapa {i + 1}{st === "travada" ? " · travada" : ""}</span>
                  <span style={{ fontSize: 15, fontWeight: 600, lineHeight: 1.25, color: st === "travada" ? "var(--muted)" : undefined }}>{e.nome}</span>
                </span>
                {st === "aprovado" && <span className="badge t-ok" style={{ marginLeft: "auto" }}><I n="pessoaOk" />Aprovado</span>}
                {st === "aguarda" && <span className="badge t-warn" style={{ marginLeft: "auto" }}>Aguarda aprovação</span>}
                {st === "rodando" && <span className="badge t-pri" style={{ marginLeft: "auto" }}>Rodando</span>}
              </button>
            </span>
          );
        })}
      </nav>

      <div className="grade">
        <div className="principal">
          {ETAPAS.filter((e) => e.id === aba).map((e) => {
            const art = a[e.id];
            const st = estado(e.id);
            const proxima: Etapa | undefined = e.id === "triagem" ? "subsidios" : e.id === "subsidios" ? "estrategia" : undefined;
            const aoVivoColeta = rodando?.tipo === "subsidios" && e.id === "subsidios" && tri;
            const meuJob = rodando && (rodando.tipo === e.id || (e.id === "triagem" && rodando.tipo === "ingestao")) ? rodando : null;
            if (aoVivoColeta) return (
              <div key={e.id} className="col" style={{ gap: 20 }}>
                <ConsoleAoVivo job={rodando!} rastro={rastro} tri={tri!} />
                <AchadosAteAgora job={rodando!} rastro={rastro} tri={tri!} />
                <Portao espera titulo="Aprovar a coleta e liberar a Estratégia de defesa"
                        selos={<span className="badge t-neu">fica disponível quando o agente terminar</span>}
                        nota="Enquanto isso, acompanhe cada passo no console e no rastro ao lado." />
              </div>
            );
            return (
              <section key={e.id} className="card" aria-labelledby="titulo-etapa" style={{ padding: 0 }}>
                <CabEtapa nome={e.nome} desc={e.desc}>
                  {!rodando && (st === "pronta" || art) && (
                    <button type="button" className={`btn ${art ? "btn-sec" : "btn-pri"}`} onClick={() => rodar(e.id)}>
                      {art ? <><I n="refresh" />Rodar de novo</> : <><I n="play" />Rodar o agente</>}
                    </button>
                  )}
                  {art && !art.aprovado && !rodando && (
                    <a href="#portao" className="btn btn-acc"><I n="check" />Revisar e aprovar</a>
                  )}
                  {art?.aprovado && (
                    <span className="badge t-ok" style={{ height: 36, padding: "0 13px", fontSize: 13 }}>
                      <I n="pessoaOk" />Aprovado por humano{aprovadoEm(e.id) ? ` · ${hora(aprovadoEm(e.id))}` : ""}
                    </span>
                  )}
                </CabEtapa>
                <div className="etapa-corpo">
                  {meuJob && <FaixaProgresso job={meuJob} rastro={rastro} />}
                  {st === "travada" && (
                    <p className="row" style={{ gap: 10, padding: "14px 16px", borderRadius: 10, background: "var(--sunk)", color: "var(--muted)", flexWrap: "nowrap" }}>
                      <I n="cadeado" />Aprove a etapa anterior para liberar esta: é o portão humano entre o que o agente prepara e o que segue adiante.
                    </p>
                  )}
                  {st === "pronta" && !art && !meuJob && (
                    <p className="row" style={{ gap: 10, padding: "14px 16px", borderRadius: 10, background: "var(--sunk)", color: "var(--muted)", flexWrap: "nowrap" }}>
                      <I n="info" />{e.id === "triagem" && proc.documentos.length === 0 ? "Envie a petição para começar." : "Pronta para rodar. Clique em Rodar o agente."}
                    </p>
                  )}
                  {e.id === "subsidios" && st !== "travada" && <FontePonto pid={pid} coletaEm={a.subsidios?.atualizado_em} aoImportar={carregar} />}
                  {e.id === "triagem" && tri && <VisaoTriagem pid={pid} t={tri} />}
                  {e.id === "subsidios" && a.subsidios && tri && (
                    <VisaoSubsidios pid={pid} s={a.subsidios.conteudo} tri={tri} pendencias={proc.pendencias} aoMudar={carregar} />
                  )}
                  {e.id === "estrategia" && a.estrategia && (
                    <VisaoEstrategia pid={pid} e={a.estrategia.conteudo} documentos={proc.documentos.length} />
                  )}
                  {art && !art.aprovado && !rodando && (
                    <PortaoDaEtapa etapa={e.id} proc={proc} aprovar={() => aprovar(e.id, proxima)} rodar={() => rodar(e.id)} />
                  )}
                </div>
              </section>
            );
          })}
        </div>

        <aside className="lateral" aria-label="Custo e atividade do agente">
          <Metricas rastro={rastro} aoVivo={!!rodando} segundosAgente={a.subsidios?.conteudo.resumo?.segundos_agente}
                    minutosManual={a.subsidios?.conteudo.resumo?.minutos_manual_estimados} />
          <Atividade rastro={rastro} jobs={jobs} aoVivo={!!rodando} />
        </aside>
      </div>
    </main>
  );
}

function PortaoDaEtapa({ etapa, proc, aprovar, rodar }: { etapa: Etapa; proc: Processo; aprovar: () => void; rodar: () => void }) {
  const a = proc.artefatos;
  const abertas = proc.pendencias.filter((p) => p.status === "aberta").length;
  if (etapa === "triagem" && a.triagem) {
    const t = a.triagem.conteudo;
    return (
      <Portao titulo="Aprovar a triagem e liberar a Coleta de subsídios" aprovar={aprovar} rodar={rodar}
              selos={<>
                <span className="badge t-neu">{t.pedidos.length} pedidos</span>
                <span className="badge t-neu">{brl(t.valor_total_pedidos)}</span>
                {t.requer_revisao > 0 ? <span className="badge t-warn">{t.requer_revisao} para revisar</span> : <span className="badge t-ok">todos com fonte e confiança alta</span>}
              </>}
              nota="Ao aprovar, o agente começa a operar os sistemas de RH. A aprovação fica no rastro auditável, com data e hora." />
    );
  }
  if (etapa === "subsidios" && a.subsidios && !a.subsidios.conteudo.bloqueado) {
    const r = a.subsidios.conteudo.resumo;
    return (
      <Portao titulo="Aprovar a coleta e liberar a Estratégia de defesa" aprovar={aprovar} rodar={rodar}
              selos={<>
                <span className="badge t-neu">{r.documentos_coletados} documentos</span>
                <span className="badge t-bad">{r.divergencias} risco</span>
                <span className="badge t-ok">{r.favoraveis} a favor</span>
                <span className="badge t-warn">{abertas} pendência(s) aberta(s)</span>
              </>}
              nota="Ao aprovar, o agente escreve a estratégia. Pendências abertas seguem visíveis e entram na estratégia como pontos fracos." />
    );
  }
  if (etapa === "estrategia" && a.estrategia) {
    return (
      <Portao titulo="Aprovar a estratégia para o advogado" aprovar={aprovar} rodar={rodar} textoAprovar="Aprovar estratégia"
              selos={<>
                <span className="badge t-neu">{a.estrategia.conteudo.secoes.length} pedidos</span>
                <span className="badge t-bad">{brl(a.estrategia.conteudo.valor_em_risco_alto)} em risco alto</span>
                <span className="badge t-warn">{abertas} pendência(s) aberta(s)</span>
              </>}
              nota="A estratégia é um insumo: a peça, o acordo e a assinatura são sempre do advogado." />
    );
  }
  return null;
}

/* ---------------- Cabeçalho de risco do processo ---------------- */

function ResumoRisco({ proc, cruzando, irPendencias }: { proc: Processo; cruzando: boolean; irPendencias: () => void }) {
  const a = proc.artefatos;
  const tri = a.triagem!.conteudo;
  const est = a.estrategia?.conteudo;
  const sub = a.subsidios?.conteudo && !a.subsidios.conteudo.bloqueado ? a.subsidios.conteudo : null;
  const abertas = proc.pendencias.filter((p) => p.status === "aberta");
  const total = tri.valor_total_pedidos || tri.pedidos.reduce((s, p) => s + (p.valor ?? 0), 0);
  const risco = (id: string) => est?.secoes.find((s) => s.pedido_id === id)?.risco ?? null;
  const ORD = { alto: 0, medio: 1, baixo: 2 } as const;
  const segs = tri.pedidos.map((p) => ({ v: p.valor ?? 0, r: risco(p.id) }))
    .sort((x, y) => (x.r ? ORD[x.r] : 3) - (y.r ? ORD[y.r] : 3));
  const soma = (r: string | null) => segs.filter((s) => s.r === r).reduce((t, s) => t + s.v, 0);
  const COR = { alto: "var(--hi-fill)", medio: "var(--mid-fill)", baixo: "var(--lo-fill)" } as const;
  const nomePed = (id: string) => tri.pedidos.find((p) => p.id === id)?.titulo ?? "";

  const div = sub?.achados.filter((x) => x.tipo === "divergencia").sort((x, y) => (y.exposicao_estimada ?? 0) - (x.exposicao_estimada ?? 0)) ?? [];
  const fav = sub?.achados.filter((x) => x.tipo === "favoravel") ?? [];
  const favDist = fav.filter((x, i) => fav.findIndex((y) => y.pedido_id === x.pedido_id) === i).slice(0, 2);
  const pendForte = abertas.find((p) => /(ponto|espelho)/i.test(p.titulo) && /\d{4}-\d{2}/.test(p.titulo));
  const leg = (cor: string, rot: string, v: number, aval = false) => (
    <span className="leg"><i className={aval ? "aval" : ""} style={aval ? undefined : { background: cor }} />{rot} <strong className="num" style={{ color: "var(--ink)", fontWeight: 600 }}>{brl(v)}</strong></span>
  );
  const vazio = (txt: string) => (
    <>
      <span style={{ fontSize: 13, color: "var(--muted)" }}>{txt}</span>
      {cruzando && <><span className="skel" style={{ width: "80%" }} /><span className="skel" style={{ width: "60%" }} /></>}
    </>
  );

  return (
    <section className="card resumo" aria-label="Resumo de risco do processo">
      <div style={{ flex: "1.5 1 340px", gap: 12 }}>
        <div className="row" style={{ alignItems: "baseline", justifyContent: "space-between", gap: 12 }}>
          <span className="over">Em jogo</span>
          <span style={{ fontSize: 12.5, color: "var(--muted)" }}>{est ? `${tri.pedidos.length} pedidos` : cruzando ? "risco: em avaliação pelo agente" : `${tri.pedidos.length} pedidos · risco sai na estratégia`}</span>
        </div>
        <div className="row" style={{ alignItems: "baseline", gap: "6px 10px" }}>
          <span className="num" style={{ font: "600 34px/1 var(--f-sans)", letterSpacing: "-0.02em" }}>{brl(total)}</span>
          <span style={{ fontSize: 13, color: "var(--muted)" }}>total pleiteado</span>
        </div>
        <div aria-hidden="true" className="barra" style={{ height: 12 }}>
          {segs.map((s, i) => <span key={i} className={s.r ? "" : "aval"} style={{ flex: `${s.v || 1} 1 0`, background: s.r ? COR[s.r] : undefined }} />)}
        </div>
        <div className="row" style={{ gap: "6px 18px", fontSize: 12.5, color: "var(--muted)" }}>
          {est ? <>{leg(COR.alto, "Risco alto", soma("alto"))}{leg(COR.medio, "médio", soma("medio"))}{leg(COR.baixo, "baixo", soma("baixo"))}</>
            : leg("", "em avaliação", total, true)}
        </div>
      </div>

      <div style={{ flex: "1 1 250px" }}>
        <span className="over row" style={{ gap: 6, color: "var(--bad)" }}><I n="alerta" />Onde a empresa perde</span>
        {div.length ? (
          <>
            <div className="col" style={{ gap: 2 }}>
              <span style={{ fontWeight: 600 }}>{nomePed(div[0].pedido_id)}</span>
              <span style={{ fontSize: 13, color: "var(--muted)" }}>{div[0].titulo}</span>
            </div>
            {div[0].exposicao_estimada ? (
              <div className="row" style={{ alignItems: "baseline", gap: "4px 8px" }}>
                <span className="num" style={{ font: "600 20px/1 var(--f-sans)", color: "var(--bad)" }}>{brl(div[0].exposicao_estimada)}</span>
                <span style={{ fontSize: 12.5, color: "var(--muted)" }}>exposição estimada</span>
              </div>
            ) : null}
            {pendForte && <span style={{ fontSize: 12.5, color: "var(--muted)" }}>E: {pendForte.titulo.toLowerCase()} (Súmula 338)</span>}
          </>
        ) : sub ? vazio("Nenhuma divergência entre os sistemas de RH.") : vazio(cruzando ? "O agente está cruzando os dados…" : "Aparece depois da coleta de subsídios.")}
      </div>

      <div style={{ flex: "1 1 250px" }}>
        <span className="over row" style={{ gap: 6, color: "var(--ok)" }}><I n="checkC" />Onde a empresa ganha</span>
        {favDist.length ? (
          <>
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
              {favDist.map((f) => (
                <li key={f.pedido_id} className="col" style={{ gap: 1 }}>
                  <span style={{ fontWeight: 600 }}>{nomePed(f.pedido_id)}</span>
                  <span style={{ fontSize: 13, color: "var(--muted)" }}>{f.titulo}</span>
                </li>
              ))}
            </ul>
            <span style={{ fontSize: 12.5, color: "var(--muted)" }}>{fav.length} prova(s) a favor no processo</span>
          </>
        ) : sub ? vazio("Nenhuma prova documental a favor encontrada.") : vazio(cruzando ? "O agente está reunindo as provas…" : "Aparece depois da coleta de subsídios.")}
      </div>

      <div className="precisa" style={{ flex: "0.8 1 210px" }}>
        <span className="over row" style={{ gap: 6, color: "var(--warn)" }}><I n="pessoa" />Precisa de você</span>
        <div className="row" style={{ alignItems: "baseline", gap: 8 }}>
          <span className="num" style={{ font: "600 34px/1 var(--f-sans)" }}>{abertas.length}</span>
          <span style={{ fontSize: 13.5 }}>pendência(s) aberta(s)</span>
        </div>
        {abertas.length > 0 && !cruzando ? (
          <button type="button" className="btn btn-sec" onClick={irPendencias} style={{ alignSelf: "flex-start", minHeight: 36, padding: "0 12px", fontSize: 13 }}>Resolver pendências<I n="seta" /></button>
        ) : (
          <span style={{ fontSize: 12.5, color: "var(--muted)" }}>{cruzando ? "O agente segue trabalhando enquanto você resolve." : "Nada esperando por você agora."}</span>
        )}
      </div>
    </section>
  );
}
