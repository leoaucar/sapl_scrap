"""Perguntas nos dois modos: opções numeradas (texto) e menus com as setas."""

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from sapyl.interface.perguntas import (
    Atalho,
    Opcao,
    PerguntasMenu,
    PerguntasTexto,
    Voltar,
    criar_perguntas,
    usar_menus,
)
from tests.apoio import roteiro

OPCOES = [Opcao('Primeira', 'a'), Opcao('Segunda', 'b'), Opcao('Terceira', 'c')]
UFS = [Opcao(uf, uf) for uf in ('MG', 'PR', 'RJ', 'SP')]
ATALHOS = [
    Atalho('Todos os estados', 'todos', ()),
    Atalho('Sul e Sudeste', 'sul-sudeste', ('PR', 'SP')),
]

BAIXO, ENTER, ESPACO, CTRL_C = '\x1b[B', '\r', ' ', '\x03'


# ---- modo texto ----


def test_escolher_numerado_pede_de_novo_o_invalido(capsys):
    ler = roteiro('x', '', '4', ' 2 ')
    assert PerguntasTexto(ler).escolher('Qual?', OPCOES) == 'b'
    assert '1- Primeira\n2- Segunda\n3- Terceira\n' in ler.perguntas[0]
    assert capsys.readouterr().out.count('Digite apenas 1, 2 ou 3.') == 3


def test_escolher_com_uma_opcao(capsys):
    assert PerguntasTexto(roteiro('2', '1')).escolher('?', OPCOES[:1]) == 'a'
    assert 'Digite apenas 1.' in capsys.readouterr().out


@pytest.mark.parametrize(
    'resposta,esperado',
    [
        ('s', True),
        ('S', True),
        (' sim ', True),
        ('1', True),
        ('n', False),
        ('NÃO', False),
        ('nao', False),
        ('2', False),
    ],
)
def test_sim_nao_formas_aceitas(resposta, esperado):
    assert PerguntasTexto(roteiro(resposta)).sim_nao('?') is esperado


def test_sim_nao_enter_vale_o_padrao_e_invalido_pede_de_novo(capsys):
    assert PerguntasTexto(roteiro('')).sim_nao('?', padrao=True) is True
    ler = roteiro('talvez', '')
    assert PerguntasTexto(ler).sim_nao('Baixar?') is False
    assert ler.perguntas[0] == 'Baixar? (s/N)\n'
    assert 'Digite s (sim) ou n (não).' in capsys.readouterr().out


def test_marcar_ufs_digitadas_na_ordem_das_opcoes():
    assert PerguntasTexto(roteiro('sp, mg  RJ')).marcar('Estados', UFS, ATALHOS) == [
        'MG',
        'RJ',
        'SP',
    ]


def test_marcar_enter_e_todos_valem_todas():
    assert PerguntasTexto(roteiro('')).marcar('Estados', UFS, ATALHOS) == []
    assert PerguntasTexto(roteiro('todos')).marcar('Estados', UFS, ATALHOS) == []


def test_marcar_atalho_se_expande_e_junta_com_outras():
    assert PerguntasTexto(roteiro('sul-sudeste')).marcar('E', UFS, ATALHOS) == ['PR', 'SP']
    assert PerguntasTexto(roteiro('MG sul-sudeste')).marcar('E', UFS, ATALHOS) == ['MG', 'PR', 'SP']


def test_marcar_desconhecido_e_nomeado_e_pedido_de_novo(capsys):
    ler = roteiro('SP, XX, yy', 'SP')
    assert PerguntasTexto(ler).marcar('Estados', UFS, ATALHOS) == ['SP']
    assert 'Não reconheci: xx, yy.' in capsys.readouterr().out


def test_texto_repete_enquanto_o_validador_recusa(capsys):
    ler = roteiro('', 'a/b', '  bom  ')

    def validar(v):
        if not v:
            return 'vazio'
        return 'barra' if '/' in v else None

    assert PerguntasTexto(ler).texto('Nome', validar) == 'bom'
    assert capsys.readouterr().out.split() == ['vazio', 'barra']


def test_fim_da_entrada_vira_eoferror():
    def fim(_):
        raise EOFError

    with pytest.raises(EOFError):
        PerguntasTexto(fim).escolher('?', OPCOES)


# ---- modo menus (teclas simuladas, sem terminal) ----


@pytest.fixture
def teclas():
    with create_pipe_input() as entrada:

        def menu(*sequencia):
            entrada.send_text(''.join(sequencia))
            return PerguntasMenu(entrada=entrada, saida=DummyOutput())

        yield menu


def test_menu_escolher_com_as_setas(teclas):
    assert teclas(BAIXO, BAIXO, ENTER).escolher('Qual?', OPCOES) == 'c'


def test_menu_sim_nao_comeca_no_padrao(teclas):
    assert teclas(ENTER).sim_nao('?') is False
    assert teclas(ENTER).sim_nao('?', padrao=True) is True
    assert teclas(BAIXO, ENTER).sim_nao('?', padrao=True) is False


def test_menu_marcar_atalho_sul_sudeste(teclas):
    # cursor: Todos, Sul e Sudeste, (separador), MG...
    assert teclas(BAIXO, ESPACO, ENTER).marcar('Estados', UFS, ATALHOS) == ['PR', 'SP']


def test_menu_marcar_uma_uf_e_nada_marcado(teclas):
    # Todos, Sul e Sudeste, MG (o separador é pulado)
    assert teclas(BAIXO, BAIXO, ESPACO, ENTER).marcar('E', UFS, ATALHOS) == ['MG']
    # Enter sem nada marcado não vale; marcar "Todos os estados" dá todas
    assert teclas(ENTER, ESPACO, ENTER).marcar('E', UFS, ATALHOS) == []


def test_menu_texto_com_validador(teclas):
    assert (
        teclas('a/b', ENTER, '\x7f\x7f\x7f', 'meu', ENTER).texto(
            'Nome', lambda v: 'barra' if '/' in v else None
        )
        == 'meu'
    )


@pytest.mark.parametrize('pergunta', ['escolher', 'sim_nao', 'marcar', 'texto'])
def test_menu_ctrl_c_lanca_keyboardinterrupt(teclas, pergunta):
    menu = teclas(CTRL_C)
    chamadas = {
        'escolher': lambda: menu.escolher('?', OPCOES),
        'sim_nao': lambda: menu.sim_nao('?'),
        'marcar': lambda: menu.marcar('?', UFS, ATALHOS),
        'texto': lambda: menu.texto('?', lambda v: None),
    }
    with pytest.raises(KeyboardInterrupt):
        chamadas[pergunta]()


def test_menu_mostrar_nao_interpreta_colchetes():
    from rich.console import Console

    console = Console(record=True, width=80)
    PerguntasMenu(entrada=object(), saida=object(), console=console).mostrar('[sapl.x] [bold]a')
    assert '[sapl.x] [bold]a' in console.export_text()


# ---- escolha do modo ----


class _Tty:
    def __init__(self, tty):
        self.tty = tty

    def isatty(self):
        return self.tty


def test_menus_so_com_input_num_terminal_interativo():
    sim, nao = _Tty(True), _Tty(False)
    assert usar_menus(input, {}, sim, sim) is True
    assert usar_menus(input, {}, nao, sim) is False
    assert usar_menus(input, {}, sim, nao) is False
    assert usar_menus(roteiro(), {}, sim, sim) is False
    assert usar_menus(input, {'SAPYL_MENUS': '0'}, sim, sim) is False
    assert usar_menus(input, {'SAPYL_MENUS': '1'}, sim, sim) is True


def test_criar_perguntas_com_roteiro_e_texto():
    assert isinstance(criar_perguntas(roteiro()), PerguntasTexto)


# ---- ← Voltar (FR-23) ----


def test_texto_voltar_e_a_ultima_opcao_numerada():
    ler = roteiro('4')
    with pytest.raises(Voltar):
        PerguntasTexto(ler).escolher('Qual?', OPCOES, voltar=True)
    assert ler.perguntas[0].endswith('3- Terceira\n4- ← Voltar\n')
    assert PerguntasTexto(roteiro('2')).escolher('?', OPCOES, voltar=True) == 'b'


@pytest.mark.parametrize('pergunta', ['sim_nao', 'marcar', 'texto'])
def test_texto_menor_que_volta(pergunta):
    p = PerguntasTexto(roteiro('<'))
    chamadas = {
        'sim_nao': lambda: p.sim_nao('?', voltar=True),
        'marcar': lambda: p.marcar('?', UFS, ATALHOS, voltar=True),
        'texto': lambda: p.texto('?', lambda v: None, voltar=True),
    }
    with pytest.raises(Voltar):
        chamadas[pergunta]()


def test_texto_sem_voltar_menor_que_e_uma_resposta(capsys):
    assert PerguntasTexto(roteiro('<')).texto('?', lambda v: None) == '<'
    assert PerguntasTexto(roteiro('<', 's')).sim_nao('?') is True
    assert 'Digite s (sim) ou n (não).' in capsys.readouterr().out


def test_texto_dicas_do_voltar():
    ler = roteiro('s')
    PerguntasTexto(ler).sim_nao('PDFs?', voltar=True)
    assert ler.perguntas[0] == 'PDFs? (s/N; < volta)\n'


def test_menu_voltar_na_lista_e_no_sim_nao(teclas):
    with pytest.raises(Voltar):
        teclas(BAIXO, BAIXO, BAIXO, ENTER).escolher('?', OPCOES, voltar=True)
    with pytest.raises(Voltar):
        teclas(BAIXO, ENTER).sim_nao('?', voltar=True)  # Não -> ← Voltar
    assert teclas(ENTER).sim_nao('?', voltar=True) is False


def test_menu_voltar_na_lista_de_marcar(teclas):
    with pytest.raises(Voltar):
        teclas(ESPACO, ENTER).marcar('?', UFS, ATALHOS, voltar=True)
    # ← Voltar, Todos, Sul e Sudeste: o atalho continua funcionando
    assert teclas(BAIXO, BAIXO, ESPACO, ENTER).marcar('?', UFS, ATALHOS, voltar=True) == [
        'PR',
        'SP',
    ]


def test_menu_texto_vazio_volta(teclas):
    with pytest.raises(Voltar):
        teclas(ENTER).texto('Nome', lambda v: 'vazio' if not v else None, voltar=True)
    assert teclas('a', ENTER).texto('Nome', lambda v: None, voltar=True) == 'a'


def test_menu_marcar_enter_sem_marcar_nao_escolhe_a_opcao_do_cursor(teclas):
    """O erro de 30/10: cursor em RJ e Enter sem a barra de espaço virava "todos"."""
    # Todos, Sul e Sudeste, MG, PR, RJ: o cursor para em RJ, Enter (recusado), espaço, Enter
    menu = teclas(BAIXO, BAIXO, BAIXO, BAIXO, ENTER, ESPACO, ENTER)
    assert menu.marcar('Estados', UFS, ATALHOS) == ['RJ']
