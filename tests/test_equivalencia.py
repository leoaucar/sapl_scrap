"""Uma casa por vez e várias ao mesmo tempo dão os mesmos arquivos (TR-4, TR-5).

SAPL falso com 7 casas: Rio Branco (API) e Cascavel (só HTML) do projeto da
Fase 1, mais 5 casas com API, buscas de várias páginas, matérias repetidas
entre palavras, PDFs, um PDF que não existe e uma matéria que falha de vez.
"""

import copy
import csv
import json
import threading
from collections import Counter

import pandas as pd
import pytest

from sapyl import materias, padroes
from sapyl.cliente_http import ClienteSAPL
from sapyl.interface import principal as programa
from sapyl.tabela import ler_final
from tests.apoio import (
    CV_FASE1,
    RB_FASE1,
    RelogioFalso,
    SessaoFalsa,
    ler_fixture,
    respostas_atualizar,
    respostas_autoria,
    respostas_novo_projeto,
    respostas_retomar,
    roteiro,
    sapl_fase1,
)

P, ORC = '"plano+diretor"', '"orçamento"+"emenda+impositiva"'
EXTRAS = [f'https://sapl.c{i}.ac.leg.br/' for i in range(5)]
CASAS = [RB_FASE1, CV_FASE1, *EXTRAS]
FALHA_EXTRA = materias.url_api(EXTRAS[2], '205')


def _api(casa, sapl_id, com_pdf=True):
    dados = copy.deepcopy(
        json.loads(ler_fixture('sapl/sapl.riobranco.ac.leg.br/api_materia_34049.json'))
    )
    texto = f'{casa}media/sapl/public/materialegislativa/2025/{sapl_id}/t.pdf' if com_pdf else None
    dados.update(id=int(sapl_id), __str__=f'Matéria {sapl_id}', anexadas=[], texto_original=texto)
    return dados


def _busca(ids):
    return ''.join(f'<a href="/materia/{i}">m</a>' for i in ids)


def sapl_varias_casas():
    falso = sapl_fase1()
    for n, casa in enumerate(EXTRAS):
        ids = [str(100 * n + j) for j in range(1, 9)]
        falso.casa(
            casa,
            buscas={P: [_busca(ids[:5]), _busca(ids[3:8])], ORC: [_busca(ids[6:] + ids[:1])]},
            api={i: _api(casa, i, com_pdf=j != 2) for j, i in enumerate(ids)},
            # sem o PDF da última: o download dela falha (404)
            pdfs={i: f'%PDF-{casa}{i}'.encode() for i in ids[:-1]},
        )
    falso.falhar(FALHA_EXTRA, 503, 503, 503, 503)
    return falso


def _cliente():
    relogio, sessao = RelogioFalso(), SessaoFalsa()
    sessao.rota(sapl_varias_casas())
    threads = set()
    get = sessao.get

    def get_com_thread(url, **kwargs):
        threads.add(threading.current_thread().name)
        return get(url, **kwargs)

    sessao.get = get_com_thread
    cliente = ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)
    return cliente, sessao, threads


@pytest.fixture
def raiz(projeto_tmp):
    pd.DataFrame({'UF': ['AC', 'PR'] + ['AC'] * len(EXTRAS), 'URL do serviço': CASAS}).to_excel(
        projeto_tmp / 'arquivos_csv' / 'casas_legislativas.xlsx', index=False
    )
    return projeto_tmp


def _rodar(raiz, nome, casas_ao_mesmo_tempo, monkeypatch, respostas=None):
    monkeypatch.setattr(padroes, 'CASAS_AO_MESMO_TEMPO', casas_ao_mesmo_tempo)
    cliente, sessao, threads = _cliente()
    # depois do primeiro projeto, aparece a pergunta de reaproveitar a tabela de casas
    reusar = '2' if (raiz / 'arquivos_csv' / 'casas_resultado.csv').exists() else None
    respostas = respostas or respostas_novo_projeto(nome, tabela=reusar, pdfs='s')
    codigo = programa.main(roteiro(*respostas), cliente, raiz)
    return codigo, sessao, threads


def _estado(pasta, nome):
    with open(pasta / f'{nome}_estado.csv', encoding='utf-8', newline='') as arquivo:
        return Counter(
            (linha['etapa'], linha['chave'], linha['status'], linha['erro'])
            for linha in csv.DictReader(arquivo)
        )


def _downloads(pasta):
    return {p.name: p.read_bytes() for p in (pasta / 'downloads').iterdir()}


def _final(pasta, nome):
    return ler_final(pasta / f'{nome}_resultado_final.csv').drop(columns=['raspada_em'])


def test_uma_e_oito_casas_ao_mesmo_tempo_dao_os_mesmos_arquivos(raiz, monkeypatch):
    codigo, _, threads_um = _rodar(raiz, 'um', 1, monkeypatch)
    assert codigo == 0
    codigo, _, threads_oito = _rodar(raiz, 'oito', 8, monkeypatch)
    assert codigo == 0
    um, oito = raiz / 'um_proj', raiz / 'oito_proj'
    assert len({t for t in threads_um if t.startswith('casa')}) == 1
    assert len({t for t in threads_oito if t.startswith('casa')}) > 1  # houve paralelismo

    final_um, final_oito = _final(um, 'um'), _final(oito, 'oito')
    assert final_oito.equals(final_um)
    assert len(final_um) == 8 + 5 * 8
    # na ordem da tabela de casas, e dentro de cada casa na ordem em que foram achadas
    hosts = [h.split('/')[2] for h in final_um['Link Casa']]
    assert hosts == sorted(hosts, key=lambda h: [c.split('/')[2] for c in CASAS].index(h))
    assert final_um[final_um['Link Casa'] == EXTRAS[0]]['sapl_id'].tolist() == [
        str(j) for j in range(1, 9)
    ]
    assert _estado(oito, 'oito') == _estado(um, 'um')
    assert _downloads(oito) == _downloads(um)
    assert (oito / 'oito_links_totais.csv').read_bytes() == (
        um / 'um_links_totais.csv'
    ).read_bytes()

    por_chave = final_um.assign(k=final_um['Link Casa'] + final_um['sapl_id']).set_index('k')
    assert por_chave.at[f'{EXTRAS[2]}205', 'erro'] == 'HTTP 503'
    assert por_chave.at[f'{EXTRAS[0]}2', 'Palavras'] == P
    assert por_chave.at[f'{EXTRAS[0]}1', 'Palavras'] == f'{P}; {ORC}'
    assert por_chave.at[f'{EXTRAS[0]}8', 'download_status'] == 'erro'
    assert por_chave.at[f'{EXTRAS[0]}3', 'download_status'] == 'sem_pdf'


def test_interrompida_com_oito_e_retomada_da_o_mesmo_resultado(raiz, monkeypatch):
    _rodar(raiz, 'inteira', 8, monkeypatch)

    original, chamadas = materias.raspar_materia, []
    trava = threading.Lock()

    def cair_na_decima(link, *args):
        with trava:
            chamadas.append(link['chave'])
            cair = len(chamadas) == 10
        if cair:
            raise KeyboardInterrupt
        return original(link, *args)

    monkeypatch.setattr(materias, 'raspar_materia', cair_na_decima)
    codigo, _, _ = _rodar(raiz, 'partes', 8, monkeypatch)
    assert codigo == 1
    pasta = raiz / 'partes_proj'
    ok_antes = {
        k for (e, k, st, _), n in _estado(pasta, 'partes').items() if e == 'materia' and st == 'ok'
    }
    assert ok_antes
    assert not (pasta / 'partes_links_totais.csv').exists()  # refeita na retomada
    monkeypatch.setattr(materias, 'raspar_materia', original)
    # a lista de projetos: inteira, partes
    codigo, sessao, _ = _rodar(raiz, 'partes', 8, monkeypatch, respostas_retomar('2'))
    assert codigo == 0

    inteira = raiz / 'inteira_proj'
    assert _final(pasta, 'partes').equals(_final(inteira, 'inteira'))
    assert _downloads(pasta) == _downloads(inteira)
    # nenhuma matéria já raspada (ok) antes da interrupção foi pedida de novo
    pedidas = [u for u in sessao.pedidos if '/api/materia/materialegislativa/' in u]
    for chave in ok_antes:
        casa, sapl_id = chave.split('/')
        assert materias.url_api(f'https://{casa}/', sapl_id) not in pedidas


def _mais_recente(pasta, padrao):
    [arquivo] = pasta.glob(padrao)
    return arquivo


def test_atualizacao_e_autoria_com_uma_e_oito_casas(raiz, monkeypatch):
    """FR-4: o modo atualização e a autoria e tramitação usam o mesmo grupo de casas."""
    for nome, n in (('um', 1), ('oito', 8)):
        assert _rodar(raiz, nome, n, monkeypatch)[0] == 0
        # a lista em ordem alfabética: "oito" antes de "um", sempre na posição 1
        assert _rodar(raiz, nome, n, monkeypatch, respostas_atualizar('s'))[0] == 0
        codigo, _, threads = _rodar(raiz, nome, n, monkeypatch, respostas_autoria())
        assert codigo == 0
        casas_threads = len({t for t in threads if t.startswith('casa')})
        assert casas_threads == 1 if n == 1 else casas_threads > 1
    um, oito = raiz / 'um_proj', raiz / 'oito_proj'

    atualizado = 'resultado_final_ATUALIZADO_*[0-9].csv'
    a = ler_final(_mais_recente(um, f'um_{atualizado}')).drop(columns=['raspada_em'])
    b = ler_final(_mais_recente(oito, f'oito_{atualizado}')).drop(columns=['raspada_em'])
    assert a.equals(b) and len(a) == 48
    assert set(a['download_status']) == {'ok', 'erro', 'sem_pdf', ''}

    autoria = '*_autoria_tramitacao.csv'
    a = ler_final(_mais_recente(um, autoria)).drop(columns=['raspada_em'])
    b = ler_final(_mais_recente(oito, autoria)).drop(columns=['raspada_em'])
    assert a.equals(b) and len(a) == 48
    assert (a['status_autoria'] == 'ok').sum() > 40


def test_autoria_interrompida_com_oito_e_retomada(raiz, monkeypatch):
    from sapyl import autoria

    assert _rodar(raiz, 'p', 8, monkeypatch)[0] == 0
    assert _rodar(raiz, 'p', 8, monkeypatch, respostas_autoria())[0] == 0
    saida = raiz / 'p_proj' / 'p_resultado_final_autoria_tramitacao.csv'
    inteira = ler_final(saida)
    for arquivo in (raiz / 'p_proj').glob('p_resultado_final_autoria_tramitacao*'):
        arquivo.unlink()

    original, chamadas, trava = autoria.raspar_autoria, [], threading.Lock()

    def cair(link, *args):
        with trava:
            chamadas.append(link)
            cair_agora = len(chamadas) == 12
        if cair_agora:
            raise KeyboardInterrupt
        return original(link, *args)

    monkeypatch.setattr(autoria, 'raspar_autoria', cair)
    assert _rodar(raiz, 'p', 8, monkeypatch, respostas_autoria())[0] == 1
    monkeypatch.setattr(autoria, 'raspar_autoria', original)
    codigo, sessao, _ = _rodar(raiz, 'p', 8, monkeypatch, respostas_autoria())
    assert codigo == 0
    assert ler_final(saida).equals(inteira)
    feitas = len([u for u in sessao.pedidos if '/api/materia/autoria/' in u or '/autoria' in u])
    assert feitas < 48  # só o que faltava
