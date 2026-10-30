"""Pasta do projeto: criar, reabrir para retomar, e os caminhos dos seus arquivos.

Um projeto `<nome>` vive em `<nome>_proj/`. As perguntas para escolher o
projeto ficam em `sapyl.interface.entrada`. As respostas dadas ao criá-lo
(palavras, filtro, limite, downloads) ficam em `config.json`, para a
retomada não precisar perguntar nada.

No modo atualização, os arquivos ganham o sufixo `_ATUALIZADO_<dd_mm_aaaa>`
e os downloads vão para `downloads<dd_mm_aaaa>/`.
"""

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sapyl.colunas import CAMPOS_ESTADO, ETAPA_BUSCA, ETAPA_MATERIA, ETAPA_PDF
from sapyl.padroes import ConfiguracaoInvalida


class Projeto:
    """Caminhos dos arquivos de um projeto (veja o README para o conteúdo de cada um)."""

    def __init__(self, raiz: str | Path, nome: str, data: str | None = None) -> None:
        self.raiz = Path(raiz)
        self.nome = nome
        self.data = data
        self.pasta = self.raiz / f'{nome}_proj'
        self.sufixo = f'_ATUALIZADO_{data}' if data else ''

    def criar(self) -> None:
        """Cria a pasta do projeto (só quando a pessoa confirma o projeto novo)."""
        self.pasta.mkdir(parents=True, exist_ok=True)

    def _arquivo(self, base: str, sufixo: bool = True) -> Path:
        return self.pasta / f'{self.nome}_{base}{self.sufixo if sufixo else ""}.csv'

    @property
    def casas(self) -> Path:
        """Tabela de casas do projeto."""
        return self.pasta / 'casas_resultado.csv'

    @property
    def cru(self) -> Path:
        """Arquivo bruto da busca das versões até 0.1 (só lido, em projetos antigos)."""
        return self._arquivo('resultados_crus_casas', sufixo=False)

    @property
    def paginas(self) -> Path:
        """Páginas da busca, só com os links de matérias de cada uma."""
        return self._arquivo('paginas_busca', sufixo=False)

    @property
    def links(self) -> Path:
        """Lista de links únicos."""
        return self._arquivo('links_totais', sufixo=False)

    @property
    def materias(self) -> Path:
        """Matérias raspadas (uma linha por tentativa)."""
        return self._arquivo('materias_legislativas')

    @property
    def estado(self) -> Path:
        """Arquivo de estado (progresso)."""
        return self._arquivo('estado')

    @property
    def final(self) -> Path:
        """Resultado final."""
        return self._arquivo('resultado_final')

    @property
    def cache(self) -> Path:
        """Fontes das casas e nomes consultados (para a retomada não perguntar de novo)."""
        return self.pasta / 'cache.json'

    @property
    def config(self) -> Path:
        """Respostas dadas ao criar o projeto."""
        return self.pasta / 'config.json'

    @property
    def downloads(self) -> Path:
        """Pasta dos textos baixados."""
        return self.pasta / (f'downloads{self.data}' if self.data else 'downloads')


def nome_limpo(nome: str) -> str:
    """Aceita o nome com ou sem o sufixo `_proj`."""
    nome = nome.strip()
    return nome[:-5] if nome.endswith('_proj') else nome


def projetos_existentes(raiz: str | Path) -> list[str]:
    """Nomes dos projetos (`<nome>_proj/`) na pasta `raiz`."""
    return sorted(p.name[:-5] for p in Path(raiz).glob('*_proj') if p.is_dir())


def salvar_config(projeto: Projeto, config: dict[str, Any]) -> None:
    """Grava as respostas do projeto em config.json."""
    projeto.config.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')


def carregar_config(projeto: Projeto) -> dict[str, Any] | None:
    """Configuração salva do projeto, ou None se não houver (projeto de versão antiga).

    Um arquivo estragado vira `ConfiguracaoInvalida`, com o caminho na mensagem.
    """
    if not projeto.config.exists():
        return None
    try:
        return json.loads(projeto.config.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as erro:
        raise ConfiguracaoInvalida(f'{projeto.config}: não é um JSON válido ({erro})') from erro


# Situação de um projeto, lida dos arquivos dele (sem nenhuma requisição)
CONCLUIDO = 'concluído'
CONCLUIDO_COM_FALHAS = 'concluído com falhas'
INTERROMPIDO = 'interrompido'
NAO_INICIADO = 'não iniciado'

# Status que contam como falha em cada etapa do estado
_FALHAS = {ETAPA_BUSCA: {'incompleta'}, ETAPA_MATERIA: {'erro'}, ETAPA_PDF: {'erro'}}
# Logs das execuções que produzem o resultado final (veja registro.caminho_do_log)
_LOG_DE_EXECUCAO = re.compile(r'_(\d{4}-\d{2}-\d{2}_\d{6})_(novo|retomada)(?:_\d+)?\.log$')


# Data e hora no nome dos logs de execução (qualquer modo)
_LOG_COM_DATA = re.compile(r'_(\d{4}-\d{2}-\d{2}_\d{6})_[a-z]+(?:_\d+)?\.log$')


@dataclass(frozen=True)
class Situacao:
    """Como um projeto está: `rotulo`, quando foi criado e atualizado, matérias no resultado.

    `ultima_execucao`: início da última execução que produz o resultado
    (novo ou retomada), usado para saber se ela terminou.
    """

    rotulo: str
    criado: datetime | None
    atualizado: datetime | None
    materias: int | None
    ultima_execucao: datetime | None = None

    def texto(self) -> str:
        """`concluído · criado em 28/10/2026 · atualizado em 30/10/2026 14:05 · 1.189 matérias`."""
        criado = self.criado.strftime('%d/%m/%Y') if self.criado else '?'
        atualizado = self.atualizado.strftime('%d/%m/%Y %H:%M') if self.atualizado else '?'
        if self.materias is None:
            materias = '? matérias'
        else:
            numero = f'{self.materias:,}'.replace(',', '.')
            materias = f'{numero} matéria{"s" if self.materias != 1 else ""}'
        return f'{self.rotulo} · criado em {criado} · atualizado em {atualizado} · {materias}'


def _datas_dos_logs(projeto: Projeto, so_execucoes: bool = False) -> list[datetime]:
    padrao = _LOG_DE_EXECUCAO if so_execucoes else _LOG_COM_DATA
    datas = []
    for log in (projeto.pasta / 'logs').glob(f'{projeto.nome}_*.log'):
        achado = padrao.search(log.name)
        if achado:
            datas.append(datetime.strptime(achado.group(1), '%Y-%m-%d_%H%M%S'))
    return datas


def _inicio_da_ultima_execucao(projeto: Projeto) -> datetime | None:
    return max(_datas_dos_logs(projeto, so_execucoes=True), default=None)


def _primeira_linha_do_estado(caminho: Path) -> datetime | None:
    try:
        with open(caminho, newline='', encoding='utf-8') as arquivo:
            leitor = csv.reader(arquivo)
            next(leitor, None)
            primeira = next(leitor, None)
        if primeira and len(primeira) == len(CAMPOS_ESTADO):
            return datetime.strptime(primeira[-1], '%d/%m/%Y %H:%M:%S')
    except (OSError, UnicodeDecodeError, csv.Error, ValueError):
        pass
    return None


def criado_em(projeto: Projeto) -> datetime | None:
    """Quando o projeto foi criado: o log mais antigo, a 1ª linha do estado ou o config.json."""
    datas = _datas_dos_logs(projeto)
    if datas:
        return min(datas)
    if projeto.estado.is_file():
        primeira = _primeira_linha_do_estado(projeto.estado)
        if primeira is not None:
            return primeira
    if projeto.config.is_file():
        return datetime.fromtimestamp(projeto.config.stat().st_mtime)
    return None


def atualizado_em(projeto: Projeto) -> datetime | None:
    """A última mudança em qualquer arquivo do projeto (resultados, estado, logs, config)."""
    arquivos = [*projeto.pasta.glob('*'), *(projeto.pasta / 'logs').glob('*')]
    datas = [a.stat().st_mtime for a in arquivos if a.is_file()]
    return datetime.fromtimestamp(max(datas)) if datas else None


def _tem_falhas(caminho: Path) -> bool:
    """Se a última linha de alguma (etapa, chave) do estado é uma falha. Só lê o arquivo."""
    ultimo: dict[tuple[str, str], str] = {}
    with open(caminho, newline='', encoding='utf-8') as arquivo:
        leitor = csv.reader(arquivo)
        if next(leitor, None) != CAMPOS_ESTADO:
            return False
        for valores in leitor:
            if len(valores) == len(CAMPOS_ESTADO) and valores[0] in _FALHAS:
                ultimo[(valores[0], valores[1])] = valores[2]
    return any(status in _FALHAS[etapa] for (etapa, _), status in ultimo.items())


def _linhas_do_resultado(caminho: Path) -> int | None:
    try:
        with open(caminho, newline='', encoding='utf-8') as arquivo:
            return max(sum(1 for _ in csv.reader(arquivo)) - 1, 0)
    except (OSError, UnicodeDecodeError, csv.Error):
        return None


def situacao(projeto: Projeto) -> Situacao:
    """Situação do projeto, lida dos arquivos (nunca escreve neles).

    - sem arquivo de estado: `não iniciado`;
    - resultado final gravado depois do início da última execução (log
      `novo`/`retomada`; sem logs, depois da última gravação do estado):
      `concluído`, ou `concluído com falhas` se o estado tem buscas
      incompletas, matérias ou PDFs com erro;
    - senão: `interrompido`.
    """
    final = projeto.final
    materias = _linhas_do_resultado(final) if final.is_file() else None
    inicio = _inicio_da_ultima_execucao(projeto)
    datas = (criado_em(projeto), atualizado_em(projeto))
    if not projeto.estado.is_file():
        return Situacao(NAO_INICIADO, *datas, materias, inicio)
    mudou_estado = projeto.estado.stat().st_mtime
    if inicio is None:
        referencia = mudou_estado
        ultima = datetime.fromtimestamp(mudou_estado)
    else:
        referencia, ultima = inicio.timestamp(), inicio
    if not final.is_file() or final.stat().st_mtime < referencia:
        return Situacao(INTERROMPIDO, *datas, materias, ultima)
    rotulo = CONCLUIDO_COM_FALHAS if _tem_falhas(projeto.estado) else CONCLUIDO
    return Situacao(rotulo, *datas, materias, ultima)
