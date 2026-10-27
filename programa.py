"""Atalho para rodar o programa sem instalá-lo: python programa.py

O código fica no pacote `sapyl` (veja sapyl/interface/principal.py).
"""
import sys

from sapyl.interface.principal import executar

if __name__ == '__main__':
    sys.exit(executar())
