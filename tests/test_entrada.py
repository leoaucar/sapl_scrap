"""Escolha do projeto ou do arquivo em cada opção do menu (FR-4, FR-5)."""

from datetime import datetime

from sapyl import projeto as gp
from sapyl.interface import entrada
from sapyl.interface.perguntas import PerguntasTexto
from tests.apoio import roteiro


def _p(*respostas):
    ler = roteiro(*respostas)
    return PerguntasTexto(ler), ler


def _com_final(raiz, nome):
    projeto = gp.Projeto(raiz, nome)
    projeto.criar()
    projeto.final.write_text('Link Materia\nhttps://x/materia/1\n', encoding='utf-8')
    return projeto


def test_projeto_novo_nao_cria_a_pasta(tmp_path):
    perguntas, _ = _p('teste')
    projeto, novo = entrada.abrir_ou_criar(tmp_path, perguntas)
    assert novo and projeto.pasta == tmp_path / 'teste_proj'
    assert not projeto.pasta.exists()
    assert projeto.final == tmp_path / 'teste_proj' / 'teste_resultado_final.csv'
    assert projeto.downloads == tmp_path / 'teste_proj' / 'downloads'


def test_nome_vazio_ou_com_barras_e_pedido_de_novo(tmp_path, capsys):
    perguntas, ler = _p('', 'a/b', 'a\\b', '  meu projeto  ')
    projeto, _ = entrada.abrir_ou_criar(tmp_path, perguntas)
    assert projeto.nome == 'meu projeto' and len(ler.perguntas) == 4
    saida = capsys.readouterr().out
    assert saida.count('vazio') == 1 and saida.count('barras') == 2


def test_projeto_existente_oferece_retomar(tmp_path):
    (tmp_path / 'teste_proj').mkdir()
    (tmp_path / 'teste_proj' / 'dado.csv').write_text('x')
    perguntas, ler = _p('teste_proj', '1')
    projeto, novo = entrada.abrir_ou_criar(tmp_path, perguntas)
    assert not novo and projeto.nome == 'teste'
    assert 'O projeto "teste" já existe.' in ler.perguntas[1]
    assert (tmp_path / 'teste_proj' / 'dado.csv').read_text() == 'x'


def test_outro_nome_pergunta_de_novo(tmp_path):
    (tmp_path / 'a_proj').mkdir()
    perguntas, ler = _p('a', 'x', '2', 'b')
    projeto, novo = entrada.abrir_ou_criar(tmp_path, perguntas)
    assert novo and projeto.nome == 'b'
    assert len(ler.perguntas) == 4


def test_lista_de_projetos_com_situacao_e_voltar(tmp_path):
    _com_final(tmp_path, 'bom')
    gp.Projeto(tmp_path, 'vazio').criar()
    perguntas, ler = _p('2')
    assert entrada.escolher_projeto(tmp_path, perguntas, 'Qual?').nome == 'vazio'
    hoje = datetime.now().strftime('%d/%m/%Y')
    assert f'1- bom — não iniciado · criado em ? · atualizado em {hoje} ' in ler.perguntas[0]
    assert (
        '2- vazio — não iniciado · criado em ? · atualizado em ? · ? matérias\n'
        in (ler.perguntas[0])
    )
    assert ler.perguntas[0].endswith('3- ← Voltar\n')
    perguntas, _ = _p('3')
    assert entrada.escolher_projeto(tmp_path, perguntas, 'Qual?') is None


def test_lista_so_com_resultado_e_lista_vazia(tmp_path, capsys):
    perguntas, ler = _p()
    assert entrada.escolher_projeto(tmp_path, perguntas, 'Qual?') is None
    assert ler.perguntas == []
    assert 'Nenhum projeto nesta pasta' in capsys.readouterr().out
    gp.Projeto(tmp_path, 'vazio').criar()
    assert entrada.escolher_projeto(tmp_path, perguntas, 'Q', so_com_resultado=True) is None
    assert 'Nenhum projeto com resultado final' in capsys.readouterr().out
    _com_final(tmp_path, 'bom')
    perguntas, ler = _p('1')
    assert entrada.escolher_projeto(tmp_path, perguntas, 'Q', so_com_resultado=True).nome == 'bom'
    assert 'vazio' not in ler.perguntas[0]


def test_autoria_de_projeto_usa_o_resultado_mais_recente(tmp_path):
    import os

    projeto = _com_final(tmp_path, 'p')
    atualizado = projeto.pasta / 'p_resultado_final_ATUALIZADO_01_01_2027.csv'
    atualizado.write_text('Link Materia\n', encoding='utf-8')
    os.utime(atualizado, (2_000_000_000, 2_000_000_000))
    perguntas, ler = _p('1')
    planilha, escolhido = entrada.escolher_entrada_autoria(tmp_path, perguntas)
    assert planilha == atualizado and escolhido.nome == 'p'
    assert '2- Outro arquivo CSV…\n3- ← Voltar\n' in ler.perguntas[0]


def test_autoria_outro_csv_e_voltar(tmp_path, capsys):
    _com_final(tmp_path, 'p')
    (tmp_path / 'minha.csv').write_text('Link Materia\n', encoding='utf-8')
    (tmp_path / 'nao.txt').write_text('x', encoding='utf-8')
    perguntas, _ = _p('2', 'nao.txt', '', 'minha.csv')
    assert entrada.escolher_entrada_autoria(tmp_path, perguntas) == (tmp_path / 'minha.csv', None)
    saida = capsys.readouterr().out
    assert 'Não encontrei o arquivo CSV "nao.txt"' in saida and 'Digite o caminho' in saida
    perguntas, _ = _p('3')
    assert entrada.escolher_entrada_autoria(tmp_path, perguntas) is None


def test_autoria_sem_projetos_pergunta_o_csv(tmp_path):
    (tmp_path / 'minha.csv').write_text('Link Materia\n', encoding='utf-8')
    perguntas, ler = _p(str(tmp_path / 'minha.csv'))  # caminho absoluto
    assert entrada.escolher_entrada_autoria(tmp_path, perguntas) == (tmp_path / 'minha.csv', None)
    assert len(ler.perguntas) == 1 and 'Caminho do arquivo CSV' in ler.perguntas[0]


def test_lista_do_mais_recente_para_o_mais_antigo(tmp_path):
    import os

    for nome, quando in (
        ('antigo', 1_700_000_000),
        ('novo', 1_800_000_000),
        ('meio', 1_750_000_000),
    ):
        projeto = _com_final(tmp_path, nome)
        os.utime(projeto.final, (quando, quando))
    perguntas, ler = _p('1')
    assert entrada.escolher_projeto(tmp_path, perguntas, 'Qual?').nome == 'novo'
    ordem = [linha.split(' — ')[0][3:] for linha in ler.perguntas[0].splitlines()[1:4]]
    assert ordem == ['novo', 'meio', 'antigo']
