"""Arquivo de estado: só acrescenta linhas, última linha vale, queda no meio."""
import pytest

from estado import ArquivoCSV, Estado, ler_csv, CAMPOS_ESTADO


def test_registrar_e_ler(tmp_path):
    caminho = tmp_path / 'p_estado.csv'
    estado = Estado(caminho)
    assert estado.status('materia', 'h/1') is None
    estado.registrar('materia', 'h/1', 'erro', 'HTTP 429')
    estado.registrar('materia', 'h/2', 'ok')
    assert estado.status('materia', 'h/1') == 'erro'
    assert estado.erro('materia', 'h/1') == 'HTTP 429'
    estado.fechar()
    linhas = ler_csv(caminho, CAMPOS_ESTADO)
    assert [(l['etapa'], l['chave'], l['status']) for l in linhas] == [
        ('materia', 'h/1', 'erro'), ('materia', 'h/2', 'ok')]
    assert all(l['quando'] for l in linhas)


def test_ultima_linha_vale_e_historico_e_mantido(tmp_path):
    caminho = tmp_path / 'e.csv'
    estado = Estado(caminho)
    estado.registrar('materia', 'h/1', 'erro', 'timeout')
    estado.registrar('materia', 'h/1', 'ok')
    estado.registrar('busca', 'h|x', 'incompleta', 'HTTP 500')
    estado.fechar()

    reaberto = Estado(caminho)
    assert reaberto.status('materia', 'h/1') == 'ok'
    assert reaberto.status('busca', 'h|x') == 'incompleta'
    reaberto.registrar('busca', 'h|x', 'completa')
    reaberto.fechar()
    assert len(ler_csv(caminho, CAMPOS_ESTADO)) == 4
    assert Estado(caminho).status('busca', 'h|x') == 'completa'


def test_linha_cortada_no_meio_e_ignorada(tmp_path):
    caminho = tmp_path / 'e.csv'
    estado = Estado(caminho)
    estado.registrar('materia', 'h/1', 'ok')
    estado.fechar()
    with open(caminho, 'a', encoding='utf-8') as f:
        f.write('materia,h/2,o')                 # queda no meio da gravação
    reaberto = Estado(caminho)
    assert reaberto.status('materia', 'h/1') == 'ok'
    assert reaberto.status('materia', 'h/2') is None
    reaberto.registrar('materia', 'h/3', 'ok')   # começa numa linha nova
    reaberto.fechar()
    final = Estado(caminho)
    assert final.status('materia', 'h/3') == 'ok'
    assert final.status('materia', 'h/2') is None


def test_chaves_e_contagens(tmp_path):
    estado = Estado(tmp_path / 'e.csv')
    for k, s in [('h/1', 'ok'), ('h/2', 'erro'), ('h/3', 'ok'), ('h/1', 'ok')]:
        estado.registrar('materia', k, s)
    estado.registrar('pdf', 'h/1', 'sem_pdf')
    assert sorted(estado.chaves('materia', 'ok')) == ['h/1', 'h/3']
    assert sorted(estado.chaves('materia')) == ['h/1', 'h/2', 'h/3']
    assert estado.contagens('materia') == {'ok': 2, 'erro': 1}
    assert estado.contagens('materia', {'h/2'}) == {'erro': 1}
    assert estado.contagens('pdf') == {'sem_pdf': 1}


def test_arquivo_csv_com_cabecalho_e_texto_com_virgulas(tmp_path):
    caminho = tmp_path / 'dados.csv'
    arquivo = ArquivoCSV(caminho, ['a', 'b'])
    arquivo.anexar({'a': 'x, "y"\nz', 'b': 1, 'extra': 'ignorado'})
    arquivo.fechar()
    ArquivoCSV(caminho, ['a', 'b']).fechar()     # reabrir não repete o cabeçalho
    assert ler_csv(caminho, ['a', 'b']) == [{'a': 'x, "y"\nz', 'b': '1'}]


def test_cabecalho_errado_e_detectado(tmp_path):
    caminho = tmp_path / 'x.csv'
    caminho.write_text('outra,coisa\n1,2\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Cabeçalho inesperado'):
        ler_csv(caminho, ['a', 'b'])
    assert ler_csv(tmp_path / 'nao_existe.csv', ['a']) == []
