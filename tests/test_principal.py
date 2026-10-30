"""Fluxo principal: projeto novo, retomada, modo atualização, interrupção."""

import importlib
import json
import logging

import pytest

from sapyl.cliente_http import ClienteSAPL
from sapyl.estado import Estado
from sapyl.interface import principal as programa
from sapyl.interface.perguntas import PerguntasMenu, PerguntasTexto
from sapyl.tabela import ler_final
from tests.apoio import (
    SaplFalso,
    respostas_atualizar,
    respostas_autoria,
    respostas_novo_projeto,
    respostas_retomar,
    roteiro,
)

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


NOVO = respostas_novo_projeto(pdfs='s')  # todos os estados, todas as casas, com PDFs
RETOMAR = respostas_retomar()


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
    # só: retomar, o projeto, continuar. Uma pergunta a mais esvaziaria o roteiro.
    assert programa.main(roteiro(*RETOMAR), cliente, projeto_tmp) == 0
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
    respostas = respostas_novo_projeto('sul', tabela='1', estados='sul-sudeste')
    assert programa.main(roteiro(*respostas), cliente, projeto_tmp) == 0
    config = json.loads((projeto_tmp / 'sul_proj' / 'config.json').read_text(encoding='utf-8'))
    assert config['estados'] == ['PR'] and 'sul_sudeste' not in config
    assert not any(u.rstrip('/').endswith('.leg.br') for u in sessao.pedidos)  # nenhum teste de URL
    assert not any('sapl.a.ac.leg.br' in u for u in sessao.pedidos)  # AC filtrado
    assert any('sapl.b.pr.leg.br/sistema/search' in u for u in sessao.pedidos)


def test_modo_atualizacao(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    sessao.pedidos.clear()
    assert programa.main(roteiro(*respostas_atualizar('n')), cliente, projeto_tmp) == 0
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
    for _ in range(2):
        perguntas = PerguntasTexto(roteiro('1', 's', '1'))  # projeto, PDFs, continuar
        programa.executar_atualizacao(projeto_tmp, cliente, perguntas, hoje='01_01_2027')
    assert (
        projeto_tmp / 'teste_proj' / 'downloads01_01_2027' / 'sapl.a.ac.leg.br_38415.pdf'
    ).exists()


def test_ctrl_c_sai_com_mensagem(projeto_tmp, cliente, capsys):
    def interromper(texto=''):
        raise KeyboardInterrupt

    assert programa.main(interromper, cliente, projeto_tmp) == 1
    assert 'Interrompido. Nada foi iniciado.' in capsys.readouterr().out


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
    assert 'Interrompido. Nada foi iniciado.' in capsys.readouterr().out


def test_boas_vindas_e_resumo_com_o_nome_sapyl(projeto_tmp, cliente, sessao, sapl, caplog, capsys):
    with caplog.at_level(logging.INFO, logger='sapyl'):
        assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 0
    saida = capsys.readouterr().out
    assert saida.startswith('SAPyL: Raspador do Sistema de Apoio Legislativo (versão 0.4.0)')
    resumo = [r.getMessage() for r in caplog.records if 'Resumo' in r.getMessage()][-1]
    assert '===== Resumo (SAPyL 0.4.0) =====' in resumo


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
        assert programa.main(roteiro(*RETOMAR), cliente, projeto_tmp) == 0
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
        programa.main(roteiro(*RETOMAR), cliente, projeto_tmp)
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
    ler = roteiro(*respostas_atualizar('s', 'n'))  # só relevantes, sem downloads
    with caplog.at_level(logging.INFO, logger='sapyl'):
        assert programa.main(ler, cliente, projeto_tmp) == 0
    assert any(programa.PERGUNTA_RELEVANTES in p for p in ler.perguntas)
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
    assert programa.main(roteiro(*respostas_atualizar('n', 'n')), cliente, projeto_tmp) == 0
    final = _atualizado(projeto_tmp)
    assert final['sapl_id'].tolist() == ['38415', '43301', '43300', '42263']
    assert final['Relevante'].tolist() == ['sim', '', '', '']


def test_sem_coluna_relevante_nao_pergunta(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    ler = roteiro(*respostas_atualizar('n'))
    assert programa.main(ler, cliente, projeto_tmp) == 0
    assert not any(programa.PERGUNTA_RELEVANTES in p for p in ler.perguntas)


# --- Opção 3: autoria e tramitação (FR-7, FR-17) ----------------------------


def _sapl_sem_api_de_autoria(sessao, casa, *ids):
    for i in ids:
        for lista in ('autoria', 'tramitacao'):
            sessao.responder(f'{casa}api/materia/{lista}/?materia={i}', status=404)
            sessao.responder(f'{casa}materia/{i}/{lista}', texto='<p>sem tabela</p>')


def test_menu_principal_no_modo_texto(projeto_tmp, cliente):
    ler = roteiro('6')
    assert programa.main(ler, cliente, projeto_tmp) == 0
    assert ler.perguntas[0] == (
        'O que você quer fazer?\n1- Novo projeto\n2- Retomar um projeto\n'
        '3- Atualizar um projeto\n4- Autoria e tramitação\n5- Ajuda\n6- Sair\n'
    )


def test_autoria_de_um_projeto_usa_o_resultado_mais_recente(projeto_tmp, cliente, sessao, sapl):
    import os

    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    pasta = projeto_tmp / 'teste_proj'
    atualizado = pasta / 'teste_resultado_final_ATUALIZADO_01_01_2027.csv'
    ler_final(pasta / 'teste_resultado_final.csv').head(1).to_csv(atualizado, index=False)
    os.utime(atualizado, (2_000_000_000, 2_000_000_000))  # mais novo
    _sapl_sem_api_de_autoria(sessao, A, '38415')
    assert programa.main(roteiro(*respostas_autoria()), cliente, projeto_tmp) == 0
    saida = pasta / 'teste_resultado_final_ATUALIZADO_01_01_2027_autoria_tramitacao.csv'
    assert ler_final(saida)['sapl_id'].tolist() == ['38415']
    assert list((pasta / 'logs').glob('teste_*_autoria.log'))


def test_autoria_de_um_csv_avulso(projeto_tmp, cliente, sessao, sapl, capsys):
    planilhas = projeto_tmp / 'planilhas'
    planilhas.mkdir()
    (planilhas / 'minha.csv').write_text(f'Link Materia\n{A}materia/43301\n', encoding='utf-8')
    _sapl_sem_api_de_autoria(sessao, A, '43301')
    # sem projetos na pasta: pergunta direto o caminho do CSV
    ler = roteiro('4', 'nao_existe.csv', 'planilhas/minha.csv', '1')
    assert programa.main(ler, cliente, projeto_tmp) == 0
    assert 'Não encontrei o arquivo CSV "nao_existe.csv"' in capsys.readouterr().out
    assert (planilhas / 'minha_autoria_tramitacao.csv').exists()
    assert (planilhas / 'minha_autoria_tramitacao_estado.csv').exists()
    assert list((planilhas / 'logs').glob('minha_*_autoria.log'))


def test_ctrl_c_na_autoria_explica_como_retomar(projeto_tmp, cliente, capsys):
    (projeto_tmp / 'minha.csv').write_text(f'Link Materia\n{A}materia/1\n', encoding='utf-8')
    respostas = iter(['4', 'minha.csv'])  # Ctrl+C na confirmação

    def ler(texto=''):
        try:
            return next(respostas)
        except StopIteration:
            raise KeyboardInterrupt from None

    assert programa.main(ler, cliente, projeto_tmp) == 1
    saida = capsys.readouterr().out
    assert 'escolha "Autoria e tramitação" e de novo' in saida and 'minha.csv' in saida


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
    assert programa.main(roteiro(*RETOMAR), cliente, projeto_tmp) == 0
    assert 'paralelo' not in json.loads(arquivo.read_text(encoding='utf-8'))


def _estragar_paralelo(pasta, valor):
    arquivo = pasta / 'config.json'
    config = json.loads(arquivo.read_text(encoding='utf-8'))
    config['paralelo'] = valor
    arquivo.write_text(json.dumps(config), encoding='utf-8')


@pytest.mark.parametrize(
    'respostas',
    [('2', '1'), ('3', '1'), ('4', '1')],  # o projeto escolhido; nada mais é perguntado
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


# --- Resumo com tempo e servidores (FR-14) ------------------------------------


def test_resumo_mostra_tempo_casas_e_servidores(projeto_tmp, sessao, relogio, sapl, caplog):
    cliente = ClienteSAPL(
        sessao=sessao,
        relogio=relogio.agora,
        dormir=relogio.dormir,
        servidor_de=lambda host: '10.0.0.1',
        limite_por_servidor=999,
    )
    with caplog.at_level(logging.INFO, logger='sapyl'):
        assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 0
    resumo = [r.getMessage() for r in caplog.records if 'Resumo' in r.getMessage()][-1]
    assert '(até 8 casas ao mesmo tempo)' in resumo and 'Tempo: ' in resumo
    # o limite do config.json (120) vale, não o do cliente criado
    assert 'Servidor 10.0.0.1 (3 casas): até 120 requisições por minuto' in resumo


def test_resumo_mostra_limite_reduzido(projeto_tmp, sessao, relogio, sapl, caplog):
    for casa in (A, 'https://sapl.b.pr.leg.br/'):
        sapl.falhar(f'{casa}sistema/search/?page=1&q={P}', 429)
    cliente = ClienteSAPL(
        sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir, servidor_de=lambda h: 'srv'
    )
    with caplog.at_level(logging.INFO, logger='sapyl'):
        assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 0
    resumo = [r.getMessage() for r in caplog.records if 'Resumo' in r.getMessage()][-1]
    assert 'Servidor srv (3 casas): limite reduzido de 120 para 60' in resumo
    assert any('Servidor srv sobrecarregado' in r.getMessage() for r in caplog.records)


def test_erro_inesperado_numa_casa_nao_perde_as_outras(
    projeto_tmp, cliente, sessao, sapl, capsys, caplog, monkeypatch
):
    from sapyl import materias

    original = materias.raspar_materia

    def quebrar_uma_casa(link, *args):
        if link['chave'].startswith('sapl.a.ac.leg.br/'):
            raise OSError('disco cheio')
        return original(link, *args)

    monkeypatch.setattr(materias, 'raspar_materia', quebrar_uma_casa)
    with caplog.at_level(logging.ERROR, logger='sapyl'):
        assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 1
    assert 'escolha "Retomar um projeto" e depois "teste"' in capsys.readouterr().out
    assert any('1 casa(s) pararam' in r.getMessage() for r in caplog.records)
    assert any(r.exc_info for r in caplog.records)  # o traceback vai para o log
    estado = Estado(projeto_tmp / 'teste_proj' / 'teste_estado.csv')
    assert estado.contagens('busca') == {'completa': 4}  # as buscas das duas casas
    estado.fechar()
    monkeypatch.setattr(materias, 'raspar_materia', original)
    assert programa.main(roteiro(*RETOMAR), cliente, projeto_tmp) == 0
    final = ler_final(projeto_tmp / 'teste_proj' / 'teste_resultado_final.csv')
    assert final['sapl_id'].tolist() == ['38415', '43301', '43300', '42263']


def test_texto_do_progresso(tmp_path):
    estado = Estado(tmp_path / 'e.csv')
    estado.registrar('materia', 'h/1', 'ok')
    estado.registrar('materia', 'h/2', 'erro', 'x')
    assert programa.progresso_das_materias(estado) == 'matérias: 1 raspadas, 1 com erro'
    estado.fechar()


# --- Menu, conferências antes de perguntar e confirmação (FR-3 a FR-16) -------


def test_ajuda_e_sair(projeto_tmp, cliente, capsys):
    assert programa.main(roteiro('5', '6'), cliente, projeto_tmp) == 0
    saida = capsys.readouterr().out
    assert 'Ajuda do SAPyL' in saida and 'palavras_chave.csv' in saida


def test_retomar_sem_projetos_volta_ao_menu(projeto_tmp, cliente, capsys):
    assert programa.main(roteiro('2', '3', '6'), cliente, projeto_tmp) == 0
    saida = capsys.readouterr().out
    assert 'Nenhum projeto nesta pasta' in saida
    assert 'Nenhum projeto com resultado final' in saida


@pytest.mark.parametrize('falta', ['palavras', 'coluna', 'planilha'])
def test_entradas_erradas_param_antes_de_perguntar_o_nome(
    projeto_tmp, cliente, sessao, capsys, falta
):
    pasta = projeto_tmp / 'arquivos_csv'
    if falta == 'palavras':
        (pasta / 'palavras_chave.xlsx').unlink()
    elif falta == 'coluna':
        (pasta / 'palavras_chave.csv').write_text('Termos\nx\n', encoding='utf-8')
    else:
        (pasta / 'casas_legislativas.xlsx').unlink()
    ler = roteiro('1')
    assert programa.main(ler, cliente, projeto_tmp) == 2
    assert len(ler.perguntas) == 1  # só o menu
    saida = capsys.readouterr().out
    assert {
        'palavras': 'Não encontrei o arquivo de palavras-chave',
        'coluna': 'não tem a coluna',
        'planilha': 'Não encontrei a planilha',
    }[falta] in saida
    assert 'Traceback' not in saida
    assert not list(projeto_tmp.glob('*_proj')) and sessao.pedidos == []


def test_palavras_aparecem_em_texto_simples_e_confirmacao(
    projeto_tmp, cliente, sessao, sapl, capsys
):
    assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 0
    saida = capsys.readouterr().out
    assert (
        '  1. plano diretor\n  2. orçamento + emenda impositiva (juntos na mesma matéria)' in saida
    )
    assert 'Casas: 3 (o programa testa quais estão no ar antes de buscar)' in saida
    assert 'Buscas: até 6 (casas × palavras)' in saida
    assert 'PDFs: sim' in saida and 'Estados: todos' in saida
    assert '"plano+diretor"' not in saida.split('Resumo')[0]


def test_cancelar_nao_cria_nada(projeto_tmp, cliente, sessao, capsys):
    respostas = respostas_novo_projeto()[:-2] + ['2']  # Cancelar em vez de Começar
    assert programa.main(roteiro(*respostas), cliente, projeto_tmp) == 0
    assert 'Cancelado. Nada foi feito.' in capsys.readouterr().out
    assert not list(projeto_tmp.glob('*_proj')) and sessao.pedidos == []


def test_voltar_um_passo_de_cada_vez(projeto_tmp, cliente, sessao, sapl):
    # só SP, teste com 10, sem PDFs; na confirmação volta (3), nos PDFs volta (<),
    # em "quantas" volta (3), muda para AC e PR, todas, sem PDFs, começa
    respostas = ['1', 'teste', 'SP', '2', 'n', '3', '<', '3', 'AC PR', '1', 'n', '1', 'n']
    assert programa.main(roteiro(*respostas), cliente, projeto_tmp) == 0
    config = json.loads((projeto_tmp / 'teste_proj' / 'config.json').read_text(encoding='utf-8'))
    assert config['estados'] == ['AC', 'PR'] and config['limite'] == '1'
    assert not any('sapl.c.sp.leg.br' in u for u in sessao.pedidos)
    # com filtro de estados, a tabela geral de casas não é trocada
    assert not (projeto_tmp / 'arquivos_csv' / 'casas_resultado.csv').exists()


def test_cancelar_a_retomada(projeto_tmp, cliente, sessao, sapl, capsys):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    sessao.pedidos.clear()
    assert programa.main(roteiro('2', '1', '2'), cliente, projeto_tmp) == 0
    assert sessao.pedidos == [] and 'Cancelado' in capsys.readouterr().out


def test_nome_existente_pode_ser_retomado_pelo_novo(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    # novo, nome que existe, retomar este projeto, continuar, sem autoria
    assert programa.main(roteiro('1', 'teste', '1', '1', 'n'), cliente, projeto_tmp) == 0
    logs = list((projeto_tmp / 'teste_proj' / 'logs').glob('*_retomada.log'))
    assert len(logs) == 1


@pytest.mark.parametrize(
    'antiga,casas',
    [
        ({'sul_sudeste': True, 'limite': '1'}, ['sapl.b.pr.leg.br', 'sapl.c.sp.leg.br']),
        (
            {'sul_sudeste': False, 'limite': '3'},
            ['sapl.a.ac.leg.br', 'sapl.b.pr.leg.br', 'sapl.c.sp.leg.br'],
        ),
        (
            {'sul_sudeste': False, 'limite': '2'},
            ['sapl.a.ac.leg.br', 'sapl.b.pr.leg.br', 'sapl.c.sp.leg.br'],
        ),
    ],
)
def test_config_antiga_retoma_com_as_mesmas_casas(
    projeto_tmp, cliente, sessao, sapl, antiga, casas
):
    projeto = programa.gp.Projeto(projeto_tmp, 'velho')
    projeto.criar()
    config = {'palavras': [P], 'reusar_tabela': False, 'downloads': False, **antiga}
    programa.gp.salvar_config(projeto, config)
    assert programa.main(roteiro(*RETOMAR), cliente, projeto_tmp) == 0
    tabela = programa.cl.ler_tabela_casas(projeto.casas)
    assert [u.split('//')[1].rstrip('/') for u in tabela['url']] == casas


def test_terminal_organizado_por_etapas(projeto_tmp, cliente, sessao, sapl, capsys):
    assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 0
    terminal = capsys.readouterr().err
    print(terminal)  # para ver com -s
    inicio = terminal.index('\nProjeto teste · todos os estados · 2 palavras\n')
    etapa1 = terminal.index('Etapa 1 de 2: testando os sites (3 casas)\n')
    no_ar = terminal.index('  2 de 3 casas no ar (fora: 1 HTTP 500)\n\n')
    assert 'Falha em' not in terminal and 'sem API' not in terminal
    etapa2 = terminal.index('Etapa 2 de 2: busca e raspagem (2 casas, até 8 ao mesmo tempo)\n\n')
    feita = terminal.index('✓ sapl.a.ac.leg.br: 2 buscas, 4 matérias (2 com erro), 2 PDFs\n')
    planilha = terminal.index('\nMontando a planilha final\n')
    assert inicio < etapa1 < no_ar < etapa2 < feita < planilha
    assert 'Começando' not in terminal and 'Buscando os termos' not in terminal
    assert 'Matéria 1 de' not in terminal and 'Download 1 de' not in terminal
    assert 'Testando casa' not in terminal and 'página(s)' not in terminal
    [log] = (projeto_tmp / 'teste_proj' / 'logs').iterdir()
    texto = log.read_text(encoding='utf-8')
    assert 'Matéria 1 de' in texto and 'Download 1 de' in texto and 'Testando casa 1 de 3' in texto


def test_linha_de_progresso_com_tempo_restante(
    projeto_tmp, cliente, sessao, sapl, monkeypatch, caplog
):
    from sapyl import execucao

    monkeypatch.setattr(execucao, 'PROGRESSO_A_CADA', 0.0)
    original = execucao.por_casa

    def a_cada_instante(*args, **kwargs):
        kwargs['a_cada'] = 0.0
        return original(*args, **kwargs)

    monkeypatch.setattr(execucao, 'por_casa', a_cada_instante)
    with caplog.at_level(logging.INFO, logger='sapyl'):
        assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 0
    linhas = [r.getMessage() for r in caplog.records if r.getMessage().startswith('Progresso')]
    assert linhas and '\n  Buscas 4 de 4 completas · Matérias ' in linhas[-1]
    assert ' · PDFs 2 baixados · 0 com erro · Tempo ' in linhas[-1]
    assert linhas[-1].endswith(', calculando')


class _MenusComRoteiro(PerguntasMenu):
    """Modo menus (painel ao vivo), mas com as respostas de um roteiro."""

    def __init__(self, ler, console):
        self._texto = PerguntasTexto(ler)
        self.console = console

    def escolher(self, texto, opcoes, voltar=False):
        return self._texto.escolher(texto, opcoes, voltar)

    def sim_nao(self, texto, padrao=False, voltar=False):
        return self._texto.sim_nao(texto, padrao, voltar)

    def marcar(self, texto, opcoes, atalhos, voltar=False):
        return self._texto.marcar(texto, opcoes, atalhos, voltar)

    def texto(self, texto, validar, voltar=False):
        return self._texto.texto(texto, validar, voltar)


def test_modo_menus_painel_e_resumo_num_quadro(projeto_tmp, cliente, sessao, sapl, monkeypatch):
    import io

    from rich.console import Console

    console = Console(record=True, width=120, file=io.StringIO(), force_terminal=True)
    menus = _MenusComRoteiro(roteiro(*NOVO), console)
    monkeypatch.setattr(programa, 'criar_perguntas', lambda entrada: menus)
    assert programa.main(input, cliente, projeto_tmp) == 0
    texto = console.export_text()
    assert '✓ sapl.a.ac.leg.br: 2 buscas, 4 matérias (2 com erro), 2 PDFs' in texto
    assert '╭' in texto and 'Resumo (SAPyL' in texto
    assert 'Matéria 1 de' not in texto


# --- Oferta da autoria, próximos passos e erros (FR-17, FR-21, FR-21a, FR-22) --


def test_oferta_de_autoria_aceita_roda_no_resultado(projeto_tmp, cliente, sessao, sapl, capsys):
    for i in ('38415', '43301', '43300', '42263'):
        _sapl_sem_api_de_autoria(sessao, A, i)
    ler = roteiro(*respostas_novo_projeto(pdfs='s', autoria='s'))
    assert programa.main(ler, cliente, projeto_tmp) == 0
    assert 'Buscar agora a autoria e a tramitação das 4 matérias' in ler.perguntas[-1]
    pasta = projeto_tmp / 'teste_proj'
    assert (pasta / 'teste_resultado_final_autoria_tramitacao.csv').exists()
    assert list((pasta / 'logs').glob('teste_*_autoria.log'))
    assert capsys.readouterr().err.count('===== Resumo') == 2


def test_oferta_recusada_e_nao_oferecida_na_autoria(projeto_tmp, cliente, sessao, sapl):
    assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 0
    assert not list((projeto_tmp / 'teste_proj').glob('*_autoria_tramitacao.csv'))
    _sapl_sem_api_de_autoria(sessao, A, '38415', '43301', '43300', '42263')
    ler = roteiro(*respostas_autoria())
    assert programa.main(ler, cliente, projeto_tmp) == 0
    assert not any('Buscar agora' in p for p in ler.perguntas)


def test_resumo_com_proximos_passos(projeto_tmp, cliente, sessao, sapl, caplog):
    with caplog.at_level(logging.INFO, logger='sapyl'):
        assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 0
    resumo = [r.getMessage() for r in caplog.records if 'Resumo' in r.getMessage()][-1]
    assert 'Próximos passos:\n- Abra o resultado numa planilha: ' in resumo
    assert 'escolha "Retomar um projeto" e depois "teste".' in resumo


def test_config_json_estragado(projeto_tmp, cliente, sessao, sapl, capsys):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    (projeto_tmp / 'teste_proj' / 'config.json').write_text('{quebrado', encoding='utf-8')
    capsys.readouterr()
    assert programa.main(roteiro('2', '1'), cliente, projeto_tmp) == 2
    saida = capsys.readouterr().out
    assert 'config.json: não é um JSON válido' in saida and 'Traceback' not in saida


@pytest.mark.parametrize(
    'erro,codigo,texto',
    [
        (
            PermissionError(13, 'Permission denied', '/sem/acesso'),
            2,
            'Sem permissão para gravar ou ler /sem/acesso',
        ),
        (OSError(28, 'No space left on device', 'x.csv'), 2, 'O disco encheu ao gravar x.csv'),
        (RuntimeError('quebrou'), 1, 'Erro inesperado: RuntimeError: quebrou'),
    ],
)
def test_erros_viram_mensagens(
    projeto_tmp, cliente, sessao, sapl, capsys, monkeypatch, erro, codigo, texto
):
    def falhar(*args, **kwargs):
        raise erro

    monkeypatch.setattr(programa, 'executar_projeto', falhar)
    assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == codigo
    saida = capsys.readouterr()
    assert texto in saida.out and 'Traceback' not in saida.out + saida.err


def test_erro_inesperado_traceback_no_log_da_execucao(
    projeto_tmp, cliente, sessao, sapl, capsys, monkeypatch
):
    monkeypatch.setattr(programa, 'executar_projeto', lambda *a, **k: 1 / 0)
    assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 1
    [log] = (projeto_tmp / 'teste_proj' / 'logs').iterdir()
    assert f'Os detalhes estão em {log}' in capsys.readouterr().out
    texto = log.read_text(encoding='utf-8')
    assert 'Traceback' in texto and 'ZeroDivisionError' in texto


def test_erro_inesperado_antes_do_log_vai_para_um_arquivo(
    projeto_tmp, cliente, capsys, monkeypatch
):
    monkeypatch.setattr(programa, 'ler_palavras', lambda pasta: 1 / 0)
    assert programa.main(roteiro('1'), cliente, projeto_tmp) == 1
    [arquivo] = projeto_tmp.glob('sapyl_erro_*.log')
    assert 'ZeroDivisionError' in arquivo.read_text(encoding='utf-8')
    assert str(arquivo) in capsys.readouterr().out


# --- ← Voltar nos fluxos (FR-23) ---------------------------------------------


def test_voltar_no_nome_volta_ao_menu(projeto_tmp, cliente, sessao):
    ler = roteiro('1', '<', '6')
    assert programa.main(ler, cliente, projeto_tmp) == 0
    assert ler.perguntas[-1].startswith('O que você quer fazer?')
    assert not list(projeto_tmp.glob('*_proj')) and sessao.pedidos == []


def test_voltar_dos_estados_pergunta_o_nome_de_novo(projeto_tmp, cliente, sessao, sapl):
    # sem tabela geral, estados é a primeira pergunta depois do nome
    respostas = ['1', 'errado', '<', 'certo', '', '1', 'n', '1', 'n']
    assert programa.main(roteiro(*respostas), cliente, projeto_tmp) == 0
    assert [p.name for p in projeto_tmp.glob('*_proj')] == ['certo_proj']


def test_voltar_na_retomada_volta_a_lista_e_ao_menu(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    sessao.pedidos.clear()
    # retomar, projeto 1, ← Voltar (3) na confirmação, ← Voltar (2) na lista, Sair
    ler = roteiro('2', '1', '3', '2', '6')
    assert programa.main(ler, cliente, projeto_tmp) == 0
    assert sessao.pedidos == []
    assert sum(p.startswith('Qual projeto retomar?') for p in ler.perguntas) == 2


def test_voltar_na_atualizacao(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    _marcar(projeto_tmp, {'38415': 'x'})
    # atualizar, projeto, relevantes s, PDFs < (volta), relevantes n, PDFs n, continuar
    ler = roteiro('3', '1', 's', '<', 'n', 'n', '1', 'n')
    assert programa.main(ler, cliente, projeto_tmp) == 0
    assert len(_atualizado(projeto_tmp)) == 4  # todas: "só relevantes" foi desfeito


def test_voltar_no_csv_da_autoria_volta_a_lista(projeto_tmp, cliente, sessao, sapl):
    programa.main(roteiro(*NOVO), cliente, projeto_tmp)
    # autoria, Outro CSV (2), < no caminho, ← Voltar na lista (3), Sair
    ler = roteiro('4', '2', '<', '3', '6')
    assert programa.main(ler, cliente, projeto_tmp) == 0
    assert sum(p.startswith('De onde vêm as matérias?') for p in ler.perguntas) == 2
