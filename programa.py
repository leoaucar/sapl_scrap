"""Atalho para rodar o programa sem instalá-lo: python programa.py

O código fica no pacote `sapyl` (veja sapyl/principal.py).
"""
import sys

from sapyl.principal import main

if __name__ == '__main__':
    sys.exit(main())
