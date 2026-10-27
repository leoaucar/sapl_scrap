"""Funções e métodos públicos do pacote têm tipos e docstring (FR-5)."""

import ast
from pathlib import Path

PACOTE = Path(__file__).resolve().parent.parent / 'sapyl'


def _publicas(arvore):
    """(nome, nó) das funções de módulo e dos métodos de classes públicas."""
    for no in arvore.body:
        if isinstance(no, ast.FunctionDef) and not no.name.startswith('_'):
            yield no.name, no
        elif isinstance(no, ast.ClassDef) and not no.name.startswith('_'):
            for item in no.body:
                publico = (
                    not item.name.startswith('_') if isinstance(item, ast.FunctionDef) else False
                )
                if publico or (isinstance(item, ast.FunctionDef) and item.name == '__init__'):
                    yield f'{no.name}.{item.name}', item


def _faltas(no):
    faltas = []
    args = no.args.posonlyargs + no.args.args + no.args.kwonlyargs
    sem_tipo = [a.arg for a in args if a.annotation is None and a.arg not in ('self', 'cls')]
    if sem_tipo:
        faltas.append('sem tipo: ' + ', '.join(sem_tipo))
    if no.returns is None and no.name != '__init__':
        faltas.append('sem tipo de retorno')
    if ast.get_docstring(no) is None and no.name != '__init__':
        faltas.append('sem docstring')
    return faltas


def test_funcoes_publicas_tem_tipos_e_docstring():
    problemas = []
    for arquivo in sorted(PACOTE.rglob('*.py')):
        arvore = ast.parse(arquivo.read_text(encoding='utf-8'))
        for nome, no in _publicas(arvore):
            for falta in _faltas(no):
                problemas.append(f'{arquivo.relative_to(PACOTE)}:{no.lineno} {nome}: {falta}')
    assert problemas == [], '\n'.join(problemas)
