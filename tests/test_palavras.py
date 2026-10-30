"""Palavras-chave: leitura com mensagens claras e descrição em palavras (FR-12, FR-13)."""

import pandas as pd
import pytest

from sapyl.padroes import EntradaInvalida
from sapyl.palavras import descrever, ler_palavras, preparar_termos


def test_ler_palavras_do_xlsx(projeto_tmp):
    assert ler_palavras(projeto_tmp / 'arquivos_csv') == [
        'plano diretor',
        'orçamento, emenda impositiva',
    ]


def test_csv_tem_prioridade(projeto_tmp):
    pasta = projeto_tmp / 'arquivos_csv'
    pd.DataFrame({'Palavras': ['saneamento']}).to_csv(pasta / 'palavras_chave.csv', index=False)
    assert ler_palavras(pasta) == ['saneamento']


def test_sem_arquivo_diz_onde_procurou(tmp_path):
    with pytest.raises(EntradaInvalida) as erro:
        ler_palavras(tmp_path / 'arquivos_csv')
    texto = str(erro.value)
    assert 'palavras_chave.csv' in texto and 'palavras_chave.xlsx' in texto
    assert str((tmp_path / 'arquivos_csv').resolve()) in texto
    assert 'coluna chamada Palavras' in texto and 'exemplo_palavras_chave.csv' in texto


def test_sem_a_coluna_palavras(tmp_path):
    pd.DataFrame({'Termos': ['x']}).to_csv(tmp_path / 'palavras_chave.csv', index=False)
    with pytest.raises(EntradaInvalida, match='não tem a coluna Palavras.*Termos'):
        ler_palavras(tmp_path)


def test_sem_nenhuma_palavra(tmp_path):
    pd.DataFrame({'Palavras': ['', None, '  ']}).to_csv(
        tmp_path / 'palavras_chave.csv', index=False
    )
    with pytest.raises(EntradaInvalida, match='nenhuma palavra-chave'):
        ler_palavras(tmp_path)


def test_xlsx_ilegivel(tmp_path):
    (tmp_path / 'palavras_chave.xlsx').write_text('não é uma planilha')
    with pytest.raises(EntradaInvalida, match='Não consegui ler'):
        ler_palavras(tmp_path)


@pytest.mark.parametrize(
    'linha,texto',
    [
        ('orçamento', 'orçamento'),
        ('plano diretor', 'plano diretor'),
        (
            'orçamento, emenda impositiva',
            'orçamento + emenda impositiva (juntos na mesma matéria)',
        ),
        (
            'lingua portuguesa, norma culta',
            'lingua portuguesa + norma culta (juntos na mesma matéria)',
        ),
    ],
)
def test_descrever_desfaz_preparar_termos(linha, texto):
    assert descrever(preparar_termos([linha])[0]) == texto


def test_descrever_consulta_sem_aspas():
    assert descrever('plano+diretor') == 'plano diretor'
