"""Grupo de threads por casa (FR-1, FR-2, FR-12, FR-13, TR-5 na parte unitária)."""

import _thread
import logging
import threading
import time

import pytest

from sapyl import execucao, registro

CASAS = [f'https://sapl.c{i}.leg.br/' for i in range(6)]


def test_resultados_na_ordem_das_casas():
    def tarefa(casa):
        time.sleep(0.01 * (6 - CASAS.index(casa)))  # as primeiras terminam por último
        return casa.upper()

    resultados = execucao.por_casa(CASAS, tarefa, 4, threading.Event())
    assert resultados == [c.upper() for c in CASAS]


def test_lista_vazia():
    assert execucao.por_casa([], str, 4, threading.Event()) == []


def test_no_maximo_n_ao_mesmo_tempo():
    trava, agora, pico = threading.Lock(), [0], [0]

    def tarefa(casa):
        with trava:
            agora[0] += 1
            pico[0] = max(pico[0], agora[0])
        time.sleep(0.03)
        with trava:
            agora[0] -= 1

    execucao.por_casa(CASAS, tarefa, 3, threading.Event())
    assert pico[0] == 3


def test_com_uma_casa_por_vez_a_ordem_e_a_da_lista():
    ordem = []
    execucao.por_casa(CASAS, ordem.append, 1, threading.Event())
    assert ordem == CASAS


def test_erro_numa_casa_nao_para_as_outras(caplog):
    feitas = []

    def tarefa(casa):
        if casa in (CASAS[1], CASAS[4]):
            raise OSError('disco cheio')
        feitas.append(casa)

    with (
        caplog.at_level(logging.ERROR, logger='sapyl'),
        pytest.raises(execucao.FalhaNasCasas) as erro,
    ):
        execucao.por_casa(CASAS, tarefa, 3, threading.Event())
    assert sorted(feitas) == sorted(set(CASAS) - {CASAS[1], CASAS[4]})
    assert [c for c, _ in erro.value.falhas] == [CASAS[1], CASAS[4]]
    assert '2 casa(s) pararam' in str(erro.value) and 'OSError: disco cheio' in str(erro.value)
    registros = [r for r in caplog.records if 'Erro inesperado' in r.getMessage()]
    assert len(registros) == 2 and all(r.exc_info for r in registros)


def test_ctrl_c_numa_tarefa_para_tudo_e_liga_o_evento():
    parar = threading.Event()
    comecadas = []

    def tarefa(casa):
        comecadas.append(casa)
        if casa == CASAS[0]:
            raise KeyboardInterrupt
        parar.wait(5)  # como o cliente: a espera acaba quando `parar` liga

    inicio = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        execucao.por_casa(CASAS, tarefa, 2, parar)
    assert parar.is_set() and time.monotonic() - inicio < 3
    assert len(comecadas) < len(CASAS)  # as da fila foram descartadas


def test_ctrl_c_na_thread_principal(caplog):
    parar = threading.Event()
    comecou = threading.Event()

    def tarefa(casa):
        comecou.set()
        if casa == CASAS[0]:
            _thread.interrupt_main()  # como um Ctrl+C no terminal
        parar.wait(5)

    with caplog.at_level(logging.WARNING, logger='sapyl'), pytest.raises(KeyboardInterrupt):
        execucao.por_casa(CASAS, tarefa, 2, parar)
    assert parar.is_set()
    assert any('Parando: esperando' in r.getMessage() for r in caplog.records)


def test_evento_ligado_antes_e_desligado_ao_comecar():
    parar = threading.Event()
    parar.set()
    assert execucao.por_casa(CASAS[:2], len, 2, parar) == [len(c) for c in CASAS[:2]]
    assert not parar.is_set()


def test_linha_de_progresso(caplog):
    def tarefa(casa):
        time.sleep(0.15 if casa == CASAS[0] else 0)

    with caplog.at_level(logging.INFO, logger='sapyl'):
        execucao.por_casa(
            CASAS, tarefa, 2, threading.Event(), progresso=lambda: 'matérias: 3 ok', a_cada=0.05
        )
    linhas = [r.getMessage() for r in caplog.records if r.getMessage().startswith('Progresso')]
    assert linhas
    assert linhas[0].endswith(' na fila\n  matérias: 3 ok') and 'de 6 casas concluídas' in linhas[0]
    assert 'em andamento' in linhas[0] and 'na fila' in linhas[0]


def test_prefixo_da_casa_no_log(tmp_path):
    registro.configurar(tmp_path, 'p')
    log = registro.logger('materias')
    http = registro.logger('http')

    def tarefa(casa):
        log.info('Matéria 1 de 1')
        http.debug('%s | x | 200', execucao.nome_da_casa(casa))

    execucao.por_casa(CASAS[:2], tarefa, 2, threading.Event())
    log.info('fora de uma casa')
    texto = next((tmp_path / 'logs').iterdir()).read_text(encoding='utf-8')
    assert 'sapyl.materias [sapl.c0.leg.br] Matéria 1 de 1' in texto
    assert 'sapyl.materias [sapl.c1.leg.br] Matéria 1 de 1' in texto
    assert 'DEBUG sapyl.http sapl.c0.leg.br | x | 200' in texto  # sem prefixo
    assert 'INFO sapyl.materias fora de uma casa' in texto


def test_prefixo_no_terminal(tmp_path, capsys):
    registro.configurar(tmp_path, 'p')
    with registro.casa_atual('sapl.x.leg.br'):
        registro.logger().info('olá')
        with registro.casa_atual('sapl.y.leg.br'):
            registro.logger().info('dentro')
        registro.logger().info('de volta')
    erro = capsys.readouterr().err
    assert '[sapl.x.leg.br] olá' in erro and '[sapl.y.leg.br] dentro' in erro
    assert '[sapl.x.leg.br] de volta' in erro


def test_linha_de_progresso_tem_a_marca(caplog):
    with caplog.at_level(logging.INFO, logger='sapyl'):
        execucao.por_casa(CASAS[:2], lambda c: time.sleep(0.12), 1, threading.Event(), a_cada=0.05)
    linhas = [r for r in caplog.records if r.getMessage().startswith('Progresso')]
    assert linhas and all(getattr(r, registro.PROGRESSO, False) for r in linhas)


def test_anunciar_comeco_e_fim_de_cada_casa(tmp_path, caplog):
    registro.configurar(tmp_path, 'p')
    with caplog.at_level(logging.DEBUG, logger='sapyl'):
        execucao.por_casa(
            CASAS[:2], len, 2, threading.Event(), anunciar=True, ao_terminar=lambda c: f'{len(c)} x'
        )
    eventos = {getattr(r, registro.EVENTO_CASA, None) for r in caplog.records}
    assert {'inicio', 'fim'} <= eventos
    texto = next((tmp_path / 'logs').iterdir()).read_text(encoding='utf-8')
    for casa in CASAS[:2]:
        host = execucao.nome_da_casa(casa)
        assert f'DEBUG sapyl.execucao [{host}] Começando' in texto
        assert f'INFO sapyl.execucao ✓ {host}: {len(casa)} x' in texto


def test_sem_anunciar_nao_ha_linhas_de_casa(caplog):
    with caplog.at_level(logging.INFO, logger='sapyl'):
        execucao.por_casa(CASAS[:2], len, 2, threading.Event())
    assert not any(hasattr(r, registro.EVENTO_CASA) for r in caplog.records)
