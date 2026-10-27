"""Projetos: criar, retomar, nunca sobrescrever, configuração salva."""
from sapyl import projeto as gp
from tests.apoio import roteiro


def test_projeto_novo(tmp_path):
    projeto, novo = gp.abrir_ou_criar(tmp_path, roteiro('teste'))
    assert novo and projeto.pasta == tmp_path / 'teste_proj' and projeto.pasta.is_dir()
    assert projeto.final == tmp_path / 'teste_proj' / 'teste_resultado_final.csv'
    assert projeto.estado.name == 'teste_estado.csv'
    assert projeto.downloads == tmp_path / 'teste_proj' / 'downloads'


def test_projeto_existente_oferece_retomar(tmp_path):
    (tmp_path / 'teste_proj').mkdir()
    (tmp_path / 'teste_proj' / 'dado.csv').write_text('x')
    projeto, novo = gp.abrir_ou_criar(tmp_path, roteiro('teste_proj', '1'))
    assert not novo and projeto.nome == 'teste'
    assert (tmp_path / 'teste_proj' / 'dado.csv').read_text() == 'x'


def test_outro_nome_pergunta_de_novo(tmp_path):
    (tmp_path / 'a_proj').mkdir()
    ler = roteiro('a', 'x', '2', 'b')
    projeto, novo = gp.abrir_ou_criar(tmp_path, ler)
    assert novo and projeto.nome == 'b'
    assert len(ler.perguntas) == 4


def test_config_ida_e_volta(tmp_path):
    projeto = gp.Projeto(tmp_path, 'p')
    projeto.pasta.mkdir()
    assert gp.carregar_config(projeto) is None
    config = {'palavras': ['"plano+diretor"', '"orçamento"+"emenda+impositiva"'], 'sul_sudeste': False,
              'limite': '4', 'downloads': True, 'reusar_tabela': True}
    gp.salvar_config(projeto, config)
    assert gp.carregar_config(projeto) == config


def test_caminhos_do_modo_atualizacao(tmp_path):
    projeto = gp.Projeto(tmp_path, 'p', data='24_10_2026')
    assert projeto.final.name == 'p_resultado_final_ATUALIZADO_24_10_2026.csv'
    assert projeto.estado.name == 'p_estado_ATUALIZADO_24_10_2026.csv'
    assert projeto.materias.name == 'p_materias_legislativas_ATUALIZADO_24_10_2026.csv'
    assert projeto.downloads.name == 'downloads24_10_2026'
    assert projeto.links.name == 'p_links_totais.csv'


def test_escolher_projeto_existente(tmp_path, capsys):
    gp.Projeto(tmp_path, 'bom').pasta.mkdir()
    gp.Projeto(tmp_path, 'bom').final.write_text('Link Materia\n')
    gp.Projeto(tmp_path, 'vazio').pasta.mkdir()
    projeto = gp.escolher_projeto_existente(tmp_path, roteiro('vazio', 'nada', 'bom_proj'))
    assert projeto.nome == 'bom'
    saida = capsys.readouterr().out
    assert 'Projetos encontrados: bom, vazio' in saida and saida.count('Não encontrei') == 2
