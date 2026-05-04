# Identificador de Candidatos v3.83 — Visual Analytics completo

## Objetivo

A v3.83 adiciona visualizações analíticas ao Identificador de Candidatos, mantendo a integração com GraphDB/SPARQL, Graph RAG, CrewAI/Ollama/fallback determinístico e os relatórios Excel/PDF.

## Novidades

### Aba Visual Analytics

Inclui:

1. **Grafo Source → Target**
   - Direcionado para o Target.
   - Arestas com tooltip de valor, quantidade e valor/qtd.
   - Espessura configurável por `valor`, `qtd` ou `valor_qtd`.

2. **Sankey Source → Target**
   - Mostra a distribuição dos fluxos agregados.
   - Peso por valor, quantidade ou valor/qtd.

3. **Timeline fiscal**
   - Usa automaticamente uma coluna temporal se existir: `PERIODO`, `DT_DOC`, `DATA`, `MES_ANO` ou `ANO_MES`.

4. **Filtros interativos**
   - UF, quando houver coluna `UF`.
   - Período, quando houver coluna temporal.
   - Valor mínimo.

5. **Ranking visual de risco**
   - Exibe os principais candidatos já calculados pelo score de risco.

### Aba Graph RAG

Ao final do Graph RAG, a aplicação agora gera um HTML **Source → Target** com o contexto recuperado pela consulta.

## Legenda do grafo

- Azul: circular/ciclo ou misto.
- Laranja: somente entrada/target.
- Vermelho: somente saída/source.
- Top N: nó hexagonal e aresta marcada com `⬢`.

## Arquivos gerados

Na pasta `output/`:

- `visual_graph_source_target.html`
- `visual_sankey_source_target.html`
- `visual_timeline_fluxos.html`
- `graph_rag_source_target.html`

