# Identificador de Candidatos v3.79 — legenda e cores do grafo

A geração do grafo HTML foi ajustada para a legenda solicitada:

- **Circular e ciclo**: nós e arestas em azul.
- **Somente entrada / target**: nós e arestas em laranja.
- **Somente saída / source**: nós e arestas em vermelho.
- **Top N**: nós incidentes aparecem em formato hexagonal e as arestas Top N recebem marcador `⬢`.
- **Misto**: azul quando não houver cor dominante; se também for Top N, recebe o marcador `⬢` e a cor é combinada com azul.

Observação técnica: o vis-network não possui uma geometria real para arestas em hexágono. Por isso, a versão usa o marcador `⬢` na aresta e forma hexagonal nos nós Top N, preservando a semântica visual pedida.
