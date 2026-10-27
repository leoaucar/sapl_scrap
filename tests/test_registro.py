"""Configuração do log (terminal + arquivo) e resumo final."""
import logging

from sapyl import registro


def _handlers():
    return [h for h in logging.getLogger(registro.LOGGER).handlers if getattr(h, '_sapl_scrap', False)]


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
    assert 'DEBUG sapl_scrap.http linha de depuração' in texto
    assert 'INFO sapl_scrap linha de progresso' in texto


def test_configurar_duas_vezes_nao_duplica(tmp_path):
    registro.configurar(tmp_path, 'a')
    registro.configurar(tmp_path, 'b')
    assert len(_handlers()) == 2
    assert (tmp_path / 'b.log').exists()


# --- Resumo final (FR-26) ---------------------------------------------------

from sapyl.estado import Estado  # noqa: E402


def _links():
    return [{'chave': 'h/1', 'Palavras': 'a; b'}, {'chave': 'h/2', 'Palavras': 'a'},
            {'chave': 'h/3', 'Palavras': 'b'}]


def test_resumo_conta_tudo_e_avisa_falhas(tmp_path):
    estado = Estado(tmp_path / 'e.csv')
    estado.registrar('materia', 'h/1', 'erro', 'HTTP 429')
    estado.registrar('materia', 'h/1', 'ok')
    estado.registrar('materia', 'h/2', 'ok')
    estado.registrar('materia', 'h/3', 'erro', 'timeout')
    estado.registrar('materia', 'outra/9', 'ok')            # não está na lista de links
    estado.registrar('pdf', 'h/1', 'ok')
    estado.registrar('pdf', 'h/2', 'sem_pdf')
    buscas = [('https://h/', 'completa'), ('https://h/', 'incompleta'), ('https://g/', 'completa')]
    texto = registro.resumo(estado, _links(), 'p/final.csv', buscas=buscas,
                            casas_inativas=4, downloads=True)
    assert 'Casas pesquisadas: 2 (1 com alguma busca incompleta; 4 fora do ar, não pesquisadas)' in texto
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
