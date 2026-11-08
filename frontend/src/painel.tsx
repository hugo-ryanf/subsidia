import { Evento, Rastro } from "./api";

const ICONE: Record<string, string> = { decisao: "◆", ferramenta: "⚙", chat: "✦", humano: "👤", erro: "⚠" };

function descrever(e: Evento): { titulo: string; sub?: string } | null {
  const d = e.detalhe || {};
  if (e.tipo === "embedding") return null;
  if (e.tipo === "decisao") {
    if (d.acao) return { titulo: `${e.etiqueta.replace("subsidios:", "")} → ${d.acao}${d.args && Object.keys(d.args).length ? " " + JSON.stringify(d.args) : ""}`, sub: d.pensamento };
    if (e.etiqueta === "pendencia_aberta") return { titulo: `Pendência escalada: ${d.titulo}`, sub: `origem: ${d.origem}` };
    return { titulo: e.etiqueta.replace(":", " · "), sub: Object.keys(d).length ? JSON.stringify(d).slice(0, 140) : undefined };
  }
  if (e.tipo === "ferramenta") {
    if (e.etiqueta.endsWith(":falhou")) return { titulo: `${e.etiqueta.replace(":falhou", "")} — sistema fora do ar, tentativa ${d.tentativa}`, sub: d.erro };
    return { titulo: `${d.sistema ?? "sistema"} · ${e.etiqueta}`, sub: d.status === "ok" ? (d.documento ? `documento anexado: ${d.documento.nome}` : "ok") : `⚠ ${d.motivo ?? d.status}` };
  }
  if (e.tipo === "chat") return { titulo: `${e.etiqueta}`, sub: `${e.modelo} · ${e.tokens_entrada + e.tokens_saida} tokens · US$ ${e.custo_usd.toFixed(4)} · ${e.segundos}s` };
  if (e.tipo === "humano") return { titulo: `Humano: ${e.etiqueta}`, sub: d.resolucao ?? d.observacao ?? undefined };
  if (e.tipo === "erro") return { titulo: `Erro em ${e.etiqueta}`, sub: d.erro };
  return { titulo: e.etiqueta };
}

export function Atividade({ rastro }: { rastro: Rastro | null }) {
  const evs = (rastro?.eventos ?? []).slice().reverse().map((e) => ({ e, d: descrever(e) })).filter((x) => x.d).slice(0, 60);
  return (
    <div className="card painel">
      <h3>Atividade do agente <span className="muted">(rastro auditável)</span></h3>
      {evs.length === 0 && <p className="muted">Nada ainda. Cada decisão, consulta a sistema e chamada de modelo aparece aqui.</p>}
      <ul className="feed">
        {evs.map(({ e, d }) => (
          <li key={e.id} className={`ev ev-${e.tipo}`}>
            <span className="ev-ico">{ICONE[e.tipo] ?? "•"}</span>
            <div>
              <div className="ev-tit">{d!.titulo}</div>
              {d!.sub && <div className="ev-sub">{d!.sub}</div>}
            </div>
            <time>{new Date(e.criado_em).toLocaleTimeString("pt-BR")}</time>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Metricas({ rastro, segundosAgente, minutosManual }: { rastro: Rastro | null; segundosAgente?: number; minutosManual?: number }) {
  const t = rastro?.totais;
  return (
    <div className="card metricas">
      <h3>Custo e ganho</h3>
      <div className="kpis">
        <div><b>US$ {(t?.custo_usd ?? 0).toFixed(3)}</b><span>custo de IA no processo</span></div>
        <div><b>{t ? (t.tokens_entrada + t.tokens_saida).toLocaleString("pt-BR") : 0}</b><span>tokens</span></div>
        <div><b>{t?.chamadas_modelo ?? 0}</b><span>chamadas de modelo</span></div>
        <div><b>{t?.ferramentas ?? 0}</b><span>operações em sistemas</span></div>
        {segundosAgente != null && <div><b>{(segundosAgente / 60).toFixed(1)} min</b><span>coleta pelo agente</span></div>}
        {minutosManual != null && <div><b>~{(minutosManual / 60).toFixed(1)} h</b><span>mesma coleta feita à mão (estimativa)</span></div>}
      </div>
    </div>
  );
}
