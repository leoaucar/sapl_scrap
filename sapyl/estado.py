"""Progresso do projeto em disco, para retomar uma execução interrompida.

`<nome>_estado.csv` só recebe linhas novas (nunca é reescrito), uma por
evento, gravadas na hora:

    etapa,chave,status,erro,quando
    busca,sapl.x.leg.br|"plano+diretor",completa,,24/10/2026 10:00:00
    materia,sapl.x.leg.br/123,ok,,24/10/2026 10:01:00
    pdf,sapl.x.leg.br/123,sem_pdf,,24/10/2026 10:05:00

Ao ler, vale a **última** linha de cada (etapa, chave). Uma linha cortada no
meio por uma queda do programa é ignorada.

`ArquivoCSV` é o mesmo mecanismo (só acrescentar linhas, com cabeçalho) para
os arquivos de dados do projeto.

Todas as classes daqui podem ser usadas por várias casas ao mesmo tempo
(threads): cada gravação é feita inteira, sob uma trava, sem misturar linhas.

`Cache` guarda em `cache.json` o que não muda entre execuções: a fonte de
cada casa (`api` ou `html`) e os nomes consultados na API (tipos, regimes...).
"""

import csv
import json
import os
import threading
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path

from sapyl import registro
from sapyl.colunas import CAMPOS_ESTADO, Linha

log = registro.logger('estado')


def _agora() -> str:
    return datetime.now().strftime('%d/%m/%Y %H:%M:%S')


class ArquivoCSV:
    """CSV em que só se acrescentam linhas; cria o cabeçalho se o arquivo é novo."""

    def __init__(self, caminho: str | Path, campos: Iterable[str]) -> None:
        self.caminho = caminho
        self.campos = list(campos)
        self._trava = threading.Lock()
        novo = not os.path.exists(caminho) or os.path.getsize(caminho) == 0
        if not novo:
            self._consertar_final()
        self._arquivo = open(caminho, 'a', newline='', encoding='utf-8')
        self._escritor = csv.DictWriter(
            self._arquivo, fieldnames=self.campos, extrasaction='ignore'
        )
        if novo:
            self._escritor.writeheader()
            self._arquivo.flush()

    def _consertar_final(self) -> None:
        """Se o arquivo não termina em quebra de linha (queda no meio de uma
        gravação), começa a próxima linha numa linha nova."""
        with open(self.caminho, 'rb+') as arquivo:
            arquivo.seek(-1, os.SEEK_END)
            if arquivo.read(1) not in (b'\n', b'\r'):
                arquivo.write(b'\n')

    def anexar(self, linha: Mapping[str, object]) -> None:
        """Grava uma linha (colunas que faltam ficam vazias) e manda para o disco."""
        valores = {c: linha.get(c, '') for c in self.campos}
        with self._trava:
            self._escritor.writerow(valores)
            self._arquivo.flush()

    def fechar(self) -> None:
        """Fecha o arquivo."""
        with self._trava:
            self._arquivo.close()


def ler_csv(caminho: str | Path, campos: list[str]) -> list[Linha]:
    """Linhas (dicts) de um CSV gravado por ArquivoCSV, sem as linhas incompletas."""
    if not os.path.exists(caminho):
        return []
    linhas = []
    with open(caminho, newline='', encoding='utf-8') as arquivo:
        leitor = csv.reader(arquivo)
        cabecalho = next(leitor, None)
        if cabecalho != list(campos):
            raise ValueError(f'Cabeçalho inesperado em {caminho}: {cabecalho}')
        for valores in leitor:
            if len(valores) == len(campos):
                linhas.append(dict(zip(campos, valores, strict=False)))
    return linhas


class Estado:
    """Lê e grava o progresso do projeto (veja o início do módulo)."""

    def __init__(self, caminho: str | Path) -> None:
        self.caminho = caminho
        self._trava = threading.Lock()
        self._ultimo = {}
        for linha in ler_csv(caminho, CAMPOS_ESTADO):
            self._ultimo[(linha['etapa'], linha['chave'])] = (linha['status'], linha['erro'])
        self._arquivo = ArquivoCSV(caminho, CAMPOS_ESTADO)

    def registrar(self, etapa: str, chave: str, status: str, erro: str = '') -> None:
        """Acrescenta o novo status de (etapa, chave) ao arquivo de estado."""
        with self._trava:
            self._arquivo.anexar(
                {'etapa': etapa, 'chave': chave, 'status': status, 'erro': erro, 'quando': _agora()}
            )
            self._ultimo[(etapa, chave)] = (status, erro)

    def _itens(self) -> list[tuple[tuple[str, str], tuple[str, str]]]:
        with self._trava:
            return list(self._ultimo.items())

    def status(self, etapa: str, chave: str) -> str | None:
        """Último status registrado, ou None se nunca foi registrado."""
        return self._ultimo.get((etapa, chave), (None, ''))[0]

    def erro(self, etapa: str, chave: str) -> str:
        """Motivo do último status de (etapa, chave), ou ''."""
        return self._ultimo.get((etapa, chave), (None, ''))[1]

    def chaves(self, etapa: str, status: str | None = None) -> list[str]:
        """Chaves da etapa (só as que estão em `status`, se dado)."""
        return [
            k for (e, k), (s, _) in self._itens() if e == etapa and (status is None or s == status)
        ]

    def contagens(self, etapa: str, chaves: Iterable[str] | None = None) -> Counter[str]:
        """Quantas chaves da etapa estão em cada status (só `chaves`, se dado)."""
        contagem = Counter()
        for (e, k), (s, _) in self._itens():
            if e == etapa and (chaves is None or k in chaves):
                contagem[s] += 1
        return contagem

    def fechar(self) -> None:
        """Fecha o arquivo de estado."""
        self._arquivo.fechar()


class Cache:
    """Fontes das casas e nomes consultados, guardados em JSON (`cache.json`).

    Sem `caminho`, fica só na memória (uma execução). Cada entrada nova é
    gravada na hora, num arquivo temporário renomeado por cima do antigo, para
    uma queda nunca deixar o arquivo pela metade. Um arquivo ilegível é
    ignorado com um aviso: a execução começa com o cache vazio.
    """

    def __init__(self, caminho: str | Path | None = None) -> None:
        self.caminho = Path(caminho) if caminho is not None else None
        self._trava = threading.Lock()
        self._dados: dict[str, dict[str, str]] = {'fontes': {}, 'nomes': {}}
        if self.caminho is not None and self.caminho.exists():
            self._carregar()

    def _carregar(self) -> None:
        try:
            dados = json.loads(self.caminho.read_text(encoding='utf-8'))
            for parte in ('fontes', 'nomes'):
                valores = dados.get(parte, {})
                if not isinstance(valores, dict):
                    raise ValueError(f'"{parte}" não é um objeto')
                self._dados[parte] = {str(k): str(v) for k, v in valores.items()}
        except (OSError, ValueError, AttributeError) as erro:
            log.warning('Cache ilegível em %s (%s): começando sem ele', self.caminho, erro)
            self._dados = {'fontes': {}, 'nomes': {}}

    def _salvar(self) -> None:
        if self.caminho is None:
            return
        temporario = self.caminho.with_name(self.caminho.name + '.tmp')
        temporario.write_text(json.dumps(self._dados, ensure_ascii=False, indent=1), 'utf-8')
        os.replace(temporario, self.caminho)

    def fontes(self) -> dict[str, str]:
        """Cópia de {host: 'api' | 'html'}."""
        with self._trava:
            return dict(self._dados['fontes'])

    def fonte(self, host: str) -> str | None:
        """Fonte guardada da casa, ou None se ainda não se sabe."""
        return self._dados['fontes'].get(host)

    def guardar_fonte(self, host: str, fonte: str) -> None:
        """Grava a fonte da casa ('api' ou 'html')."""
        with self._trava:
            if self._dados['fontes'].get(host) != fonte:
                self._dados['fontes'][host] = fonte
                self._salvar()

    def nome(self, url: str) -> str | None:
        """Nome guardado para a URL da API, ou None."""
        return self._dados['nomes'].get(url)

    def guardar_nome(self, url: str, nome: str) -> None:
        """Grava um nome obtido (nunca um vazio: consultas que falharam não vão para o disco)."""
        with self._trava:
            if nome and self._dados['nomes'].get(url) != nome:
                self._dados['nomes'][url] = nome
                self._salvar()
