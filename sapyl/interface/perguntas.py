"""Perguntas no terminal, em dois modos com as mesmas perguntas e respostas.

- `PerguntasMenu`: menus com as setas do teclado (`questionary`), usados
  quando o terminal é interativo.
- `PerguntasTexto`: opções numeradas, lidas por uma função (`input`, ou um
  roteiro nos testes). Usadas quando a entrada vem de um arquivo ou de outro
  programa, ou com `SAPYL_MENUS=0`.

`criar_perguntas` escolhe o modo. Ctrl+C numa pergunta sempre lança
`KeyboardInterrupt` (nunca vira uma resposta vazia).
"""

import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any, NamedTuple, Protocol

# Função que mostra a pergunta e devolve a resposta (`input`, ou um roteiro nos testes)
Leitor = Callable[[str], str]

# Confere uma resposta de texto: devolve a mensagem de erro, ou None se está boa
Validador = Callable[[str], str | None]

VARIAVEL_MENUS = 'SAPYL_MENUS'
# Dicas dos menus (no lugar das do questionary, em inglês)
DICA_ESCOLHER = '(setas e Enter)'
DICA_MARCAR = '(setas; ESPAÇO marca; Enter confirma)'
NADA_MARCADO = (
    'Nada marcado: marque com a barra de espaço (ou marque "Todos os estados") e depois Enter.'
)

SIM = ('s', 'sim', '1')
NAO = ('n', 'não', 'nao', '2')


class Opcao(NamedTuple):
    """Uma opção de menu: o texto mostrado e o valor devolvido."""

    rotulo: str
    valor: str


class Atalho(NamedTuple):
    """Uma opção da lista de marcar que vale por várias (ex.: Sul e Sudeste).

    `valor` é o que se digita no modo texto (ex.: `sul-sudeste`); `valores`
    vazio quer dizer "todas".
    """

    rotulo: str
    valor: str
    valores: tuple[str, ...]


class Voltar(Exception):  # noqa: N818 (é um pedido da pessoa, não um erro)
    """A pessoa pediu para voltar à pergunta anterior (`← Voltar`)."""


ROTULO_VOLTAR = '← Voltar'
_VOLTAR = '__voltar__'
TECLA_VOLTAR = '<'  # no modo texto, nas perguntas sem lista numerada


class Perguntas(Protocol):
    """O que o programa pergunta, nos dois modos.

    Com `voltar=True`, a pergunta oferece `← Voltar`; escolhê-lo lança `Voltar`.
    """

    def escolher(self, texto: str, opcoes: Sequence[Opcao], voltar: bool = False) -> str:
        """Uma opção da lista. Devolve o `valor` dela."""
        ...

    def sim_nao(self, texto: str, padrao: bool = False, voltar: bool = False) -> bool:
        """Sim ou não."""
        ...

    def marcar(
        self,
        texto: str,
        opcoes: Sequence[Opcao],
        atalhos: Sequence[Atalho],
        voltar: bool = False,
    ) -> list[str]:
        """Várias opções. Devolve os valores marcados; lista vazia = todas."""
        ...

    def texto(self, texto: str, validar: Validador, voltar: bool = False) -> str:
        """Texto livre (sem espaços nas pontas), repetido até `validar` aceitar."""
        ...

    def mostrar(self, texto: str) -> None:
        """Mostra um texto (sem pergunta)."""
        ...


def _juntar(
    marcados: Sequence[str], opcoes: Sequence[Opcao], atalhos: Sequence[Atalho]
) -> list[str]:
    """Valores das opções marcadas, com os atalhos expandidos, na ordem das opções."""
    escolhidos: set[str] = set()
    por_valor = {a.valor: a for a in atalhos}
    for valor in marcados:
        atalho = por_valor.get(valor)
        if atalho is None:
            escolhidos.add(valor)
        elif not atalho.valores:
            return []  # "todas"
        else:
            escolhidos.update(atalho.valores)
    return [o.valor for o in opcoes if o.valor in escolhidos]


def _com_voltar(opcoes: Sequence[Opcao], voltar: bool) -> list[Opcao]:
    return [*opcoes, Opcao(ROTULO_VOLTAR, _VOLTAR)] if voltar else list(opcoes)


class PerguntasTexto:
    """Perguntas com opções numeradas; respostas inválidas são pedidas de novo.

    `← Voltar` é a última opção numerada; nas outras perguntas, `<` volta.
    """

    def __init__(self, entrada: Leitor = input) -> None:
        self.entrada = entrada

    def _ler(self, texto: str) -> str:
        return str(self.entrada(texto)).strip()

    def _ler_ou_voltar(self, texto: str, voltar: bool) -> str:
        resposta = self._ler(texto)
        if voltar and resposta == TECLA_VOLTAR:
            raise Voltar
        return resposta

    def escolher(self, texto: str, opcoes: Sequence[Opcao], voltar: bool = False) -> str:
        """Lista numerada (`1- …`); devolve o valor da opção do número digitado."""
        opcoes = _com_voltar(opcoes, voltar)
        numeros = [str(i) for i in range(1, len(opcoes) + 1)]
        pergunta = (
            texto
            + '\n'
            + ''.join(f'{n}- {o.rotulo}\n' for n, o in zip(numeros, opcoes, strict=True))
        )
        lista = ', '.join(numeros[:-1]) + ' ou ' + numeros[-1] if len(numeros) > 1 else '1'
        while True:
            resposta = self._ler(pergunta)
            if resposta in numeros:
                valor = opcoes[int(resposta) - 1].valor
                if valor == _VOLTAR:
                    raise Voltar
                return valor
            print(f'Digite apenas {lista}.')

    def sim_nao(self, texto: str, padrao: bool = False, voltar: bool = False) -> bool:
        """Aceita s, n, sim, não, nao, 1 e 2; Enter vale o `padrao`; `<` volta."""
        dica = '(S/n' if padrao else '(s/N'
        dica += f'; {TECLA_VOLTAR} volta)' if voltar else ')'
        while True:
            resposta = self._ler_ou_voltar(f'{texto} {dica}\n', voltar).lower()
            if not resposta:
                return padrao
            if resposta in SIM:
                return True
            if resposta in NAO:
                return False
            print('Digite s (sim) ou n (não).')

    def marcar(
        self,
        texto: str,
        opcoes: Sequence[Opcao],
        atalhos: Sequence[Atalho],
        voltar: bool = False,
    ) -> list[str]:
        """Valores digitados separados por vírgula ou espaço; Enter = todas; `<` volta."""
        validos = {o.valor.lower(): o.valor for o in opcoes}
        validos.update({a.valor.lower(): a.valor for a in atalhos})
        exemplos = ', '.join(f'{a.valor} ({a.rotulo})' for a in atalhos)
        volta = f' {TECLA_VOLTAR}: volta.' if voltar else ''
        pergunta = (
            f'{texto}\nDigite separados por vírgula ou espaço '
            f'({", ".join(o.valor for o in opcoes)}), ou {exemplos}. Enter: todos.{volta}\n'
        )
        while True:
            resposta = self._ler_ou_voltar(pergunta, voltar)
            partes = [p for p in re.split(r'[,\s]+', resposta.lower()) if p]
            if not partes:
                return []
            desconhecidos = [p for p in partes if p not in validos]
            if not desconhecidos:
                return _juntar([validos[p] for p in partes], opcoes, atalhos)
            print('Não reconheci: ' + ', '.join(desconhecidos) + '.')

    def texto(self, texto: str, validar: Validador, voltar: bool = False) -> str:
        """Repete a pergunta enquanto `validar` devolver uma mensagem de erro; `<` volta."""
        dica = f' ({TECLA_VOLTAR} volta)' if voltar else ''
        while True:
            resposta = self._ler_ou_voltar(texto + dica + '\n', voltar)
            erro = validar(resposta)
            if erro is None:
                return resposta
            print(erro)

    def mostrar(self, texto: str) -> None:
        """Escreve o texto no terminal."""
        print(texto)


class PerguntasMenu:
    """Menus com as setas do teclado (`questionary`).

    `entrada` e `saida` são repassados ao `prompt_toolkit` (nos testes, uma
    entrada simulada); `console` é o console do `rich` para `mostrar`.
    `← Voltar` é a última opção das listas, o primeiro item da lista de marcar
    e, no texto, a resposta vazia.
    """

    def __init__(self, entrada: Any = None, saida: Any = None, console: Any = None) -> None:
        from rich.console import Console

        self._es = {k: v for k, v in (('input', entrada), ('output', saida)) if v is not None}
        self.console = console or Console()

    def _perguntar(self, pergunta: Any) -> Any:
        # unsafe_ask: Ctrl+C lança KeyboardInterrupt em vez de devolver None
        resposta = pergunta.unsafe_ask()
        if resposta == _VOLTAR:
            raise Voltar
        return resposta

    def escolher(self, texto: str, opcoes: Sequence[Opcao], voltar: bool = False) -> str:
        """Lista para escolher com as setas e Enter."""
        import questionary

        escolhas = [
            questionary.Choice(o.rotulo, value=o.valor) for o in _com_voltar(opcoes, voltar)
        ]
        pergunta = questionary.select(
            texto, choices=escolhas, instruction=DICA_ESCOLHER, **self._es
        )
        return self._perguntar(pergunta)

    def sim_nao(self, texto: str, padrao: bool = False, voltar: bool = False) -> bool:
        """`Sim` / `Não` com as setas; o cursor começa no `padrao`."""
        import questionary

        escolhas = [questionary.Choice('Sim', value=True), questionary.Choice('Não', value=False)]
        inicial = escolhas[0] if padrao else escolhas[1]
        if voltar:
            escolhas.append(questionary.Choice(ROTULO_VOLTAR, value=_VOLTAR))
        pergunta = questionary.select(
            texto, choices=escolhas, default=inicial, instruction=DICA_ESCOLHER, **self._es
        )
        return bool(self._perguntar(pergunta))

    def marcar(
        self,
        texto: str,
        opcoes: Sequence[Opcao],
        atalhos: Sequence[Atalho],
        voltar: bool = False,
    ) -> list[str]:
        """Lista de marcar (espaço marca, Enter confirma), com os atalhos no topo.

        Com `voltar`, o primeiro item é `← Voltar`: marcado, volta (o resto é ignorado).
        Enter sem nada marcado não vale: é fácil achar que o cursor numa opção a
        escolhe, sem apertar a barra de espaço. Para todas, marca-se o atalho.
        """
        import questionary

        escolhas: list[Any] = []
        if voltar:
            escolhas.append(questionary.Choice(ROTULO_VOLTAR, value=_VOLTAR))
        escolhas += [questionary.Choice(a.rotulo, value=a.valor) for a in atalhos]
        if atalhos:
            escolhas.append(questionary.Separator())
        escolhas += [questionary.Choice(o.rotulo, value=o.valor) for o in opcoes]
        pergunta = questionary.checkbox(
            texto,
            choices=escolhas,
            instruction=DICA_MARCAR,
            validate=lambda marcados: True if marcados else NADA_MARCADO,
            **self._es,
        )
        marcados = list(pergunta.unsafe_ask() or [])
        if _VOLTAR in marcados:
            raise Voltar
        return _juntar(marcados, opcoes, atalhos)

    def texto(self, texto: str, validar: Validador, voltar: bool = False) -> str:
        """Texto livre; o erro de `validar` aparece embaixo. Com `voltar`, vazio volta."""
        import questionary

        def conferir(valor: str) -> bool | str:
            if voltar and not valor.strip():
                return True
            erro = validar(valor.strip())
            return True if erro is None else erro

        dica = '(Enter vazio volta)' if voltar else ''
        resposta = str(
            self._perguntar(
                questionary.text(texto, validate=conferir, instruction=dica, **self._es)
            )
        ).strip()
        if voltar and not resposta:
            raise Voltar
        return resposta

    def mostrar(self, texto: str) -> None:
        """Escreve o texto como está (colchetes não viram formatação)."""
        self.console.print(texto, markup=False, highlight=False)


def usar_menus(
    entrada: Leitor,
    ambiente: Mapping[str, str] | None = None,
    stdin: Any = None,
    stdout: Any = None,
) -> bool:
    """Menus só com `input` num terminal interativo e sem `SAPYL_MENUS=0`."""
    ambiente = os.environ if ambiente is None else ambiente
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    if entrada is not input or ambiente.get(VARIAVEL_MENUS, '').strip() == '0':
        return False
    try:
        return bool(stdin.isatty() and stdout.isatty())
    except (AttributeError, ValueError):
        return False


def criar_perguntas(entrada: Leitor = input) -> Perguntas:
    """`PerguntasMenu` num terminal interativo; senão, `PerguntasTexto(entrada)`."""
    return PerguntasMenu() if usar_menus(entrada) else PerguntasTexto(entrada)
