"""Cliente HTTP: limite por site, retentativas e motivos de falha."""

import logging
import re

import pytest
import requests

from sapyl import cliente_http as http_sapl
from sapyl.cliente_http import ClienteSAPL, ler_retry_after

A = 'https://sapl.a.leg.br/'
B = 'https://sapl.b.leg.br/'


@pytest.fixture
def cliente(sessao, relogio):
    return ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)


# --- Limite por site (FR-2) -------------------------------------------------


def test_35_requisicoes_passam_sem_esperar(cliente, sessao, relogio):
    sessao.responder(A, texto='ok')
    for _ in range(35):
        assert cliente.get(A).ok
    assert relogio.esperas == []


def test_36a_requisicao_espera_a_janela_liberar(cliente, sessao, relogio):
    sessao.responder(A, texto='ok')
    inicio = relogio.agora()
    for _ in range(35):
        cliente.get(A)
        relogio.t += 1  # uma requisição por segundo
    cliente.get(A)
    # a mais antiga foi em `inicio`; a 36ª só sai 61 s depois dela (60 s + margem, V4)
    assert relogio.agora() == pytest.approx(inicio + 61, abs=0.05)
    assert sum(relogio.esperas) == pytest.approx(26, abs=0.05)


def test_nunca_mais_de_35_em_60_segundos(cliente, sessao, relogio):
    sessao.responder(A, texto='ok')
    horarios = []
    for _ in range(200):
        cliente.get(A)
        horarios.append(relogio.agora())
        relogio.t += 0.1
    for i, t in enumerate(horarios):
        na_janela = [h for h in horarios[i:] if h - t < 60]
        assert len(na_janela) <= 35


def test_sites_diferentes_nao_se_afetam(cliente, sessao, relogio):
    sessao.responder(A, texto='a').responder(B, texto='b')
    for _ in range(35):
        cliente.get(A)
    for _ in range(35):
        cliente.get(B)
    assert relogio.esperas == []


def test_limite_configuravel(sessao, relogio):
    cliente = ClienteSAPL(
        sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir, limite_por_minuto=2
    )
    sessao.responder(A, texto='ok')
    cliente.get(A)
    cliente.get(A)
    assert relogio.esperas == []
    cliente.get(A)
    assert relogio.esperas == [61]  # janela de 60 s + margem (V4)


def test_timeout_padrao_e_stream_repassados(cliente, sessao):
    sessao.responder(A, texto='ok')
    cliente.get(A)
    cliente.get(A, stream=True, timeout=(1, 2))
    assert sessao.chamadas[0][1] == {'timeout': http_sapl.TIMEOUT_PADRAO, 'stream': False}
    assert sessao.chamadas[1][1] == {'timeout': (1, 2), 'stream': True}


# --- 429 e Retry-After (FR-3) -----------------------------------------------


def test_429_espera_retry_after_e_tenta_de_novo(cliente, sessao, relogio):
    sessao.responder(A, status=429, headers={'Retry-After': '30'}).responder(A, texto='ok')
    inicio = relogio.agora()
    r = cliente.get(A)
    assert r.ok and r.tentativas == 2
    assert relogio.agora() - inicio == pytest.approx(30, abs=0.05)


def test_429_sem_cabecalho_espera_60(cliente, sessao, relogio):
    sessao.responder(A, status=429).responder(A, texto='ok')
    inicio = relogio.agora()
    assert cliente.get(A).ok
    assert relogio.agora() - inicio == pytest.approx(60, abs=0.05)


def test_retry_after_limitado_e_em_data():
    assert ler_retry_after('9999') == http_sapl.RETRY_AFTER_MAXIMO
    assert ler_retry_after('0') == 1
    assert ler_retry_after('lixo') == http_sapl.RETRY_AFTER_PADRAO
    assert ler_retry_after(
        'Sat, 24 Oct 2026 12:00:45 GMT', agora_epoch=1792843200.0
    ) == pytest.approx(45)


def test_429_bloqueia_o_site_inteiro(cliente, sessao, relogio):
    url1, url2 = A + 'materia/1', A + 'materia/2'
    sessao.responder(url1, status=429, headers={'Retry-After': '40'})
    sessao.responder(url2, texto='ok')
    r = cliente.get(url1, max_tentativas=1)
    assert not r.ok and r.erro == 'HTTP 429'
    # com 1 tentativa não há espera nem bloqueio: a falha volta na hora
    assert relogio.esperas == []

    sessao.responder(url1, status=429, headers={'Retry-After': '40'})
    cliente2 = ClienteSAPL(
        sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir, max_tentativas=2
    )
    inicio = relogio.agora()
    cliente2.get(url1)  # 429, bloqueia, tenta de novo após 40 s
    assert relogio.agora() - inicio == pytest.approx(40, abs=0.05)
    cliente2._bloqueado_ate['sapl.a.leg.br'] = relogio.agora() + 10
    cliente2.get(url2)  # outra URL do mesmo site também espera
    assert relogio.agora() - inicio == pytest.approx(50, abs=0.05)


# --- Erros de rede e 5xx (FR-4, FR-5) ---------------------------------------


@pytest.mark.parametrize(
    'erro, motivo',
    [
        (requests.Timeout(), 'timeout'),
        (requests.ConnectTimeout(), 'timeout'),
        (requests.ConnectionError(), 'conexao'),
    ],
)
def test_erro_de_rede_tenta_com_esperas_crescentes(cliente, sessao, relogio, erro, motivo):
    sessao.responder(A, erro=erro)
    r = cliente.get(A)
    assert not r.ok
    assert r.erro == motivo and r.status is None
    assert r.tentativas == 4 and len(sessao.pedidos) == 4
    assert relogio.esperas == [5, 15, 45]


def test_5xx_tenta_de_novo_e_desiste_com_motivo(cliente, sessao, relogio):
    sessao.responder(A, status=503)
    r = cliente.get(A)
    assert (r.ok, r.status, r.erro, r.tentativas) == (False, 503, 'HTTP 503', 4)
    assert relogio.esperas == [5, 15, 45]


def test_5xx_depois_sucesso(cliente, sessao, relogio):
    sessao.responder(A, status=500).responder(A, status=502).responder(A, texto='ok')
    r = cliente.get(A)
    assert r.ok and r.texto == 'ok' and r.tentativas == 3
    assert relogio.esperas == [5, 15]


def test_429_insistente_desiste(cliente, sessao, relogio):
    sessao.responder(A, status=429, headers={'Retry-After': '60'})
    r = cliente.get(A)
    assert (r.ok, r.erro, len(sessao.pedidos)) == (False, 'HTTP 429', 4)


@pytest.mark.parametrize('status', [404, 403, 400])
def test_4xx_nao_tenta_de_novo(cliente, sessao, relogio, status):
    sessao.responder(A, status=status)
    r = cliente.get(A)
    assert (r.ok, r.status, r.erro, r.tentativas) == (False, status, f'HTTP {status}', 1)
    assert len(sessao.pedidos) == 1 and relogio.esperas == []


def test_retentativas_contam_no_limite(sessao, relogio):
    cliente = ClienteSAPL(
        sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir, limite_por_minuto=3
    )
    sessao.responder(A, status=500).responder(A, status=500).responder(A, texto='ok')
    cliente.get(A)  # 3 requisições (2 retentativas)
    assert len(cliente._janelas['sapl.a.leg.br']) == 3


def test_max_tentativas_por_chamada(cliente, sessao, relogio):
    sessao.responder(A, erro=requests.Timeout())
    r = cliente.get(A, max_tentativas=2)
    assert r.tentativas == 2 and relogio.esperas == [5]


def test_falha_fecha_respostas_intermediarias(cliente, sessao):
    sessao.responder(A, status=503)
    cliente.get(A, max_tentativas=2)
    assert sessao.get(A).fechada


# --- Log de cada tentativa (FR-25a) -----------------------------------------


def test_uma_linha_de_log_por_tentativa(cliente, sessao, caplog):
    sessao.responder(A, status=503).responder(A, texto='ok')
    with caplog.at_level(logging.DEBUG, logger='sapyl.http'):
        cliente.get(A)
    linhas = [r.getMessage() for r in caplog.records if r.name == 'sapyl.http']
    assert [lin.split(' | enviada ')[0] for lin in linhas] == [
        f'sapl.a.leg.br | {A} | 503 | tentativa 1 | espera 5',
        f'sapl.a.leg.br | {A} | 200 | tentativa 2 | espera 0',
    ]
    # hora de envio com milissegundos, para conferir o limite pelo log
    assert all(re.search(r' \| enviada \d\d:\d\d:\d\d\.\d{3}$', lin) for lin in linhas)


def test_log_de_erro_de_rede_e_aviso_final(cliente, sessao, caplog):
    sessao.responder(A, erro=requests.Timeout())
    with caplog.at_level(logging.DEBUG, logger='sapyl.http'):
        cliente.get(A, max_tentativas=1)
    mensagens = [r.getMessage() for r in caplog.records]
    assert any(
        m.startswith(f'sapl.a.leg.br | {A} | timeout | tentativa 1 | espera 0 | enviada ')
        for m in mensagens
    )
    assert any('Falha em' in m and 'timeout' in m for m in mensagens)


def test_resposta_json_e_texto(cliente, sessao):
    sessao.responder(A, json_dados={'id': 1})
    r = cliente.get(A)
    assert r.json() == {'id': 1} and r.texto == '{"id": 1}'
    falha = http_sapl.Resposta(A, False)
    assert falha.texto == ''
    falha.fechar()


def test_sessao_padrao_tem_user_agent():
    agente = http_sapl.criar_sessao().headers['User-Agent']
    assert agente.startswith('SAPyL/0.2.0 ') and 'github.com/leoaucar/sapyl' in agente


# --- Limite entre execuções (achado V2 da validação) ------------------------


def _cliente_com_historico(sessao, relogio, caminho, **kw):
    return ClienteSAPL(
        sessao=sessao,
        relogio=relogio.agora,
        dormir=relogio.dormir,
        historico=str(caminho),
        relogio_parede=relogio.agora,
        **kw,
    )


def test_nova_execucao_respeita_requisicoes_da_anterior(sessao, relogio, tmp_path):
    sessao.responder(A, texto='ok')
    primeira = _cliente_com_historico(sessao, relogio, tmp_path / 'h.json')
    inicio = relogio.agora()
    for _ in range(35):
        primeira.get(A)
        relogio.t += 0.5
    # programa interrompido e retomado: um cliente novo, com janela vazia na memória
    segunda = _cliente_com_historico(sessao, relogio, tmp_path / 'h.json')
    segunda.get(A)
    assert relogio.agora() >= inicio + 61 - 0.05


def test_historico_antigo_e_ignorado(sessao, relogio, tmp_path):
    sessao.responder(A, texto='ok')
    primeira = _cliente_com_historico(sessao, relogio, tmp_path / 'h.json')
    for _ in range(35):
        primeira.get(A)
    relogio.t += 61
    segunda = _cliente_com_historico(sessao, relogio, tmp_path / 'h.json')
    esperas_antes = len(relogio.esperas)
    for _ in range(35):
        segunda.get(A)
    assert len(relogio.esperas) == esperas_antes


def test_bloqueio_de_429_passa_para_a_proxima_execucao(sessao, relogio, tmp_path):
    sessao.responder(A, status=429, headers={'Retry-After': '40'})

    def interromper(segundos):
        raise KeyboardInterrupt

    primeira = ClienteSAPL(
        sessao=sessao,
        relogio=relogio.agora,
        dormir=interromper,
        historico=str(tmp_path / 'h.json'),
        relogio_parede=relogio.agora,
    )
    with pytest.raises(KeyboardInterrupt):
        primeira.get(A)  # Ctrl+C durante a espera do Retry-After
    sessao.limpar(A).responder(A, texto='ok')
    inicio = relogio.agora()
    _cliente_com_historico(sessao, relogio, tmp_path / 'h.json').get(A)
    assert relogio.agora() - inicio == pytest.approx(40, abs=0.05)


def test_historico_ilegivel_nao_impede_execucao(sessao, relogio, tmp_path, caplog):
    (tmp_path / 'h.json').write_text('{quebrado', encoding='utf-8')
    sessao.responder(A, texto='ok')
    with caplog.at_level(logging.WARNING):
        assert _cliente_com_historico(sessao, relogio, tmp_path / 'h.json').get(A).ok
    assert any('ilegível' in r.getMessage() for r in caplog.records)
    assert 'requisicoes' in (tmp_path / 'h.json').read_text(encoding='utf-8')


def test_historico_guarda_no_maximo_o_limite_por_site(sessao, relogio, tmp_path):
    import json

    sessao.responder(A, texto='ok')
    cliente = _cliente_com_historico(sessao, relogio, tmp_path / 'h.json')
    for _ in range(80):
        cliente.get(A)
    dados = json.loads((tmp_path / 'h.json').read_text(encoding='utf-8'))
    assert len(dados['requisicoes']['sapl.a.leg.br']) <= 35
    assert not (tmp_path / 'h.json.tmp').exists()


# --- Erros permanentes: SSL e DNS (FR-24) -----------------------------------


def _erro_dns(com_resolucao=True):
    """O erro que o requests lança para um nome que não existe (veja a cadeia real)."""
    import socket

    from urllib3.exceptions import MaxRetryError, NameResolutionError

    origem = socket.gaierror(-2, 'Name or service not known')
    if not com_resolucao:
        erro = requests.ConnectionError('falha ao conectar')
        erro.__cause__ = origem
        return erro
    motivo = NameResolutionError('sapl.x.leg.br', None, origem)
    return requests.ConnectionError(MaxRetryError(None, A, reason=motivo))


@pytest.mark.parametrize(
    'erro, motivo',
    [
        (requests.exceptions.SSLError('certificate verify failed'), 'ssl'),
        (_erro_dns(), 'dns'),
        (_erro_dns(com_resolucao=False), 'dns'),
    ],
    ids=['ssl', 'dns-urllib3', 'dns-gaierror'],
)
def test_erro_permanente_volta_numa_tentativa(cliente, sessao, relogio, erro, motivo, caplog):
    sessao.responder(A, erro=erro)
    with caplog.at_level(logging.DEBUG, logger='sapyl.http'):
        r = cliente.get(A)
    assert (r.ok, r.status, r.erro, r.tentativas) == (False, None, motivo, 1)
    assert len(sessao.pedidos) == 1 and relogio.esperas == []
    assert any('sem nova tentativa' in m.getMessage() for m in caplog.records)


def test_outros_erros_de_conexao_continuam_com_retentativas(cliente, sessao, relogio):
    erro = requests.ConnectionError('conexão recusada')
    erro.__cause__ = ConnectionRefusedError(111, 'Connection refused')
    sessao.responder(A, erro=erro)
    r = cliente.get(A)
    assert (r.erro, r.tentativas) == ('conexao', 4)
    assert relogio.esperas == [5, 15, 45]


def test_motivo_permanente_nao_se_perde_em_ciclos():
    erro = requests.ConnectionError('a')
    outro = requests.ConnectionError(erro)
    erro.__context__ = outro  # ciclo
    assert http_sapl.motivo_permanente(erro) == ''


# --- Margem na janela (achado V4, FR-29) -------------------------------------


def test_requisicoes_1_e_36_saem_a_pelo_menos_61_segundos(cliente, sessao, relogio):
    sessao.responder(A, texto='ok')
    horarios = []
    for _ in range(80):  # rajada: o limitador decide quando cada uma sai
        cliente.get(A)
        horarios.append(relogio.agora())
    for i in range(len(horarios) - 35):
        assert horarios[i + 35] - horarios[i] >= 61 - 1e-9
    assert http_sapl.MARGEM_SEGUNDOS == 1.0


# --- Pronto para threads (plano §4, T03) -------------------------------------


def test_parar_durante_a_espera_lanca_interrompido_na_hora(sessao):
    import threading
    import time

    sessao.responder(A, texto='ok')
    cliente = http_sapl.ClienteSAPL(sessao=sessao, limite_por_minuto=1)
    cliente.get(A)  # a próxima espera ~61 s, com o relógio de verdade
    resultado = []

    def segunda():
        try:
            cliente.get(A)
        except http_sapl.Interrompido as erro:
            resultado.append(erro)

    thread = threading.Thread(target=segunda)
    inicio = time.monotonic()
    thread.start()
    time.sleep(0.05)
    cliente.parar.set()
    thread.join(timeout=5)
    assert not thread.is_alive() and time.monotonic() - inicio < 2
    assert len(resultado) == 1 and isinstance(resultado[0], KeyboardInterrupt)
    assert len(sessao.pedidos) == 1


def test_parado_nao_faz_requisicao(cliente, sessao):
    sessao.responder(A, texto='ok')
    cliente.parar.set()
    with pytest.raises(http_sapl.Interrompido):
        cliente.get(A)
    assert sessao.pedidos == []


def test_parar_depois_da_espera_de_erro(sessao, relogio):
    import requests

    cliente = ClienteSAPL(
        sessao=sessao, relogio=relogio.agora, dormir=lambda s: cliente.parar.set()
    )
    sessao.responder(A, erro=requests.ConnectionError('caiu'))
    with pytest.raises(http_sapl.Interrompido):
        cliente.get(A)
    assert len(sessao.pedidos) == 1


def test_evento_parar_compartilhado():
    import threading

    evento = threading.Event()
    assert http_sapl.ClienteSAPL(sessao=object(), parar=evento).parar is evento


def test_uma_sessao_por_thread_sem_sessao_dada():
    import threading

    cliente = http_sapl.ClienteSAPL()
    sessoes = []
    threads = [threading.Thread(target=lambda: sessoes.append(cliente.sessao)) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len({id(s) for s in sessoes}) == 3
    assert cliente.sessao is cliente.sessao  # a mesma na mesma thread
    assert cliente.sessao.headers['User-Agent'] == http_sapl.USER_AGENT


def test_sessao_dada_vale_para_todas_as_threads(cliente, sessao):
    import threading

    vistas = []
    thread = threading.Thread(target=lambda: vistas.append(cliente.sessao))
    thread.start()
    thread.join()
    assert vistas == [sessao] and cliente.sessao is sessao


def test_janela_e_margem_configuraveis_e_ao_reservar(sessao, relogio):
    reservas = []
    cliente = ClienteSAPL(
        sessao=sessao,
        relogio=relogio.agora,
        dormir=relogio.dormir,
        limite_por_minuto=2,
        janela_segundos=0.2,
        margem_segundos=0.05,
        ao_reservar=lambda h, s, t: reservas.append((h, s, t)),
    )
    sessao.responder(A, texto='ok')
    for _ in range(3):
        cliente.get(A)
    assert [t for _, _, t in reservas] == [1000.0, 1000.0, pytest.approx(1000.25)]
    assert {h for h, _, _ in reservas} == {'sapl.a.leg.br'}
    assert cliente.total_requisicoes == 3


# --- Limite por servidor (FR-6, FR-7, TR-1) ----------------------------------

C = 'https://sapl.c.leg.br/'
SEM_DNS = 'https://sapl.sumiu.leg.br/'


def _servidor_de(host):
    return None if 'sumiu' in host else '10.0.0.1'


def _cliente_servidor(sessao, relogio, teto=70, **kw):
    reservas = []
    cliente = ClienteSAPL(
        sessao=sessao,
        relogio=relogio.agora,
        dormir=relogio.dormir,
        servidor_de=_servidor_de,
        limite_por_servidor=teto,
        ao_reservar=lambda h, s, t: reservas.append((h, s, t)),
        **kw,
    )
    return cliente, reservas


def test_teto_do_servidor_soma_os_sites(sessao, relogio):
    for url in (A, B, C):
        sessao.responder(url, texto='ok')
    cliente, reservas = _cliente_servidor(sessao, relogio)
    inicio = relogio.agora()
    for _ in range(23):
        for url in (A, B, C):
            cliente.get(url)
    cliente.get(A)  # 70ª: ainda cabe (A tem 24 de 35)
    assert relogio.agora() == inicio
    cliente.get(B)  # 71ª no servidor: espera, embora o site B tenha vaga
    assert relogio.agora() == pytest.approx(inicio + 61)
    assert {s for _, s, _ in reservas} == {'10.0.0.1'}


def test_vale_o_mais_estrito_dos_dois(sessao, relogio):
    sessao.responder(A, texto='ok')
    cliente, _ = _cliente_servidor(sessao, relogio, teto=200)
    for _ in range(35):
        cliente.get(A)
    inicio = relogio.agora()
    cliente.get(A)  # o servidor tem vaga, o site não
    assert relogio.agora() == pytest.approx(inicio + 61)


def test_site_sem_servidor_so_tem_o_limite_do_site(sessao, relogio):
    sessao.responder(A, texto='ok').responder(SEM_DNS, texto='ok')
    cliente, reservas = _cliente_servidor(sessao, relogio, teto=35)
    for _ in range(35):
        cliente.get(A)
    inicio = relogio.agora()
    for _ in range(35):
        cliente.get(SEM_DNS)
    assert relogio.agora() == inicio
    assert reservas[-1][1] is None
    assert cliente.servidores() == {'10.0.0.1': ['sapl.a.leg.br']}


def test_sem_servidor_de_nao_ha_teto(sessao, relogio, cliente):
    for url in (A, B, C):
        sessao.responder(url, texto='ok')
    for _ in range(35):
        for url in (A, B, C):
            cliente.get(url)
    assert relogio.esperas == [] and cliente.servidores() == {}


def test_servidor_consultado_uma_vez_por_site(sessao, relogio):
    consultas = []

    def servidor_de(host):
        consultas.append(host)
        return '10.0.0.1'

    sessao.responder(A, texto='ok').responder(B, texto='ok')
    cliente = ClienteSAPL(
        sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir, servidor_de=servidor_de
    )
    for _ in range(3):
        cliente.get(A)
        cliente.get(B)
    assert consultas == ['sapl.a.leg.br', 'sapl.b.leg.br']
    assert cliente.servidores() == {'10.0.0.1': ['sapl.a.leg.br', 'sapl.b.leg.br']}


def test_definir_limite_por_servidor(sessao, relogio):
    cliente, _ = _cliente_servidor(sessao, relogio, teto=70)
    cliente.definir_limite_por_servidor(50)
    assert cliente.teto('10.0.0.1') == 50 == cliente.limite_por_servidor


def test_resolver_servidor(monkeypatch):
    import socket

    def falso(host):
        if host == 'sapl.sumiu.leg.br':
            raise socket.gaierror(-2, 'Name or service not known')
        return '201.54.51.178'

    monkeypatch.setattr(socket, 'gethostbyname', falso)
    assert http_sapl.resolver_servidor('sapl.a.leg.br') == '201.54.51.178'
    assert http_sapl.resolver_servidor('sapl.sumiu.leg.br') is None


def test_historico_guarda_as_janelas_dos_servidores(sessao, relogio, tmp_path):
    import json

    for url in (A, B, C):
        sessao.responder(url, texto='ok')
    kw = {'historico': str(tmp_path / 'h.json'), 'relogio_parede': relogio.agora}
    primeira, _ = _cliente_servidor(sessao, relogio, teto=40, **kw)
    inicio = relogio.agora()
    for _ in range(20):
        primeira.get(A)
        primeira.get(B)
    dados = json.loads((tmp_path / 'h.json').read_text(encoding='utf-8'))
    assert len(dados['servidores']['10.0.0.1']) == 40
    # outra execução logo depois: o servidor ainda está cheio
    segunda, _ = _cliente_servidor(sessao, relogio, teto=40, **kw)
    segunda.get(C)
    assert relogio.agora() == pytest.approx(inicio + 61)


def test_historico_sem_servidores_ainda_e_lido(sessao, relogio, tmp_path):
    import json

    caminho = tmp_path / 'h.json'
    caminho.write_text(
        json.dumps({'requisicoes': {'sapl.a.leg.br': [relogio.agora()] * 35}, 'bloqueios': {}})
    )
    sessao.responder(A, texto='ok')
    cliente, _ = _cliente_servidor(
        sessao, relogio, historico=str(caminho), relogio_parede=relogio.agora
    )
    inicio = relogio.agora()
    cliente.get(A)
    assert relogio.agora() == pytest.approx(inicio + 61)


# --- Redução do teto com 429 (FR-8, TR-3) ------------------------------------


def _com_429(sessao, *urls):
    for url in urls:
        sessao.responder(url, status=429, headers={'Retry-After': '1'}).responder(url, texto='ok')


def test_429_de_dois_sites_do_servidor_reduz_o_teto_uma_vez(sessao, relogio, caplog):
    _com_429(sessao, A, B, C)
    cliente, _ = _cliente_servidor(sessao, relogio, teto=120)
    with caplog.at_level(logging.WARNING, logger='sapyl'):
        cliente.get(A)
        assert cliente.teto('10.0.0.1') == 120
        cliente.get(B)
        assert cliente.teto('10.0.0.1') == 60
        cliente.get(C)  # mesma leva (menos de 10 min): não reduz de novo
    assert cliente.teto('10.0.0.1') == 60
    assert cliente.reducoes == [('10.0.0.1', 120, 60)]
    avisos = [r.getMessage() for r in caplog.records if 'reduzido' in r.getMessage()]
    assert len(avisos) == 1 and 'de 120 para 60' in avisos[0]


def test_429_de_um_site_so_nao_reduz(sessao, relogio):
    sessao.responder(A, status=429, headers={'Retry-After': '1'})
    cliente, _ = _cliente_servidor(sessao, relogio, teto=120, max_tentativas=4)
    cliente.get(A)
    assert len(sessao.pedidos) == 4 and cliente.teto('10.0.0.1') == 120
    assert cliente.reducoes == []


def test_429_espalhados_mais_de_10_min_nao_reduzem(sessao, relogio):
    _com_429(sessao, A, B)
    cliente, _ = _cliente_servidor(sessao, relogio, teto=120)
    cliente.get(A)
    relogio.t += 601
    cliente.get(B)
    assert cliente.reducoes == []


def test_nova_leva_depois_de_10_min_reduz_de_novo_ate_o_piso(sessao, relogio):
    cliente, _ = _cliente_servidor(sessao, relogio, teto=150)
    tetos = []
    for _ in range(4):
        sessao.limpar(A).limpar(B)
        _com_429(sessao, A, B)
        cliente.get(A)
        cliente.get(B)
        tetos.append(cliente.teto('10.0.0.1'))
        relogio.t += 601
    assert tetos == [75, 37, 35, 35]
    assert [n for _, _, n in cliente.reducoes] == [75, 37, 35]


def test_429_em_site_sem_servidor_nao_reduz_nada(sessao, relogio):
    _com_429(sessao, SEM_DNS)
    cliente, _ = _cliente_servidor(sessao, relogio, teto=120)
    cliente.get(SEM_DNS)
    assert cliente.reducoes == []
