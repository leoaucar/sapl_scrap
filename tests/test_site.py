"""Página do projeto em docs/ (FR-13a, TR-8)."""

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from sapyl.palavras import preparar_termos

DOCS = Path(__file__).resolve().parent.parent / 'docs'
REPOSITORIO = 'https://github.com/leoaucar/sapyl'
SECOES = ['o-que-e', 'como-funciona', 'resultado', 'instalar', 'usar', 'tempo', 'citar']
# Nomes que saíram nesta versão e não podem voltar na página
REMOVIDOS = ['autoria_e_tramit.py', 'palavras_chave_res.csv', 'sapl_scrap', 'requirements.txt']


class _Leitor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.recursos, self.links, self.titulo, self._no_titulo = set(), [], [], '', False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.add(a['id'])
        if tag == 'script' and 'src' in a:
            self.recursos.append(a['src'])
        if tag == 'link' and 'href' in a:
            self.recursos.append(a['href'])
        if tag in ('img', 'iframe', 'source'):
            self.recursos.append(a.get('src', ''))
        if tag == 'a' and 'href' in a:
            self.links.append(a['href'])
        self._no_titulo = tag == 'title'

    def handle_endtag(self, tag):
        if tag == 'title':
            self._no_titulo = False

    def handle_data(self, data):
        if self._no_titulo:
            self.titulo += data


@pytest.fixture(scope='module')
def pagina():
    texto = (DOCS / 'index.html').read_text(encoding='utf-8')
    leitor = _Leitor()
    leitor.feed(texto)
    return texto, leitor


def test_titulo_e_secoes(pagina):
    _, leitor = pagina
    assert leitor.titulo.startswith('SAPyL')
    assert [s for s in SECOES if s not in leitor.ids] == []


def test_instalacao_e_uso(pagina):
    texto, _ = pagina
    assert 'pip install .' in texto
    assert '<pre><code>sapyl</code></pre>' in texto
    assert f'git clone {REPOSITORIO}.git' in texto


def test_so_carrega_arquivos_da_propria_pasta(pagina):
    _, leitor = pagina
    assert sorted(leitor.recursos) == ['estilo.css', 'sapyl.js']
    for recurso in leitor.recursos:
        assert (DOCS / recurso).is_file()
    css = (DOCS / 'estilo.css').read_text(encoding='utf-8')
    assert not re.search(r'@import|url\(\s*["\']?https?:', css)


def test_links_para_o_repositorio_e_ancoras_validas(pagina):
    _, leitor = pagina
    assert REPOSITORIO in leitor.links
    externos = [h for h in leitor.links if h.startswith('http')]
    assert all(h.startswith(REPOSITORIO) for h in externos), externos
    ancoras = [h[1:] for h in leitor.links if h.startswith('#')]
    assert [a for a in ancoras if a not in leitor.ids] == []


def test_sem_nomes_antigos(pagina):
    texto, _ = pagina
    assert [n for n in REMOVIDOS if n in texto] == []


def test_consulta_da_pagina_igual_a_do_programa():
    node = shutil.which('node')
    if node is None:
        pytest.skip('node não instalado')
    linhas = [
        'plano diretor',
        'orçamento, emenda impositiva',
        '  professor,  conviccoes morais ',
        'saneamento básico',
        'a,,b',
        'lingua  não   binaria',
    ]
    script = (
        f'const s = require({json.dumps(str(DOCS / "sapyl.js"))});'
        f'console.log(JSON.stringify({json.dumps(linhas)}.map(s.prepararTermo)));'
    )
    saida = subprocess.run([node, '-e', script], capture_output=True, text=True, check=True)
    assert json.loads(saida.stdout) == preparar_termos(linhas)


def test_estimativa_de_tempo():
    node = shutil.which('node')
    if node is None:
        pytest.skip('node não instalado')
    script = (
        f'const s = require({json.dumps(str(DOCS / "sapyl.js"))});'
        'console.log(JSON.stringify([0, 35, 1000, 4200].map('
        '(n) => s.formatarDuracao(s.minutosParaRaspar(n)))));'
    )
    saida = subprocess.run([node, '-e', script], capture_output=True, text=True, check=True)
    assert json.loads(saida.stdout) == [
        'menos de 1 minuto',
        'cerca de 1 minuto',
        'cerca de 29 minutos',
        'cerca de 2 horas',
    ]
