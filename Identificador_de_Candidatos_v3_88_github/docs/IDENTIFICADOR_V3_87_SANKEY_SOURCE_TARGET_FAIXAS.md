# Identificador de Candidatos v3.87 — Sankey Source→Target por faixas

Alterações:

- Removido o Sankey do grafo inteiro.
- A segmentação por faixa agora é aplicada somente ao Sankey Source→Target.
- Faixas sem arestas não geram HTML e não aparecem no seletor.
- As faixas continuam sugeridas pelo histograma e podem ser editadas no Streamlit.
- Fundo branco preservado nos HTMLs.
- Candidatas identificadas seguem marcadas com `*`.


## v3.88

- Removido o Sankey Source→Target filtrado geral e o arquivo `visual_sankey_source_target.html`.
- Mantidos apenas os Sankeys Source→Target segmentados por faixa de valor, sem gerar HTML para faixas sem arestas.
