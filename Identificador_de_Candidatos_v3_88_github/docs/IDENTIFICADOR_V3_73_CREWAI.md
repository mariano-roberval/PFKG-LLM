# Identificador de Candidatos v3.73

Correções e melhorias:

- Opção para habilitar CrewAI no Graph RAG Fiscal.
- Opção separada para habilitar Ollama.
- Fallback automático: CrewAI -> Ollama -> resposta determinística.
- Correção do erro pandas: `operation 'or_' not supported for dtype 'str' with dtype 'str'`.
- A geração de listas, grafo HTML e gráficos passou a ser feita em blocos independentes; uma falha não bloqueia as demais etapas.
- Inclusão do prefixo `xsd:` na consulta SPARQL padrão.
- Gráfico de barras dos Top fluxos no Streamlit.

## Execução

```bat
streamlit run apps\identificador_de_candidatos.py
```

## CrewAI

Para usar CrewAI local com Ollama:

```bat
pip install crewai
ollama serve
ollama pull llama3.1
```

Depois habilite `Habilitar CrewAI` na aba Configuração.
