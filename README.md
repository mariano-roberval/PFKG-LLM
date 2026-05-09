## PFKG-LLM: Exploração Guiada de Dados Fiscais em Larga Escala com Grafos de Conhecimento e LLMs

Utiliza Agentes LLM locais desenvolvidos em CrewAI e Ollama, para exploração guiada em larga escala 
em Grados de Conhecimentos (Knowledge Graph).

## Execução local

1. Instale Python 3.11+.
2. Instale e execute o GraphDB em `http://localhost:7202`.
3. Crie o repositório `KG_EFD_Demo`.
4. Importe `sample_data/KG_EFD_Demo_sample.trig`.
5. Instale dependências:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.json config.json
streamlit run app_identificador_de_candidatos.py
