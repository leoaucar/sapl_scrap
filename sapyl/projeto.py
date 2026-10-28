"""Pasta do projeto: criar, reabrir para retomar, e os caminhos dos seus arquivos.

Um projeto `<nome>` vive em `<nome>_proj/`. As perguntas para escolher o
projeto ficam em `sapyl.interface.entrada`. As respostas dadas ao criá-lo
(palavras, filtro, limite, downloads) ficam em `config.json`, para a
retomada não precisar perguntar nada.

No modo atualização, os arquivos ganham o sufixo `_ATUALIZADO_<dd_mm_aaaa>`
e os downloads vão para `downloads<dd_mm_aaaa>/`.
"""

import json
from pathlib import Path
from typing import Any


class Projeto:
    """Caminhos dos arquivos de um projeto (veja o README para o conteúdo de cada um)."""

    def __init__(self, raiz: str | Path, nome: str, data: str | None = None) -> None:
        self.raiz = Path(raiz)
        self.nome = nome
        self.data = data
        self.pasta = self.raiz / f'{nome}_proj'
        self.sufixo = f'_ATUALIZADO_{data}' if data else ''

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
    """Configuração salva do projeto, ou None se não houver (projeto de versão antiga)."""
    if not projeto.config.exists():
        return None
    return json.loads(projeto.config.read_text(encoding='utf-8'))
