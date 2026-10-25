"""Script de autoria e tramitação."""
import pandas as pd
import pytest

from autoria_e_tramitacao import autoria_e_tramit as at
from http_sapl import ClienteSAPL
from tests.apoio import ler_fixture, roteiro

AL = 'https://sapl.al.ac.leg.br/'
RB = 'https://sapl.riobranco.ac.leg.br/'


@pytest.fixture
def cliente(sessao, relogio):
    return ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)


def test_autoria_e_tramitacao_das_paginas_reais(cliente, sessao):
    sessao.responder(AL + 'materia/15951/autoria', fixture='sapl/sapl.al.ac.leg.br/materia_15951_autoria.html')
    sessao.responder(AL + 'materia/15951/tramitacao',
                     fixture='sapl/sapl.al.ac.leg.br/materia_15951_tramitacao.html')
    assert at.buscar_autoria(AL + 'materia/15951/ta', cliente) == ('PEDRO LONGO (Parlamentar)', '')
    tramite, erro = at.buscar_tramitacao(AL + 'materia/15951/', cliente)
    assert erro == ''
    assert tramite == ('10/07/2024 | SUB SEC ATIV LEGISLATIVA - SALEGIS | SECRETARIA EXECUTIVA - SE | '
                       'Autógrafo enviado')


def test_falha_e_registrada(cliente, sessao):
    sessao.responder(RB + 'materia/1/autoria', status=503)
    sessao.responder(RB + 'materia/1/tramitacao', status=404)
    assert at.buscar_autoria(RB + 'materia/1', cliente) == ('', 'HTTP 503')
    assert at.buscar_tramitacao(RB + 'materia/1', cliente) == ('', 'HTTP 404')


def test_pagina_sem_tabela(cliente, sessao):
    sessao.responder(RB + 'materia/2/tramitacao', texto='<p>Nenhuma tramitação</p>')
    assert at.buscar_tramitacao(RB + 'materia/2', cliente) == ('', '')


def test_main_escolhe_arquivo_e_grava_novo(tmp_path, cliente, sessao):
    entrada = tmp_path / 'resultado.csv'
    pd.DataFrame({'Link Materia': [AL + 'materia/15951', RB + 'materia/1'], 'Titulo': ['a', 'b']}
                 ).to_csv(entrada)                 # com índice, como os arquivos antigos
    (tmp_path / 'outro.csv').write_text('x\n1\n')
    original = entrada.read_text()
    sessao.responder(AL + 'materia/15951/autoria', fixture='sapl/sapl.al.ac.leg.br/materia_15951_autoria.html')
    sessao.responder(AL + 'materia/15951/tramitacao',
                     fixture='sapl/sapl.al.ac.leg.br/materia_15951_tramitacao.html')
    sessao.responder(RB + 'materia/1/autoria', status=503)
    sessao.responder(RB + 'materia/1/tramitacao', texto=ler_fixture(
        'sapl/sapl.riobranco.ac.leg.br/materia_34049_tramitacao.html'))
    ler = roteiro('3', '2')          # opção inválida, depois resultado.csv (2ª na lista)
    assert at.main(tmp_path, ler, cliente) == 0
    assert '1- outro.csv' in ler.perguntas[0] and '2- resultado.csv' in ler.perguntas[0]
    assert entrada.read_text() == original
    saida = pd.read_csv(tmp_path / 'resultado_autoria_tramitacao.csv', dtype=str, keep_default_na=False)
    assert list(saida.columns) == ['Link Materia', 'Titulo', 'Autoria', 'Tramite', 'status_autoria',
                                   'status_tramitacao', 'erro_autoria_tramitacao']
    assert saida['status_autoria'].tolist() == ['ok', 'erro']
    assert saida['erro_autoria_tramitacao'].tolist() == ['', 'autoria: HTTP 503']
    assert saida['Tramite'][0].startswith('10/07/2024 | ')
    assert not saida['Tramite'][1].startswith('[')            # texto, não lista Python
    # a saída não aparece como opção numa próxima execução
    assert len(list(tmp_path.glob('*.csv'))) == 3
    assert at.escolher_csv(tmp_path, roteiro('2')).name == 'resultado.csv'


def test_main_sem_csv(tmp_path, capsys):
    assert at.main(tmp_path, roteiro(), None) == 1
    assert 'Nenhum arquivo .csv' in capsys.readouterr().out
