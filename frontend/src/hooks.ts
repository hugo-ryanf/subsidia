import { useEffect, useRef, useState } from "react";
import { api, Job } from "./api";

/** Acompanha um job até `concluido`/`erro` e chama `aoTerminar` uma vez. */
export function useJob(jobId: string | null, aoTerminar: (j: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  const cb = useRef(aoTerminar);
  cb.current = aoTerminar;
  useEffect(() => {
    if (!jobId) { setJob(null); return; }
    let vivo = true;
    let timer: number;
    const tick = async () => {
      try {
        const j = await api.job(jobId);
        if (!vivo) return;
        setJob(j);
        if (j.status === "concluido" || j.status === "erro") { cb.current(j); return; }
      } catch { /* rede oscilou: tenta de novo */ }
      timer = window.setTimeout(tick, 1500);
    };
    tick();
    return () => { vivo = false; window.clearTimeout(timer); };
  }, [jobId]);
  return job;
}

/** Repete `fn` a cada `ms` enquanto `ativo`. */
export function usePolling(fn: () => void, ms: number, ativo: boolean) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    if (!ativo) return;
    ref.current();
    const t = window.setInterval(() => ref.current(), ms);
    return () => window.clearInterval(t);
  }, [ms, ativo]);
}
