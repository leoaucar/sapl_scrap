"""Texto da opção "Ajuda" do menu principal."""

TEXTO = """\
Ajuda do SAPyL

O que cada opção faz
  Novo projeto           busca as palavras-chave nas casas escolhidas, raspa cada
                         matéria encontrada e monta a planilha final
  Retomar um projeto     continua um projeto de onde parou e tenta de novo o que
                         falhou (nada é feito duas vezes)
  Atualizar um projeto   raspa de novo as matérias de um resultado final (todas ou
                         só as marcadas na coluna Relevante)
  Autoria e tramitação   acrescenta os autores e a última tramitação a um resultado
                         (de um projeto ou de qualquer CSV com a coluna Link Materia)

Palavras-chave
  O programa lê arquivos_csv/palavras_chave.csv (ou, se não existir,
  arquivos_csv/palavras_chave.xlsx) na pasta em que o sapyl foi aberto.
  A planilha precisa de uma coluna chamada Palavras, com uma busca por linha:
    plano diretor                   a expressão exata
    orçamento, emenda impositiva    os dois termos juntos na mesma matéria
  Exemplos: arquivos_csv/exemplo_palavras_chave.csv

Resultados
  Cada projeto fica na pasta <nome>_proj/. A planilha para abrir é
  <nome>_proj/<nome>_resultado_final.csv (uma linha por matéria).
  O log de cada execução fica em <nome>_proj/logs/.

Interromper e retomar
  Ctrl+C para tudo em poucos segundos. Para continuar, rode o sapyl de novo e
  escolha "Retomar um projeto".

Mais informações
  README:  https://github.com/leoaucar/sapyl#readme
  Página:  https://leoaucar.github.io/sapyl/
"""
