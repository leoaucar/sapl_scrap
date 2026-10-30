"""Projetos: criar, retomar, nunca sobrescrever, configuração salva, situação."""

import os
from datetime import datetime

from sapyl import projeto as gp
from sapyl.interface import entrada
from tests.apoio import roteiro


def test_projeto_novo(tmp_path):
    projeto, novo = entrada.abrir_ou_criar(tmp_path, roteiro('teste'))
    assert novo and projeto.pasta == tmp_path / 'teste_proj' and projeto.pasta.is_dir()
    assert projeto.final == tmp_path / 'teste_proj' / 'teste_resultado_final.csv'
    assert projeto.estado.name == 'teste_estado.csv'
    assert projeto.downloads == tmp_path / 'teste_proj' / 'downloads'


def test_projeto_existente_oferece_retomar(tmp_path):
    (tmp_path / 'teste_proj').mkdir()
    (tmp_path / 'teste_proj' / 'dado.csv').write_text('x')
    projeto, novo = entrada.abrir_ou_criar(tmp_path, roteiro('teste_proj', '1'))
    assert not novo and projeto.nome == 'teste'
    assert (tmp_path / 'teste_proj' / 'dado.csv').read_text() == 'x'


def test_outro_nome_pergunta_de_novo(tmp_path):
    (tmp_path / 'a_proj').mkdir()
    ler = roteiro('a', 'x', '2', 'b')
    projeto, novo = entrada.abrir_ou_criar(tmp_path, ler)
    assert novo and projeto.nome == 'b'
    assert len(ler.perguntas) == 4


def test_config_ida_e_volta(tmp_path):
    projeto = gp.Projeto(tmp_path, 'p')
    projeto.pasta.mkdir()
    assert gp.carregar_config(projeto) is None
    config = {
        'palavras': ['"plano+diretor"', '"orçamento"+"emenda+impositiva"'],
        'sul_sudeste': False,
        'limite': '4',
        'downloads': True,
        'reusar_tabela': True,
    }
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
    projeto = entrada.escolher_projeto_existente(tmp_path, roteiro('vazio', 'nada', 'bom_proj'))
    assert projeto.nome == 'bom'
    saida = capsys.readouterr().out
    assert 'Projetos encontrados: bom, vazio' in saida and saida.count('Não encontrei') == 2


# ---- situação do projeto (FR-4a) ----

CABECALHO = 'etapa,chave,status,erro,quando\n'


def _projeto(tmp_path, nome='p'):
    projeto = gp.Projeto(tmp_path, nome)
    projeto.criar()
    return projeto


def _log(projeto, quando, modo='novo'):
    pasta = projeto.pasta / 'logs'
    pasta.mkdir(exist_ok=True)
    caminho = pasta / f'{projeto.nome}_{quando}_{modo}.log'
    caminho.write_text('x')
    return caminho


def _datar(caminho, quando):
    t = datetime.strptime(quando, '%Y-%m-%d_%H%M%S').timestamp()
    os.utime(caminho, (t, t))


def _final(projeto, linhas, quando):
    projeto.final.write_text('Link Materia,Ementa\n' + ''.join(linhas), encoding='utf-8')
    _datar(projeto.final, quando)


def test_criar_so_quando_pedido(tmp_path):
    projeto = gp.Projeto(tmp_path, 'novo')
    assert not projeto.pasta.exists()
    projeto.criar()
    projeto.criar()  # de novo não dá erro
    assert projeto.pasta.is_dir()


def test_nao_iniciado(tmp_path):
    s = gp.situacao(_projeto(tmp_path))
    assert (s.rotulo, s.materias) == (gp.NAO_INICIADO, None)
    assert s.texto() == 'não iniciado · ? · ? matérias'


def test_concluido_conta_as_materias_mesmo_com_quebra_de_linha(tmp_path):
    projeto = _projeto(tmp_path)
    projeto.estado.write_text(
        CABECALHO + 'materia,h/1,ok,,x\nmateria,h/2,erro,,x\nmateria,h/2,ok,,x\n', encoding='utf-8'
    )
    _log(projeto, '2026-10-28_100000')
    _log(projeto, '2026-10-29_100000', 'autoria')  # autoria não conta como execução
    _final(projeto, ['a,"uma\nementa"\n', 'b,c\n'], '2026-10-28_120000')
    s = gp.situacao(projeto)
    assert (s.rotulo, s.materias) == (gp.CONCLUIDO, 2)
    assert s.texto() == 'concluído · 28/10/2026 · 2 matérias'


def test_concluido_com_falhas(tmp_path):
    for linha in (
        'materia,h/1,erro,timeout,x\n',
        'busca,h|"a",incompleta,,x\n',
        'pdf,h/1,erro,HTTP 500,x\n',
    ):
        projeto = _projeto(tmp_path, nome=str(abs(hash(linha))))
        projeto.estado.write_text(CABECALHO + linha, encoding='utf-8')
        _log(projeto, '2026-10-28_100000')
        _final(projeto, ['a,b\n'], '2026-10-28_120000')
        assert gp.situacao(projeto).rotulo == gp.CONCLUIDO_COM_FALHAS


def test_interrompido_sem_final_ou_com_final_de_antes(tmp_path):
    projeto = _projeto(tmp_path)
    projeto.estado.write_text(CABECALHO + 'materia,h/1,ok,,x\n', encoding='utf-8')
    _log(projeto, '2026-10-28_100000')
    assert gp.situacao(projeto).rotulo == gp.INTERROMPIDO
    _final(projeto, ['a,b\n'], '2026-10-28_120000')
    _log(projeto, '2026-10-29_090000', 'retomada')  # retomada que parou no meio
    s = gp.situacao(projeto)
    assert (s.rotulo, s.materias) == (gp.INTERROMPIDO, 1)
    assert s.ultima_execucao == datetime(2026, 10, 29, 9, 0)


def test_projeto_antigo_sem_logs_usa_a_data_do_estado(tmp_path):
    projeto = _projeto(tmp_path)
    projeto.estado.write_text(CABECALHO + 'materia,h/1,ok,,x\n', encoding='utf-8')
    _datar(projeto.estado, '2026-10-20_100000')
    _final(projeto, ['a,b\n'], '2026-10-20_100500')
    s = gp.situacao(projeto)
    assert (s.rotulo, s.ultima_execucao.date().isoformat()) == (gp.CONCLUIDO, '2026-10-20')


def test_ler_a_situacao_nao_muda_o_estado(tmp_path):
    projeto = _projeto(tmp_path)
    conteudo = CABECALHO + 'materia,h/1,erro,x,y\nmateria,h/2,ok,,y\nlinha cortada'
    projeto.estado.write_text(conteudo, encoding='utf-8')
    antes = projeto.estado.stat().st_mtime_ns
    gp.situacao(projeto)
    assert projeto.estado.read_text(encoding='utf-8') == conteudo
    assert projeto.estado.stat().st_mtime_ns == antes


def test_milhar_com_ponto():
    s = gp.Situacao(gp.CONCLUIDO, datetime(2026, 10, 28), 1189)
    assert s.texto() == 'concluído · 28/10/2026 · 1.189 matérias'
    assert gp.Situacao(gp.CONCLUIDO, None, 1).texto().endswith('1 matéria')
