"""Uso: python medir_rampa.py <pasta do projeto> <teto por servidor>

Medidas de uma rampa (como na §7 da validação do paralelismo): por servidor (IP)."""

import collections
import datetime as dt
import pathlib
import re
import socket
import statistics
import sys

pasta = pathlib.Path(sys.argv[1])
pat = re.compile(
    r'^(\S+ \S+) DEBUG sapyl\.http (\S+) \| \S+ \| (\S+) \| tentativa.*?\| enviada (\S+)$'
)
envios = collections.defaultdict(list)
tempos, status = [], collections.Counter()
hosts429 = set()
por_minuto = collections.defaultdict(list)
inicio = fim = None
for arquivo in sorted(pasta.glob('logs/*.log')):
    for linha in arquivo.read_text(encoding='utf-8').splitlines():
        m = pat.match(linha)
        if not m:
            continue
        quando = dt.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S,%f')
        enviada = dt.datetime.combine(
            quando.date(), dt.datetime.strptime(m.group(4), '%H:%M:%S.%f').time()
        )
        host, st = m.group(2), m.group(3)
        envios[host].append(enviada)
        resp = (quando - enviada).total_seconds()
        if resp >= 0:
            tempos.append(resp)
            por_minuto[enviada.strftime('%H:%M')].append(resp)
        status[st] += 1
        if st == '429':
            hosts429.add(host)
        inicio = min(inicio or enviada, enviada)
        fim = max(fim or enviada, enviada)
ips = {}
for h in envios:
    try:
        ips[h] = socket.gethostbyname(h)
    except OSError:
        ips[h] = '?'
por_ip = collections.defaultdict(list)
for h, ts in envios.items():
    por_ip[ips[h]] += ts
teto = int(sys.argv[2])
for ip, ts in sorted(por_ip.items(), key=lambda x: -len(x[1])):
    ts.sort()
    maximo, j = 0, 0
    minutos_no_teto = set()
    for i, t in enumerate(ts):
        while ts[j] < t - dt.timedelta(seconds=60):
            j += 1
        n = i - j + 1
        maximo = max(maximo, n)
        if n >= 0.95 * teto:
            minutos_no_teto.add(t.strftime('%H:%M'))
    casas = len([h for h in envios if ips[h] == ip])
    print(
        f'{ip}: {casas} casas, {len(ts)} requisições, máx em 60 s: {maximo}, '
        f'minutos no teto: {len(minutos_no_teto)}'
        + (f' ({min(minutos_no_teto)}–{max(minutos_no_teto)})' if minutos_no_teto else '')
    )
q = statistics.quantiles(tempos, n=20)
print(f'resposta mediana {statistics.median(tempos):.2f} s, p95 {q[18]:.2f} s')
pior = max((statistics.quantiles(v, n=20)[18], k) for k, v in por_minuto.items() if len(v) >= 20)
print(f'pior p95 por minuto: {pior[0]:.2f} s às {pior[1]}')
print('status:', dict(status.most_common(8)), '| hosts com 429:', len(hosts429))
print(f'duração (1º ao último envio): {fim - inicio}')
