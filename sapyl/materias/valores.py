"""Normalização dos valores das matérias (texto, datas, sim/não, links)."""

from datetime import datetime
from urllib.parse import urlparse


def limpar(valor: object) -> str:
    """Texto numa linha só, sem espaços sobrando; None vira ''."""
    if valor is None:
        return ''
    return ' '.join(str(valor).split())


def data_br(valor: object) -> str:
    """'2025-07-02' -> '02/07/2025'. Outros formatos voltam como vieram."""
    valor = limpar(valor)
    try:
        return datetime.strptime(valor[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        return valor


def data_hora_br(valor: object) -> str:
    """'2026-09-21T13:25:49.124190-03:00' -> '21/09/2026 13:25' (hora local do site)."""
    valor = limpar(valor)
    try:
        return datetime.strptime(valor[:16], '%Y-%m-%dT%H:%M').strftime('%d/%m/%Y %H:%M')
    except ValueError:
        return valor


def sim_nao(valor: object) -> str:
    """True -> 'Sim', False -> 'Não', vazio -> ''."""
    if valor is None or valor == '':
        return ''
    return 'Sim' if valor else 'Não'


def esquema_da_casa(link: str, casa_url: str) -> str:
    """Troca o esquema/host do link pelos da casa (a API devolve `http://`)."""
    if not link:
        return ''
    partes, casa = urlparse(link), urlparse(casa_url)
    if partes.hostname == casa.hostname:
        return partes._replace(scheme=casa.scheme, netloc=casa.netloc).geturl()
    return link
