# Identificador de Candidatos v3.86 — Sankey por Faixas de Valores

Melhorias incluídas:

- Segmentação do **Sankey do grafo inteiro** por faixas de valores.
- As faixas são sugeridas conforme histograma da coluna `VALOR`.
- As faixas podem ser editadas no Streamlit no formato `nome|min|max`.
- Cada faixa gera um HTML próprio em `output/sankey_faixas/`.
- É gerado também `resumo_sankey_faixas.csv` com quantidade de arestas, sources, targets e valor total por faixa.
- Mantém fundo branco e `*` para candidatos identificados.
