"""Fluxo principal: projeto novo, retomada, modo atualização, interrupção."""

import importlib
import json
import logging

import pytest

from sapyl.cliente_http import ClienteSAPL
from sapyl.estado import Estado
from sapyl.interface import principal as programa
from sapyl.tabela import ler_final
from tests.apoio import SaplFalso, roteiro

A = 'https://sapl.a.ac.leg.br/'
CV = 'sapl/sapl.cascavel.pr.leg.br/'
P = '"plano+diretor"'
ORC = '"orçamento"+"emenda+impositiva"'


@pytest.fixture
def sapl(sessao):
    falso = SaplFalso()
    falso.casa(
        A,
        api=None,
        buscas={P: [CV + 'busca_p1.html'], ORC: ['<a href="/materia/43301">x</a>']},
        html={'38415': CV + 'materia_38415.html', '43301': CV + 'materia_43301.html'},
        pdfs={'38415': b'%PDF-um', '43301': b'%PDF-dois'},
    )
    falso.casa(
        'https://sapl.b.pr.leg.br/',
        buscas={P: [CV + 'busca_vazia.html'], ORC: [CV + 'busca_vazia.html']},
    )
    falso.casa('https://sapl.c.sp.leg.br/', ativa=False)
    sessao.rota(falso)
    return falso


@pytest.fixture
def cliente(sessao, relogio):
    return ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)


NOVO = ('1', 'teste', '2', '1', '1')  # novo projeto, nome, sem Sul/Sudeste, todas, downloads


def test_importar_nao_executa_nada():
    importlib.reload(programa)  # pytest bloqueia o stdin: se perguntasse algo, falharia


def test_projeto_novo_do_comeco_ao_fim(projeto_tmp, cliente, sessao, sapl):
    assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 0
    pasta = projeto_tmp / 'teste_proj'
    final = ler_final(pasta / 'teste_resultado_final.csv')
    assert final['sapl_id'].tolist() == ['38415', '43301', '43300', '42263']
    assert final['status'].tolist() == ['ok', 'ok', 'erro', 'erro']
    assert final['erro'].tolist()[2:] == ['HTTP 404', 'HTTP 404']
    assert final['Palavras'].tolist()[1] == f'{P}; {ORC}'
    assert final['fonte'].tolist()[:2] == ['html', 'html']
    assert final['download_status'].tolist() == ['ok', 'ok', '', '']
    assert sorted(p.name for p in (pasta / 'downloads').iterdir()) == [
        'sapl.a.ac.leg.br_38415.pdf',
        'sapl.a.ac.leg.br_43301.pdf',
    ]
    config = json.loads((pasta / 'config.json').read_text(encoding='utf-8'))
    assert config['palavras'] == [P, ORC] and config['downloads'] is True
    logs = sorted(p.name for p in (pasta / 'logs').iterdir())
    assert len(logs) == 1 and logs[0].startswith('teste_') and logs[0].endswith('_novo.log')
    assert not (pasta / 'teste.log').exists()
    # todas as casas testadas e sem filtro: a tabela geral é atualizada
    geral = (projeto_tmp / 'arquivos_csv' / 'casas_resultado.csv').read_text()
    assert 'https://sapl.c.sp.leg.br/,False,HTTP 500,SP' in geral
    assert not any('sapl.c.sp.leg.br/sistema' in u for u in sessao.pedidos)


def test_retomada_nao_pergunta_nada_e_so_refaz_o_que_falhou(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    sapl._casas['sapl.a.ac.leg.br']['html']['43300'] = CV + 'materia_43301.html'
    sessao.pedidos.clear()
    # só: não atualizar, nome, retomar. Uma pergunta a mais esvaziaria o roteiro.
    assert programa.main(roteiro('1', 'teste', '1'), cliente, projeto_tmp) == 0
    assert not any('/sistema/search/' in u for u in sessao.pedidos)
    assert not any(u.endswith('/materia/38415') for u in sessao.pedidos)
    assert any(u.endswith('/materia/43300') for u in sessao.pedidos)
    final = ler_final(projeto_tmp / 'teste_proj' / 'teste_resultado_final.csv')
    assert final['status'].tolist() == ['ok', 'ok', 'ok', 'erro']
    # o PDF já baixado não é pedido de novo
    assert sum('/media/' in u and '38415' in u for u in sessao.pedidos) == 0


def test_tabela_de_casas_reaproveitada_e_filtrada(projeto_tmp, cliente, sessao, sapl):
    (projeto_tmp / 'arquivos_csv' / 'casas_resultado.csv').write_text(
        '0,1\nhttps://sapl.a.ac.leg.br/,True\nhttps://sapl.b.pr.leg.br/,True\n'
        'https://sapl.c.sp.leg.br/,False\n',
        encoding='utf-8',
    )
    # novo projeto, nome, reusar tabela, Sul/Sudeste, todas, sem downloads
    programa.main(roteiro('1', 'sul', '1', '1', '1', '2'), cliente, projeto_tmp)
    assert not any(u.rstrip('/').endswith('.leg.br') for u in sessao.pedidos)  # nenhum teste de URL
    assert not any('sapl.a.ac.leg.br' in u for u in sessao.pedidos)  # AC filtrado
    assert any('sapl.b.pr.leg.br/sistema/search' in u for u in sessao.pedidos)


def test_modo_atualizacao(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    sessao.pedidos.clear()
    assert programa.main(roteiro('2', 'teste', '2'), cliente, projeto_tmp) == 0
    pasta = projeto_tmp / 'teste_proj'
    atualizados = sorted(p.name for p in pasta.glob('*_ATUALIZADO_*'))
    assert [n.split('_ATUALIZADO_')[0] for n in atualizados] == [
        'teste_estado',
        'teste_materias_legislativas',
        'teste_resultado_final',
    ]
    final = ler_final(next(pasta.glob('teste_resultado_final_ATUALIZADO_*')))
    assert final['sapl_id'].tolist() == ['38415', '43301', '43300', '42263']
    assert not any('/sistema/search/' in u for u in sessao.pedidos)


def test_modo_atualizacao_com_downloads_duas_vezes(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    programa.executar_atualizacao(projeto_tmp, cliente, roteiro('teste', '1'), hoje='01_01_2027')
    programa.executar_atualizacao(projeto_tmp, cliente, roteiro('teste', '1'), hoje='01_01_2027')
    assert (
        projeto_tmp / 'teste_proj' / 'downloads01_01_2027' / 'sapl.a.ac.leg.br_38415.pdf'
    ).exists()


def test_ctrl_c_sai_com_mensagem(projeto_tmp, cliente, capsys):
    def interromper(texto=''):
        raise KeyboardInterrupt

    assert programa.main(interromper, cliente, projeto_tmp) == 1
    assert 'retomar' in capsys.readouterr().out


def test_ctrl_c_no_meio_da_raspagem_permite_retomar(
    projeto_tmp, cliente, sessao, sapl, monkeypatch
):
    from sapyl import materias

    original = materias.raspar_materia
    chamadas = []

    def raspar_e_cair(link, *args):
        chamadas.append(link['chave'])
        if len(chamadas) == 2:
            raise KeyboardInterrupt
        return original(link, *args)

    monkeypatch.setattr(materias, 'raspar_materia', raspar_e_cair)
    assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 1
    estado = Estado(projeto_tmp / 'teste_proj' / 'teste_estado.csv')
    assert estado.contagens('materia') == {'ok': 1}
    estado.fechar()


def test_resumo_aparece_no_fim(projeto_tmp, cliente, sessao, sapl, caplog):
    import logging

    with caplog.at_level(logging.INFO, logger='sapyl'):
        programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    resumo = [r.getMessage() for r in caplog.records if 'Resumo' in r.getMessage()]
    assert resumo and 'Matérias: 5 encontradas, 4 únicas, 2 raspadas, 2 com erro' in resumo[-1]
    assert 'Downloads: 2 baixados' in resumo[-1]


def test_palavras_csv_tem_prioridade(projeto_tmp):
    from sapyl.palavras import importar_palavras, preparar_termos

    (projeto_tmp / 'arquivos_csv' / 'palavras_chave.csv').write_text(
        'Palavras\n"professor,  conviccoes morais"\n\n', encoding='utf-8'
    )
    termos = preparar_termos(importar_palavras(projeto_tmp / 'arquivos_csv'))
    assert termos == ['"professor"+"conviccoes+morais"']


def test_fim_da_entrada_numa_pergunta_sai_com_mensagem(projeto_tmp, cliente, capsys):
    """Achado V5: Ctrl+D (ou respostas acabando) numa pergunta não gera traceback."""

    def sem_mais_respostas(texto=''):
        raise EOFError

    assert programa.main(sem_mais_respostas, cliente, projeto_tmp) == 1
    assert 'retomar' in capsys.readouterr().out


def test_boas_vindas_e_resumo_com_o_nome_sapyl(projeto_tmp, cliente, sessao, sapl, caplog, capsys):
    with caplog.at_level(logging.INFO, logger='sapyl'):
        assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 0
    saida = capsys.readouterr().out
    assert saida.startswith('SAPyL: Raspador do Sistema de Apoio Legislativo (versão 0.2.0)')
    resumo = [r.getMessage() for r in caplog.records if 'Resumo' in r.getMessage()][-1]
    assert '===== Resumo (SAPyL 0.2.0) =====' in resumo


# --- Palavras mudadas na retomada (FR-23) -----------------------------------


def _palavras(projeto_tmp, *linhas):
    texto = 'Palavras\n' + ''.join(f'"{linha}"\n' for linha in linhas)
    (projeto_tmp / 'arquivos_csv' / 'palavras_chave.csv').write_text(texto, encoding='utf-8')


def test_retomada_avisa_palavras_mudadas_e_usa_as_salvas(
    projeto_tmp, cliente, sessao, sapl, caplog
):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    _palavras(projeto_tmp, 'plano diretor', 'saneamento')  # saiu "orçamento, ..."; entrou uma
    sessao.pedidos.clear()
    with caplog.at_level(logging.WARNING, logger='sapyl'):
        assert programa.main(roteiro('1', 'teste', '1'), cliente, projeto_tmp) == 0
    aviso = next(r.getMessage() for r in caplog.records if 'palavras-chave mudou' in r.getMessage())
    assert 'Novas no arquivo (não serão buscadas): "saneamento"' in aviso
    assert f'Do projeto, fora do arquivo (continuam): {ORC}' in aviso
    assert 'crie um projeto novo' in aviso
    assert not any('saneamento' in u for u in sessao.pedidos)
    config = json.loads((projeto_tmp / 'teste_proj' / 'config.json').read_text(encoding='utf-8'))
    assert config['palavras'] == [P, ORC]


def test_sem_aviso_quando_as_palavras_sao_iguais(projeto_tmp, cliente, sessao, sapl, caplog):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    with caplog.at_level(logging.WARNING, logger='sapyl'):
        programa.main(roteiro('1', 'teste', '1'), cliente, projeto_tmp)
    assert not any('palavras-chave mudou' in r.getMessage() for r in caplog.records)


def test_sem_aviso_sem_arquivo_de_palavras(projeto_tmp):
    (projeto_tmp / 'arquivos_csv' / 'palavras_chave.xlsx').unlink()
    assert programa.avisar_palavras_mudadas(projeto_tmp, [P]) == []


# --- Atualização com colunas da pessoa e Relevante (FR-19, FR-20) ------------


def _marcar(projeto_tmp, relevantes):
    caminho = projeto_tmp / 'teste_proj' / 'teste_resultado_final.csv'
    final = ler_final(caminho)
    final['Relevante'] = [relevantes.get(i, '') for i in final['sapl_id']]
    final['Notas'] = [f'nota {i}' for i in final['sapl_id']]
    final.to_csv(caminho, index=False)


def _atualizado(projeto_tmp):
    pasta = projeto_tmp / 'teste_proj'
    return ler_final(next(pasta.glob('teste_resultado_final_ATUALIZADO_*')))


def test_atualizacao_mantem_colunas_e_filtra_relevantes(projeto_tmp, cliente, sessao, sapl, caplog):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    _marcar(projeto_tmp, {'38415': ' Sim', '43300': 'x'})
    sessao.pedidos.clear()
    ler = roteiro('2', 'teste', '1', '2')  # atualizar, nome, só relevantes, sem downloads
    with caplog.at_level(logging.INFO, logger='sapyl'):
        assert programa.main(ler, cliente, projeto_tmp) == 0
    assert programa.PERGUNTA_RELEVANTES in ler.perguntas
    final = _atualizado(projeto_tmp)
    assert final['sapl_id'].tolist() == ['38415', '43300']
    assert list(final.columns)[-2:] == ['Relevante', 'Notas']
    assert final['Notas'].tolist() == ['nota 38415', 'nota 43300']
    assert any('Só as relevantes: 2 de 4' in r.getMessage() for r in caplog.records)
    raspadas = [u for u in sessao.pedidos if '/materia/' in u and '/media/' not in u]
    assert not any('43301' in u or '42263' in u for u in raspadas)


def test_atualizacao_sem_filtro_mantem_todas_e_as_colunas(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    _marcar(projeto_tmp, {'38415': 'sim'})
    assert programa.main(roteiro('2', 'teste', '2', '2'), cliente, projeto_tmp) == 0
    final = _atualizado(projeto_tmp)
    assert final['sapl_id'].tolist() == ['38415', '43301', '43300', '42263']
    assert final['Relevante'].tolist() == ['sim', '', '', '']


def test_sem_coluna_relevante_nao_pergunta(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    ler = roteiro('2', 'teste', '2')
    assert programa.main(ler, cliente, projeto_tmp) == 0
    assert programa.PERGUNTA_RELEVANTES not in ler.perguntas


# --- Opção 3: autoria e tramitação (FR-7, FR-17) ----------------------------


def _sapl_sem_api_de_autoria(sessao, casa, *ids):
    for i in ids:
        for lista in ('autoria', 'tramitacao'):
            sessao.responder(f'{casa}api/materia/{lista}/?materia={i}', status=404)
            sessao.responder(f'{casa}materia/{i}/{lista}', texto='<p>sem tabela</p>')


def test_menu_tem_tres_opcoes():
    assert '1- novo projeto' in programa.PERGUNTA_MODO
    assert '2- atualizar' in programa.PERGUNTA_MODO
    assert '3- autoria e tramitação' in programa.PERGUNTA_MODO


def test_autoria_de_um_projeto_usa_o_resultado_mais_recente(projeto_tmp, cliente, sessao, sapl):
    import os

    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    pasta = projeto_tmp / 'teste_proj'
    atualizado = pasta / 'teste_resultado_final_ATUALIZADO_01_01_2027.csv'
    ler_final(pasta / 'teste_resultado_final.csv').head(1).to_csv(atualizado, index=False)
    os.utime(atualizado, (2_000_000_000, 2_000_000_000))  # mais novo
    _sapl_sem_api_de_autoria(sessao, A, '38415')
    assert programa.main(roteiro('3', 'teste'), cliente, projeto_tmp) == 0
    saida = pasta / 'teste_resultado_final_ATUALIZADO_01_01_2027_autoria_tramitacao.csv'
    assert ler_final(saida)['sapl_id'].tolist() == ['38415']
    assert list((pasta / 'logs').glob('teste_*_autoria.log'))


def test_autoria_de_um_csv_avulso(projeto_tmp, cliente, sessao, sapl, capsys):
    planilhas = projeto_tmp / 'planilhas'
    planilhas.mkdir()
    (planilhas / 'minha.csv').write_text(f'Link Materia\n{A}materia/43301\n', encoding='utf-8')
    _sapl_sem_api_de_autoria(sessao, A, '43301')
    ler = roteiro('3', 'nao_existe', 'planilhas/minha.csv')
    assert programa.main(ler, cliente, projeto_tmp) == 0
    assert 'Não encontrei o projeto nem o arquivo "nao_existe"' in capsys.readouterr().out
    assert (planilhas / 'minha_autoria_tramitacao.csv').exists()
    assert (planilhas / 'minha_autoria_tramitacao_estado.csv').exists()
    assert list((planilhas / 'logs').glob('minha_*_autoria.log'))


def test_ctrl_c_na_autoria_explica_como_retomar(projeto_tmp, cliente, capsys):
    respostas = iter(['3'])

    def ler(texto=''):
        try:
            return next(respostas)
        except StopIteration:
            raise KeyboardInterrupt from None

    assert programa.main(ler, cliente, projeto_tmp) == 1
    assert 'escolha 3 e digite a mesma entrada' in capsys.readouterr().out


# --- `paralelo` no config.json (TR-7) -----------------------------------------


def test_projeto_novo_grava_os_padroes_de_paralelo(projeto_tmp, cliente, sessao, sapl):
    assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 0
    config = json.loads((projeto_tmp / 'teste_proj' / 'config.json').read_text(encoding='utf-8'))
    assert config['paralelo'] == {'casas_ao_mesmo_tempo': 8, 'limite_por_servidor': 120}


def test_projeto_antigo_sem_paralelo_usa_os_padroes(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    arquivo = projeto_tmp / 'teste_proj' / 'config.json'
    config = json.loads(arquivo.read_text(encoding='utf-8'))
    del config['paralelo']
    arquivo.write_text(json.dumps(config), encoding='utf-8')
    assert programa.main(roteiro('1', 'teste', '1'), cliente, projeto_tmp) == 0
    assert 'paralelo' not in json.loads(arquivo.read_text(encoding='utf-8'))


def _estragar_paralelo(pasta, valor):
    arquivo = pasta / 'config.json'
    config = json.loads(arquivo.read_text(encoding='utf-8'))
    config['paralelo'] = valor
    arquivo.write_text(json.dumps(config), encoding='utf-8')


@pytest.mark.parametrize(
    'respostas',
    [('1', 'teste', '1'), ('2', 'teste', '2'), ('3', 'teste')],
    ids=['retomada', 'atualizacao', 'autoria'],
)
def test_valor_invalido_para_antes_de_qualquer_requisicao(
    projeto_tmp, cliente, sessao, sapl, capsys, respostas
):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    _estragar_paralelo(projeto_tmp / 'teste_proj', {'limite_por_servidor': 10})
    sessao.pedidos.clear()
    capsys.readouterr()
    assert programa.main(roteiro(*respostas), cliente, projeto_tmp) == 2
    assert sessao.pedidos == []
    saida = capsys.readouterr().out
    assert 'config.json' in saida and '"paralelo.limite_por_servidor" = 10' in saida
    assert 'no mínimo 35' in saida
