# Material de submissão — Converge Challenge (prazo: dom 8/11, 13h)

## 1. Descrição do projeto (colar no painel da Canastra)

**Subsídia: digital worker de contencioso trabalhista** · responde ao **Desafio Tako (Digital Workers para RH)**

**Problema.** Quando chega uma reclamação trabalhista, o advogado pede ao RH dezenas de documentos espalhados em
vários sistemas: ponto, folha, FGTS, segurança do trabalho. O RH vira a "cola" entre os sistemas, com idas e vindas e
atraso. E documento que não chega custa caro: sem cartão de ponto, a Justiça presume verdadeira a jornada alegada
pelo ex-funcionário (Súmula 338 do TST).

**Para quem.** Empresas com volume de processos trabalhistas (varejo, logística, call center, bancos,
terceirização), seus departamentos jurídico e pessoal, e os escritórios que as atendem.

**Solução.** Um agente que recebe a petição inicial e conduz a coleta de prova de ponta a ponta:
1. separa cada pedido da reclamação, com valor, categoria, confiança e a página de onde tirou;
2. **opera sozinho os sistemas da empresa**, decidindo a cada passo o que buscar, e anexa os documentos ao processo;
3. **cruza os dados com regras determinísticas** (ponto × holerite, prazo do TRCT, competências do FGTS, EPI e laudo):
   aponta onde a empresa ganha, onde perde e quanto está exposta;
4. escala para um humano o que não fecha (documento ausente, prova que depende de testemunha), com o contexto pronto;
5. entrega a estratégia por pedido: tese, prova a favor, pontos fracos e recomendação, tudo citando o documento.

**Como o agente funciona.** Loop próprio de decisão → ferramenta → observação (o modelo responde a próxima ação em
JSON), com portões humanos entre as etapas. O risco é calculado pelas regras, não pela opinião do modelo. Cada
decisão, consulta a sistema e chamada de modelo fica num rastro auditável com tokens, custo e tempo. Quando um
sistema cai, o agente tenta de novo; quando o modelo falha, troca de modelo e, no limite, executa um playbook
determinístico, para a coleta nunca parar. Nada é descartado em silêncio.

**Resultado no caso de demonstração** (dados sintéticos, medido pelo `eval/run.py`):
- 6/6 pedidos extraídos;
- 3/3 problemas plantados encontrados;
- 3/3 defesas comprovadas;
- 52 documentos coletados;
- cerca de US$ 0,02 de IA por processo;
- poucos minutos de agente contra cerca de 7,7 h estimadas da mesma coleta à mão.

## 2. Links

- Plataforma navegável e testável: https://subsidia.onrender.com (botão "Rodar o caso de demonstração"; abrir uns minutos antes para acordar o servidor gratuito)
- Código: https://github.com/hugo-ryanf/subsidia (privado; liberar acesso se a organização pedir)

## 3. Ferramentas, modelos e APIs

- Featherless (API OpenAI-compatible): `zai-org/GLM-5.2`, `google/gemma-4-31B-it`, `Qwen/Qwen3-Embedding-4B`
- FastAPI, SQLite (FTS5), NumPy, PyMuPDF, fpdf2, React, Vite, marked
- Claude Code (assistente de desenvolvimento)
- Sistemas de RH (ponto, folha, FGTS, SST, cadastro) **simulados** com dados sintéticos, como o desafio permite

## 4. Roteiro do vídeo (~2 min)

1. (0:00) Tela inicial: "Rodar o caso de demonstração". Uma frase sobre a dor (Súmula 338).
2. (0:15) Triagem: os 6 pedidos, valores e citação clicável (abrir a página da petição).
3. (0:35) Aprovar e seguir: coleta rodando. Mostrar o painel "Atividade do agente" ao vivo, com o agente decidindo,
   consultando ponto e folha, e o FGTS caindo (503) e sendo retentado.
4. (1:05) Achados: horas extras não pagas (risco, R$ estimados), ponto de jun/2024 ausente (pendência), TRCT no
   prazo, FGTS e EPI (a favor). Abrir um holerite citado.
5. (1:25) Resolver uma pendência com justificativa (portão humano).
6. (1:35) Estratégia: risco por pedido, seção de horas extras com pontos fracos honestos e recomendação.
7. (1:50) Painel de custo: US$ 0,02 e minutos × ~7,7 h manuais.

## 5. Roteiro do pitch (3 min)

- **0:00 Dor (30s).** "Toda empresa com funcionário recebe reclamação trabalhista. O advogado pede ao RH ponto,
  holerite, TRCT, FGTS, EPI... de 5 sistemas. Faltou o cartão de ponto? A Justiça presume que o ex-funcionário diz
  a verdade (Súmula 338). Documento que não chega vira condenação."
- **0:30 Solução (30s).** "Um digital worker que recebe a petição e faz a coleta sozinho: lê os pedidos, opera os
  sistemas, cruza os dados e mostra onde a empresa ganha e onde perde, sempre citando o documento."
- **1:00 Demo ao vivo (75s).** Caso demo: achados e estratégia. Destaque: ele encontrou as horas extras que o
  próprio ponto registra e a folha não pagou, e disse com franqueza que nesse pedido vale avaliar acordo.
- **2:15 Por que funciona fora da demo (20s).** Regras determinísticas para o risco, rastro auditável, retentativa
  e fallback, portões humanos.
- **2:35 Negócio (25s).** Cliente: empresas com contencioso de massa e os escritórios que as atendem. Cobrança por
  processo. Custo de IA de centavos contra horas de trabalho. Próximo passo: rodar no **desligamento**, auditando a
  rescisão antes de virar processo. *(Conferir no TST o volume anual de casos novos antes de citar número.)*
