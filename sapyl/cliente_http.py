"""Cliente HTTP único para todos os acessos ao SAPL.

Garante, para cada site (host):
- no máximo `LIMITE_POR_MINUTO` requisições em qualquer janela de 60 s
  (contando as retentativas);
- em `HTTP 429`, espera o `Retry-After` (bloqueando o site inteiro) e tenta
  de novo;
- em erro de rede, timeout ou 5xx, tenta de novo com esperas crescentes;
- nunca tenta para sempre: depois de `max_tentativas`, devolve a falha com o
  motivo (`HTTP 429`, `HTTP 503`, `timeout`, `conexao`).

Com `historico` (um arquivo JSON), os horários das requisições recentes de
cada site são guardados no disco a cada requisição e lidos quando o cliente
começa. Assim, uma execução retomada logo depois de interrompida (ou outro
projeto rodado em seguida) não passa do limite somando as duas.

404 e outros 4xx voltam na hora, sem nova tentativa: quem chamou decide
(fim da paginação, casa sem API, matéria inexistente).

Cada tentativa gera uma linha DEBUG no log:
`<host> | <url> | <status ou erro> | tentativa <n> | espera <s> | enviada <hora>`.
A hora de envio (com milissegundos) é a que conta para o limite; a hora da
linha do log é a da resposta, que pode chegar segundos depois.
"""

import json
import os
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import requests

from sapyl import registro

# Limite observado nos servidores do SAPL (teste de 15/10/2026)
LIMITE_POR_MINUTO = 35
JANELA_SEGUNDOS = 60.0
MAX_TENTATIVAS = 4
ESPERAS_ERRO = (5, 15, 45)  # segundos, para erro de rede/timeout/5xx
RETRY_AFTER_PADRAO = 60
RETRY_AFTER_MAXIMO = 300
TIMEOUT_PADRAO = (10, 30)  # (conexão, leitura), em segundos
ESPERA_MINIMA = 0.01  # segundos
USER_AGENT = 'sapl_scrap (pesquisa; +https://github.com/leoaucar/sapl_scrap)'

log = registro.logger('http')


@dataclass
class Resposta:
    """Resultado de `ClienteSAPL.get`. Se `ok` é False, `erro` diz o motivo."""

    url: str
    ok: bool
    status: int | None = None  # None: erro de rede
    erro: str = ''
    tentativas: int = 0
    bruta: Any = None  # requests.Response (ou equivalente)

    @property
    def texto(self) -> str:
        """Corpo da resposta como texto ('' se não houve resposta)."""
        return self.bruta.text if self.bruta is not None else ''

    def json(self) -> Any:
        """Corpo como JSON. Lança ValueError se não for JSON."""
        return self.bruta.json()

    def iter_content(self, tamanho: int) -> Iterator[bytes]:
        """Corpo aos pedaços de `tamanho` bytes (para downloads com `stream=True`)."""
        return self.bruta.iter_content(tamanho)

    def fechar(self) -> None:
        """Libera a conexão (necessário com `stream=True`)."""
        if self.bruta is not None:
            self.bruta.close()


def criar_sessao() -> requests.Session:
    """Sessão `requests` com o User-Agent do programa."""
    sessao = requests.Session()
    sessao.headers['User-Agent'] = USER_AGENT
    return sessao


def ler_retry_after(valor: str | None, agora_epoch: float | None = None) -> float:
    """Segundos de espera a partir do cabeçalho Retry-After (número ou data HTTP)."""
    if valor is None or str(valor).strip() == '':
        return RETRY_AFTER_PADRAO
    valor = str(valor).strip()
    try:
        segundos = float(valor)
    except ValueError:
        try:
            data = parsedate_to_datetime(valor)
            agora_epoch = time.time() if agora_epoch is None else agora_epoch
            segundos = data.timestamp() - agora_epoch
        except (TypeError, ValueError, OverflowError):
            return RETRY_AFTER_PADRAO
    return min(max(segundos, 1), RETRY_AFTER_MAXIMO)


class ClienteSAPL:
    """Faz GETs respeitando o limite por site. Uma instância por execução."""

    def __init__(
        self,
        sessao: Any = None,
        relogio: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], None] = time.sleep,
        limite_por_minuto: int = LIMITE_POR_MINUTO,
        max_tentativas: int = MAX_TENTATIVAS,
        timeout: tuple[float, float] = TIMEOUT_PADRAO,
        historico: str | None = None,
        relogio_parede: Callable[[], float] = time.time,
    ) -> None:
        self.sessao = sessao if sessao is not None else criar_sessao()
        self.relogio = relogio
        self.relogio_parede = relogio_parede
        self.dormir = dormir
        self.limite = limite_por_minuto
        self.max_tentativas = max_tentativas
        self.timeout = timeout
        self.historico = historico
        self._janelas = defaultdict(deque)  # host -> horários das últimas requisições
        self._parede = defaultdict(deque)  # os mesmos horários, no relógio de parede
        self._bloqueado_ate = {}  # host -> horário (após um 429)
        self._bloqueado_parede = {}
        self.total_requisicoes = 0
        if historico:
            self._carregar_historico()

    # --- Histórico em disco (limite entre execuções) -------------------------

    def _carregar_historico(self):
        try:
            with open(self.historico, encoding='utf-8') as arquivo:
                dados = json.load(arquivo)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as erro:
            log.warning('Histórico de requisições ilegível (%s): começando sem ele', erro)
            return
        agora, parede = self.relogio(), self.relogio_parede()
        for host, horarios in (dados.get('requisicoes') or {}).items():
            for t in sorted(horarios)[-self.limite :]:
                if parede - t < JANELA_SEGUNDOS:
                    self._janelas[host].append(agora - (parede - t))
                    self._parede[host].append(t)
        for host, ate in (dados.get('bloqueios') or {}).items():
            if ate > parede:
                self._bloqueado_ate[host] = agora + (ate - parede)
                self._bloqueado_parede[host] = ate

    def _salvar_historico(self):
        parede = self.relogio_parede()
        dados = {
            'requisicoes': {
                h: [t for t in ts if parede - t < JANELA_SEGUNDOS] for h, ts in self._parede.items()
            },
            'bloqueios': {h: t for h, t in self._bloqueado_parede.items() if t > parede},
        }
        dados['requisicoes'] = {h: ts for h, ts in dados['requisicoes'].items() if ts}
        temporario = f'{self.historico}.tmp'
        try:
            with open(temporario, 'w', encoding='utf-8') as arquivo:
                json.dump(dados, arquivo)
            os.replace(temporario, self.historico)
        except OSError as erro:
            log.warning('Não foi possível gravar o histórico de requisições: %s', erro)

    def _aguardar_vez(self, host):
        """Dorme o necessário para a próxima requisição a `host` respeitar o limite."""
        while True:
            agora = self.relogio()
            espera = self._bloqueado_ate.get(host, 0) - agora
            if espera <= 0:
                janela = self._janelas[host]
                while janela and agora - janela[0] >= JANELA_SEGUNDOS:
                    janela.popleft()
                if len(janela) < self.limite:
                    janela.append(agora)
                    parede = self._parede[host]
                    parede.append(self.relogio_parede())
                    while len(parede) > self.limite:
                        parede.popleft()
                    if self.historico:
                        self._salvar_historico()
                    return
                espera = JANELA_SEGUNDOS - (agora - janela[0])
            # Espera mínima: evita laço infinito com esperas de 1e-14 s (arredondamento)
            self.dormir(max(espera, ESPERA_MINIMA))

    def get(
        self,
        url: str,
        stream: bool = False,
        timeout: tuple[float, float] | None = None,
        max_tentativas: int | None = None,
    ) -> Resposta:
        """GET respeitando o limite do site, com retentativas. Nunca lança erro de rede."""
        host = urlparse(url).hostname or ''
        tentativas = max_tentativas or self.max_tentativas
        status, erro = None, ''
        for tentativa in range(1, tentativas + 1):
            self._aguardar_vez(host)
            self.total_requisicoes += 1
            enviada = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            bruta = None
            try:
                bruta = self.sessao.get(url, timeout=timeout or self.timeout, stream=stream)
            except requests.Timeout:
                status, erro = None, 'timeout'
            except requests.RequestException:
                status, erro = None, 'conexao'
            else:
                status = bruta.status_code
                if status == 200:
                    self._registrar(host, url, status, tentativa, 0, enviada)
                    return Resposta(url, True, status, '', tentativa, bruta)
                erro = f'HTTP {status}'
                if status != 429 and status < 500:
                    # 404 e demais 4xx: definitivos, sem nova tentativa
                    self._registrar(host, url, status, tentativa, 0, enviada)
                    return Resposta(url, False, status, erro, tentativa, bruta)

            ultima = tentativa == tentativas
            if status == 429:
                espera = ler_retry_after(bruta.headers.get('Retry-After'))
            else:
                espera = ESPERAS_ERRO[min(tentativa - 1, len(ESPERAS_ERRO) - 1)]
            self._registrar(
                host,
                url,
                status if status is not None else erro,
                tentativa,
                0 if ultima else espera,
                enviada,
            )
            if bruta is not None:
                bruta.close()
            if ultima:
                break
            if status == 429:
                # O site inteiro fica bloqueado até passar o Retry-After
                self._bloqueado_ate[host] = self.relogio() + espera
                self._bloqueado_parede[host] = self.relogio_parede() + espera
                if self.historico:
                    self._salvar_historico()
            else:
                self.dormir(espera)
        log.warning('Falha em %s: %s (%d tentativas)', url, erro, tentativas)
        return Resposta(url, False, status, erro, tentativas, None)

    @staticmethod
    def _registrar(host, url, resultado, tentativa, espera, enviada):
        log.debug(
            '%s | %s | %s | tentativa %d | espera %g | enviada %s',
            host,
            url,
            resultado,
            tentativa,
            espera,
            enviada,
        )
