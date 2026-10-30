"""Configuração do log (terminal + arquivo) e resumo final."""

import logging
from datetime import datetime
from pathlib import Path

import pytest

from sapyl import registro


def _handlers():
    return [h for h in logging.getLogger(registro.LOGGER).handlers if getattr(h, '_sapyl', False)]


def test_configurar_cria_terminal_info_e_arquivo_debug(tmp_path):
    caminho = registro.configurar(tmp_path / 'proj', 'teste')
    handlers = _handlers()
    niveis = sorted((type(h).__name__, h.level) for h in handlers)
    assert niveis == [('FileHandler', logging.DEBUG), ('StreamHandler', logging.INFO)]

    registro.logger('http').debug('linha de depuração')
    registro.logger().info('linha de progresso')
    for h in handlers:
        h.flush()
    texto = open(caminho, encoding='utf-8').read()
    assert 'DEBUG sapyl.http linha de depuração' in texto
    assert 'INFO sapyl linha de progresso' in texto


def test_configurar_duas_vezes_nao_duplica(tmp_path):
    registro.configurar(tmp_path, 'a')
    caminho = registro.configurar(tmp_path, 'b')
    assert len(_handlers()) == 2
    assert Path(caminho).parent == tmp_path / 'logs' and Path(caminho).name.startswith('b_')


# --- Resumo final (FR-26) ---------------------------------------------------

from sapyl.estado import Estado  # noqa: E402


def _links():
    return [
        {'chave': 'h/1', 'Palavras': 'a; b'},
        {'chave': 'h/2', 'Palavras': 'a'},
        {'chave': 'h/3', 'Palavras': 'b'},
    ]


def test_resumo_conta_tudo_e_avisa_falhas(tmp_path):
    estado = Estado(tmp_path / 'e.csv')
    estado.registrar('materia', 'h/1', 'erro', 'HTTP 429')
    estado.registrar('materia', 'h/1', 'ok')
    estado.registrar('materia', 'h/2', 'ok')
    estado.registrar('materia', 'h/3', 'erro', 'timeout')
    estado.registrar('materia', 'outra/9', 'ok')  # não está na lista de links
    estado.registrar('pdf', 'h/1', 'ok')
    estado.registrar('pdf', 'h/2', 'sem_pdf')
    buscas = [('https://h/', 'completa'), ('https://h/', 'incompleta'), ('https://g/', 'completa')]
    texto = registro.resumo(
        estado, _links(), 'p/final.csv', buscas=buscas, casas_inativas=4, downloads=True
    )
    assert (
        'Casas pesquisadas: 2 (1 com alguma busca incompleta; 4 fora do ar, não pesquisadas)'
        in texto
    )
    assert 'Buscas: 3 (1 incompletas)' in texto
    assert 'Matérias: 4 encontradas, 3 únicas, 2 raspadas, 1 com erro' in texto
    assert 'Downloads: 1 baixados, 0 com erro, 1 sem texto original' in texto
    assert 'Resultado: p/final.csv' in texto
    assert 'retomar este projeto' in texto


def test_resumo_sem_falhas_nao_traz_aviso(tmp_path):
    estado = Estado(tmp_path / 'e.csv')
    for k in ('h/1', 'h/2', 'h/3'):
        estado.registrar('materia', k, 'ok')
    texto = registro.resumo(estado, _links(), 'f.csv', buscas=[('https://h/', 'completa')])
    assert 'retomar' not in texto and 'Downloads' not in texto
    # modo atualização: sem buscas
    assert 'Casas' not in registro.resumo(estado, _links(), 'f.csv')


def test_resumo_depois_de_retomada_conta_o_projeto_inteiro(tmp_path):
    estado = Estado(tmp_path / 'e.csv')
    estado.registrar('materia', 'h/1', 'ok')
    estado.registrar('materia', 'h/2', 'erro', 'x')
    estado.fechar()
    retomado = Estado(tmp_path / 'e.csv')
    retomado.registrar('materia', 'h/2', 'ok')
    retomado.registrar('materia', 'h/3', 'ok')
    assert '3 raspadas, 0 com erro' in registro.resumo(retomado, _links(), 'f.csv')


def test_log_comeca_com_nome_e_versao(tmp_path):
    caminho = registro.configurar(tmp_path, 'p')
    primeira = open(caminho, encoding='utf-8').readline()
    assert 'DEBUG sapyl SAPyL: Raspador do Sistema de Apoio Legislativo 0.3.0' in primeira


# --- Um log por execução (FR-26) --------------------------------------------

AGORA = datetime(2026, 10, 27, 14, 5, 9)


@pytest.mark.parametrize('modo', ['novo', 'retomada', 'atualizacao', 'autoria'])
def test_nome_do_log_tem_data_hora_e_modo(tmp_path, modo):
    caminho = registro.configurar(tmp_path / 'p_proj', 'p', modo, agora=AGORA)
    assert caminho == str(tmp_path / 'p_proj' / 'logs' / f'p_2026-10-27_140509_{modo}.log')


def test_modo_desconhecido_e_recusado(tmp_path):
    with pytest.raises(ValueError):
        registro.configurar(tmp_path, 'p', 'outro')


def test_cada_execucao_tem_o_seu_arquivo_mesmo_no_mesmo_segundo(tmp_path):
    primeiro = registro.configurar(tmp_path, 'p', 'novo', agora=AGORA)
    registro.logger().info('primeira execução')
    segundo = registro.configurar(tmp_path, 'p', 'retomada', agora=AGORA)
    terceiro = registro.configurar(tmp_path, 'p', 'retomada', agora=AGORA)
    assert len({primeiro, segundo, terceiro}) == 3
    assert terceiro.endswith('_retomada_2.log')
    assert 'primeira execução' in open(primeiro, encoding='utf-8').read()
    assert 'primeira execução' not in open(segundo, encoding='utf-8').read()


def test_log_antigo_do_projeto_fica_como_esta(tmp_path):
    antigo = tmp_path / 'p.log'
    antigo.write_text('log da Fase 1\n', encoding='utf-8')
    registro.configurar(tmp_path, 'p', 'retomada')
    registro.logger().info('nova execução')
    assert antigo.read_text(encoding='utf-8') == 'log da Fase 1\n'


def test_resumo_termina_com_o_log_desta_execucao(tmp_path):
    from sapyl.estado import Estado

    caminho = registro.configurar(tmp_path, 'p', 'novo')
    estado = Estado(tmp_path / 'e.csv')
    texto = registro.resumo(estado, [], 'f.csv')
    estado.fechar()
    assert texto.splitlines()[-1] == f'Log desta execução: {caminho}'


# --- Tempo, casas ao mesmo tempo e servidores no resumo (FR-14) --------------


@pytest.mark.parametrize(
    ('segundos', 'texto'),
    [(7.4, '7 s'), (65, '1 min 05 s'), (3725.4, '1 h 02 min 05 s'), (0, '0 s')],
)
def test_formatar_duracao(segundos, texto):
    assert registro.formatar_duracao(segundos) == texto


def test_linhas_da_execucao():
    linhas = registro.linhas_da_execucao(
        3725, 8, [('201.54.51.178', 9, 120, 120), ('201.54.51.179', 1, 120, 60)]
    )
    assert linhas == [
        'Tempo: 1 h 02 min 05 s (até 8 casas ao mesmo tempo)',
        'Servidor 201.54.51.178 (9 casas): até 120 requisições por minuto',
        'Servidor 201.54.51.179 (1 casa): limite reduzido de 120 para 60 requisições por minuto '
        '(429 de mais de uma casa)',
    ]


def test_resumos_mostram_as_linhas_da_execucao(tmp_path):
    from collections import Counter

    extra = ['Tempo: 7 s (até 8 casas ao mesmo tempo)']
    estado = Estado(tmp_path / 'e.csv')
    texto = registro.resumo(estado, [], tmp_path / 'f.csv', execucao=extra)
    estado.fechar()
    assert extra[0] in texto and texto.index(extra[0]) < texto.index('Resultado:')
    texto = registro.resumo_autoria(Counter(ok=1), tmp_path / 's.csv', execucao=extra)
    assert extra[0] in texto


# --- Terminal mais limpo (FR-19) -------------------------------------------


def test_andamento_e_debug_com_o_registro(caplog):
    with caplog.at_level(logging.DEBUG, logger='sapyl'):
        registro.andamento(
            registro.logger('materias'), registro.MATERIAS, 3, 9, 'Matéria %d', 3, status='ok'
        )
    [linha] = caplog.records
    assert linha.levelno == logging.DEBUG and linha.getMessage() == 'Matéria 3'
    assert linha.andamento == ('materias', 3, 9, 'ok')


def test_linhas_de_item_so_no_arquivo(tmp_path, capsys):
    registro.configurar(tmp_path, 'p')
    log = registro.logger('materias')
    registro.andamento(log, registro.MATERIAS, 1, 2, 'Matéria 1 de 2: título')
    log.info('Concluída')
    erro = capsys.readouterr().err
    assert 'Concluída' in erro and 'Matéria 1 de 2' not in erro
    texto = next((tmp_path / 'logs').iterdir()).read_text(encoding='utf-8')
    assert 'DEBUG sapyl.materias Matéria 1 de 2: título' in texto and 'Concluída' in texto


def test_configurar_com_o_terminal_da_interface(tmp_path, capsys):
    class Guardar(logging.Handler):
        def __init__(self):
            super().__init__(logging.DEBUG)
            self.mensagens = []

        def emit(self, record):
            self.mensagens.append(record.getMessage())

    guardar = Guardar()
    registro.configurar(tmp_path, 'p', terminal=guardar)
    registro.andamento(registro.logger(), registro.PDFS, 1, 1, 'Download 1')
    assert guardar.mensagens[-1] == 'Download 1' and capsys.readouterr().err == ''
    quantas = len(guardar.mensagens)
    registro.configurar(tmp_path, 'p')  # troca: o handler antigo sai
    registro.logger().info('depois')
    assert len(guardar.mensagens) == quantas
