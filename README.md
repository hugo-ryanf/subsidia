# Subsídia — digital worker de contencioso trabalhista

> Converge Challenge powered by Tako · **Desafio Tako: Digital Workers para RH**
>
> **Demo ao vivo:** https://subsidia.onrender.com 

| | |
|---|---|
| **Projeto** | Subsídia |
| **Time** | Canário Belga |
| **Resumo** | Agente que lê a petição trabalhista, opera os sistemas de RH, cruza ponto, folha e FGTS e entrega a estratégia de defesa por pedido, com cada prova citada. |
| **Vídeo demo** | https://www.youtube.com/watch?v=zvCosxyy4FU |
| **Link do projeto** | https://subsidia.onrender.com |
| **Apresentação** | [Descrição (PDF)](Subsidia_Descricao.pdf) · [Pitch (Google Slides)](https://docs.google.com/presentation/d/1B5-2eMra6kLr4SII9Xc3fE2IwlyM9FhZ4r6-N3dUjeY/edit?slide=id.p1#slide=id.p1) |
| **Código-fonte** | https://github.com/hugo-ryanf/subsidia |
| **Tags** | Digital Workers, RH, Jurídico trabalhista, AI agents, RAG, Legaltech, FastAPI, Desafio Tako |

**Integrantes:** Rafael Henrique Ribeiro Amancio · Caio Vitor Melo De Santana · Hugo Ryan Santos de França

## O problema e a solução

Quando uma empresa recebe uma reclamação trabalhista, o advogado pede ao RH dezenas de documentos
espalhados em vários sistemas (ponto, folha, FGTS, SST). Há idas e vindas, atraso e risco real: **sem
cartão de ponto, a Justiça presume verdadeira a jornada alegada pelo ex-funcionário (Súmula 338 do TST)**.

O Subsídia é um agente que:

1. **lê a petição inicial** e separa cada pedido, com valor, categoria, confiança e a página de onde tirou;
2. **opera os sistemas da empresa sozinho** (ponto, folha, FGTS, SST, cadastro), decidindo o que buscar
   pedido a pedido, e anexa cada documento ao processo, citável por documento e página;
3. **cruza os dados com regras determinísticas**: ponto × holerite, prazo do TRCT, competências do FGTS,
   cadência do EPI e laudo. O resultado diz onde a empresa ganha e onde perde, com exposição estimada;
4. **escala para um humano** o que não fecha (documento ausente, prova que depende de testemunha), com o
   contexto pronto;
5. **escreve a estratégia por pedido**: tese, prova a favor, pontos fracos e recomendação. O risco sai dos
   achados, não da opinião do modelo, e citação inválida é marcada.

Entre as etapas há **portões humanos**: o agente prepara, a pessoa aprova. Decisão de acordo e assinatura
da defesa são sempre do advogado.

## Resultado no caso de demonstração (`eval/run.py`)

| Métrica | Resultado |
|---|---|
| Pedidos extraídos da inicial (valor + categoria + citação) | 6/6 |
| Problemas plantados detectados (horas extras não pagas, ponto ausente, dano moral sem prova) | 3/3 |
| Defesas comprovadas (TRCT no prazo, FGTS integral, EPI + LTCAT) | 3/3 |
| Seções da estratégia com citação válida | 6/6 |
| Documentos coletados nos sistemas | 52 |
| Tempo do agente × mesma coleta manual (estimativa) | ~1–3 min × ~7,7 h |

## Integração real: AFD do ponto

Além dos sistemas simulados, o Subsídia lê o **AFD (Arquivo Fonte de Dados)**, o arquivo que **todo registrador
eletrônico de ponto no Brasil é obrigado a exportar**, com layout fixo definido pelas Portarias 1510/2009 e 671/2021.
Importado no processo, o agente passa a ler o ponto direto dele, sem integração com o sistema de cada fabricante:

- reconhece os dois layouts de marcação (PIS da 1510 e CPF da 671) e filtra o empregado do processo;
- monta a jornada por dia e aponta **batida faltando** (marcação ímpar) como pendência, sem descartar nada;
- gera o espelho em PDF a partir do AFD (com arquivo e faixa de NSR) para a citação continuar valendo;
- linha que não se entende aparece no resumo da importação. Limitação declarada: o CRC-16 ainda não é validado.

Para testar: na etapa de coleta, "baixar AFD de exemplo" e depois "Importar AFD".

## Regras

1. Todo input tem retorno explícito; etapas com IA retornam confiança. Falha vira status ou pendência, nunca log silencioso.
2. Perímetro explícito: a UI sinaliza quando a IA roda em nuvem. Em produção, o mesmo código aponta para Ollama local.
3. Toda busca é escopada por `processo_id` dentro da própria query.
4. Nada é descartado em silêncio: baixa confiança vira `requer_revisao`; descarte exige justificativa humana.

**Confiabilidade:** retentativa com backoff quando o sistema de RH cai (o FGTS simulado devolve 503 na
primeira chamada, de propósito); nova tentativa quando o modelo devolve resposta vazia; troca para o
modelo mais forte; por fim, **playbook determinístico** para a coleta não parar. Há também um guarda
contra loop de ações repetidas.

## Arquitetura

```
frontend (React + Vite) ── servido pelo mesmo app
app FastAPI
  camada/    ingestão PyMuPDF → chunks com overlap entre páginas → embeddings → busca híbrida (vetorial + FTS5, RRF)
  agentes/   triagem · worker de subsídios (loop de ferramentas) · cruzamento determinístico · estratégia
  rh_mock/   "sistemas da empresa" simulados: cadastro, ponto, folha, FGTS, SST (API + PDFs)
  rastro     cada decisão, ferramenta e chamada de modelo (tokens, custo, tempo) → painel auditável
SQLite (dados + FTS5 + vetores) · Featherless (LLM e embedding)
```

## Modelos e ferramentas

- **Featherless** (API OpenAI-compatible): `zai-org/GLM-5.2` (triagem e estratégia), `google/gemma-4-31B-it`
  (decisões do loop e síntese), `Qwen/Qwen3-Embedding-4B` (embeddings)
- FastAPI, SQLite/FTS5, NumPy, PyMuPDF, fpdf2, React, Vite, marked
- Desenvolvido com Claude Code

## Rodar

```bash
cp .env.example .env            # coloque LLM_API_KEY (Featherless)
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # (Linux/mac: .venv/bin/pip)
cd frontend && npm ci && npm run build && cd ..
.venv/Scripts/python -m uvicorn app.main:app --port 8000
# abra http://localhost:8000 e clique em "Rodar o caso de demonstração"
```

Docker: `docker build -t subsidia . && docker run -p 8000:8000 -e LLM_API_KEY=... -v subsidia:/data subsidia`

Testes: `pytest tests/test_rh_mock.py tests/test_fallback.py` (offline) · `python -m eval.run` (ponta a ponta, usa a API).

**Dados:** 100% sintéticos (empresa, empregado, petição e documentos fictícios).
