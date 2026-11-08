"""Autos longos: a triagem lê tudo em blocos, sem LLM real e sem banco."""
import re

import pytest

from app.agentes import fontes, triagem


def _chunk(i: int, texto: str) -> dict:
    return {"id": f"c{i}", "documento_id": "doc", "documento": "inicial.pdf", "classe": "autos", "texto": texto,
            "pagina_inicio": i, "pagina_fim": i, "requer_revisao": 0}


def _pedido(pid: str, titulo: str, fonte: str, **extra) -> dict:
    return {"id": pid, "titulo": titulo, "valor": 100.0, "alegacao": "alegação", "arquetipo": "jornada",
            "fontes": [fonte], "confianca": 0.9, **extra}


@pytest.fixture
def ambiente(monkeypatch):
    """Troca banco e LLM; o LLM responde pedidos de acordo com o texto recebido."""
    salvos: dict = {}
    prompts: list[str] = []
    respostas: dict[str, dict] = {}

    def chat_json(_system, user, **_kw):
        prompts.append(user)
        trechos = user.split("CATEGORIAS POSSÍVEIS")[0]
        for marca, resposta in respostas.items():
            if marca in trechos:
                return resposta
        return {"processo": {}, "pedidos": []}

    monkeypatch.setattr(triagem.llm, "chat_json", chat_json)
    monkeypatch.setattr(triagem.db, "salvar_artefato",
                        lambda _p, _t, conteudo, aprovado=False: salvos.update(conteudo))
    monkeypatch.setattr(triagem.rastro, "registrar", lambda *a, **k: None)
    return monkeypatch, salvos, prompts, respostas


def _usar_chunks(monkeypatch, chunks: list[dict]) -> None:
    monkeypatch.setattr(triagem.fontes, "chunks_do_processo", lambda *_a, **_k: chunks)


def test_em_blocos_nao_perde_nem_reordena_chunks():
    chunks = [_chunk(i, "x" * 40) for i in range(1, 6)] + [_chunk(6, "y" * 500), _chunk(7, "z")]
    blocos = fontes.em_blocos(chunks, limite_chars=100)
    assert [c for b in blocos for c in b] == chunks
    assert all(sum(len(c["texto"]) for c in b) <= 100 or len(b) == 1 for b in blocos)


def test_rotular_com_inicio_continua_a_numeracao():
    _, refs = fontes.rotular([_chunk(1, "a"), _chunk(2, "b")], inicio=3)
    assert list(refs) == ["D4", "D5"]


def test_rotular_sem_limite_nao_corta():
    _, refs = fontes.rotular([_chunk(i, "x" * 50000) for i in range(1, 5)])
    assert len(refs) == 4


def test_autos_curtos_usam_uma_chamada_sem_aviso(ambiente):
    mp, salvos, prompts, respostas = ambiente
    _usar_chunks(mp, [_chunk(1, "PEDIDO_A")])
    respostas["PEDIDO_A"] = {"processo": {"fontes": ["D1"]}, "pedidos": [_pedido("a", "Pedido A", "D1")]}

    triagem.executar("proc")

    assert len(prompts) == 1 and "bloco" not in prompts[0].lower()
    assert "aviso" not in salvos
    assert salvos["requer_revisao"] == 0


def test_pedido_alem_do_limite_nao_se_perde_e_autos_longos_avisam(ambiente):
    mp, salvos, prompts, respostas = ambiente
    tamanho = triagem.LIMITE_CHARS_POR_BLOCO // 2 + 1000
    _usar_chunks(mp, [_chunk(1, "INICIO" + "x" * tamanho), _chunk(2, "MEIO" + "x" * tamanho),
                      _chunk(3, "DOS_PEDIDOS" + "x" * tamanho)])
    respostas["INICIO"] = {"processo": {"numero": "123", "reclamante": None, "fontes": ["D1"]},
                           "pedidos": [_pedido("a", "Pedido A", "D1")]}
    respostas["DOS_PEDIDOS"] = {"processo": {"numero": None, "reclamante": "Fulana", "fontes": ["D3"]},
                                "pedidos": [_pedido("b", "Pedido B", "D3")]}

    triagem.executar("proc")

    assert len(prompts) == 3
    assert [p["id"] for p in salvos["pedidos"]] == ["a", "b"]
    assert [f["ref"] for f in salvos["pedidos"][1]["fontes"]] == ["D3"]
    assert salvos["processo"]["numero"] == "123" and salvos["processo"]["reclamante"] == "Fulana"
    assert "3 blocos" in salvos["aviso"]
    assert salvos["requer_revisao"] == 2
    assert all(any("repetido" in m for m in p["motivos_revisao"]) for p in salvos["pedidos"])


def test_mesmo_pedido_em_blocos_diferentes_vira_um_so(ambiente):
    mp, salvos, _prompts, respostas = ambiente
    tamanho = triagem.LIMITE_CHARS_POR_BLOCO
    _usar_chunks(mp, [_chunk(1, "PRIMEIRO" + "x" * tamanho), _chunk(2, "SEGUNDO" + "x" * tamanho)])
    respostas["PRIMEIRO"] = {"pedidos": [_pedido("he", "Horas Extras", "D1", valor=None, confianca=0.9)]}
    respostas["SEGUNDO"] = {"pedidos": [_pedido("horas", "horas extras", "D2", valor=500.0, confianca=0.7)]}

    triagem.executar("proc")

    assert len(salvos["pedidos"]) == 1
    p = salvos["pedidos"][0]
    assert p["valor"] == 500.0 and p["confianca"] == 0.7
    assert sorted(f["ref"] for f in p["fontes"]) == ["D1", "D2"]


def test_rotulos_nao_se_repetem_entre_blocos(ambiente):
    mp, _salvos, prompts, _respostas = ambiente
    tamanho = triagem.LIMITE_CHARS_POR_BLOCO
    _usar_chunks(mp, [_chunk(1, "x" * tamanho), _chunk(2, "y" * tamanho)])

    triagem.executar("proc")

    rotulos = [r for p in prompts for r in re.findall(r"^\[(D\d+)\]", p, re.M)]
    assert rotulos == ["D1", "D2"]
