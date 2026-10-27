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
"""
from collections import Counter
import csv
from datetime import datetime

from sapyl.colunas import CAMPOS_ESTADO
import os



def _agora():
    return datetime.now().strftime('%d/%m/%Y %H:%M:%S')


class ArquivoCSV:
    """CSV em que só se acrescentam linhas; cria o cabeçalho se o arquivo é novo."""

    def __init__(self, caminho, campos):
        self.caminho = caminho
        self.campos = list(campos)
        novo = not os.path.exists(caminho) or os.path.getsize(caminho) == 0
        if not novo:
            self._consertar_final()
        self._arquivo = open(caminho, 'a', newline='', encoding='utf-8')
        self._escritor = csv.DictWriter(self._arquivo, fieldnames=self.campos,
                                        extrasaction='ignore')
        if novo:
            self._escritor.writeheader()
            self._arquivo.flush()

    def _consertar_final(self):
        """Se o arquivo não termina em quebra de linha (queda no meio de uma
        gravação), começa a próxima linha numa linha nova."""
        with open(self.caminho, 'rb+') as arquivo:
            arquivo.seek(-1, os.SEEK_END)
            if arquivo.read(1) not in (b'\n', b'\r'):
                arquivo.write(b'\n')

    def anexar(self, linha):
        self._escritor.writerow({c: linha.get(c, '') for c in self.campos})
        self._arquivo.flush()

    def fechar(self):
        self._arquivo.close()


def ler_csv(caminho, campos):
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
                linhas.append(dict(zip(campos, valores)))
    return linhas


class Estado:
    """Lê e grava o progresso do projeto (veja o início do módulo)."""

    def __init__(self, caminho):
        self.caminho = caminho
        self._ultimo = {}
        for linha in ler_csv(caminho, CAMPOS_ESTADO):
            self._ultimo[(linha['etapa'], linha['chave'])] = (linha['status'], linha['erro'])
        self._arquivo = ArquivoCSV(caminho, CAMPOS_ESTADO)

    def registrar(self, etapa, chave, status, erro=''):
        self._arquivo.anexar({'etapa': etapa, 'chave': chave, 'status': status,
                              'erro': erro, 'quando': _agora()})
        self._ultimo[(etapa, chave)] = (status, erro)

    def status(self, etapa, chave):
        """Último status registrado, ou None se nunca foi registrado."""
        return self._ultimo.get((etapa, chave), (None, ''))[0]

    def erro(self, etapa, chave):
        return self._ultimo.get((etapa, chave), (None, ''))[1]

    def chaves(self, etapa, status=None):
        return [k for (e, k), (s, _) in self._ultimo.items()
                if e == etapa and (status is None or s == status)]

    def contagens(self, etapa, chaves=None):
        """Quantas chaves da etapa estão em cada status (só `chaves`, se dado)."""
        contagem = Counter()
        for (e, k), (s, _) in self._ultimo.items():
            if e == etapa and (chaves is None or k in chaves):
                contagem[s] += 1
        return contagem

    def fechar(self):
        self._arquivo.fechar()
