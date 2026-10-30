"""Validação da v0.4.0 num terminal de verdade (pty), esperando cada pergunta antes de responder.

Uso: python validar_no_terminal.py <pasta_de_trabalho> <python_do_venv> <arquivo_de_saida>
Cada passo só envia teclas depois de ver o texto esperado na tela; se o texto
não aparecer no tempo dado, o script mata o programa (nada é escolhido às cegas).
"""

import fcntl
import os
import pty
import re
import select
import signal
import struct
import sys
import termios
import time

PASTA, PYTHON, SAIDA = sys.argv[1], sys.argv[2], sys.argv[3]
BAIXO, CIMA, ENTER, ESPACO, CTRL_C = '\x1b[B', '\x1b[A', '\r', ' ', '\x03'
ANSI = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[()][0-9A-Za-z]|\x1b[=>]')

registro = open(SAIDA, 'a', encoding='utf-8')


def log(texto):
    registro.write(texto + '\n')
    registro.flush()


class Terminal:
    def __init__(self, nome):
        self.nome = nome
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.chdir(PASTA)
            os.environ.update(
                PYTHONFAULTHANDLER=os.environ.get('PYTHONFAULTHANDLER', ''),
                TERM='xterm-256color',
                COLUMNS='110',
                LINES='40',
            )
            os.execv(PYTHON, [PYTHON, '-m', 'sapyl'])
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack('HHHH', 40, 110, 0, 0))
        self.bruto = ''
        self.marca = 0
        log(f'\n===== {nome} =====')

    def ler(self, segundos):
        fim = time.time() + segundos
        while time.time() < fim:
            r, _, _ = select.select([self.fd], [], [], 0.1)
            if not r:
                continue
            try:
                dados = os.read(self.fd, 65536).decode('utf-8', 'replace')
            except OSError:
                return False
            if '\x1b[6n' in dados:  # o prompt_toolkit pergunta a posição do cursor
                os.write(self.fd, b'\x1b[1;1R')
            self.bruto += dados
        return True

    def tela(self, desde=None):
        return ANSI.sub('', self.bruto[self.marca if desde is None else desde :])

    def esperar(self, texto, segundos=60):
        fim = time.time() + segundos
        while time.time() < fim:
            if texto in self.tela():
                return True
            if not self.ler(0.5):
                break
        log(f'!! não apareceu: {texto!r}')
        log(self.tela()[-3000:])
        self.matar()
        sys.exit(1)

    def enviar(self, teclas, descricao):
        log(f'>> {descricao}')
        self.marca = len(self.bruto)
        os.write(self.fd, teclas.encode())
        self.ler(0.8)

    def apontar(self, alvo, maximo=40):
        """Desce até a linha com o cursor (») mostrar `alvo`."""
        for _ in range(maximo):
            linhas = [
                linha for linha in self.tela(len(self.bruto) - 4000).splitlines() if '»' in linha
            ]
            if linhas and alvo in linhas[-1]:
                return
            os.write(self.fd, BAIXO.encode())
            self.ler(0.4)
        log(f'!! cursor não chegou em {alvo!r}')
        self.matar()
        sys.exit(1)

    def matar(self):
        try:
            os.kill(self.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def fim(self, segundos=60):
        self.ler(segundos)
        _, status = os.waitpid(self.pid, 0)
        log(self.tela(0)[-6000:] if False else '')
        return os.waitstatus_to_exitcode(status)


def novo_projeto():
    t = Terminal('V1/V7: projeto novo, com ← Voltar')
    t.esperar('O que você quer fazer?')
    t.enviar(ENTER, 'Novo projeto')
    t.esperar('Nome do projeto')
    t.enviar('teste_voltar' + ENTER, 'nome provisório')
    t.esperar('Em quais estados buscar?')
    t.apontar('← Voltar')
    t.enviar(ESPACO + ENTER, '← Voltar na lista de estados')
    t.esperar('Nome do projeto')
    t.enviar(ENTER, 'nome vazio = ← Voltar ao menu')
    t.esperar('O que você quer fazer?')
    t.enviar(ENTER, 'Novo projeto de novo')
    t.esperar('Nome do projeto')
    t.enviar('v04' + ENTER, 'nome v04')
    t.esperar('Em quais estados buscar?')
    t.apontar(' RR')
    t.enviar(ESPACO + ENTER, 'marca RR')
    t.esperar('Quantas casas?')
    t.apontar('Teste com 10')
    t.enviar(ENTER, 'teste com 10 casas')
    t.esperar('Baixar os textos originais')
    t.enviar(ENTER, 'PDFs: Não (padrão)')
    t.esperar('Tudo certo?')
    log(t.tela())
    t.apontar('← Voltar')
    t.enviar(ENTER, '← Voltar na confirmação')
    t.esperar('Baixar os textos originais')
    t.enviar(ENTER, 'PDFs: Não')
    t.esperar('Tudo certo?')
    t.enviar(ENTER, 'Começar')
    t.esperar('Etapa 2 de 2', 600)
    # deixa rodar até haver matérias raspadas, então Ctrl+C (V2)
    inicio = time.time()
    while time.time() - inicio < 1800:
        t.ler(5)
        texto = t.tela()
        if 'Resumo (SAPyL' in texto:
            log('-- terminou antes de dar para interromper (poucas matérias)')
            break
        achado = re.findall(r'Matérias\s+(\d+) raspadas', texto)
        if achado and int(achado[-1]) >= 5:
            log(f'-- {achado[-1]} matérias raspadas: Ctrl+C')
            log('--- painel antes do Ctrl+C ---')
            log(texto[-2500:])
            t.enviar(CTRL_C, 'Ctrl+C')
            t.esperar('Execução interrompida', 120)
            break
    codigo = t.fim(15)
    log(t.tela(0)[-5000:])
    log(f'-- código de saída: {codigo}')


def retomar():
    t = Terminal('V2/V3: retomar da lista e aceitar a autoria')
    t.esperar('O que você quer fazer?')
    t.apontar('Retomar um projeto')
    t.enviar(ENTER, 'Retomar um projeto')
    t.esperar('Qual projeto retomar?')
    t.ler(1)
    log('--- lista de projetos ---')
    log(t.tela())
    t.apontar('v04 —')
    t.enviar(ENTER, 'escolhe v04')
    t.esperar('Continuar este projeto?')
    t.enviar(ENTER, 'Continuar')
    t.esperar('Resumo (SAPyL', 3600)
    t.ler(2)
    texto = t.tela()
    if 'Buscar agora a autoria' in texto:
        t.apontar('Sim')
        t.enviar(ENTER, 'Sim: autoria e tramitação agora')
        t.esperar('Autoria e tramitação:', 3600)
        t.ler(3)
    else:
        log('-- oferta da autoria não apareceu')
    codigo = t.fim(30)
    log(t.tela(0)[-7000:])
    log(f'-- código de saída: {codigo}')


if __name__ == '__main__':
    etapa = sys.argv[4] if len(sys.argv) > 4 else 'tudo'
    if etapa in ('tudo', 'novo'):
        novo_projeto()
    if etapa in ('tudo', 'retomar'):
        retomar()
    log('===== fim =====')
