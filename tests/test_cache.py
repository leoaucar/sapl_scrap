"""Cache das fontes e dos nomes no projeto (FR-25)."""

import json
import logging

import pytest

from sapyl import materias as m
from sapyl.cliente_http import ClienteSAPL
from sapyl.estado import Cache
from tests.test_materias import AL, RB, _link, _responder_consultas


@pytest.fixture
def cliente(sessao, relogio):
    return ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)


def test_guarda_e_le_de_novo(tmp_path):
    cache = Cache(tmp_path / 'cache.json')
    cache.guardar_fonte('sapl.a.leg.br', 'html')
    cache.guardar_nome('https://a/api/x/1/', 'Projeto de Lei')
    outro = Cache(tmp_path / 'cache.json')
    assert outro.fonte('sapl.a.leg.br') == 'html'
    assert outro.nome('https://a/api/x/1/') == 'Projeto de Lei'
    assert outro.fonte('sapl.b.leg.br') is None and outro.nome('https://b/') is None


def test_gravacao_atomica_sem_temporario(tmp_path):
    caminho = tmp_path / 'cache.json'
    Cache(caminho).guardar_fonte('h', 'api')
    assert json.loads(caminho.read_text(encoding='utf-8')) == {'fontes': {'h': 'api'}, 'nomes': {}}
    assert list(tmp_path.iterdir()) == [caminho]


def test_nome_vazio_nunca_vai_para_o_disco(tmp_path):
    cache = Cache(tmp_path / 'cache.json')
    cache.guardar_nome('https://a/api/x/1/', '')
    assert not (tmp_path / 'cache.json').exists()


@pytest.mark.parametrize('conteudo', ['{nao e json', '[]', '{"fontes": []}', ''])
def test_arquivo_ilegivel_da_aviso_e_cache_vazio(tmp_path, caplog, conteudo):
    caminho = tmp_path / 'cache.json'
    caminho.write_text(conteudo, encoding='utf-8')
    with caplog.at_level(logging.WARNING, logger='sapyl'):
        cache = Cache(caminho)
    assert cache.fontes() == {}
    assert any('Cache ilegível' in r.getMessage() for r in caplog.records)
    cache.guardar_fonte('h', 'api')  # e volta a funcionar
    assert Cache(caminho).fonte('h') == 'api'


def test_casa_html_conhecida_nao_tem_a_api_sondada_de_novo(tmp_path, cliente, sessao):
    caminho = tmp_path / 'cache.json'
    sessao.responder(m.url_api(AL, '15951'), status=404)
    sessao.responder(AL + 'materia/15951', fixture='sapl/sapl.al.ac.leg.br/materia_15951.html')
    sessao.responder(AL + 'materia/17764', fixture='sapl/sapl.al.ac.leg.br/materia_17764.html')
    m.raspar_materia(_link(AL, '15951'), cliente, m.Fontes(Cache(caminho)))
    assert Cache(caminho).fonte('sapl.al.ac.leg.br') == 'html'

    sessao.pedidos.clear()
    linha = m.raspar_materia(_link(AL, '17764'), cliente, m.Fontes(Cache(caminho)))  # "retomada"
    assert (linha['status'], linha['fonte']) == ('ok', 'html')
    assert sessao.contar('/api/') == 0


def test_casa_api_conhecida_ja_vale_como_confirmada(tmp_path):
    caminho = tmp_path / 'cache.json'
    Cache(caminho).guardar_fonte('sapl.riobranco.ac.leg.br', 'api')
    fontes = m.Fontes(Cache(caminho))
    assert fontes.de(RB) == 'api' and fontes.api_confirmada(RB)
    fontes.usar_html(RB, '404 isolado')  # não troca a casa inteira
    assert fontes.de(RB) == 'api'
    assert Cache(caminho).fonte('sapl.riobranco.ac.leg.br') == 'api'


def test_nomes_conhecidos_nao_sao_consultados_de_novo(tmp_path, cliente, sessao):
    caminho = tmp_path / 'cache.json'
    _responder_consultas(sessao)
    assert m.Consultas(cliente, RB, Cache(caminho)).tipo(1) == 'Projeto de Lei Ordinária'
    sessao.pedidos.clear()
    assert m.Consultas(cliente, RB, Cache(caminho)).tipo(1) == 'Projeto de Lei Ordinária'
    assert sessao.pedidos == []


def test_consulta_que_falhou_e_tentada_na_proxima_execucao(tmp_path, cliente, sessao):
    caminho = tmp_path / 'cache.json'
    url = RB + 'api/materia/tipomaterialegislativa/1/'
    sessao.responder(url, status=404)
    consultas = m.Consultas(cliente, RB, Cache(caminho))
    assert consultas.tipo(1) == '' and consultas.tipo(1) == ''
    assert sessao.contar('tipomaterialegislativa/1/') == 1  # na mesma execução, uma vez só
    assert Cache(caminho).nome(url) is None
    m.Consultas(cliente, RB, Cache(caminho)).tipo(1)  # próxima execução
    assert sessao.contar('tipomaterialegislativa/1/') == 2
