"""Andamento da execução: registros do log, contagens e tempo restante (FR-18, FR-20)."""

import io
import logging
import threading

import pytest
from rich.console import Console

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
    modelo = status.Andamento(lambda: [('Matérias', '0 raspadas')], relogio.agora)
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
    assert modelo.foto().em_andamento == [
        (A, 'buscando', 2, 3),
        (B, 'começando', 0, 0),
    ]
    _materias(modelo, relogio, A, 2, 5, erro_em={2})
    modelo.receber(_registro(andamento=('pdfs', 1, 1, 'ok')), A)
    assert modelo.resumo_da_casa(f'https://{A}/') == '1 busca, 2 matérias (1 com erro), 1 PDF'
    modelo.receber(_registro('fim'), A)
    foto = modelo.foto()
    assert foto.concluidas == 1 and foto.em_andamento == [(B, 'começando', 0, 0)]
    assert foto.total_casas == 3 and foto.contagens == [('Matérias', '0 raspadas')]


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
    assert modelo2.progresso() == 'Matérias 0 raspadas · Tempo 2 s, calculando'


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
    assert modelo.progresso().endswith('Tempo 1 min 40 s, faltam ~2 min (estimativa)')


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


# ---- painel ao vivo e tela (FR-18, FR-21) ----


def _console():
    return Console(record=True, width=100, file=io.StringIO(), force_terminal=True)


def test_painel_mostra_barra_contagens_e_casas():
    foto = status.Foto(
        5,
        2,
        [(A, 'matérias', 45, 120), (B, 'buscando', 1, 3), (C, 'começando', 0, 0)],
        (0, 0),
        125,
        4800,
        [('Buscas', '9 de 15 completas'), ('Matérias', '9 raspadas · 0 com erro')],
        'Projeto p · AC · 5 casas no ar · 3 palavras',
    )
    console = Console(record=True, width=80, file=io.StringIO(), force_terminal=True)
    console.print(status.painel(foto))
    linhas = [linha.rstrip() for linha in console.export_text().splitlines()]
    assert linhas[0] == 'Projeto p · AC · 5 casas no ar · 3 palavras'
    assert set(linhas[1]) == {'─'}
    assert linhas[2].startswith('Casas      ━') and linhas[2].endswith('2 de 5 concluídas (40%)')
    assert linhas[3] == 'Tempo      2 min 05 s · faltam ~1 h 20 min (estimativa)'
    assert linhas[4] == ''
    assert linhas[5:7] == ['Buscas     9 de 15 completas', 'Matérias   9 raspadas · 0 com erro']
    assert linhas[7] == '' and linhas[8] == 'Em andamento (3)'
    assert linhas[9].startswith(f'  {A}  matérias   45/120  ━')
    assert linhas[10].split() == [B, 'buscando', '1/3', '━━━━'] or B in linhas[10]
    assert linhas[11].split() == [C, 'começando']
    assert max(len(linha) for linha in linhas) <= 80


def test_painel_durante_o_teste_das_casas():
    console = _console()
    console.print(status.painel(status.Foto(0, 0, [], (120, 1404), 30, None, [])))
    texto = console.export_text()
    assert texto.startswith('Testando   ━') and '120 de 1404 sites testados (9%)' in texto
    assert 'Tempo      30 s · calculando' in texto


def test_tela_texto_nao_tem_terminal_proprio():
    tela = status.Tela()
    assert tela.terminal() is None and not tela.ao_vivo


def test_handler_do_terminal_filtra_progresso_e_so_arquivo(tmp_path):
    console = _console()
    tela = status.Tela(ao_vivo=True, console=console)
    registro.configurar(tmp_path, 'p', terminal=tela.terminal())
    log = registro.logger()
    with registro.casa_atual('sapl.x.leg.br'):
        log.info('[colchetes] Começando')
    log.info('Progresso: 1 de 2', extra={registro.PROGRESSO: True})
    log.info('resumo', extra={status.SO_ARQUIVO: True})
    registro.andamento(log, registro.MATERIAS, 1, 1, 'Matéria 1 de 1')
    with tela.acompanhar():
        log.info('Progresso: escondida', extra={registro.PROGRESSO: True})
    texto = console.export_text()
    assert '[sapl.x.leg.br] [colchetes] Começando' in texto
    assert 'Progresso: 1 de 2' in texto  # sem o painel, a linha aparece
    assert 'escondida' not in texto and 'resumo' not in texto and 'Matéria 1' not in texto
    arquivo = next((tmp_path / 'logs').iterdir()).read_text(encoding='utf-8')
    assert 'resumo' in arquivo and 'escondida' in arquivo


def test_painel_para_no_ctrl_c():
    tela = status.Tela(ao_vivo=True, console=_console())
    with pytest.raises(KeyboardInterrupt), tela.acompanhar() as andamento:
        andamento.comecar(2)
        assert tela.terminal().painel_ligado
        raise KeyboardInterrupt
    assert not tela.terminal().painel_ligado
    assert not tela.console.is_alt_screen and tela.console._live_stack == []


def test_resumo_num_quadro_e_no_log(tmp_path):
    console = _console()
    tela = status.Tela(ao_vivo=True, console=console)
    registro.configurar(tmp_path, 'p', terminal=tela.terminal())
    tela.resumo('\n===== Resumo =====\nResultado: [x].csv')
    texto = console.export_text()
    assert '╭' in texto and 'Resultado: [x].csv' in texto and texto.count('Resumo') == 1
    assert 'Resultado: [x].csv' in next((tmp_path / 'logs').iterdir()).read_text(encoding='utf-8')
