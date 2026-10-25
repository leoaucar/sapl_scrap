"""Fixtures compartilhadas pelos testes."""
import logging
import socket

import pandas as pd
import pytest

from tests.apoio import RelogioFalso, SessaoFalsa


def _rede_bloqueada(*args, **kwargs):
    raise RuntimeError('Acesso à rede bloqueado nos testes (use SessaoFalsa)')


@pytest.fixture(autouse=True)
def bloquear_rede(monkeypatch):
    """Qualquer tentativa de abrir uma conexão de verdade faz o teste falhar."""
    monkeypatch.setattr(socket.socket, 'connect', _rede_bloqueada)
    monkeypatch.setattr(socket.socket, 'connect_ex', _rede_bloqueada)
    monkeypatch.setattr(socket, 'create_connection', _rede_bloqueada)


@pytest.fixture(autouse=True)
def limpar_log():
    """Remove os handlers de log criados por `registro.configurar` em cada teste."""
    yield
    log = logging.getLogger('sapl_scrap')
    for handler in list(log.handlers):
        log.removeHandler(handler)
        handler.close()


@pytest.fixture
def relogio():
    return RelogioFalso()


@pytest.fixture
def sessao():
    return SessaoFalsa()


@pytest.fixture
def projeto_tmp(tmp_path):
    """Pasta de trabalho com arquivos_csv/ mínimo (planilha de casas e palavras)."""
    pasta = tmp_path / 'arquivos_csv'
    pasta.mkdir()
    pd.DataFrame({
        'Casa Legislativa': ['Câmara A', 'Câmara B', 'Câmara C'],
        'Município': ['A', 'B', 'C'],
        'UF': ['AC', 'PR', 'SP'],
        'URL do serviço': ['https://sapl.a.ac.leg.br/', 'https://sapl.b.pr.leg.br/',
                           'https://sapl.c.sp.leg.br/'],
    }).to_excel(pasta / 'casas_legislativas.xlsx', index=False)
    pd.DataFrame({'Palavras': ['plano diretor', 'orçamento, emenda impositiva']}).to_excel(
        pasta / 'palavras_chave.xlsx', index=False)
    return tmp_path
