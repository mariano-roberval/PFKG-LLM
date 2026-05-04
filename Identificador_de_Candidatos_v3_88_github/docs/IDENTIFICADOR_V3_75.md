# Identificador de Candidatos v3.75

Correções principais:

- Aba **Conversas dos Agentes**.
- Caixa de texto para lista de CPF/CNPJ e diagnóstico independente do threshold.
- Geração de listas e grafo mesmo com consulta vazia.
- Substituição de `use_container_width=True` por `width="stretch"` com fallback.
- Remoção de `st.components.v1.html`; exibição via `st.iframe`/`st.html` quando disponível.
- Registro de logs em `logs/conversas_agentes.jsonl`.
