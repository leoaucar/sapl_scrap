"""Tabela final: ordem das colunas, tentativa mais recente, compatibilidade."""
import pandas as pd

from sapyl import materias as m
from sapyl import tabela as t
from sapyl.estado import ArquivoCSV

CV = 'https://sapl.cascavel.pr.leg.br/'


def _link(i, palavras):
    return {'chave': m.chave(CV, i), 'Link Materia': f'{CV}materia/{i}', 'Link Casa': CV,
            'Palavras': palavras, 'sapl_id': i}


def test_colunas_finais_na_ordem_esperada():
    antigas = ['Link Materia', 'Link Casa', 'Palavras', 'Titulo', 'Ementa', 'Ano', 'Data', 'Numero',
               'Observacao', 'Tipo de Materia Legislativa', 'texto_original']
    assert m.COLUNAS_FINAIS[:len(antigas)] == antigas
    assert 'Assuntos' not in m.COLUNAS_FINAIS and 'texto_integral' not in m.COLUNAS_FINAIS
    assert m.COLUNAS_FINAIS[-7:] == ['sapl_id', 'fonte', 'status', 'erro', 'raspada_em',
                                     'arquivo_pdf', 'download_status']
    for nova in ('Indexacao', 'Em Tramitacao', 'Regime Tramitacao', 'Materia Anexada',
                 'Resultado', 'Data Publicacao', 'Numero Protocolo', 'Ultima Atualizacao'):
        assert nova in m.COLUNAS_FINAIS


def test_montar_final_usa_tentativa_mais_recente_e_palavras_dos_links(tmp_path):
    links = [_link('2', 'b'), _link('1', 'a; c')]
    arquivo = ArquivoCSV(tmp_path / 'mat.csv', m.COLUNAS_MATERIAS)
    arquivo.anexar({**m.linha_vazia(links[1]), 'status': 'erro', 'erro': 'HTTP 429'})
    arquivo.anexar({**m.linha_vazia(links[0]), 'status': 'ok', 'Titulo': 'Dois'})
    arquivo.anexar({**m.linha_vazia(links[1]), 'status': 'ok', 'Titulo': 'Um', 'Palavras': 'a'})
    arquivo.fechar()
    final = t.montar_final(tmp_path / 'mat.csv', links)
    assert list(final.columns) == m.COLUNAS_FINAIS
    assert list(final['Titulo']) == ['Dois', 'Um']
    assert list(final['status']) == ['ok', 'ok']
    assert list(final['Palavras']) == ['b', 'a; c']


def test_materia_nunca_raspada_aparece_como_erro(tmp_path):
    ArquivoCSV(tmp_path / 'mat.csv', m.COLUNAS_MATERIAS).fechar()
    final = t.montar_final(tmp_path / 'mat.csv', [_link('7', 'x')])
    assert final.iloc[0]['status'] == 'erro' and final.iloc[0]['erro'] == 'não raspada'


def test_salvar_e_ler_final_e_formato_antigo(tmp_path):
    final = pd.DataFrame([{c: '' for c in m.COLUNAS_FINAIS}])
    t.salvar_final(final, tmp_path / 'f.csv')
    assert list(t.ler_final(tmp_path / 'f.csv').columns) == m.COLUNAS_FINAIS
    # versões antigas gravavam o índice do pandas como primeira coluna
    pd.DataFrame({'Link Materia': ['x'], 'Link Casa': ['y']}).to_csv(tmp_path / 'velho.csv')
    assert list(t.ler_final(tmp_path / 'velho.csv').columns) == ['Link Materia', 'Link Casa']
