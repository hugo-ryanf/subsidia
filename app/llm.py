"""Cliente de LLM e embedding (dialeto OpenAI).

Regra #1: qualquer falha vira LLMError com o corpo do provedor; nunca resposta vazia
engolida. Cada chamada registra tokens, custo (`usage.cost`, que a Featherless devolve)
e latência no rastro do processo, para o painel "custo por execução".
"""
from __future__ import annotations

import json
import logging
import random
import re
import threading
import time

import httpx

from app.config import cfg

logger = logging.getLogger(__name__)

_STATUS_RETENTAVEIS = {429, 500, 502, 503, 504}
_ERROS_RETENTAVEIS = (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)
_MAX_RETENTATIVAS = 3
_MAX_ADAPTACOES = 2
_ESPERA_INICIAL_S = 1.5

_cliente: httpx.Client | None = None
_trava = threading.Lock()


class LLMError(RuntimeError):
    """Falha do provedor, sempre com contexto suficiente para virar status/pendência."""


def _http() -> httpx.Client:
    global _cliente
    with _trava:
        if _cliente is None:
            _cliente = httpx.Client(limits=httpx.Limits(max_connections=8))
        return _cliente


def _headers() -> dict:
    return {"Content-Type": "application/json", "Authorization": f"Bearer {cfg.llm_api_key}"}


def _espera(resposta: httpx.Response | None, tentativa: int) -> float:
    base = _ESPERA_INICIAL_S * (2 ** tentativa)
    if resposta is not None:
        try:
            base = max(0.5, min(float(resposta.headers.get("Retry-After", "")), 60.0))
        except ValueError:
            pass
    return base + random.uniform(0, base * 0.3)


def _adaptar(body: dict, corpo_erro: str) -> str | None:
    """Ajusta o corpo ao dialeto do provedor a partir do 400."""
    erro = corpo_erro.lower()
    for campo in ("response_format", "reasoning_effort", "temperature"):
        if campo in erro and campo in body:
            body.pop(campo)
            return f"{campo} removido"
    return None


def _post(path: str, body: dict, model: str, timeout: float) -> dict:
    url = f"{cfg.llm_base_url.rstrip('/')}{path}"
    retent = adapt = 0
    while True:
        try:
            r = _http().post(url, json=body, headers=_headers(), timeout=timeout)
        except _ERROS_RETENTAVEIS as e:
            if retent >= _MAX_RETENTATIVAS:
                raise LLMError(f"{model}: sem resposta do provedor ({type(e).__name__})") from e
            time.sleep(_espera(None, retent))
            retent += 1
            continue
        if r.status_code == 400 and adapt < _MAX_ADAPTACOES:
            mudanca = _adaptar(body, r.text)
            if mudanca:
                logger.warning("dialeto do provedor (%s): %s", model, mudanca)
                adapt += 1
                continue
        if r.status_code in _STATUS_RETENTAVEIS and retent < _MAX_RETENTATIVAS:
            time.sleep(_espera(r, retent))
            retent += 1
            continue
        if r.status_code >= 400:
            raise LLMError(f"{model}: HTTP {r.status_code} — {r.text[:400]}")
        return r.json()


# --- rastro --------------------------------------------------------------------------
# Hook preenchido por app.rastro para gravar cada chamada no processo corrente sem
# acoplar este módulo ao banco.
registrar_chamada = None  # type: ignore[assignment]


def _registrar(tipo: str, model: str, uso: dict, segundos: float, etiqueta: str) -> dict:
    info = {
        "tipo": tipo,
        "modelo": model,
        "etiqueta": etiqueta,
        "tokens_entrada": uso.get("prompt_tokens", 0) or 0,
        "tokens_saida": uso.get("completion_tokens", 0) or 0,
        "custo_usd": float(uso.get("cost", 0) or 0),
        "segundos": round(segundos, 2),
    }
    if registrar_chamada:
        try:
            registrar_chamada(info)
        except Exception:  # rastro nunca derruba a chamada; mas fica no log
            logger.exception("falha ao registrar rastro da chamada %s", etiqueta)
    return info


# --- fachada ---------------------------------------------------------------------------

def chat(system: str, user: str, *, pesado: bool = False, json_mode: bool = False,
         max_tokens: int = 4000, temperature: float = 0.1, timeout: float = 180,
         etiqueta: str = "") -> str:
    model = cfg.model_pesado if pesado else cfg.model_leve
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    t0 = time.time()
    dados = _post("/chat/completions", body, model, timeout)
    escolha = (dados.get("choices") or [{}])[0]
    conteudo = ((escolha.get("message") or {}).get("content") or "").strip()
    _registrar("chat", model, dados.get("usage") or {}, time.time() - t0, etiqueta)
    if not conteudo:
        raise LLMError(f"{model}: resposta vazia (finish_reason={escolha.get('finish_reason')})")
    return conteudo


def chat_json(system: str, user: str, **kw) -> dict:
    """Chat que DEVE devolver um objeto JSON. Tolera cerca de markdown; senão LLMError."""
    texto = chat(system, user, json_mode=True, **kw)
    return extrair_json(texto)


def extrair_json(texto: str) -> dict:
    limpo = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    try:
        obj = json.loads(limpo)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", limpo, re.S)
        if not m:
            raise LLMError(f"resposta não é JSON: {texto[:200]}")
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise LLMError(f"JSON inválido: {e}; trecho: {texto[:200]}") from e
    if not isinstance(obj, dict):
        raise LLMError(f"esperado objeto JSON, veio {type(obj).__name__}")
    return obj


def embed(textos: list[str], etiqueta: str = "embedding", lote: int = 32) -> list[list[float]]:
    """Embeddings em lote. Falha sobe como LLMError — quem chama decide requer_revisao."""
    vetores: list[list[float]] = []
    for i in range(0, len(textos), lote):
        parte = textos[i:i + lote]
        t0 = time.time()
        dados = _post("/embeddings", {"model": cfg.embed_model, "input": parte}, cfg.embed_model, 120)
        itens = sorted(dados.get("data") or [], key=lambda d: d.get("index", 0))
        if len(itens) != len(parte):
            raise LLMError(f"embedding devolveu {len(itens)} vetores para {len(parte)} textos")
        vetores.extend(d["embedding"] for d in itens)
        _registrar("embedding", cfg.embed_model, dados.get("usage") or {}, time.time() - t0, etiqueta)
    return vetores
