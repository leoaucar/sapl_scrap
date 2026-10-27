"""Teste de ponta a ponta contra um SAPL falso (TR-9).

Duas casas: Rio Branco com API, Cascavel sem API (só HTML). A busca de Rio
Branco tem 40 páginas (passa do limite de 35/min), uma página recebe 429 e
uma matéria falha de vez. Confere tabela final, estado, PDFs, resumo,
retomada e que nenhum site recebe mais de 35 requisições em 60 s.
"""
import copy
import json
import logging

import pytest

from sapyl import materias
from sapyl import principal as programa
from sapyl.estado import Estado
from sapyl.cliente_http import ClienteSAPL
from tests.apoio import RelogioFalso, SaplFalso, SessaoFalsa, ler_fixture, roteiro
from sapyl.tabela import ler_final

RB = 'https://sapl.riobranco.ac.leg.br/'
CV = 'https://sapl.cascavel.pr.leg.br/'
F_RB, F_CV = 'sapl/sapl.riobranco.ac.leg.br/', 'sapl/sapl.cascavel.pr.leg.br/'
P = '"plano+diretor"'
O = '"orçamento"+"emenda+impositiva"'
PAGINAS_RB = 40
FALHA = materias.url_api(RB, '44086')        # falha de vez (4 × 503)


def _api_minima(sapl_id, titulo):
    dados = copy.deepcopy(json.loads(ler_fixture(F_RB + 'api_materia_34049.json')))
    dados.update(id=int(sapl_id), __str__=titulo, anexadas=[], texto_original=None)
    return dados


def montar(projeto_tmp):
    """Sessão, relógio e cliente novos, com o SAPL falso das duas casas."""
    falso = SaplFalso()
    falso.casa(RB, buscas={P: [F_RB + 'busca_p1.html'] + ['<a href="/materia/34049">x</a>'] * (PAGINAS_RB - 1),
                       O: [F_RB + 'busca_vazia.html']},
               api={'34049': F_RB + 'api_materia_34049.json', '46496': F_RB + 'api_materia_46496.json',
                    '37559': _api_minima('37559', 'Projeto de Lei Complementar nº 26 de 2025'),
                    '44086': _api_minima('44086', 'Indicação nº 1 de 2026')},
               nomes={('tipomaterialegislativa', '1'): 'Projeto de Lei Ordinária',
                      ('tipomaterialegislativa', '15'): 'Veto',
                      ('regimetramitacao', '1'): 'Ordinária'},
               pdfs={'34049': b'%PDF-34049', '46496': b'%PDF-46496'})
    falso.casa(CV, api=None,
               buscas={P: [F_CV + 'busca_p1.html'], O: ['<a href="/materia/38415">r</a>']},
               html={'38415': F_CV + 'materia_38415.html', '43301': F_CV + 'materia_43301.html',
                     '43300': 'sinteticas/materia_sem_pdf.html', '42263': 'sinteticas/materia_sem_data.html'},
               pdfs={'38415': b'%PDF-38415'})
    falso.falhar(f'{RB}sistema/search/?page=2&q={P}', 429)
    falso.falhar(FALHA, 503, 503, 503, 503)

    relogio, sessao = RelogioFalso(), SessaoFalsa()
    sessao.rota(falso)
    horarios = []
    get_original = sessao.get

    def get_com_horario(url, **kwargs):
        horarios.append((url.split('/')[2], relogio.agora()))
        return get_original(url, **kwargs)
    sessao.get = get_com_horario
    cliente = ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)

    arquivos = projeto_tmp / 'arquivos_csv'
    import pandas as pd
    pd.DataFrame({'UF': ['AC', 'PR'], 'URL do serviço': [RB, CV]}).to_excel(
        arquivos / 'casas_legislativas.xlsx', index=False)
    return cliente, sessao, horarios


NOVO = ('2', 'p', '2', '1', '1')      # projeto novo "p", sem filtro, todas as casas, com downloads


@pytest.fixture
def execucao(projeto_tmp, caplog):
    cliente, sessao, horarios = montar(projeto_tmp)
    with caplog.at_level(logging.INFO, logger='sapl_scrap'):
        assert programa.main(roteiro(*NOVO), cliente, projeto_tmp) == 0
    resumo = [r.getMessage() for r in caplog.records if 'Resumo' in r.getMessage()][-1]
    return projeto_tmp / 'p_proj', sessao, horarios, resumo


def test_tabela_final(execucao):
    pasta, _, _, _ = execucao
    final = ler_final(pasta / 'p_resultado_final.csv')
    chaves = list(zip(final['Link Casa'], final['sapl_id']))
    assert len(chaves) == len(set(chaves)) == 8                  # sem duplicatas
    ok = final[final['status'] == 'ok']
    assert (ok['Titulo'] != '').all()                            # nenhuma linha ok vazia
    erros = final[final['status'] == 'erro']
    assert erros['sapl_id'].tolist() == ['44086'] and erros['erro'].tolist() == ['HTTP 503']
    por_id = final.set_index('sapl_id')
    assert por_id.at['38415', 'Palavras'] == f'{P}; {O}'
    assert por_id.at['34049', 'fonte'] == 'api' and por_id.at['38415', 'fonte'] == 'html'
    assert por_id.at['46496', 'Materia Anexada'] == 'Projeto de Lei Complementar nº 26 de 2025'
    assert por_id.at['46496', 'Tipo de Materia Legislativa'] == 'Veto'
    assert por_id.at['42263', 'Data'] == '' and por_id.at['34049', 'Data'] == '02/07/2025'


def test_downloads_e_estado(execucao):
    pasta, _, _, _ = execucao
    final = ler_final(pasta / 'p_resultado_final.csv').set_index('sapl_id')
    assert sorted(p.name for p in (pasta / 'downloads').iterdir()) == [
        'sapl.cascavel.pr.leg.br_38415.pdf', 'sapl.riobranco.ac.leg.br_34049.pdf',
        'sapl.riobranco.ac.leg.br_46496.pdf']
    assert final.at['43300', 'download_status'] == 'sem_pdf'
    assert final.at['44086', 'download_status'] == ''
    # PDFs de 43301 e 42263 não existem no servidor falso (404)
    assert final.at['43301', 'download_status'] == 'erro'
    estado = Estado(pasta / 'p_estado.csv')
    assert estado.contagens('materia') == {'ok': 7, 'erro': 1}
    assert estado.contagens('busca') == {'completa': 4}
    estado.fechar()


def test_resumo(execucao):
    _, _, _, resumo = execucao
    assert 'Casas pesquisadas: 2 (0 com alguma busca incompleta; 0 fora do ar' in resumo
    assert '8 únicas, 7 raspadas, 1 com erro' in resumo
    assert 'Downloads: 3 baixados, 2 com erro, 2 sem texto original' in resumo
    assert 'retomar este projeto' in resumo


def test_limite_de_35_por_minuto_em_cada_site(execucao):
    _, _, horarios, _ = execucao
    for site in {s for s, _ in horarios}:
        tempos = sorted(t for s, t in horarios if s == site)
        for i, t in enumerate(tempos):
            assert sum(1 for u in tempos[i:] if u - t < 60) <= 35, site
    assert len([1 for s, _ in horarios if s == 'sapl.riobranco.ac.leg.br']) > 35


def test_429_na_busca_foi_esperado_e_refeito(execucao):
    _, sessao, _, _ = execucao
    assert sessao.contar(f'{RB}sistema/search/?page=2&q={P}') == 2


def test_retomada_so_pede_a_materia_que_falhou(execucao, projeto_tmp):
    pasta, sessao, _, _ = execucao
    sessao.pedidos.clear()
    assert programa.main(roteiro('2', 'p', '1'), sessao_cliente(sessao), projeto_tmp) == 0
    # nova execução refaz as consultas de nomes (cache da execução), mas das
    # matérias só pede a que falhou
    materias_pedidas = [u for u in sessao.pedidos
                        if '/materia/' in u and '/media/' not in u and 'tipomateria' not in u
                        and 'regimetramitacao' not in u]
    assert materias_pedidas == [FALHA]
    assert not any('/sistema/search/' in u for u in sessao.pedidos)
    final = ler_final(pasta / 'p_resultado_final.csv')
    assert set(final['status']) == {'ok'}


def sessao_cliente(sessao):
    relogio = RelogioFalso(5000)
    return ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)


def test_interrompida_e_retomada_da_o_mesmo_resultado(projeto_tmp, monkeypatch):
    # execução sem interrupção, projeto "a"
    cliente, _, _ = montar(projeto_tmp)
    programa.main(roteiro('2', 'a', '2', '1', '1'), cliente, projeto_tmp)

    # execução interrompida na 4ª matéria e retomada, projeto "b"
    cliente, _, _ = montar(projeto_tmp)
    original, chamadas = materias.raspar_materia, []

    def cair_na_quarta(link, *args):
        chamadas.append(link['chave'])
        if len(chamadas) == 4:
            raise KeyboardInterrupt
        return original(link, *args)
    monkeypatch.setattr(materias, 'raspar_materia', cair_na_quarta)
    # a execução "a" criou a tabela geral de casas: aparece a pergunta de reaproveitá-la
    assert programa.main(roteiro('2', 'b', '2', '2', '1', '1'), cliente, projeto_tmp) == 1
    monkeypatch.setattr(materias, 'raspar_materia', original)
    assert programa.main(roteiro('2', 'b', '1'), cliente, projeto_tmp) == 0

    a = ler_final(projeto_tmp / 'a_proj' / 'a_resultado_final.csv').drop(columns=['raspada_em'])
    b = ler_final(projeto_tmp / 'b_proj' / 'b_resultado_final.csv').drop(columns=['raspada_em'])
    assert a.equals(b)
    assert sorted(p.name for p in (projeto_tmp / 'b_proj' / 'downloads').iterdir()) == \
        sorted(p.name for p in (projeto_tmp / 'a_proj' / 'downloads').iterdir())


def test_retomada_com_cliente_novo_respeita_o_limite(projeto_tmp, monkeypatch):
    """Achado V2: o programa retomado é outro processo, com o limitador vazio."""
    cliente, sessao, horarios = montar(projeto_tmp)
    relogio = cliente.relogio.__self__
    historico = str(projeto_tmp / '.sapl_historico.json')
    primeiro = ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir,
                           historico=historico, relogio_parede=relogio.agora)
    original, chamadas = materias.raspar_materia, []

    def cair(link, *args):
        chamadas.append(1)
        if len(chamadas) == 6:
            raise KeyboardInterrupt
        return original(link, *args)
    monkeypatch.setattr(materias, 'raspar_materia', cair)
    assert programa.main(roteiro(*NOVO), primeiro, projeto_tmp) == 1
    monkeypatch.setattr(materias, 'raspar_materia', original)

    segundo = ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir,
                          historico=historico, relogio_parede=relogio.agora)
    assert programa.main(roteiro('2', 'p', '1'), segundo, projeto_tmp) == 0
    for site in {s for s, _ in horarios}:
        tempos = sorted(t for s, t in horarios if s == site)
        for i, t in enumerate(tempos):
            assert sum(1 for u in tempos[i:] if u - t < 60) <= 35, site
