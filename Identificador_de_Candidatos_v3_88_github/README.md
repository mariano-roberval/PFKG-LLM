# Identificador de Candidatos — Graph RAG Fiscal v3.88

Aplicação Streamlit para análise de candidatos em grafos fiscais RDF/SPARQL. A aplicação consulta um endpoint GraphDB/SPARQL, gera listas ordenadas e sem repetição de CNPJ/CPF para a próxima interação, produz grafos HTML, Chord circular e Sankey Source→Target segmentado por faixas de valor.

## Recursos principais

- Consulta SPARQL em endpoint GraphDB ou compatível.
- Entrada por CNPJ/CPF único e por lista de CNPJ/CPF.
- Graph RAG com CrewAI e/ou Ollama opcionais, com fallback determinístico.
- Aba de conversas dos agentes e diagnóstico de falhas de LLM como aviso, não como falha da análise SPARQL.
- Geração de listas de candidatos:
  - só entradas/targets;
  - só saídas/sources;
  - circulares/ciclos/carrossel;
  - outliers/bursts;
  - valores próximos ao threshold;
  - Top N global, por Source, por Target, por período e por UF quando disponível.
- Grafo HTML com tema claro, UTF-8, cores automáticas e Top N destacado.
- Chord circular na aba de grafo.
- Visual Analytics com Sankey Source→Target por faixas de valor editáveis.
- Exportação para Excel/PDF quando habilitada.

## Estrutura

```text
.
├── app_identificador_de_candidatos.py
├── services/
│   ├── candidate_analysis.py
│   ├── graph_html.py
│   ├── graph_rag_service.py
│   ├── sparql_service.py
│   └── visual_analytics.py
├── docs/
├── input/          # não versionar dados reais
├── output/         # HTMLs, CSVs e relatórios gerados
├── logs/
├── reports/
├── config.example.json
├── .env.example
├── requirements.txt
└── executar_identificador_de_candidatos.bat
```

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

No Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuração

Copie o arquivo de exemplo:

```bash
copy config.example.json config.json
```

Edite `config.json` e ajuste o endpoint, threshold e Top N:

```json
{
  "endpoint_url": "http://localhost:7202/repositories/KG_EFD_Demo",
  "threshold": 30000,
  "top_n": 50,
  "limite_arestas": 1000,
  "usar_crewai": false,
  "usar_ollama": false
}
```

## Execução

```bash
streamlit run app_identificador_de_candidatos.py
```

Ou no Windows:

```bat
executar_identificador_de_candidatos.bat
```

## Uso com CrewAI/Ollama

CrewAI e Ollama são opcionais. A aplicação continua funcionando com resposta determinística se eles não estiverem disponíveis.

Para habilitar Ollama:

```bash
ollama serve
ollama pull llama3.1
```

No `config.json`:

```json
{
  "usar_ollama": true,
  "ollama_model": "llama3.1",
  "ollama_timeout": 120
}
```

Para CrewAI, instale separadamente:

```bash
pip install crewai crewai-tools
```

A telemetria CrewAI/OTel é desabilitada para evitar erro de signal/thread no Streamlit.

## Observação de segurança

Não versionar dados fiscais reais, RDFs completos, relatórios gerados, HTMLs de execução ou configurações locais com endpoints/senhas. O `.gitignore` já bloqueia esses arquivos por padrão.

## Licença

Defina a licença do projeto conforme a política do autor/instituição antes de publicar publicamente.
