"""Andamento da execução: registros do log, contagens e tempo restante (FR-18, FR-20)."""

import logging
import threading

from sapyl import execucao, registro
from sapyl.interface import status
from tests.apoio import RelogioFalso

A, B, C = 'sapl.a.leg.br', 'sapl.b.leg.br', 'sapl.c.leg.br'


def _registro(evento=None, andamento=None):
    record = logging.LogRecord('sapyl', logging.DEBUG, __file__, 1, 'x', (), None)
    if evento:
        setattr(record, registro.EVENTO_CASA, evento)
    if andamento:
        setattr(record, registro.ANDAMENTO, andamento)
    return record


def _modelo(total=3):
    relogio = RelogioFalso(1000)
    modelo = status.Andamento(lambda: 'matérias: 0 raspadas', relogio.agora)
    modelo.comecar(total)
    return modelo, relogio


def _materias(modelo, relogio, host, n, total, intervalo=1.0, erro_em=()):
    modelo.receber(_registro(andamento=('materias', 0, total, None)), host)
    for i in range(1, n + 1):
        relogio.dormir(intervalo)
        st = 'erro' if i in erro_em else 'ok'
        modelo.receber(_registro(andamento=('materias', i, total, st)), host)


def test_etapas_das_casas_em_andamento_e_concluidas():
    modelo, relogio = _modelo()
    modelo.receber(_registro('inicio'), A)
    modelo.receber(_registro(andamento=('busca', 0, 3, None)), A)
    modelo.receber(_registro(andamento=('busca', 2, 3, 'completa')), A)
    modelo.receber(_registro('inicio'), B)
    assert modelo.foto().em_andamento == [(A, 'buscando 2/3'), (B, 'começando')]
    _materias(modelo, relogio, A, 2, 5, erro_em={2})
    modelo.receber(_registro(andamento=('pdfs', 1, 1, 'ok')), A)
    assert modelo.resumo_da_casa(f'https://{A}/') == '1 busca, 2 matérias (1 com erro), 1 PDF'
    modelo.receber(_registro('fim'), A)
    foto = modelo.foto()
    assert foto.concluidas == 1 and foto.em_andamento == [(B, 'começando')]
    assert foto.total_casas == 3 and foto.contagens == 'matérias: 0 raspadas'


def test_resumo_da_casa_sem_nada():
    modelo, _ = _modelo()
    assert modelo.resumo_da_casa(A) == 'nada a fazer'


def test_teste_das_casas_conta_a_parte():
    modelo, _ = _modelo()
    for i in (1, 3, 2):
        modelo.receber(_registro(andamento=('teste', i, 10, None)), A)
    assert modelo.foto().teste == (3, 10) and modelo.foto().em_andamento == []


def test_registros_sem_andamento_sao_ignorados():
    modelo, _ = _modelo()
    modelo.receber(_registro(), A)
    assert modelo.foto().em_andamento == []


def test_tempo_restante_calculando_antes_de_um_minuto_ou_sem_casa_concluida():
    modelo, relogio = _modelo()
    modelo.receber(_registro('inicio'), A)
    _materias(modelo, relogio, A, 10, 100, intervalo=10)  # 100 s, nenhuma casa concluída
    assert modelo.restante() is None
    modelo2, relogio2 = _modelo()
    modelo2.receber(_registro('inicio'), A)
    _materias(modelo2, relogio2, A, 2, 2, intervalo=1)
    modelo2.receber(_registro('fim'), A)
    assert modelo2.restante() is None  # 2 s: menos de 1 minuto
    assert modelo2.progresso() == 'matérias: 0 raspadas; tempo restante: calculando'


def test_tempo_restante_pelas_materias_por_minuto():
    modelo, relogio = _modelo(total=3)
    # A: 60 matérias em 60 s (1 por segundo), concluída
    modelo.receber(_registro('inicio'), A)
    _materias(modelo, relogio, A, 60, 60)
    modelo.receber(_registro('fim'), A)
    # B: 40 de 100 feitas; C não começou (vale a média, 60)
    modelo.receber(_registro('inicio'), B)
    _materias(modelo, relogio, B, 40, 100)
    # ritmo: 100 matérias em 100 s; falta: 60 (B) + 60 (C) = 120 -> 120 s
    assert round(modelo.restante()) == 120
    assert modelo.progresso().endswith('tempo restante: ~2 min (estimativa)')


def test_tempo_restante_casa_ainda_buscando_vale_a_media():
    modelo, relogio = _modelo(total=2)
    modelo.receber(_registro('inicio'), A)
    _materias(modelo, relogio, A, 90, 90)
    modelo.receber(_registro('fim'), A)
    modelo.receber(_registro('inicio'), B)
    modelo.receber(_registro(andamento=('busca', 1, 3, 'completa')), B)
    assert round(modelo.restante()) == 90  # média 90, ritmo 1/s


def test_ritmo_usa_so_os_ultimos_5_minutos():
    modelo, relogio = _modelo(total=2)
    modelo.receber(_registro('inicio'), A)
    _materias(modelo, relogio, A, 10, 10, intervalo=1)
    modelo.receber(_registro('fim'), A)
    modelo.receber(_registro('inicio'), B)
    _materias(modelo, relogio, B, 1, 21, intervalo=600)  # parado 10 min, depois 1 matéria
    # na janela de 5 min só há 1 matéria: 1/300 por segundo; faltam 20
    assert round(modelo.restante()) == 20 * 300


def test_autoria_conta_como_trabalho():
    relogio = RelogioFalso(0)
    modelo = status.Andamento(relogio=relogio.agora)
    for host, n in ((A, 60), (B, 30)):
        modelo.receber(_registro('inicio'), host)
        for i in range(1, n + 1):
            relogio.dormir(1)
            modelo.receber(_registro(andamento=('autoria', i, 60, 'ok')), host)
    modelo.receber(_registro('fim'), A)
    assert modelo.foto().total_casas == 2
    assert modelo.resumo_da_casa(A) == 'autoria de 60 matérias'
    assert round(modelo.restante()) == 30


def test_texto_restante():
    assert status.texto_restante(None) == 'calculando'
    assert status.texto_restante(10) == '~1 min (estimativa)'
    assert status.texto_restante(299) == '~5 min (estimativa)'
    assert status.texto_restante(4800) == '~1 h 20 min (estimativa)'


def test_handler_le_o_log_das_threads_de_cada_casa():
    with status.acompanhar() as modelo:
        modelo.comecar(4)
        log = registro.logger('materias')

        def tarefa(casa):
            for i in range(1, 6):
                registro.andamento(log, registro.MATERIAS, i, 5, 'm', status='ok')

        casas = [f'https://sapl.c{i}.leg.br/' for i in range(4)]
        execucao.por_casa(
            casas, tarefa, 4, threading.Event(), anunciar=True, ao_terminar=modelo.resumo_da_casa
        )
        foto = modelo.foto()
    assert foto.concluidas == 4 and foto.em_andamento == []
    assert modelo.resumo_da_casa(casas[0]) == '5 matérias'
    registro.andamento(log, registro.MATERIAS, 6, 6, 'depois', status='ok')  # já desligado
    assert modelo.resumo_da_casa(casas[0]) == '5 matérias'


def test_erro_no_andamento_nao_derruba_a_execucao(monkeypatch):
    with status.acompanhar() as modelo:
        monkeypatch.setattr(modelo, 'receber', lambda *a: 1 / 0)
        monkeypatch.setattr(logging, 'raiseExceptions', False)
        registro.andamento(registro.logger(), registro.MATERIAS, 1, 1, 'x', status='ok')
