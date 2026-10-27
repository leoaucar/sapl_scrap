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
    # a mais antiga foi em `inicio`; a 36ª só sai 60 s depois dela
    assert relogio.agora() == pytest.approx(inicio + 60, abs=0.05)
    assert sum(relogio.esperas) == pytest.approx(25, abs=0.05)


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
    assert relogio.esperas == [60]


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
    assert relogio.agora() >= inicio + 60 - 0.05


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
