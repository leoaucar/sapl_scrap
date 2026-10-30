"""O repositório só guarda código, documentação, fixtures e exemplos (FR-8 a FR-10a)."""

import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from sapyl.casas import importar_casas
from sapyl.interface import principal
from sapyl.interface.perguntas import PerguntasTexto
from sapyl.palavras import importar_palavras, preparar_termos
from tests.apoio import roteiro

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / 'arquivos_csv' / 'exemplo_palavras_chave.csv'
EDUCACAO = RAIZ / 'arquivos_csv' / 'exemplo_palavras_chave_educacao.csv'

# Arquivos gerados pelo programa ou dados de pesquisa: nunca no git
PROIBIDOS = [
    'arquivos_csv/casas_resultado.csv',
    'arquivos_csv/palavras_chave_res.csv',
    'arquivos_csv/teste_raspagem.csv',
    'autoria_e_tramitacao/tabela_limpa_2.csv',
    '.sapl_historico.json',
]


def _ler(caminho, pasta):
    """Lê um exemplo como o programa lê, copiando-o para `palavras_chave.csv`."""
    shutil.copy(caminho, pasta / 'palavras_chave.csv')
    return importar_palavras(pasta)


@pytest.mark.parametrize('arquivo', [EXEMPLO, EDUCACAO], ids=['neutro', 'educacao'])
def test_exemplos_limpos(arquivo):
    bruto = arquivo.read_bytes()
    assert not bruto.startswith(b'\xef\xbb\xbf')  # sem BOM
    texto = bruto.decode('utf-8')
    assert texto.splitlines()[0] == 'Palavras'
    assert '  ' not in texto
    assert list(pd.read_csv(arquivo).columns) == ['Palavras']


def test_exemplo_neutro_vira_as_consultas_do_readme(tmp_path):
    assert preparar_termos(_ler(EXEMPLO, tmp_path)) == [
        '"orçamento"',
        '"plano+diretor"',
        '"lei+orgânica"',
        '"orçamento"+"emenda+impositiva"',
        '"saneamento+básico"',
        '"saneamento+basico"',
    ]


def test_exemplo_educacao_tem_23_consultas_com_a_grafia_corrigida(tmp_path):
    termos = preparar_termos(_ler(EDUCACAO, tmp_path))
    assert len(termos) == 23
    assert '"aparelhamento+ideologico"' in termos
    assert not any('aparellhamento' in t for t in termos)
    assert '"professor"+"conviccoes+morais"' in termos


def _arquivos_no_git():
    if shutil.which('git') is None:
        pytest.skip('git não instalado')
    resultado = subprocess.run(
        ['git', 'ls-files'], cwd=RAIZ, capture_output=True, text=True, check=False
    )
    if resultado.returncode != 0:
        pytest.skip('fora de um repositório git')
    return set(resultado.stdout.splitlines())


def test_git_nao_guarda_dados_gerados_nem_de_pesquisa():
    arquivos = _arquivos_no_git()
    assert [p for p in PROIBIDOS if p in arquivos] == []
    assert not [p for p in arquivos if p.split('/')[0].endswith('_proj')]
    assert {'arquivos_csv/casas_legislativas.xlsx', 'arquivos_csv/palavras_chave.xlsx'} <= arquivos


def test_sem_tabela_geral_nao_oferece_reaproveitar(projeto_tmp):
    # clone novo: não existe arquivos_csv/casas_resultado.csv
    assert not (projeto_tmp / 'arquivos_csv' / 'casas_resultado.csv').exists()
    ler = roteiro('', '1', 'n')  # todos os estados, todas as casas, sem downloads
    planilha = importar_casas(projeto_tmp / 'arquivos_csv' / 'casas_legislativas.xlsx')
    respostas = principal.perguntar_configuracao(projeto_tmp, PerguntasTexto(ler), planilha)
    assert len(ler.perguntas) == 3 and 'Lista de casas' not in ler.perguntas[0]
    assert respostas.reusar_tabela is False and respostas.casas == 3
