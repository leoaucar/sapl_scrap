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


NOVO = ('2', 'teste', '2', '1', '1')  # não atualizar, nome, sem Sul/Sudeste, todas, downloads


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
    assert programa.main(roteiro('2', 'teste', '1'), cliente, projeto_tmp) == 0
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
    # não atualizar, nome, reusar tabela, Sul/Sudeste, todas, sem downloads
    programa.main(roteiro('2', 'sul', '1', '1', '1', '2'), cliente, projeto_tmp)
    assert not any(u.rstrip('/').endswith('.leg.br') for u in sessao.pedidos)  # nenhum teste de URL
    assert not any('sapl.a.ac.leg.br' in u for u in sessao.pedidos)  # AC filtrado
    assert any('sapl.b.pr.leg.br/sistema/search' in u for u in sessao.pedidos)


def test_modo_atualizacao(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    sessao.pedidos.clear()
    assert programa.main(roteiro('1', 'teste', '2'), cliente, projeto_tmp) == 0
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
        assert programa.main(roteiro('2', 'teste', '1'), cliente, projeto_tmp) == 0
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
        programa.main(roteiro('2', 'teste', '1'), cliente, projeto_tmp)
    assert not any('palavras-chave mudou' in r.getMessage() for r in caplog.records)


def test_sem_aviso_sem_arquivo_de_palavras(projeto_tmp):
    (projeto_tmp / 'arquivos_csv' / 'palavras_chave.xlsx').unlink()
    assert programa.avisar_palavras_mudadas(projeto_tmp, [P]) == []
