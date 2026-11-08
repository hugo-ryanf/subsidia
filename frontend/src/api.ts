export type Fonte = { ref: string; documento_id: string; documento: string; pagina_inicio: number; pagina_fim: number };

export type Pedido = {
  id: string; titulo: string; valor: number | null; alegacao: string | null; periodo_alegado: string | null;
  arquetipo: string; arquetipo_nome: string | null; fontes: Fonte[]; confianca: number;
  requer_revisao: boolean; motivos_revisao: string[];
};

export type Triagem = {
  processo: Record<string, any> & { fontes: Fonte[] };
  pedidos: Pedido[]; total_pedidos: number; valor_total_pedidos: number; requer_revisao: number;
};

export type Evidencia = { documento_id: string; nome: string; sistema: string; chave: string };
export type Achado = {
  pedido_id: string; tipo: "favoravel" | "divergencia" | "pendencia" | "cobertura"; severidade: string;
  titulo: string; detalhe: string; evidencias: Evidencia[]; exposicao_estimada: number | null;
};

export type Subsidios = {
  bloqueado?: boolean; motivo?: string;
  matricula: string; funcionario: string; documentos: Evidencia[];
  coletas: { pedido_id: string; concluido: boolean; modo?: string; resumo?: string | null; passos: { acao: string; args: any; pensamento: string; observacao: string }[] }[];
  achados: Achado[];
  resumo: { documentos_coletados: number; favoraveis: number; divergencias: number; pendencias: number;
    exposicao_estimada: number; segundos_agente: number; minutos_manual_estimados: number };
};

export type Secao = {
  pedido_id: string; titulo: string; valor: number | null; risco: "baixo" | "medio" | "alto";
  exposicao_estimada: number | null; markdown: string; citacoes: Fonte[]; requer_revisao: boolean; motivos_revisao: string[];
};
export type Estrategia = { sintese: string; secoes: Secao[]; valor_total_pleiteado: number; valor_em_risco_alto: number; pendencias_abertas: number };

export type Artefato<T> = { conteudo: T; aprovado: boolean; atualizado_em: string } | null;

export type Pendencia = { id: string; pedido_id: string | null; titulo: string; contexto: string; status: string; resolucao: string | null };

export type Processo = {
  id: string; nome: string; criado_em: string;
  documentos: { id: string; nome: string; classe: string; origem: string; paginas: number; chunks: number; paginas_revisao: number; status: string; erro: string | null }[];
  pendencias: Pendencia[];
  artefatos: { triagem: Artefato<Triagem>; subsidios: Artefato<Subsidios>; estrategia: Artefato<Estrategia> };
};

export type Job = { id: string; tipo: string; status: "queued" | "processando" | "concluido" | "erro"; etapa: string | null; erro: string | null };

export type Evento = {
  id: number; tipo: string; etiqueta: string; modelo: string | null; tokens_entrada: number; tokens_saida: number;
  custo_usd: number; segundos: number; detalhe: any; criado_em: string; job_id: string | null;
};
export type Rastro = {
  eventos: Evento[];
  totais: { chamadas_modelo: number; ferramentas: number; tokens_entrada: number; tokens_saida: number; custo_usd: number; segundos_modelo: number };
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  if (!r.ok) {
    let msg = `${r.status}`;
    try { const j = await r.json(); msg = j.detail ?? JSON.stringify(j); } catch { /* corpo vazio */ }
    throw new Error(msg);
  }
  return r.json();
}

const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  health: () => req<{ perimetro: string; provedor: string; modelos: Record<string, string> }>("/health"),
  processos: () => req<{ id: string; nome: string; criado_em: string }[]>("/processos"),
  processo: (id: string) => req<Processo>(`/processos/${id}`),
  jobs: (id: string) => req<Record<string, Job>>(`/processos/${id}/jobs`),
  job: (id: string) => req<Job>(`/jobs/${id}`),
  rastro: (id: string) => req<Rastro>(`/processos/${id}/rastro`),
  pronto: () => req<{ processo_id: string }>("/demo/pronto", { method: "POST" }),
  demo: () => req<{ processo_id: string; job_id: string }>("/demo/processo", { method: "POST" }),
  criar: (nome: string) => req<{ processo_id: string }>("/processos", json({ nome })),
  upload: (id: string, f: File) => {
    const fd = new FormData(); fd.append("arquivo", f);
    return req<{ job_id: string }>(`/processos/${id}/documentos`, { method: "POST", body: fd });
  },
  rodar: (id: string, etapa: "triagem" | "subsidios" | "estrategia") => req<{ job_id: string }>(`/processos/${id}/${etapa}`, { method: "POST" }),
  aprovar: (id: string, tipo: string, observacao?: string) => req(`/processos/${id}/aprovar/${tipo}`, json({ observacao })),
  resolver: (id: string, pend: string, status: "resolvida" | "descartada", resolucao: string) =>
    req(`/processos/${id}/pendencias/${pend}`, json({ status, resolucao })),
};

export const docUrl = (pid: string, f: { documento_id: string; pagina_inicio?: number }) =>
  `/processos/${pid}/documentos/${f.documento_id}/arquivo${f.pagina_inicio ? `#page=${f.pagina_inicio}` : ""}`;

export const brl = (v: number | null | undefined) =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
