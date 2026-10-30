"""Escolha do projeto (ou do arquivo) em cada opção do menu.

As perguntas passam por `Perguntas` (menus com as setas ou opções
numeradas, veja `perguntas.py`). Nada aqui cria pastas: o projeto novo só é
criado quando a pessoa confirma (veja `principal`).
"""

from collections.abc import Callable, Sequence
from pathlib import Path

from sapyl.interface.perguntas import Opcao, Perguntas, Voltar
from sapyl.projeto import Projeto, nome_limpo, projetos_existentes, situacao

OUTRO_CSV = '__outro_csv__'

PERGUNTA_NOME = 'Nome do projeto (a pasta será <nome>_proj/)'
PERGUNTA_ENTRADA_AUTORIA = 'De onde vêm as matérias?'
PERGUNTA_CSV = 'Caminho do arquivo CSV (com a coluna Link Materia)'


def validar_nome(nome: str) -> str | None:
    """Mensagem de erro do nome do projeto, ou None se está bom."""
    if not nome:
        return 'O nome não pode ficar vazio.'
    if '/' in nome or '\\' in nome:
        return 'Não use barras ( / ou \\ ) no nome.'
    return None


def em_passos(passos: Sequence[Callable[[], object]]) -> None:
    """Roda as perguntas em ordem; `Voltar` numa delas repete a anterior.

    Cada passo guarda a resposta onde quiser (as anteriores ficam). `Voltar`
    no primeiro passo é repassado a quem chamou.
    """
    i = 0
    while i < len(passos):
        try:
            passos[i]()
            i += 1
        except Voltar:
            if i == 0:
                raise
            i -= 1


def abrir_ou_criar(
    raiz: str | Path, perguntas: Perguntas, voltar: bool = False
) -> tuple[Projeto, bool]:
    """Pergunta o nome. Devolve (Projeto, novo); a pasta de um projeto novo não é criada.

    Se o nome já existe, oferece retomar esse projeto ou escolher outro nome
    (`← Voltar` ali também pergunta o nome de novo). Um projeto existente
    nunca é sobrescrito. Com `voltar`, `Voltar` no nome é repassado.
    """
    while True:
        nome = nome_limpo(perguntas.texto(PERGUNTA_NOME, validar_nome, voltar=voltar))
        projeto = Projeto(raiz, nome)
        if not projeto.pasta.exists():
            return projeto, True
        try:
            escolha = perguntas.escolher(
                f'O projeto "{nome}" já existe.',
                [Opcao('Retomar este projeto', 'retomar'), Opcao('Escolher outro nome', 'outro')],
                voltar=True,
            )
        except Voltar:
            continue
        if escolha == 'retomar':
            return projeto, False


def resultado_mais_recente(projeto: Projeto) -> Path | None:
    """O resultado final do projeto, ou o `_ATUALIZADO_` mais novo, se houver um."""
    candidatos = [
        projeto.final,
        *projeto.pasta.glob(f'{projeto.nome}_resultado_final_ATUALIZADO_*.csv'),
    ]
    existentes = [c for c in candidatos if c.is_file()]
    return max(existentes, key=lambda c: c.stat().st_mtime) if existentes else None


def rotulo_do_projeto(projeto: Projeto) -> str:
    """`nome — concluído · 28/10/2026 · 1.189 matérias`."""
    return f'{projeto.nome} — {situacao(projeto).texto()}'


def escolher_projeto(
    raiz: str | Path, perguntas: Perguntas, texto: str, so_com_resultado: bool = False
) -> Projeto | None:
    """Um projeto da lista (`<nome>_proj/` na pasta), com a situação de cada um.

    Devolve None se não há projetos (avisa) ou se a pessoa escolhe `← Voltar`.
    """
    projetos = [Projeto(raiz, nome) for nome in projetos_existentes(raiz)]
    if so_com_resultado:
        projetos = [p for p in projetos if p.final.is_file()]
    if not projetos:
        tipo = 'com resultado final ' if so_com_resultado else ''
        perguntas.mostrar(f'Nenhum projeto {tipo}nesta pasta ({Path(raiz).resolve()}).')
        return None
    opcoes = [Opcao(rotulo_do_projeto(p), p.nome) for p in projetos]
    try:
        return Projeto(raiz, perguntas.escolher(texto, opcoes, voltar=True))
    except Voltar:
        return None


def _csv_em(raiz: str | Path, resposta: str) -> Path:
    caminho = Path(resposta).expanduser()
    return caminho if caminho.is_absolute() else Path(raiz) / caminho


def perguntar_csv(raiz: str | Path, perguntas: Perguntas, voltar: bool = False) -> Path:
    """Caminho de um CSV que existe (relativo à pasta de trabalho, ou absoluto)."""

    def validar(resposta: str) -> str | None:
        if not resposta:
            return 'Digite o caminho do arquivo.'
        caminho = _csv_em(raiz, resposta)
        if not caminho.is_file() or caminho.suffix.lower() != '.csv':
            return f'Não encontrei o arquivo CSV "{resposta}". Confira o caminho.'
        return None

    return _csv_em(raiz, perguntas.texto(PERGUNTA_CSV, validar, voltar=voltar))


def escolher_entrada_autoria(
    raiz: str | Path, perguntas: Perguntas
) -> tuple[Path, Projeto | None] | None:
    """Um projeto com resultado (usa o mais recente) ou um CSV avulso.

    Devolve (planilha de entrada, projeto ou None para um CSV avulso), ou None
    se a pessoa volta ao menu (`← Voltar` na lista, ou no caminho quando não há
    projetos; no caminho escolhido pela lista, `← Voltar` volta à lista).
    """
    projetos = [Projeto(raiz, nome) for nome in projetos_existentes(raiz)]
    projetos = [p for p in projetos if resultado_mais_recente(p) is not None]
    if not projetos:
        try:
            return perguntar_csv(raiz, perguntas, voltar=True), None
        except Voltar:
            return None
    opcoes = [Opcao(rotulo_do_projeto(p), p.nome) for p in projetos]
    opcoes.append(Opcao('Outro arquivo CSV…', OUTRO_CSV))
    while True:
        try:
            escolha = perguntas.escolher(PERGUNTA_ENTRADA_AUTORIA, opcoes, voltar=True)
        except Voltar:
            return None
        if escolha != OUTRO_CSV:
            break
        try:
            return perguntar_csv(raiz, perguntas, voltar=True), None
        except Voltar:
            continue
    projeto = Projeto(raiz, escolha)
    return resultado_mais_recente(projeto) or projeto.final, projeto
