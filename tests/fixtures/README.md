# Fixtures dos testes

Páginas e respostas reais do SAPL, salvas para que os testes rodem sem rede.
**Nunca** troque estes arquivos por versões novas sem rever os testes que
dependem dos valores exatos.

## `sapl/` — coletadas em 24/10/2026

Três casas: Câmara de Rio Branco/AC (`sapl.riobranco.ac.leg.br`), Assembleia
Legislativa do Acre (`sapl.al.ac.leg.br`) e Câmara de Cascavel/PR
(`sapl.cascavel.pr.leg.br`). A URL de origem, o status HTTP e a data de cada
arquivo estão em [`sapl/index.json`](sapl/index.json) (as entradas `HEAD`
só registram os cabeçalhos dos PDFs, sem arquivo).

| Arquivo | Origem |
|---|---|
| `busca_p1.html` | `/sistema/search/?page=1&q="plano+diretor"` |
| `busca_vazia.html` | busca sem resultados (200, "Foram encontrados 0 registros") |
| `busca_fim.html` | `page=999` (404: fim da paginação) |
| `materia_<id>.html` | página da matéria `/materia/<id>` |
| `materia_<id>_autoria.html`, `materia_<id>_tramitacao.html` | abas de autoria e tramitação |
| `materia_34049_assunto.html` | aba "Assunto" (vazia; motivo de remover a coluna `Assuntos`) |
| `api_materia_<id>.json` | `/api/materia/materialegislativa/<id>/` |
| `api_tipomateria_1.json`, `api_regime_1.json`, `api_autor_145.json` | consultas de nomes na API |
| `api_autoria_<id>.json`, `api_tramitacao_<id>.json` | listas `/api/materia/autoria/?materia=<id>` e `/api/materia/tramitacao/?materia=<id>` (34049 em 24/10; as demais em 27/10/2026) |
| `api_autor_<id>.json`, `api_tipoautor_<id>.json` | `/api/base/autor/<id>/` e `/api/base/tipoautor/<id>/` |
| `api_statustramitacao_<id>.json`, `api_unidadetramitacao_<id>.json` | nomes do status e das unidades do último trâmite |

Particularidades usadas nos testes:

- Autoria e tramitação pela API existem para 34049 e 46496 (Rio Branco) e
  38415 e 43301 (Cascavel), as mesmas matérias que têm as abas HTML. Em
  27/10/2026 o último trâmite e os autores pela API batiam com as páginas
  HTML de 24/10. O nome do autor no HTML é o `__str__` da API (`nome - cargo`
  quando há cargo, ex.: "Executivo Municipal - sapladm"), não o campo `nome`.

- `sapl.riobranco.ac.leg.br/materia_34049.html` tem **dois**
  `div_id_texto_original`; só o primeiro tem o link do PDF.
- Nas respostas da API, os campos `ip`, `user` e `operadores` (dados de
  servidores das casas) foram apagados (`null`) antes de salvar.

## `sinteticas/` — derivadas das reais

| Arquivo | Como foi feito |
|---|---|
| `materia_sem_data.html` | `sapl.cascavel.pr.leg.br/materia_43301.html` com o valor de `div_id_data_apresentacao` esvaziado |
| `materia_sem_pdf.html` | `sapl.al.ac.leg.br/materia_15951.html` sem os links de `div_id_texto_original` |

Respostas que não vêm de arquivo (429 com `Retry-After`, erros 5xx, timeouts,
casas sem API) são montadas nos próprios testes com `tests/apoio.py`.

## `projeto_fase1/` — pasta de projeto gravada pela versão da Fase 1

Gravada em 27/10/2026 por [`gerar_projeto_fase1.py`](gerar_projeto_fase1.py),
com o código da Fase 1 (antes do pacote `sapyl`), contra o SAPL falso
`tests.apoio.sapl_fase1`: Rio Branco (API) e Cascavel (só HTML), 8 matérias,
com downloads. A matéria `sapl.riobranco.ac.leg.br/44086` ficou com `erro`
(HTTP 503). Tem o arquivo bruto antigo (`_resultados_crus_casas.csv`, com o
HTML das páginas) e o log antigo (`fase1.log`).

Serve para conferir que projetos antigos continuam retomando e atualizando
(`tests/test_compat_fase1.py`). **Não regrave:** o script importa módulos da
Fase 1 que deixam de existir depois da mudança para o pacote. Os testes
sempre trabalham numa cópia.
