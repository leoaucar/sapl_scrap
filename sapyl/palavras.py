"""Leitura e formatação das palavras-chave de busca."""

import os
import re
import zipfile
from pathlib import Path

import pandas as pd

from sapyl.padroes import EntradaInvalida

COLUNA = 'Palavras'
LEIA_O_README = (
    'O arquivo precisa de uma coluna chamada Palavras, com uma busca por linha. '
    'Veja o exemplo arquivos_csv/exemplo_palavras_chave.csv e a seção '
    '"Preparando os arquivos de entrada" do README.'
)


def importar_palavras(pasta: str | os.PathLike[str] = 'arquivos_csv') -> list[str]:
    """Lê a coluna `Palavras` de `<pasta>/palavras_chave.csv` ou, se não existir, do `.xlsx`."""
    csv = os.path.join(pasta, 'palavras_chave.csv')
    if os.path.exists(csv):
        df = pd.read_csv(csv, header=0)
    else:
        df = pd.read_excel(os.path.join(pasta, 'palavras_chave.xlsx'), header=0)
    return [str(p) for p in df[COLUNA].dropna() if str(p).strip()]


def arquivo_de_palavras(pasta: str | os.PathLike[str]) -> Path | None:
    """O arquivo de palavras usado: `palavras_chave.csv`, senão o `.xlsx`, senão None."""
    for nome in ('palavras_chave.csv', 'palavras_chave.xlsx'):
        caminho = Path(pasta) / nome
        if caminho.is_file():
            return caminho
    return None


def ler_palavras(pasta: str | os.PathLike[str] = 'arquivos_csv') -> list[str]:
    """Como `importar_palavras`, mas um arquivo ausente ou errado vira `EntradaInvalida`.

    A mensagem diz qual arquivo foi procurado, em que pasta e o formato esperado.
    """
    caminho = arquivo_de_palavras(pasta)
    if caminho is None:
        onde = Path(pasta).resolve()
        raise EntradaInvalida(
            'Não encontrei o arquivo de palavras-chave: procurei palavras_chave.csv e '
            f'palavras_chave.xlsx em {onde}. Rode o sapyl na pasta que tem a pasta '
            f'arquivos_csv/. {LEIA_O_README}'
        )
    try:
        if caminho.suffix == '.csv':
            df = pd.read_csv(caminho, header=0)
        else:
            df = pd.read_excel(caminho, header=0)
    except (OSError, ValueError, zipfile.BadZipFile, pd.errors.ParserError) as erro:
        raise EntradaInvalida(f'Não consegui ler {caminho}: {erro}. {LEIA_O_README}') from erro
    if COLUNA not in df.columns:
        colunas = ', '.join(str(c) for c in df.columns) or 'nenhuma'
        raise EntradaInvalida(
            f'O arquivo {caminho} não tem a coluna Palavras (colunas encontradas: '
            f'{colunas}). {LEIA_O_README}'
        )
    palavras = [str(p) for p in df[COLUNA].dropna() if str(p).strip()]
    if not palavras:
        raise EntradaInvalida(
            f'O arquivo {caminho} não tem nenhuma palavra-chave na coluna Palavras. {LEIA_O_README}'
        )
    return palavras


def preparar_termos(palavras: list[str]) -> list[str]:
    """Converte cada linha de palavras-chave em uma consulta para a busca do SAPL.

    Termos separados por vírgula viram expressões exatas unidas por '+':
    "lingua portuguesa, norma culta" -> '"lingua+portuguesa"+"norma+culta"'
    """
    consultas = []
    for linha in palavras:
        termos = [t.strip() for t in str(linha).split(',') if t.strip()]
        consultas.append('+'.join('"' + '+'.join(t.split()) + '"' for t in termos))
    return consultas


def descrever(consulta: str) -> str:
    """Uma consulta do SAPL em palavras: o contrário de `preparar_termos`.

    '"plano+diretor"' -> 'plano diretor';
    '"orçamento"+"emenda+impositiva"' -> 'orçamento + emenda impositiva (juntos na mesma
    matéria)'. Uma consulta sem aspas só troca '+' por espaço.
    """
    termos = re.findall(r'"([^"]*)"', consulta) or [consulta]
    termos = [' '.join(t.replace('+', ' ').split()) for t in termos]
    termos = [t for t in termos if t]
    texto = ' + '.join(termos)
    return texto + ' (juntos na mesma matéria)' if len(termos) > 1 else texto
