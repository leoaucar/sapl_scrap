#!/bin/bash
# Rampa 120 (de novo) e 150, uma depois da outra, com 5 min entre elas.
cd "${PASTA:-val_ramp}" || exit 1
SAPYL=../.venv/bin/sapyl
for nome in ramp_120b ramp_150; do
  echo "===== $nome $(date +%H:%M:%S)"
  # Retomar (2), o projeto na posição 2 da lista, Continuar (1), sem autoria (n)
  printf '2\n2\n1\nn\n' | SAPYL_MENUS=0 $SAPYL > ${SAIDA:-/tmp}/$nome.out 2>&1
  echo "saída $? $(date +%H:%M:%S)"
  grep -m1 "^2- \|Projeto: " ${SAIDA:-/tmp}/$nome.out
  grep -m1 "Retomando o projeto" ${SAIDA:-/tmp}/$nome.out
  [ "$nome" = ramp_120b ] && sleep 300
done
echo "===== fim $(date +%H:%M:%S)"
