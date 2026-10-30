"""Testes das próprias peças de apoio (rede bloqueada, sessão e relógio falsos)."""

import socket

import pandas as pd
import pytest
import requests

from tests.apoio import ler_fixture


def test_rede_real_bloqueada():
    with pytest.raises(RuntimeError, match='bloqueado'):
        socket.create_connection(('example.com', 80))
    with pytest.raises(RuntimeError, match='bloqueado'):
        requests.get('http://example.com', timeout=1)
    with pytest.raises(RuntimeError, match='bloqueado'):
        socket.gethostbyname('example.com')


def test_sessao_falsa_repete_ultima_resposta_e_registra_pedidos(sessao):
    sessao.responder('http://x/a', status=429).responder('http://x/a', status=200, texto='ok')
    assert sessao.get('http://x/a').status_code == 429
    assert sessao.get('http://x/a').text == 'ok'
    assert sessao.get('http://x/a').text == 'ok'
    assert sessao.pedidos == ['http://x/a'] * 3
    assert sessao.contar('/a') == 3


def test_sessao_falsa_lanca_erro_e_recusa_url_desconhecida(sessao):
    sessao.responder('http://x/t', erro=requests.Timeout())
    with pytest.raises(requests.Timeout):
        sessao.get('http://x/t')
    with pytest.raises(AssertionError, match='sem resposta'):
        sessao.get('http://x/outra')


def test_sessao_falsa_rotas_e_fixtures(sessao):
    sessao.rota(lambda url: None)
    from tests.apoio import RespostaFalsa

    sessao.rota(lambda url: RespostaFalsa(200, 'rota') if url.endswith('/r') else None)
    assert sessao.get('http://x/r').text == 'rota'
    sessao.responder('http://x/f', fixture='sapl/sapl.al.ac.leg.br/busca_vazia.html')
    assert 'Foram encontrados 0 registros' in sessao.get('http://x/f').text
    assert ler_fixture('sapl/index.json').startswith('[')


def test_download_falso_falha_no_meio(sessao):
    sessao.responder('http://x/p.pdf', conteudo=b'abcdef', falhar_no_meio=True)
    r = sessao.get('http://x/p.pdf', stream=True)
    partes = r.iter_content(2)
    assert next(partes) == b'ab'
    with pytest.raises(requests.ConnectionError):
        next(partes)


def test_relogio_falso_nao_espera(relogio):
    inicio = relogio.agora()
    relogio.dormir(60)
    relogio.dormir(-1)
    assert relogio.agora() == inicio + 60
    assert relogio.esperas == [60, -1]


def test_projeto_tmp(projeto_tmp):
    casas = pd.read_excel(projeto_tmp / 'arquivos_csv' / 'casas_legislativas.xlsx')
    assert list(casas['UF']) == ['AC', 'PR', 'SP']
    assert (projeto_tmp / 'arquivos_csv' / 'palavras_chave.xlsx').exists()
