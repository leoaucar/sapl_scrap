"""Nenhum módulo acessa a rede por fora do cliente HTTP (FR-1)."""
from pathlib import Path
import re

RAIZ = Path(__file__).resolve().parent.parent
PROIBIDO = re.compile(r'\brequests\.(get|post|head|request|Session)\s*\(')


def test_so_http_sapl_usa_requests_diretamente():
    usos = []
    for arquivo in RAIZ.rglob('*.py'):
        partes = arquivo.relative_to(RAIZ).parts
        if partes[0] in ('tests', '.venv') or arquivo.name == 'http_sapl.py':
            continue
        for n, linha in enumerate(arquivo.read_text(encoding='utf-8').splitlines(), start=1):
            if PROIBIDO.search(linha):
                usos.append(f'{arquivo.relative_to(RAIZ)}:{n}')
    assert usos == []
