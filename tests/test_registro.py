"""Configuração do log (terminal + arquivo) e resumo final."""
import logging

import pytest

import registro


@pytest.fixture(autouse=True)
def limpar_handlers():
    yield
    log = logging.getLogger(registro.LOGGER)
    for handler in list(log.handlers):
        log.removeHandler(handler)
        handler.close()


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
