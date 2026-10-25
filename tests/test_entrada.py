"""Perguntas no terminal: respostas inválidas são pedidas de novo."""
import entrada


def roteiro(*respostas):
    """Função de entrada que devolve as respostas em ordem e registra as perguntas."""
    fila = list(respostas)
    perguntas = []

    def ler(texto=''):
        perguntas.append(texto)
        return fila.pop(0)
    ler.perguntas = perguntas
    return ler


def test_opcao_invalida_vazia_e_fora_da_faixa_sao_pedidas_de_novo(capsys):
    ler = roteiro('x', '', '9', ' 2 ')
    assert entrada.perguntar_opcao('Escolha', ['1', '2', '3', '4'], ler) == '2'
    assert len(ler.perguntas) == 4
    assert capsys.readouterr().out.count('Digite apenas 1, 2, 3 ou 4.') == 3


def test_menu_de_limite_recusa_5():
    ler = roteiro('5', '4')
    assert entrada.perguntar_opcao('Limite', [1, 2, 3, 4], ler) == '4'
    assert len(ler.perguntas) == 2


def test_sim_nao():
    assert entrada.perguntar_sim_nao('?', roteiro('sim', '1')) is True
    assert entrada.perguntar_sim_nao('?', roteiro('2')) is False


def test_opcao_unica(capsys):
    assert entrada.perguntar_opcao('?', ['1'], roteiro('0', '1')) == '1'
    assert 'Digite apenas 1.' in capsys.readouterr().out


def test_texto_recusa_vazio_e_barras_e_tira_espacos(capsys):
    ler = roteiro('', '   ', 'a/b', 'a\\b', '  meu projeto  ')
    assert entrada.perguntar_texto('Nome', ler) == 'meu projeto'
    saida = capsys.readouterr().out
    assert saida.count('vazia') == 2 and saida.count('barras') == 2
