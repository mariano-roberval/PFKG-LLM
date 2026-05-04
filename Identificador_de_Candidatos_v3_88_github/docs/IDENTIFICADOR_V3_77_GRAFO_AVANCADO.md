# Identificador de Candidatos v3.77 — Grafo avançado

## Melhorias

- Renderização robusta do HTML do grafo no Streamlit.
- Correção do erro `st.html(..., height=...)`.
- Fallbacks: `st.iframe`, `components.html`, `st.html` sem `height` e botão de download.
- Grafo PyVis com recursos embutidos (`cdn_resources="in_line"`) para uso offline.
- Legenda no próprio HTML.
- Filtros client-side por classe:
  - ciclos / circulares;
  - somente entradas / targets;
  - somente saídas / sources;
  - Top N;
  - busca textual por nó.
- Botões para ativar/congelar física do grafo.
- Destaque visual dos Top N em roxo.

## Cores

- Azul: ciclo/circular.
- Laranja: somente target/entrada.
- Vermelho: somente source/saída.
- Roxo: Top N.
- Cinza: misto.
