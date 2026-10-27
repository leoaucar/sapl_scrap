"""Cada camada só importa das camadas abaixo dela (FR-3, plano §3)."""
import ast
from pathlib import Path

PACOTE = Path(__file__).resolve().parent.parent / 'sapyl'

# De baixo para cima. Um módulo importa do próprio grupo e dos grupos anteriores.
CAMADAS = [
    {'registro', 'colunas'},
    {'cliente_http', 'estado'},
    {'casas', 'palavras', 'links'},
    {'busca', 'materias', 'autoria'},
    {'tabela', 'downloads'},
    {'projeto'},
    {'interface'},
]
# Até a T18, autoria.py ainda pergunta qual CSV usar (essa escolha vai para a interface)
EXCECOES = {('autoria', 'interface')}


def _grupo(modulo):
    """'sapyl.materias.api' -> 'materias'; módulos de fora do pacote -> None."""
    partes = modulo.split('.')
    if partes[0] != 'sapyl' or len(partes) < 2 or partes[1].startswith('__'):
        return None   # inclui `from sapyl import __version__`
    return partes[1]


def _nivel(grupo):
    return next(i for i, camada in enumerate(CAMADAS) if grupo in camada)


def _importados(arquivo):
    for no in ast.walk(ast.parse(arquivo.read_text(encoding='utf-8'))):
        if isinstance(no, ast.Import):
            yield from (a.name for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            if no.module == 'sapyl':
                yield from (f'sapyl.{a.name}' for a in no.names)
            else:
                yield no.module


def test_todo_modulo_esta_numa_camada():
    grupos = {p.stem for p in PACOTE.glob('*.py')} | {p.name for p in PACOTE.iterdir() if p.is_dir()}
    grupos -= {'__init__', '__main__', '__pycache__'}
    sem_camada = [g for g in grupos if not any(g in c for c in CAMADAS)]
    assert sem_camada == []


def test_nenhum_modulo_importa_de_uma_camada_acima():
    violacoes = []
    for arquivo in PACOTE.rglob('*.py'):
        relativo = arquivo.relative_to(PACOTE)
        origem = relativo.parts[0].removesuffix('.py')
        if origem in ('__init__', '__main__'):
            continue
        for modulo in _importados(arquivo):
            destino = _grupo(modulo)
            if destino is None or (origem, destino) in EXCECOES:
                continue
            if _nivel(destino) > _nivel(origem):
                violacoes.append(f'{relativo}: {modulo}')
    assert violacoes == []
