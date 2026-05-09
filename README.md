## PFKG-LLM: Exploração Guiada de Dados Fiscais em Larga Escala com Grafos de Conhecimento e LLMs

Utiliza Agentes LLM locais desenvolvidos em CrewAI e Ollama, para exploração guiada em larga escala 
em Grafos de Conhecimentos Fiscais ( Fiscal Knowledge Graph).

![Fluxos Fiscais em Sankey](Fluxos_Fiscais_SANKEY.jpg)

Exemplo de Conversa dos Agentes Relacionados
![COnversa dos Agentes](Histórico_Conversa_dos_Agentes.jpg)

## Execução local

1. Instale Python 3.11+.
2. Instale e execute o GraphDB em `http://localhost:7202`.
3. Crie o repositório `KG_EFD_Demo`.
4. Importe `sample_data/KG_EFD_Demo_sample.trig`, de https://github.com/mariano-roberval/KG_EFD_Demo
5. Instale dependências:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.json config.json
streamlit run app_identificador_de_candidatos.py

## Vídeos Associados:

![Aba de Configuração com o botão de testar Agentes Ollama.mp4](https://github.com/mariano-roberval/PFKG-LLM/blob/main/Aba%20Execu%C3%A7%C3%A3o%20An%C3%A1lie%20e%20Consulta.mp4))
![Aba Execução Análise e Consulta.mp4](Aba Execução Análie e Consulta.mp4)
![Aba Execução Análise e Consulta - Sem lista de CNPJ.mp4](Aba Execução Análie e Consulta - Sem lista de CNPJ.mp4)
![Aba Dashboard SBBD.mp4](Aba Dashboard SBBD.mp4)
![Aba Graph RAG.mp4](Aba Graph RAG.mp4)
![Aba Graph RAG - A pergunta aos Agentes e a resposta deles.mp4](Aba Graph RAG - A pergunta aos Agentes e a resposta deles.mp4)
