# Identificador de Candidatos v3.78 — Correção UTF-8 no Grafo

Correção aplicada na geração do HTML do grafo:

- Evita `net.save_graph()`, que em algumas versões do PyVis usa o encoding padrão do Windows.
- Usa `net.generate_html()` e grava explicitamente com `encoding='utf-8'`.
- Mantém legenda, filtros, busca, Top N e cores automáticas da v3.77.

Erro corrigido:

```text
UnicodeEncodeError: 'charmap' codec can't encode characters
```
