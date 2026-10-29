"""Cliente HTTP único para todos os acessos ao SAPL.

Garante, para cada site (host):
- no máximo `LIMITE_POR_MINUTO` requisições em qualquer janela de 60 s
  (contando as retentativas);
- em `HTTP 429`, espera o `Retry-After` (bloqueando o site inteiro) e tenta
  de novo;
- em erro de rede, timeout ou 5xx, tenta de novo com esperas crescentes;
- nunca tenta para sempre: depois de `max_tentativas`, devolve a falha com o
  motivo (`HTTP 429`, `HTTP 503`, `timeout`, `conexao`);
- erros que não passam sozinhos voltam na hora, numa tentativa só:
  certificado inválido (`ssl`) e nome que não existe mais no DNS (`dns`).

Por servidor (o endereço IP do site, `servidor_de`): quase todas as casas
ficam no mesmo servidor do Interlegis, então cada requisição também conta na
janela do servidor, com no máximo `limite_por_servidor` requisições em
qualquer janela de 60 s (+ a margem), somando todas as casas dele. Uma
requisição espera até o site **e** o servidor terem vaga. Se sites
diferentes do mesmo servidor recebem 429 em menos de 10 minutos, o teto desse
servidor cai pela metade até o fim da execução (nunca abaixo de 35); cada
redução vai para o log e para `reducoes`.

Com `historico` (um arquivo JSON), os horários das requisições recentes de
cada site e de cada servidor são guardados no disco a cada requisição e lidos quando o cliente
começa. Assim, uma execução retomada logo depois de interrompida (ou outro
projeto rodado em seguida) não passa do limite somando as duas.

Várias casas podem usar o mesmo cliente ao mesmo tempo (threads): uma trava
protege as janelas, os bloqueios e o histórico; cada thread tem a sua sessão
`requests`; as esperas acontecem fora da trava. Com o evento `parar` ligado
(Ctrl+C), toda espera acaba na hora e a próxima requisição lança
`Interrompido`.

404 e outros 4xx voltam na hora, sem nova tentativa: quem chamou decide
(fim da paginação, casa sem API, matéria inexistente).

Cada tentativa gera uma linha DEBUG no log:
`<host> | <url> | <status ou erro> | tentativa <n> | espera <s> | enviada <hora>`.
A hora de envio (com milissegundos) é a que conta para o limite; a hora da
linha do log é a da resposta, que pode chegar segundos depois.
"""

import json
import os
import socket
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import requests
from urllib3.exceptions import NameResolutionError

from sapyl import __version__, registro
from sapyl.padroes import (
    JANELA_LENTIDAO,
    JANELA_SEGUNDOS,
    LIMITE_POR_SERVIDOR,
    LIMITE_POR_SITE,
    MARGEM_SEGUNDOS,
    PISO_POR_SERVIDOR,
)

# Nomes antigos (os valores ficam em `sapyl.padroes`). Com a margem, a 1ª e a
# 36ª requisição a um site saem sempre a pelo menos 61 s uma da outra.
LIMITE_POR_MINUTO = LIMITE_POR_SITE
JANELA_COM_MARGEM = JANELA_SEGUNDOS + MARGEM_SEGUNDOS
MAX_TENTATIVAS = 4
ESPERAS_ERRO = (5, 15, 45)  # segundos, para erro de rede/timeout/5xx
RETRY_AFTER_PADRAO = 60
RETRY_AFTER_MAXIMO = 300
TIMEOUT_PADRAO = (10, 30)  # (conexão, leitura), em segundos
ESPERA_MINIMA = 0.01  # segundos
USER_AGENT = f'SAPyL/{__version__} (pesquisa; +https://github.com/leoaucar/sapyl)'

log = registro.logger('http')

# Quantos níveis de "causado por" seguir ao procurar a causa de um erro de rede
PROFUNDIDADE_CAUSAS = 8


class Interrompido(KeyboardInterrupt):
    """A execução foi interrompida (Ctrl+C): o cliente não faz mais requisições.

    É um `KeyboardInterrupt`, então quem já trata o Ctrl+C trata isto também.
    """


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


def _causas(erro: BaseException) -> list[BaseException]:
    """O erro e as exceções que o causaram (`__cause__`, `__context__`, `args`, `reason`).

    O `requests` embrulha o erro original: ConnectionError -> MaxRetryError
    (em `args`) -> `.reason` NameResolutionError -> socket.gaierror.
    """
    achadas, fila, vistas = [], [(erro, 0)], set()
    while fila:
        atual, nivel = fila.pop(0)
        if not isinstance(atual, BaseException) or id(atual) in vistas:
            continue
        vistas.add(id(atual))
        achadas.append(atual)
        if nivel >= PROFUNDIDADE_CAUSAS:
            continue
        seguintes = [getattr(atual, 'reason', None), atual.__cause__, atual.__context__]
        seguintes += list(getattr(atual, 'args', ()))
        fila += [(s, nivel + 1) for s in seguintes]
    return achadas


def motivo_permanente(erro: BaseException) -> str:
    """'ssl' ou 'dns' se o erro não vai passar tentando de novo; '' nos demais."""
    if isinstance(erro, requests.exceptions.SSLError):
        return 'ssl'
    if any(isinstance(c, (NameResolutionError, socket.gaierror)) for c in _causas(erro)):
        return 'dns'
    return ''


def criar_sessao() -> requests.Session:
    """Sessão `requests` com o User-Agent do programa."""
    sessao = requests.Session()
    sessao.headers['User-Agent'] = USER_AGENT
    return sessao


def resolver_servidor(host: str) -> str | None:
    """Endereço IP de `host` (o servidor), ou None se o nome não existe no DNS."""
    try:
        return socket.gethostbyname(host)
    except (OSError, UnicodeError):
        return None


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
    """Faz GETs respeitando o limite por site. Uma instância por execução.

    `sessao`: uma sessão para todas as threads (testes); sem ela, cada thread
    cria a sua. `dormir`: como esperar (padrão: `parar.wait`, que acorda no
    Ctrl+C). `janela_segundos` e `margem_segundos` só mudam nos testes com
    threads de verdade. `ao_reservar(host, servidor, horario)` é chamada, sob
    a trava, a cada requisição liberada, com o horário que conta para o limite.

    `servidor_de(host)` diz o servidor de cada site (`resolver_servidor` no
    programa); é chamada uma vez por site. Sem ela (padrão dos testes), não há
    limite por servidor. Um site sem servidor (None) só tem o limite do site.
    """

    def __init__(
        self,
        sessao: Any = None,
        relogio: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], object] | None = None,
        limite_por_minuto: int = LIMITE_POR_MINUTO,
        max_tentativas: int = MAX_TENTATIVAS,
        timeout: tuple[float, float] = TIMEOUT_PADRAO,
        historico: str | None = None,
        relogio_parede: Callable[[], float] = time.time,
        parar: threading.Event | None = None,
        janela_segundos: float = JANELA_SEGUNDOS,
        margem_segundos: float = MARGEM_SEGUNDOS,
        ao_reservar: Callable[[str, str | None, float], None] | None = None,
        servidor_de: Callable[[str], str | None] | None = None,
        limite_por_servidor: int = LIMITE_POR_SERVIDOR,
    ) -> None:
        self._sessao_fixa = sessao
        self._local = threading.local()
        self._trava = threading.Lock()
        self.parar = parar if parar is not None else threading.Event()
        self.relogio = relogio
        self.relogio_parede = relogio_parede
        self.dormir = dormir if dormir is not None else self.parar.wait
        self.limite = limite_por_minuto
        self.max_tentativas = max_tentativas
        self.timeout = timeout
        self.historico = historico
        self.janela = janela_segundos + margem_segundos
        self.ao_reservar = ao_reservar
        self._janelas = defaultdict(deque)  # host -> horários das últimas requisições
        self._parede = defaultdict(deque)  # os mesmos horários, no relógio de parede
        self._bloqueado_ate = {}  # host -> horário (após um 429)
        self._bloqueado_parede = {}
        self.servidor_de = servidor_de
        self.limite_por_servidor = limite_por_servidor
        self._servidores: dict[str, str | None] = {}  # host -> servidor
        self._janelas_srv = defaultdict(deque)  # servidor -> horários
        self._parede_srv = defaultdict(deque)
        self._teto: dict[str, int] = {}  # servidor -> teto atual (se mudou)
        self._429s = defaultdict(list)  # servidor -> [(horário, host)] dos 429 recentes
        self._ultima_reducao: dict[str, float] = {}
        self.reducoes: list[tuple[str, int, int]] = []  # (servidor, teto antigo, novo)
        self.total_requisicoes = 0
        if historico:
            self._carregar_historico()

    @property
    def sessao(self) -> Any:
        """Sessão HTTP desta thread (ou a sessão dada ao criar o cliente)."""
        if self._sessao_fixa is not None:
            return self._sessao_fixa
        sessao = getattr(self._local, 'sessao', None)
        if sessao is None:
            sessao = self._local.sessao = criar_sessao()
        return sessao

    def servidor(self, host: str) -> str | None:
        """Servidor do site (consultado uma vez por site), ou None."""
        if self.servidor_de is None:
            return None
        with self._trava:
            if host in self._servidores:
                return self._servidores[host]
        endereco = self.servidor_de(host)  # fora da trava: o DNS pode demorar
        with self._trava:
            return self._servidores.setdefault(host, endereco)

    def teto(self, servidor: str) -> int:
        """Requisições por minuto permitidas agora no servidor."""
        return self._teto.get(servidor, self.limite_por_servidor)

    def _anotar_429(self, host: str, servidor: str | None) -> None:
        """Reduz o teto do servidor se sites diferentes dele receberam 429 (sob a trava)."""
        if servidor is None:
            return
        agora = self.relogio()
        recentes = [(t, h) for t, h in self._429s[servidor] if agora - t < JANELA_LENTIDAO]
        recentes.append((agora, host))
        self._429s[servidor] = recentes
        if len({h for _, h in recentes}) < 2:
            return
        ultima = self._ultima_reducao.get(servidor)
        if ultima is not None and agora - ultima < JANELA_LENTIDAO:
            return
        antigo = self.teto(servidor)
        novo = max(PISO_POR_SERVIDOR, antigo // 2)
        self._429s[servidor] = []  # a mesma leva de 429 não conta duas vezes
        self._ultima_reducao[servidor] = agora
        if novo < antigo:
            self._teto[servidor] = novo
            self.reducoes.append((servidor, antigo, novo))
            log.warning(
                'Servidor %s sobrecarregado (429 de %d casas): limite reduzido de %d para '
                '%d requisições por minuto até o fim da execução',
                servidor,
                len({h for _, h in recentes}),
                antigo,
                novo,
            )

    def definir_limite_por_servidor(self, limite: int) -> None:
        """Troca o teto inicial dos servidores (o `paralelo` do config.json)."""
        with self._trava:
            self.limite_por_servidor = limite
            self._teto.clear()

    def servidores(self) -> dict[str, list[str]]:
        """{servidor: sites} dos sites usados nesta execução (sem os que não têm servidor)."""
        with self._trava:
            grupos: dict[str, list[str]] = {}
            for host, servidor in self._servidores.items():
                if servidor is not None:
                    grupos.setdefault(servidor, []).append(host)
            return grupos

    def verificar_parada(self) -> None:
        """Lança `Interrompido` se a execução foi interrompida (evento `parar`)."""
        if self.parar.is_set():
            raise Interrompido

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
                if parede - t < self.janela:
                    self._janelas[host].append(agora - (parede - t))
                    self._parede[host].append(t)
        for servidor, horarios in (dados.get('servidores') or {}).items():
            for t in sorted(horarios):
                if parede - t < self.janela:
                    self._janelas_srv[servidor].append(agora - (parede - t))
                    self._parede_srv[servidor].append(t)
        for host, ate in (dados.get('bloqueios') or {}).items():
            if ate > parede:
                self._bloqueado_ate[host] = agora + (ate - parede)
                self._bloqueado_parede[host] = ate

    def _salvar_historico(self):
        parede = self.relogio_parede()
        dados = {
            'requisicoes': {
                h: [t for t in ts if parede - t < self.janela] for h, ts in self._parede.items()
            },
            'servidores': {
                s: [t for t in ts if parede - t < self.janela] for s, ts in self._parede_srv.items()
            },
            'bloqueios': {h: t for h, t in self._bloqueado_parede.items() if t > parede},
        }
        for parte in ('requisicoes', 'servidores'):
            dados[parte] = {k: ts for k, ts in dados[parte].items() if ts}
        temporario = f'{self.historico}.tmp'
        try:
            with open(temporario, 'w', encoding='utf-8') as arquivo:
                json.dump(dados, arquivo)
            os.replace(temporario, self.historico)
        except OSError as erro:
            log.warning('Não foi possível gravar o histórico de requisições: %s', erro)

    def _espera_da_janela(self, janela: deque, limite: int, agora: float) -> float:
        """Quanto falta para a janela ter vaga (0 se já tem). Descarta os horários velhos."""
        while janela and agora - janela[0] >= self.janela:
            janela.popleft()
        return 0.0 if len(janela) < limite else self.janela - (agora - janela[0])

    def _reservar(self, host: str, servidor: str | None, agora: float) -> None:
        """Conta a requisição nas janelas do site e do servidor (sob a trava)."""
        parede_agora = self.relogio_parede()
        self._janelas[host].append(agora)
        parede = self._parede[host]
        parede.append(parede_agora)
        while len(parede) > self.limite:
            parede.popleft()
        if servidor is not None:
            self._janelas_srv[servidor].append(agora)
            parede = self._parede_srv[servidor]
            parede.append(parede_agora)
            while parede and parede_agora - parede[0] >= self.janela:
                parede.popleft()
        self.total_requisicoes += 1
        if self.ao_reservar is not None:
            self.ao_reservar(host, servidor, agora)
        if self.historico:
            self._salvar_historico()

    def _aguardar_vez(self, host, servidor=None):
        """Espera o necessário para a próxima requisição a `host` respeitar os limites.

        Espera o mais longo dos dois: o do site e o do servidor.
        """
        while True:
            with self._trava:
                self.verificar_parada()
                agora = self.relogio()
                espera = self._bloqueado_ate.get(host, 0) - agora
                if espera <= 0:
                    espera = self._espera_da_janela(self._janelas[host], self.limite, agora)
                    if servidor is not None:
                        espera = max(
                            espera,
                            self._espera_da_janela(
                                self._janelas_srv[servidor], self.teto(servidor), agora
                            ),
                        )
                    if espera <= 0:
                        self._reservar(host, servidor, agora)
                        return
            # Fora da trava, para as outras casas seguirem. Espera mínima: evita
            # laço infinito com esperas de 1e-14 s (arredondamento)
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
        servidor = self.servidor(host)
        tentativas = max_tentativas or self.max_tentativas
        status, erro = None, ''
        for tentativa in range(1, tentativas + 1):
            self._aguardar_vez(host, servidor)
            enviada = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            bruta = None
            try:
                bruta = self.sessao.get(url, timeout=timeout or self.timeout, stream=stream)
            except requests.Timeout:
                status, erro = None, 'timeout'
            except requests.RequestException as falha:
                status, erro = None, motivo_permanente(falha) or 'conexao'
                if erro != 'conexao':
                    # certificado inválido ou nome inexistente: tentar de novo não resolve
                    self._registrar(host, url, erro, tentativa, 0, enviada)
                    log.warning('Falha em %s: %s (sem nova tentativa)', url, erro)
                    return Resposta(url, False, None, erro, tentativa, None)
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
                with self._trava:
                    self._anotar_429(host, servidor)
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
                with self._trava:
                    self._bloqueado_ate[host] = self.relogio() + espera
                    self._bloqueado_parede[host] = self.relogio_parede() + espera
                    if self.historico:
                        self._salvar_historico()
            else:
                self.dormir(espera)
                self.verificar_parada()
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
