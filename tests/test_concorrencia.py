"""Várias threads ao mesmo tempo, de verdade (TR-2, TR-6).

Arquivos compartilhados: nenhuma linha perdida, cortada, juntada ou repetida.
"""

import json
import threading

from sapyl.colunas import CAMPOS_ESTADO
from sapyl.estado import ArquivoCSV, Cache, Estado, ler_csv

THREADS = 16
POR_THREAD = 200


def _em_threads(funcao, n=THREADS):
    """Roda `funcao(i)` em `n` threads que começam juntas; repassa o primeiro erro."""
    largada = threading.Barrier(n)
    erros = []

    def rodar(i):
        try:
            largada.wait()
            funcao(i)
        except BaseException as erro:  # noqa: BLE001 - o teste mostra qualquer erro
            erros.append(erro)

    threads = [threading.Thread(target=rodar, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert erros == []


def test_arquivo_csv_compartilhado(tmp_path):
    caminho = tmp_path / 'm.csv'
    arquivo = ArquivoCSV(caminho, ['chave', 'texto'])
    texto = 'x' * 5000 + ', "aspas" e\nquebra de linha'

    def gravar(i):
        for j in range(POR_THREAD):
            arquivo.anexar({'chave': f'{i}/{j}', 'texto': texto})

    _em_threads(gravar)
    arquivo.fechar()
    linhas = ler_csv(caminho, ['chave', 'texto'])
    assert len(linhas) == THREADS * POR_THREAD
    assert {linha['chave'] for linha in linhas} == {
        f'{i}/{j}' for i in range(THREADS) for j in range(POR_THREAD)
    }
    assert all(linha['texto'] == texto for linha in linhas)


def test_estado_compartilhado(tmp_path):
    estado = Estado(tmp_path / 'e.csv')

    def registrar(i):
        for j in range(POR_THREAD):
            estado.registrar('materia', f'sapl.{i}.leg.br/{j}', 'ok' if j % 2 else 'erro', 'x')
            estado.contagens('materia')

    _em_threads(registrar)
    total = THREADS * POR_THREAD
    assert estado.contagens('materia') == {'ok': total // 2, 'erro': total // 2}
    estado.fechar()
    assert len(ler_csv(tmp_path / 'e.csv', CAMPOS_ESTADO)) == total
    relido = Estado(tmp_path / 'e.csv')
    assert sum(relido.contagens('materia').values()) == total
    relido.fechar()


def test_cache_compartilhado(tmp_path):
    cache = Cache(tmp_path / 'cache.json')

    def guardar(i):
        for j in range(50):
            cache.guardar_nome(f'https://sapl.{i}.leg.br/api/x/{j}/', f'nome {i} {j}')
        cache.guardar_fonte(f'sapl.{i}.leg.br', 'api' if i % 2 else 'html')

    _em_threads(guardar)
    dados = json.loads((tmp_path / 'cache.json').read_text(encoding='utf-8'))
    assert len(dados['nomes']) == THREADS * 50
    assert len(dados['fontes']) == THREADS
    assert Cache(tmp_path / 'cache.json').fontes() == cache.fontes()
