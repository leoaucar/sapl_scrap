"""Pasta do projeto: criar, reabrir para retomar, e os caminhos dos seus arquivos.

Um projeto `<nome>` vive em `<nome>_proj/`. As respostas dadas ao criá-lo
(palavras, filtro, limite, downloads) ficam em `config.json`, para a
retomada não precisar perguntar nada.

No modo atualização, os arquivos ganham o sufixo `_ATUALIZADO_<dd_mm_aaaa>`
e os downloads vão para `downloads<dd_mm_aaaa>/`.
"""
import json
from pathlib import Path

from entrada import perguntar_opcao, perguntar_texto


class Projeto:
    """Caminhos dos arquivos de um projeto (veja o README para o conteúdo de cada um)."""

    def __init__(self, raiz, nome, data=None):
        self.raiz = Path(raiz)
        self.nome = nome
        self.data = data
        self.pasta = self.raiz / f'{nome}_proj'
        self.sufixo = f'_ATUALIZADO_{data}' if data else ''

    def _arquivo(self, base, sufixo=True):
        return self.pasta / f'{self.nome}_{base}{self.sufixo if sufixo else ""}.csv'

    @property
    def casas(self):
        return self.pasta / 'casas_resultado.csv'

    @property
    def cru(self):
        return self._arquivo('resultados_crus_casas', sufixo=False)

    @property
    def links(self):
        return self._arquivo('links_totais', sufixo=False)

    @property
    def materias(self):
        return self._arquivo('materias_legislativas')

    @property
    def estado(self):
        return self._arquivo('estado')

    @property
    def final(self):
        return self._arquivo('resultado_final')

    @property
    def config(self):
        return self.pasta / 'config.json'

    @property
    def downloads(self):
        return self.pasta / (f'downloads{self.data}' if self.data else 'downloads')


def nome_limpo(nome):
    """Aceita o nome com ou sem o sufixo `_proj`."""
    nome = nome.strip()
    return nome[:-5] if nome.endswith('_proj') else nome


def projetos_existentes(raiz):
    return sorted(p.name[:-5] for p in Path(raiz).glob('*_proj') if p.is_dir())


def abrir_ou_criar(raiz, entrada=input):
    """Pergunta o nome; cria o projeto ou, se já existe, oferece retomá-lo.

    Devolve (Projeto, novo). Nunca sobrescreve um projeto existente.
    """
    while True:
        nome = nome_limpo(perguntar_texto('Defina o nome do projeto\n', entrada))
        projeto = Projeto(raiz, nome)
        if not projeto.pasta.exists():
            projeto.pasta.mkdir(parents=True)
            return projeto, True
        escolha = perguntar_opcao(
            f'O projeto "{nome}" já existe.\n1- retomar este projeto\n2- escolher outro nome\n',
            ['1', '2'], entrada)
        if escolha == '1':
            return projeto, False


def escolher_projeto_existente(raiz, entrada=input):
    """Para o modo atualização: pergunta até achar um projeto com resultado final."""
    existentes = projetos_existentes(raiz)
    if existentes:
        print('Projetos encontrados: ' + ', '.join(existentes))
    while True:
        nome = nome_limpo(perguntar_texto('Digite o nome do projeto para atualizar\n', entrada))
        projeto = Projeto(raiz, nome)
        if projeto.final.exists():
            return projeto
        print(f'Não encontrei {projeto.final}. Confira o nome do projeto.')


def salvar_config(projeto, config):
    projeto.config.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')


def carregar_config(projeto):
    """Configuração salva do projeto, ou None se não houver (projeto de versão antiga)."""
    if not projeto.config.exists():
        return None
    return json.loads(projeto.config.read_text(encoding='utf-8'))
