"""Limites e valores padrão do programa, num lugar só.

- Por site (host): no máximo `LIMITE_POR_SITE` requisições em qualquer
  janela de `JANELA_SEGUNDOS` + `MARGEM_SEGUNDOS`.
- Por servidor (o endereço IP do site): quase todas as casas ficam no mesmo
  servidor do Interlegis, então a soma das casas de um servidor também tem um
  teto, `LIMITE_POR_SERVIDOR` por minuto. Se casas diferentes do mesmo
  servidor recebem 429 em `JANELA_LENTIDAO` segundos, o teto cai pela metade
  (nunca abaixo de `PISO_POR_SERVIDOR`).
- `CASAS_AO_MESMO_TEMPO`: quantas casas são processadas em paralelo.

Os dois últimos valores ficam no `config.json` do projeto, em `paralelo`, e
podem ser mudados à mão antes de retomar (veja `validar_paralelo`).
"""

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

# Limite observado nos servidores do SAPL (teste de 15/10/2026)
LIMITE_POR_SITE = 35
JANELA_SEGUNDOS = 60.0
# Folga além da janela (achado V4 da spec 1): com atraso de rede, requisições
# enviadas a 60,0 s uma da outra podem chegar ao servidor a menos de 60 s.
MARGEM_SEGUNDOS = 1.0

# Teto inicial por servidor (requisições por minuto, somando as casas dele)
LIMITE_POR_SERVIDOR = 120
# O teto nunca cai abaixo disto: uma casa na velocidade máxima
PISO_POR_SERVIDOR = LIMITE_POR_SITE
# 429 de casas diferentes do mesmo servidor dentro deste tempo reduzem o teto
JANELA_LENTIDAO = 600.0

CASAS_AO_MESMO_TEMPO = 8
# De quanto em quanto tempo aparece a linha de progresso geral (segundos)
PROGRESSO_A_CADA = 60.0

CHAVE_PARALELO = 'paralelo'


class ConfiguracaoInvalida(ValueError):
    """Valor inválido em `paralelo` no config.json do projeto."""


class EntradaInvalida(ValueError):
    """Arquivo de entrada ausente ou errado (palavras-chave, planilha de casas).

    A mensagem já está pronta para a pessoa: o que faltou, onde e como corrigir.
    """


def padroes_paralelo() -> dict[str, int]:
    """Valores padrão de `paralelo` (gravados no config.json de um projeto novo)."""
    return {
        'casas_ao_mesmo_tempo': CASAS_AO_MESMO_TEMPO,
        'limite_por_servidor': LIMITE_POR_SERVIDOR,
    }


def _minimos() -> dict[str, int]:
    return {'casas_ao_mesmo_tempo': 1, 'limite_por_servidor': PISO_POR_SERVIDOR}


def validar_paralelo(dados: Any) -> dict[str, int]:
    """Confere `paralelo` do config.json e completa o que falta com os padrões.

    Cada valor tem de ser um número inteiro, no mínimo 1 casa ao mesmo tempo e
    35 requisições por minuto por servidor. Lança `ConfiguracaoInvalida` com o
    nome da chave e o que é aceito.
    """
    if dados is None:
        dados = {}
    if not isinstance(dados, dict):
        raise ConfiguracaoInvalida(
            f'"{CHAVE_PARALELO}" tem de ser um objeto, por exemplo {padroes_paralelo()}'
        )
    valores = padroes_paralelo()
    minimos = _minimos()
    desconhecidas = sorted(set(dados) - set(valores))
    if desconhecidas:
        raise ConfiguracaoInvalida(
            f'chave desconhecida em "{CHAVE_PARALELO}": {", ".join(desconhecidas)} '
            f'(as aceitas são {", ".join(valores)})'
        )
    for chave, valor in dados.items():
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < minimos[chave]:
            raise ConfiguracaoInvalida(
                f'"{CHAVE_PARALELO}.{chave}" = {valor!r}: tem de ser um número inteiro, '
                f'no mínimo {minimos[chave]}'
            )
        valores[chave] = valor
    return valores


T = TypeVar('T')
# Como rodar uma tarefa para cada casa: `mapear(tarefa, casas)` devolve os
# resultados na ordem de `casas`. O padrão é uma casa por vez; a interface
# passa `sapyl.execucao.por_casa`, que roda várias ao mesmo tempo.
Mapear = Callable[[Callable[[str], T], Sequence[str]], list[T]]


def em_sequencia(tarefa: Callable[[str], T], casas: Sequence[str]) -> list[T]:
    """Roda `tarefa` para cada casa, uma por vez (o `Mapear` padrão)."""
    return [tarefa(casa) for casa in casas]
