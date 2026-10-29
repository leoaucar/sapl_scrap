"""Limites e valores padrão, e a conferência de `paralelo` no config.json (TR-7)."""

import pytest

from sapyl import cliente_http, padroes


def test_padroes_iniciais():
    assert padroes.padroes_paralelo() == {'casas_ao_mesmo_tempo': 8, 'limite_por_servidor': 120}
    assert padroes.PISO_POR_SERVIDOR == padroes.LIMITE_POR_SITE == 35
    assert padroes.JANELA_LENTIDAO == 600


def test_cliente_usa_os_valores_daqui():
    assert cliente_http.LIMITE_POR_MINUTO == padroes.LIMITE_POR_SITE
    assert cliente_http.JANELA_COM_MARGEM == padroes.JANELA_SEGUNDOS + padroes.MARGEM_SEGUNDOS


@pytest.mark.parametrize('dados', [None, {}])
def test_sem_valores_usa_os_padroes(dados):
    assert padroes.validar_paralelo(dados) == padroes.padroes_paralelo()


def test_completa_o_que_falta():
    assert padroes.validar_paralelo({'casas_ao_mesmo_tempo': 3}) == {
        'casas_ao_mesmo_tempo': 3,
        'limite_por_servidor': 120,
    }
    assert padroes.validar_paralelo({'casas_ao_mesmo_tempo': 1, 'limite_por_servidor': 35}) == {
        'casas_ao_mesmo_tempo': 1,
        'limite_por_servidor': 35,
    }


@pytest.mark.parametrize(
    ('dados', 'trecho'),
    [
        ({'casas_ao_mesmo_tempo': 0}, 'paralelo.casas_ao_mesmo_tempo" = 0'),
        ({'casas_ao_mesmo_tempo': 2.5}, 'número inteiro'),
        ({'casas_ao_mesmo_tempo': '4'}, "'4'"),
        ({'casas_ao_mesmo_tempo': True}, 'True'),
        ({'limite_por_servidor': 34}, 'no mínimo 35'),
        ({'limite_por_servidr': 60}, 'chave desconhecida em "paralelo": limite_por_servidr'),
        ([8, 120], 'tem de ser um objeto'),
    ],
)
def test_valores_invalidos_sao_recusados(dados, trecho):
    with pytest.raises(padroes.ConfiguracaoInvalida) as erro:
        padroes.validar_paralelo(dados)
    assert trecho in str(erro.value)
    assert isinstance(erro.value, ValueError)


def test_em_sequencia_mantem_a_ordem():
    assert padroes.em_sequencia(str.upper, ['b', 'a']) == ['B', 'A']
