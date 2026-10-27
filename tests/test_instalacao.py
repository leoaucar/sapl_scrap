"""Comando `sapyl`, `python -m sapyl` e o atalho `programa.py` (FR-2, TR-5)."""
import subprocess
import sys
from pathlib import Path

from sapyl import __version__
from sapyl.interface.principal import executar

RAIZ = Path(__file__).resolve().parent.parent


def test_executar_version(capsys):
    assert executar(['--version']) == 0
    assert capsys.readouterr().out.strip() == f'sapyl {__version__}'


def test_executar_argumento_desconhecido_mostra_o_uso(capsys):
    assert executar(['--qualquer']) == 2
    assert 'Uso: sapyl' in capsys.readouterr().out


def _rodar(*comando):
    # processo separado: não herda o bloqueio de rede do conftest, mas
    # `--version` sai antes de qualquer pergunta ou requisição
    return subprocess.run([sys.executable, *comando, '--version'], cwd=RAIZ,
                          capture_output=True, text=True, timeout=60)


def test_python_m_sapyl_version():
    resultado = _rodar('-m', 'sapyl')
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == f'sapyl {__version__}'


def test_programa_py_version():
    resultado = _rodar('programa.py')
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == f'sapyl {__version__}'
