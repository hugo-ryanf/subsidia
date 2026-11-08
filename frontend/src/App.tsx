import { useCallback, useEffect, useState } from "react";
import { api, Job, Processo, Rastro } from "./api";
import { VisaoEstrategia, VisaoSubsidios, VisaoTriagem } from "./etapas";
import { useJob, usePolling } from "./hooks";
import { Atividade, Metricas } from "./painel";

type Etapa = "triagem" | "subsidios" | "estrategia";
const ETAPAS: { id: Etapa; nome: string; desc: string }[] = [
  { id: "triagem", nome: "1. Triagem da inicial", desc: "O agente lê a reclamação e separa cada pedido, com valor, categoria e a página de onde tirou." },
  { id: "subsidios", nome: "2. Coleta de subsídios", desc: "O digital worker opera ponto, folha, FGTS e SST, anexa os documentos e cruza os dados." },
  { id: "estrategia", nome: "3. Estratégia de defesa", desc: "Tese, prova citada, pontos fracos e risco por pedido. A decisão final é do advogado." },
];

export default function App() {
  const [pid, setPid] = useState<string | null>(() => new URLSearchParams(location.search).get("p"));
  const [health, setHealth] = useState<{ perimetro: string; provedor: string; modelos: Record<string, string> } | null>(null);
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, []);
  const abrir = (id: string | null) => {
    setPid(id);
    history.replaceState(null, "", id ? `?p=${id}` : location.pathname);
  };
  return (
    <div className="app">
      <header className="topo">
        <div className="marca" onClick={() => abrir(null)}>
          <span className="logo">⚖</span>
          <div><b>Subsídia</b><small>digital worker de contencioso trabalhista</small></div>
        </div>
        {health && (
          <div className={`perimetro p-${health.perimetro}`} title={`${health.provedor}\n${Object.values(health.modelos).join("\n")}`}>
            {health.perimetro === "nuvem" ? "☁ IA em nuvem (Featherless) · dados sintéticos" : "🔒 IA local"}
          </div>
        )}
      </header>
      {pid ? <TelaProcesso pid={pid} voltar={() => abrir(null)} /> : <Inicio abrir={abrir} />}
    </div>
  );
}

function Inicio({ abrir }: { abrir: (id: string) => void }) {
  const [lista, setLista] = useState<{ id: string; nome: string; criado_em: string }[]>([]);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [nome, setNome] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  useEffect(() => { api.processos().then(setLista).catch((e) => setErro(e.message)); }, []);
  const demo = async () => {
    setOcupado(true); setErro(null);
    try { const r = await api.demo(); abrir(r.processo_id); } catch (e: any) { setErro(e.message); setOcupado(false); }
  };
  const pronto = async () => {
    setOcupado(true); setErro(null);
    try { const r = await api.pronto(); abrir(r.processo_id); } catch (e: any) { setErro(e.message); setOcupado(false); }
  };
  const enviar = async () => {
    if (!arquivo) return;
    setOcupado(true); setErro(null);
    try {
      const r = await api.criar(nome || arquivo.name);
      await api.upload(r.processo_id, arquivo);
      abrir(r.processo_id);
    } catch (e: any) { setErro(e.message); setOcupado(false); }
  };
  return (
    <main className="inicio">
      <section className="hero">
        <h1>Da reclamação trabalhista à defesa pronta, com prova tirada dos sistemas de RH</h1>
        <p>O agente lê a petição, busca sozinho ponto, holerites, TRCT, FGTS e EPI, cruza os dados e mostra onde a
          empresa ganha e onde perde, sempre citando o documento. O que não fecha vai para uma pessoa decidir.</p>
        <div className="cta">
          <button className="grande" onClick={pronto} disabled={ocupado}>⚡ Ver caso já analisado</button>
          <button className="sec grande-sec" onClick={demo} disabled={ocupado}>▶ Rodar o agente ao vivo (~6 min)</button>
        </div>
        <p className="muted small">Mercado Exemplo Ltda × ex-repositor de câmara fria (dados 100% sintéticos). O caso analisado abre na hora,
          com o rastro de tudo que o agente fez; ao vivo, você acompanha o agente trabalhando passo a passo.</p>
      </section>
      {erro && <div className="alerta">{erro}</div>}
      <section className="card">
        <h3>Nova reclamação</h3>
        <div className="form-linha">
          <input placeholder="Nome do processo" value={nome} onChange={(e) => setNome(e.target.value)} />
          <input type="file" accept="application/pdf" onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
          <button onClick={enviar} disabled={!arquivo || ocupado}>Enviar petição</button>
        </div>
        <p className="muted small">Os sistemas de RH desta demo são simulados: a coleta funciona para o empregado da empresa fictícia.</p>
      </section>
      {lista.length > 0 && (
        <section className="card">
          <h3>Processos</h3>
          <ul className="lista">
            {lista.map((p) => (
              <li key={p.id} onClick={() => abrir(p.id)}>{p.nome}<span className="muted small">{new Date(p.criado_em).toLocaleString("pt-BR")}</span></li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

function TelaProcesso({ pid, voltar }: { pid: string; voltar: () => void }) {
  const [proc, setProc] = useState<Processo | null>(null);
  const [rastro, setRastro] = useState<Rastro | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [aba, setAba] = useState<Etapa>("triagem");
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const [p, r] = await Promise.all([api.processo(pid), api.rastro(pid)]);
      setProc(p); setRastro(r);
      return p;
    } catch (e: any) { setErro(e.message); return null; }
  }, [pid]);

  const rodar = useCallback(async (etapa: Etapa) => {
    setErro(null);
    try { const r = await api.rodar(pid, etapa); setJobId(r.job_id); setAba(etapa); } catch (e: any) { setErro(e.message); }
  }, [pid]);

  // Retoma um job em andamento depois de reload; abre a aba da etapa mais avançada.
  useEffect(() => {
    (async () => {
      const p = await carregar();
      const js = await api.jobs(pid).catch(() => ({} as Record<string, Job>));
      const andamento = Object.values(js).find((j) => j.status === "queued" || j.status === "processando");
      if (andamento) setJobId(andamento.id);
      const pedida = new URLSearchParams(location.search).get("aba") as Etapa | null;
      if (pedida && ETAPAS.some((e) => e.id === pedida)) setAba(pedida);
      else if (p?.artefatos.estrategia) setAba("estrategia");
      else if (p?.artefatos.subsidios) setAba("subsidios");
    })();
  }, [pid, carregar]);

  const job = useJob(jobId, async (j) => {
    setJobId(null);
    if (j.status === "erro") setErro(`${j.tipo}: ${j.erro}`);
    const p = await carregar();
    if (j.status === "concluido" && j.tipo !== "ingestao") setAba(j.tipo as Etapa);
    // Petição indexada → a triagem começa sozinha (o humano aprova depois).
    if (j.status === "concluido" && j.tipo === "ingestao" && p && !p.artefatos.triagem) rodar("triagem");
  });
  usePolling(() => { api.rastro(pid).then(setRastro).catch(() => {}); }, 2000, !!jobId);

  const aprovar = async (tipo: Etapa, proxima?: Etapa) => {
    setErro(null);
    try { await api.aprovar(pid, tipo); await carregar(); if (proxima) rodar(proxima); } catch (e: any) { setErro(e.message); }
  };

  if (!proc) return <main><p className="muted">Carregando…</p>{erro && <div className="alerta">{erro}</div>}</main>;
  const a = proc.artefatos;
  const rodando = !!job && (job.status === "queued" || job.status === "processando");
  const estado = (e: Etapa) => (rodando && job?.tipo === e ? "rodando" : a[e] ? (a[e]!.aprovado ? "aprovado" : "aguarda aprovação") : "pendente");

  return (
    <main className="processo">
      <div className="cab-proc">
        <button className="sec" onClick={voltar}>← processos</button>
        <h2>{proc.nome}</h2>
        <span className="muted small">{proc.documentos.length} documento(s) · {proc.pendencias.filter((p) => p.status === "aberta").length} pendência(s) aberta(s)</span>
      </div>
      {erro && <div className="alerta">{erro}</div>}
      <div className="colunas">
        <div className="principal">
          <nav className="stepper">
            {ETAPAS.map((e) => (
              <button key={e.id} className={`step ${aba === e.id ? "ativo" : ""} st-${estado(e.id).split(" ")[0]}`} onClick={() => setAba(e.id)}>
                <b>{e.nome}</b><span>{estado(e.id)}</span>
              </button>
            ))}
          </nav>
          {rodando && (
            <div className="rodando">
              <span className="spinner" /> {job!.tipo === "ingestao" ? "Lendo e indexando a petição…" : `Agente trabalhando: ${job!.etapa ?? job!.tipo}…`}
            </div>
          )}
          {ETAPAS.filter((e) => e.id === aba).map((e) => {
            const art = a[e.id];
            const anterior = e.id === "subsidios" ? a.triagem : e.id === "estrategia" ? a.subsidios : null;
            const liberado = e.id === "triagem" || !!anterior?.aprovado;
            const proxima: Etapa | undefined = e.id === "triagem" ? "subsidios" : e.id === "subsidios" ? "estrategia" : undefined;
            return (
              <section key={e.id} className="card etapa">
                <div className="etapa-cab">
                  <div><h3>{e.nome}</h3><p className="muted small">{e.desc}</p></div>
                  <div className="acoes">
                    {!rodando && liberado && <button className="sec" onClick={() => rodar(e.id)}>{art ? "Rodar de novo" : "Rodar agente"}</button>}
                    {art && !art.aprovado && !rodando && <button onClick={() => aprovar(e.id, proxima)}>✓ Aprovar{proxima ? " e seguir" : ""}</button>}
                    {art?.aprovado && <span className="tag tag-ok">aprovado por humano</span>}
                  </div>
                </div>
                {!liberado && <p className="muted">Aprove a etapa anterior para liberar esta (portão humano).</p>}
                {e.id === "triagem" && a.triagem && <VisaoTriagem pid={pid} t={a.triagem.conteudo} />}
                {e.id === "subsidios" && a.subsidios && a.triagem && (
                  <VisaoSubsidios pid={pid} s={a.subsidios.conteudo} tri={a.triagem.conteudo} pendencias={proc.pendencias} aoMudar={carregar} />
                )}
                {e.id === "estrategia" && a.estrategia && <VisaoEstrategia pid={pid} e={a.estrategia.conteudo} />}
              </section>
            );
          })}
        </div>
        <aside className="lateral">
          <Metricas rastro={rastro} segundosAgente={a.subsidios?.conteudo.resumo?.segundos_agente}
                    minutosManual={a.subsidios?.conteudo.resumo?.minutos_manual_estimados} />
          <Atividade rastro={rastro} />
        </aside>
      </div>
    </main>
  );
}
