"""Tabela final: ordem das colunas, tentativa mais recente, compatibilidade."""

import pandas as pd
import pytest

from sapyl import colunas
from sapyl import links as lk
from sapyl import materias as m
from sapyl import tabela as t
from sapyl.estado import ArquivoCSV

CV = 'https://sapl.cascavel.pr.leg.br/'


def _link(i, palavras):
    return {
        'chave': lk.chave(CV, i),
        'Link Materia': f'{CV}materia/{i}',
        'Link Casa': CV,
        'Palavras': palavras,
        'sapl_id': i,
    }


def test_colunas_finais_na_ordem_esperada():
    antigas = [
        'Link Materia',
        'Link Casa',
        'Palavras',
        'Titulo',
        'Ementa',
        'Ano',
        'Data',
        'Numero',
        'Observacao',
        'Tipo de Materia Legislativa',
        'texto_original',
    ]
    assert colunas.COLUNAS_FINAIS[: len(antigas)] == antigas
    assert (
        'Assuntos' not in colunas.COLUNAS_FINAIS and 'texto_integral' not in colunas.COLUNAS_FINAIS
    )
    assert colunas.COLUNAS_FINAIS[-7:] == [
        'sapl_id',
        'fonte',
        'status',
        'erro',
        'raspada_em',
        'arquivo_pdf',
        'download_status',
    ]
    for nova in (
        'Indexacao',
        'Em Tramitacao',
        'Regime Tramitacao',
        'Materia Anexada',
        'Resultado',
        'Data Publicacao',
        'Numero Protocolo',
        'Ultima Atualizacao',
    ):
        assert nova in colunas.COLUNAS_FINAIS


def test_montar_final_usa_tentativa_mais_recente_e_palavras_dos_links(tmp_path):
    links = [_link('2', 'b'), _link('1', 'a; c')]
    arquivo = ArquivoCSV(tmp_path / 'mat.csv', colunas.COLUNAS_MATERIAS)
    arquivo.anexar({**m.linha_vazia(links[1]), 'status': 'erro', 'erro': 'HTTP 429'})
    arquivo.anexar({**m.linha_vazia(links[0]), 'status': 'ok', 'Titulo': 'Dois'})
    arquivo.anexar({**m.linha_vazia(links[1]), 'status': 'ok', 'Titulo': 'Um', 'Palavras': 'a'})
    arquivo.fechar()
    final = t.montar_final(tmp_path / 'mat.csv', links)
    assert list(final.columns) == colunas.COLUNAS_FINAIS
    assert list(final['Titulo']) == ['Dois', 'Um']
    assert list(final['status']) == ['ok', 'ok']
    assert list(final['Palavras']) == ['b', 'a; c']


def test_materia_nunca_raspada_aparece_como_erro(tmp_path):
    ArquivoCSV(tmp_path / 'mat.csv', colunas.COLUNAS_MATERIAS).fechar()
    final = t.montar_final(tmp_path / 'mat.csv', [_link('7', 'x')])
    assert final.iloc[0]['status'] == 'erro' and final.iloc[0]['erro'] == 'não raspada'


def test_salvar_e_ler_final_e_formato_antigo(tmp_path):
    final = pd.DataFrame([{c: '' for c in colunas.COLUNAS_FINAIS}])
    t.salvar_final(final, tmp_path / 'f.csv')
    assert list(t.ler_final(tmp_path / 'f.csv').columns) == colunas.COLUNAS_FINAIS
    # versões antigas gravavam o índice do pandas como primeira coluna
    pd.DataFrame({'Link Materia': ['x'], 'Link Casa': ['y']}).to_csv(tmp_path / 'velho.csv')
    assert list(t.ler_final(tmp_path / 'velho.csv').columns) == ['Link Materia', 'Link Casa']


# --- Colunas da pessoa e relevantes (FR-19, FR-20) --------------------------

CASA = 'https://sapl.a.leg.br/'


def _final(*ids):
    linhas = []
    for i in ids:
        linha = {c: '' for c in colunas.COLUNAS_FINAIS}
        linha.update({'Link Casa': CASA, 'Link Materia': f'{CASA}materia/{i}', 'sapl_id': i})
        linhas.append(linha)
    return pd.DataFrame(linhas, columns=colunas.COLUNAS_FINAIS)


@pytest.mark.parametrize('valor', ['sim', 'S', ' x ', '1', 'TRUE', 'Sim '])
def test_valores_aceitos_como_relevante(valor):
    assert t.eh_relevante(valor)


@pytest.mark.parametrize('valor', ['', 'não', 'n', '0', 'false', 'talvez'])
def test_valores_nao_relevantes(valor):
    assert not t.eh_relevante(valor)


def test_colunas_extras_e_filtro():
    entrada = _final('1', '2', '3')
    entrada['Relevante'] = ['x', '', 'sim']
    entrada['Notas'] = ['a', 'b', 'c']
    assert t.colunas_extras(entrada) == ['Relevante', 'Notas']
    assert t.filtrar_relevantes(entrada)['sapl_id'].tolist() == ['1', '3']


def test_juntar_extras_pela_chave_e_na_ordem():
    entrada = _final('1', '2', '3')
    entrada['Notas'] = ['um', 'dois', 'três']
    entrada['Relevante'] = ['x', '', 'x']
    # final em outra ordem, com /ta no link da entrada e uma matéria a mais
    entrada.loc[1, 'Link Materia'] = f'{CASA}materia/2/ta'
    final = _final('3', '2', '1', '9')
    junto = t.juntar_colunas_extras(final, entrada)
    assert list(junto.columns) == colunas.COLUNAS_FINAIS + ['Notas', 'Relevante']
    assert junto['Notas'].tolist() == ['três', 'dois', 'um', '']
    assert junto['Relevante'].tolist() == ['x', '', 'x', '']


def test_sem_extras_nao_muda_nada():
    final = _final('1')
    assert t.juntar_colunas_extras(final, _final('1')) is final
