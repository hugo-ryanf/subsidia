import type { CSSProperties } from "react";
/** Ícones do sistema visual (traço 1,75, 24×24). Sempre decorativos: o texto ao lado diz o que é. */
const P = {
  refresh: "M20 11a8 8 0 0 0-14.9-3.5M4 4v4h4M4 13a8 8 0 0 0 14.9 3.5M20 20v-4h-4",
  voltar: "M19 12H5M11 6l-6 6 6 6",
  raio: "M13 2L4.5 13.5H11L10 22l8.5-11.5H12L13 2z",
  play: "M7 4.5v15l12-7.5z",
  check: "M5 12.5l4.5 4.5L19 7.5",
  checkC: "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M8 12.5l2.8 2.8L16 10",
  alerta: "M12 4L2.5 20h19L12 4zM12 10v4.5M12 17.5v.01",
  pessoa: "M8.5 8a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0-7 0M5 20a7 7 0 0 1 14 0",
  pessoaOk: "M5.5 8a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0-7 0M2.5 20a6.5 6.5 0 0 1 13 0M16 11.5l2 2 4-4",
  menosC: "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M8.5 12h7",
  xC: "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M9 9l6 6M15 9l-6 6",
  arco: "M20 12a8 8 0 1 1-8-8",
  cadeado: "M7 11h10a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2zM8 11V8a4 4 0 0 1 8 0v3",
  externo: "M7 17L17 7M9 7h8v8",
  doc: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5",
  docLinhas: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6",
  chevD: "M9 6l6 6-6 6",
  chevB: "M6 9l6 6 6-6",
  placa: "M12 3v18M5 6h11l3 3-3 3H5zM9 21h6",
  banco: "M5 6c0-1.7 3.1-3 7-3s7 1.3 7 3-3.1 3-7 3-7-1.3-7-3zM5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3",
  faisca: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM18.5 16.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z",
  nuvem: "M7 18h10a4 4 0 0 0 .6-7.96A6 6 0 0 0 6.2 9.4 4.3 4.3 0 0 0 7 18z",
  x: "M6 6l12 12M18 6L6 18",
  upload: "M12 16V4M7 9l5-5 5 5M5 20h14",
  download: "M12 4v12M7 11l5 5 5-5M5 20h14",
  info: "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 11v5M12 8v.01",
  seta: "M5 12h14M13 6l6 6-6 6",
  setaB: "M12 5v14M6 13l6 6 6-6",
  circulo: "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0",
} as const;

export type NomeIcone = keyof typeof P;
const CHEIOS = new Set<NomeIcone>(["raio", "play"]);

export function I({ n, cls = "", style }: { n: NomeIcone; cls?: string; style?: CSSProperties }) {
  return (
    <svg className={`i ${CHEIOS.has(n) ? "f" : ""} ${n === "arco" ? "spin" : ""} ${cls}`} viewBox="0 0 24 24" aria-hidden="true" style={style}>
      <path d={P[n]} />
    </svg>
  );
}

/** Glifo de barras do nível de risco: legível sem cor. */
export function Barras({ nivel }: { nivel: "alto" | "medio" | "baixo" }) {
  const b2 = nivel === "baixo" ? 0.3 : 1, b3 = nivel === "alto" ? 1 : 0.3;
  return (
    <svg viewBox="0 0 14 14" aria-hidden="true" style={{ width: 13, height: 13, fill: "currentColor" }}>
      <rect x="1" y="8" width="3" height="5" rx="1" /><rect x="5.5" y="5" width="3" height="8" rx="1" opacity={b2} />
      <rect x="10" y="2" width="3" height="11" rx="1" opacity={b3} />
    </svg>
  );
}
