# Identificador de Candidatos v3.85 — Final Artigo SBBD

Melhorias desta versão:

- Corrige `NameError: gerar_sankey_grafo_inteiro_html`.
- Corrige import de `gerar_chord_circular_html`.
- Mantém Sankey do grafo inteiro com `*` para candidatas identificadas.
- Mantém Chord circular na aba Grafo HTML.
- Aplica fundo branco/sem fundo preto nos HTMLs de grafo, Sankey, Timeline e Chord.
- Mantém legenda: azul=circular/ciclo/misto; laranja=somente entrada/target; vermelho=somente saída/source; Top N com hexágono/⬢.
- HTMLs são gravados em UTF-8.

Execução:

```bat
streamlit run app_identificador_de_candidatos.py
```
