"""Downloads: nome estável, gravação aos pedaços, falhas e retomada."""
import os

import pandas as pd
import pytest

from sapyl import downloads as d
from sapyl import materias as m
from sapyl.estado import Estado
from sapyl.cliente_http import ClienteSAPL

RB = 'https://sapl.riobranco.ac.leg.br/'
PDF1 = RB + 'media/sapl/public/materialegislativa/2025/1/a.pdf'
PDF2 = RB + 'media/sapl/public/materialegislativa/2025/2/b.PDF'


@pytest.fixture
def cliente(sessao, relogio):
    return ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)


def _final(*linhas):
    registros = []
    for sapl_id, status, link in linhas:
        linha = {c: '' for c in m.COLUNAS_FINAIS}
        linha.update({'Link Casa': RB, 'sapl_id': sapl_id, 'status': status, 'texto_original': link})
        registros.append(linha)
    return pd.DataFrame(registros, columns=m.COLUNAS_FINAIS)


def test_nome_estavel():
    assert d.nome_arquivo('sapl.riobranco.ac.leg.br/34049', PDF1) == 'sapl.riobranco.ac.leg.br_34049.pdf'
    assert d.nome_arquivo('h/1', PDF2) == 'h_1.pdf'
    assert d.nome_arquivo('h/1', RB + 'media/x.docx') == 'h_1.docx'
    assert d.nome_arquivo('h/1', RB + 'media/download?id=3') == 'h_1.pdf'


def test_baixa_aos_pedacos_e_preenche_colunas(tmp_path, cliente, sessao):
    conteudo = b'%PDF-' + b'x' * 200_000
    sessao.responder(PDF1, conteudo=conteudo)
    estado = Estado(tmp_path / 'e.csv')
    final = d.baixar_todos(_final(('1', 'ok', PDF1)), str(tmp_path / 'dl'), cliente, estado)
    nome = 'sapl.riobranco.ac.leg.br_1.pdf'
    assert (tmp_path / 'dl' / nome).read_bytes() == conteudo
    assert final.iloc[0][['arquivo_pdf', 'download_status']].tolist() == [nome, 'ok']
    assert estado.status('pdf', 'sapl.riobranco.ac.leg.br/1') == 'ok'
    _, kwargs = sessao.chamadas[0]
    assert kwargs == {'stream': True, 'timeout': d.TIMEOUT_DOWNLOAD}


def test_falha_no_meio_nao_deixa_part(tmp_path, cliente, sessao):
    sessao.responder(PDF1, conteudo=b'x' * 200_000, falhar_no_meio=True)
    estado = Estado(tmp_path / 'e.csv')
    final = d.baixar_todos(_final(('1', 'ok', PDF1)), str(tmp_path / 'dl'), cliente, estado)
    assert os.listdir(tmp_path / 'dl') == []
    assert final.iloc[0]['download_status'] == 'erro'
    assert estado.erro('pdf', 'sapl.riobranco.ac.leg.br/1') == 'download interrompido'


def test_erro_http_no_download(tmp_path, cliente, sessao):
    sessao.responder(PDF1, status=404)
    estado = Estado(tmp_path / 'e.csv')
    final = d.baixar_todos(_final(('1', 'ok', PDF1)), str(tmp_path / 'dl'), cliente, estado)
    assert final.iloc[0]['download_status'] == 'erro'
    assert estado.erro('pdf', 'sapl.riobranco.ac.leg.br/1') == 'HTTP 404'


def test_sem_link_e_materia_com_erro(tmp_path, cliente, sessao):
    estado = Estado(tmp_path / 'e.csv')
    final = d.baixar_todos(_final(('1', 'ok', ''), ('2', 'erro', PDF2)),
                           str(tmp_path / 'dl'), cliente, estado)
    assert final['download_status'].tolist() == ['sem_pdf', '']
    assert sessao.pedidos == []
    assert estado.status('pdf', 'sapl.riobranco.ac.leg.br/1') == 'sem_pdf'


def test_retomada_pula_arquivo_ja_baixado_e_refaz_erro(tmp_path, cliente, sessao):
    sessao.responder(PDF1, conteudo=b'um').responder(PDF2, status=503)
    estado = Estado(tmp_path / 'e.csv')
    tabela = _final(('1', 'ok', PDF1), ('2', 'ok', PDF2))
    d.baixar_todos(tabela, str(tmp_path / 'dl'), cliente, estado)

    sessao.pedidos.clear()
    sessao.limpar(PDF2).responder(PDF2, conteudo=b'dois')
    final = d.baixar_todos(tabela, str(tmp_path / 'dl'), cliente, estado)
    assert sessao.pedidos == [PDF2]
    assert final['download_status'].tolist() == ['ok', 'ok']


def test_arquivo_apagado_e_baixado_de_novo(tmp_path, cliente, sessao):
    sessao.responder(PDF1, conteudo=b'um')
    estado = Estado(tmp_path / 'e.csv')
    tabela = _final(('1', 'ok', PDF1))
    d.baixar_todos(tabela, str(tmp_path / 'dl'), cliente, estado)
    os.remove(tmp_path / 'dl' / 'sapl.riobranco.ac.leg.br_1.pdf')
    d.baixar_todos(tabela, str(tmp_path / 'dl'), cliente, estado)
    assert sessao.contar('a.pdf') == 2


def test_pasta_existente_nao_quebra(tmp_path, cliente, sessao):
    (tmp_path / 'dl').mkdir()
    estado = Estado(tmp_path / 'e.csv')
    d.baixar_todos(_final(('1', 'ok', '')), str(tmp_path / 'dl'), cliente, estado)
