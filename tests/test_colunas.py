"""Listas de colunas e etapas definidas num lugar só, sapyl/colunas.py (FR-4)."""

import ast
from pathlib import Path

from sapyl import colunas

PACOTE = Path(__file__).resolve().parent.parent / 'sapyl'
MARCAS = {'Link Materia', 'etapa'}


def _listas_com_marca(arvore):
    for no in ast.walk(arvore):
        if isinstance(no, (ast.List, ast.Tuple, ast.Set)):
            valores = {e.value for e in no.elts if isinstance(e, ast.Constant)}
            if valores & MARCAS:
                yield no.lineno


def test_nenhum_outro_modulo_define_lista_de_colunas_ou_etapas():
    achados = []
    for arquivo in PACOTE.rglob('*.py'):
        if arquivo.name == 'colunas.py':
            continue
        arvore = ast.parse(arquivo.read_text(encoding='utf-8'))
        achados += [f'{arquivo.relative_to(PACOTE)}:{n}' for n in _listas_com_marca(arvore)]
    assert achados == []


def test_a_marca_e_encontrada_em_colunas():
    arvore = ast.parse((PACOTE / 'colunas.py').read_text(encoding='utf-8'))
    assert list(_listas_com_marca(arvore))


def test_listas_derivadas_continuam_iguais_as_da_fase1():
    assert colunas.COLUNAS_FINAIS[:3] == ['Link Materia', 'Link Casa', 'Palavras']
    assert colunas.COLUNAS_MATERIAS == ['chave'] + colunas.COLUNAS_FINAIS
    assert colunas.COLUNAS_LINKS == ['chave', 'Link Materia', 'Link Casa', 'Palavras', 'sapl_id']
    assert colunas.ETAPAS == ('busca', 'materia', 'pdf')
