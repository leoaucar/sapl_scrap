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
            if j % 20 == 0:
                estado.contagens('materia')  # leitura enquanto as outras gravam

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


# --- Limites com threads de verdade (TR-2) -----------------------------------

JANELA, MARGEM = 0.2, 0.02
LIMITE_SITE, TETO = 4, 6


def _pico(tempos):
    tempos = sorted(tempos)
    return max(sum(1 for u in tempos[i:] if u - t < JANELA + MARGEM) for i, t in enumerate(tempos))


def test_limites_com_threads_de_verdade():
    """12 threads, 6 sites: 4 deles num servidor só, 2 sem servidor. Relógio de verdade."""
    import time

    from sapyl.cliente_http import ClienteSAPL
    from tests.apoio import RespostaFalsa, SessaoFalsa

    sites = [f'https://sapl.c{i}.leg.br/' for i in range(6)]
    no_servidor = {f'sapl.c{i}.leg.br' for i in range(4)}
    sessao = SessaoFalsa()

    def responder(url):
        time.sleep(0.002)  # a resposta demora um pouco
        return RespostaFalsa(200, 'ok')

    sessao.rota(responder)
    reservas, trava = [], threading.Lock()

    def anotar(host, servidor, horario):
        with trava:
            reservas.append((host, servidor, horario))

    cliente = ClienteSAPL(
        sessao=sessao,
        limite_por_minuto=LIMITE_SITE,
        janela_segundos=JANELA,
        margem_segundos=MARGEM,
        servidor_de=lambda host: 'srv' if host in no_servidor else None,
        limite_por_servidor=TETO,
        ao_reservar=anotar,
    )

    def trabalhar(i):
        for _ in range(5):
            assert cliente.get(sites[i % 6]).ok

    _em_threads(trabalhar, n=12)
    assert len(reservas) == 60 == len(sessao.pedidos)
    for host in {h for h, _, _ in reservas}:
        assert _pico([t for h, _, t in reservas if h == host]) <= LIMITE_SITE, host
    tempos_servidor = [t for _, s, t in reservas if s == 'srv']
    assert len(tempos_servidor) == 40
    assert _pico(tempos_servidor) == TETO  # atingido, nunca passado
    # um site sem servidor só tem o próprio limite, e chegou a ele
    assert _pico([t for h, _, t in reservas if h == 'sapl.c4.leg.br']) == LIMITE_SITE


def test_ctrl_c_com_threads_esperando_na_janela():
    """Com o evento ligado, as threads que esperam vaga param na hora."""
    import time

    from sapyl.cliente_http import ClienteSAPL, Interrompido
    from tests.apoio import RespostaFalsa, SessaoFalsa

    sessao = SessaoFalsa().rota(lambda url: RespostaFalsa(200, 'ok'))
    cliente = ClienteSAPL(sessao=sessao, limite_por_minuto=1)  # janela de 61 s de verdade
    paradas = []

    def trabalhar(i):
        try:
            for _ in range(3):
                cliente.get('https://sapl.a.leg.br/')
        except Interrompido:
            paradas.append(i)

    threads = [threading.Thread(target=trabalhar, args=(i,)) for i in range(6)]
    inicio = time.monotonic()
    for t in threads:
        t.start()
    time.sleep(0.1)
    cliente.parar.set()
    for t in threads:
        t.join(timeout=5)
    assert time.monotonic() - inicio < 2
    assert sorted(paradas) == list(range(6)) and len(sessao.pedidos) == 1
