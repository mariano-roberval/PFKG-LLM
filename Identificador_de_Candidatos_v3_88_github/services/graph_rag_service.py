# -*- coding: utf-8 -*-
"""
Graph RAG fiscal com SPARQL + resposta determinística + Ollama opcional + CrewAI opcional.
CrewAI é opcional: se não estiver instalado/configurado, o sistema cai para Ollama ou resposta determinística.
"""
from __future__ import annotations

import os
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Sequence

import pandas as pd

from services.sparql_service import query_to_dataframe


@dataclass
class GraphRAGConfig:
    endpoint_url: str
    threshold: float = 30000.0
    ollama_url: str = "http://localhost:11434/api/generate"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    usar_ollama: bool = False
    usar_crewai: bool = False
    timeout: int = 120


def normalizar_lista_cnpj_cpf(texto: str | Sequence[str] | None) -> List[str]:
    """Extrai CPF/CNPJ válidos (11 ou 14 dígitos), remove repetidos e ordena."""
    import re
    if texto is None:
        return []
    if isinstance(texto, (list, tuple, set)):
        bruto = "\n".join(str(x) for x in texto)
    else:
        bruto = str(texto)
    candidatos = re.findall(r"\d+", bruto)
    ids = []
    for c in candidatos:
        limpo = re.sub(r"\D", "", c)
        if len(limpo) in (11, 14):
            ids.append(limpo)
    return sorted(set(ids))


def montar_filtro_ids(ids: Sequence[str]) -> str:
    ids = normalizar_lista_cnpj_cpf(ids)
    if not ids:
        return ""
    values = " ".join(f'"{x}"' for x in ids)
    return f"VALUES ?ID_ALVO {{ {values} }}\n  FILTER(?Source = ?ID_ALVO || ?Target = ?ID_ALVO)"


def montar_query_fluxos(cnpj_cpf: str = "", threshold: float = 30000.0, limit: int = 1000, lista_cnpj_cpf: str | Sequence[str] | None = None) -> str:
    ids = normalizar_lista_cnpj_cpf(lista_cnpj_cpf)
    ids += [x for x in normalizar_lista_cnpj_cpf(cnpj_cpf) if x not in ids]
    filtro = montar_filtro_ids(ids)
    return f'''
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX vocab: <http://www.dados/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?Source ?Target (SUM(xsd:decimal(?VL)) AS ?VALOR) (COUNT(?doc) AS ?QTD)
WHERE {{
  ?doc ?pValor ?VL .
  FILTER(STR(?pValor) IN ("http://www.dados/VL_MERC", "http://www.dados/VL_DOC", "http://www.dados/VL_ITEM"))
  {{ ?doc vocab:hasSourceOrganization ?so . ?so vocab:CNPJ ?Source . }}
  UNION {{ ?doc vocab:hasSourcePerson ?sp . ?sp vocab:CPF ?Source . }}
  {{ ?doc vocab:hasTargetOrganization ?to . ?to vocab:CNPJ ?Target . }}
  UNION {{ ?doc vocab:hasTargetPerson ?tp . ?tp vocab:CPF ?Target . }}
  {filtro}
}}
GROUP BY ?Source ?Target
HAVING (SUM(xsd:decimal(?VL)) >= {float(threshold)})
ORDER BY DESC(?VALOR)
LIMIT {int(limit)}
'''


def montar_query_diagnostico_ids(ids: Sequence[str]) -> str:
    """Consulta leve para verificar se CPF/CNPJ informado existe como Source/Target no KG, sem aplicar threshold."""
    norm = normalizar_lista_cnpj_cpf(ids)
    if not norm:
        return ""
    values = " ".join([f'"{x}"' for x in norm])
    return f"""
PREFIX vocab: <http://www.dados/>
SELECT ?CNPJ_CPF (COUNT(?doc) AS ?QTD_OCORRENCIAS)
WHERE {{
  VALUES ?CNPJ_CPF {{ {values} }}
  {{ ?doc vocab:hasSourceOrganization ?so . ?so vocab:CNPJ ?CNPJ_CPF . }}
  UNION {{ ?doc vocab:hasSourcePerson ?sp . ?sp vocab:CPF ?CNPJ_CPF . }}
  UNION {{ ?doc vocab:hasTargetOrganization ?to . ?to vocab:CNPJ ?CNPJ_CPF . }}
  UNION {{ ?doc vocab:hasTargetPerson ?tp . ?tp vocab:CPF ?CNPJ_CPF . }}
}}
GROUP BY ?CNPJ_CPF
ORDER BY ?CNPJ_CPF
"""


def diagnosticar_ids_no_kg(endpoint_url: str, ids: Sequence[str]) -> pd.DataFrame:
    query = montar_query_diagnostico_ids(ids)
    if not query:
        return pd.DataFrame(columns=["CNPJ_CPF", "QTD_OCORRENCIAS"])
    return query_to_dataframe(endpoint_url, query)


def recuperar_contexto_graph_rag(cfg: GraphRAGConfig, pergunta: str, cnpj_cpf: str = "", lista_cnpj_cpf: str | Sequence[str] | None = None, limit: int = 1000) -> Dict[str, Any]:
    query = montar_query_fluxos(cnpj_cpf=cnpj_cpf, lista_cnpj_cpf=lista_cnpj_cpf, threshold=cfg.threshold, limit=limit)
    df = query_to_dataframe(cfg.endpoint_url, query)
    resumo = resumir_dataframe_fluxos(df)
    return {"pergunta": pergunta, "query": query, "df": df, "resumo": resumo}


def resumir_dataframe_fluxos(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or df.empty:
        return {"qtd_arestas": 0, "valor_total": 0.0, "top_fluxos": []}
    d = df.copy()
    if "VALOR" in d.columns:
        d["VALOR"] = pd.to_numeric(d["VALOR"], errors="coerce").fillna(0)
    top = d.sort_values("VALOR", ascending=False).head(10).to_dict(orient="records") if "VALOR" in d.columns else d.head(10).to_dict(orient="records")
    return {
        "qtd_arestas": int(len(d)),
        "qtd_sources": int(d["Source"].nunique()) if "Source" in d.columns else 0,
        "qtd_targets": int(d["Target"].nunique()) if "Target" in d.columns else 0,
        "valor_total": float(d["VALOR"].sum()) if "VALOR" in d.columns else 0.0,
        "top_fluxos": top,
    }


def montar_prompt(pergunta: str, resumo: Dict[str, Any]) -> str:
    return f"""
Você é um analista fiscal especialista em grafos de conhecimento, Graph RAG e SPARQL.
Responda com base apenas no contexto abaixo. Não invente dados.

Pergunta: {pergunta}
Resumo recuperado via SPARQL:
{json.dumps(resumo, ensure_ascii=False, indent=2)}

Responda objetivamente com:
1. Achados principais.
2. Sinais de risco fiscal/relacional.
3. CNPJ/CPF prioritários para próxima carga/análise.
4. Limitações dos dados retornados.
""".strip()


def chamar_ollama(prompt: str, cfg: GraphRAGConfig) -> str:
    payload = {
        "model": cfg.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(cfg.ollama_url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=cfg.timeout) as resp:
        out = json.loads(resp.read().decode("utf-8", errors="replace"))
    return out.get("response", "").strip()


def chamar_crewai(prompt: str, cfg: GraphRAGConfig) -> str:
    """
    Executa CrewAI com LLM local via Ollama quando disponível.
    Mantém import opcional para não quebrar instalação sem CrewAI.
    """
    try:
        from crewai import Agent, Task, Crew, Process, LLM
    except Exception as e:
        raise RuntimeError(f"CrewAI não está instalado/disponível: {e}")

    try:
        llm = LLM(model=f"ollama/{cfg.ollama_model}", base_url=cfg.ollama_base_url, temperature=0.1)
    except Exception:
        # Fallback para versões antigas do CrewAI que aceitam string model.
        llm = f"ollama/{cfg.ollama_model}"

    analista = Agent(
        role="Analista fiscal de grafos de conhecimento",
        goal="Interpretar resultados SPARQL de grafos fiscais e apontar candidatos para próxima carga/análise.",
        backstory="Especialista em DF-e, EFD, Graph RAG, SPARQL, detecção de fluxos circulares, saídas sem entradas e outliers.",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    tarefa = Task(
        description=prompt,
        expected_output="Resposta técnica objetiva em português, com achados, riscos, candidatos e limitações.",
        agent=analista,
    )
    crew = Crew(agents=[analista], tasks=[tarefa], process=Process.sequential, verbose=False)
    resultado = crew.kickoff()
    return str(resultado)


def responder_graph_rag(cfg: GraphRAGConfig, pergunta: str, cnpj_cpf: str = "", lista_cnpj_cpf: str | Sequence[str] | None = None) -> Dict[str, Any]:
    """
    Executa Graph RAG com degradação controlada.

    Importante: falha de CrewAI/Ollama NÃO é falha da análise. A consulta
    SPARQL e a síntese determinística continuam sendo consideradas sucesso.
    O retorno inclui status/avisos para a interface exibir em amarelo.
    """
    contexto = recuperar_contexto_graph_rag(cfg, pergunta, cnpj_cpf=cnpj_cpf, lista_cnpj_cpf=lista_cnpj_cpf)
    resumo = contexto["resumo"]
    prompt = montar_prompt(pergunta, resumo)

    resposta = ""
    mecanismo = "deterministico"
    status_llm = "desabilitado"
    avisos: list[str] = []

    if cfg.usar_crewai:
        try:
            resposta = chamar_crewai(prompt, cfg)
            mecanismo = "crewai"
            status_llm = "ok"
        except Exception as e_crewai:
            avisos.append(f"CrewAI indisponível/falhou: {e_crewai}")
            if cfg.usar_ollama:
                try:
                    resposta = chamar_ollama(prompt, cfg)
                    mecanismo = "ollama_fallback_crewai"
                    status_llm = "fallback_ollama"
                except Exception as e_ollama:
                    avisos.append(f"Ollama indisponível/falhou: {e_ollama}")
                    resposta = resposta_deterministica(resumo, erro_ollama="; ".join(avisos))
                    mecanismo = "deterministico_fallback"
                    status_llm = "fallback_deterministico"
            else:
                resposta = resposta_deterministica(resumo, erro_ollama="; ".join(avisos))
                mecanismo = "deterministico_fallback"
                status_llm = "fallback_deterministico"
    elif cfg.usar_ollama:
        try:
            resposta = chamar_ollama(prompt, cfg)
            mecanismo = "ollama"
            status_llm = "ok"
        except Exception as e:
            avisos.append(f"Ollama indisponível/falhou: {e}")
            resposta = resposta_deterministica(resumo, erro_ollama="; ".join(avisos))
            mecanismo = "deterministico_fallback"
            status_llm = "fallback_deterministico"
    else:
        resposta = resposta_deterministica(resumo)

    return {
        "resposta": resposta,
        "contexto": contexto,
        "mecanismo": mecanismo,
        "status_llm": status_llm,
        "avisos": avisos,
    }


def resposta_deterministica(resumo: Dict[str, Any], erro_ollama: Optional[str] = None) -> str:
    linhas = []
    if erro_ollama:
        linhas.append(f"LLM indisponível ou com falha; usando resposta determinística. Detalhe: {erro_ollama}")
    linhas.append(f"Foram recuperadas {resumo.get('qtd_arestas', 0)} arestas acima do threshold.")
    linhas.append(f"Sources distintos: {resumo.get('qtd_sources', 0)}; Targets distintos: {resumo.get('qtd_targets', 0)}.")
    linhas.append(f"Valor total agregado: {resumo.get('valor_total', 0.0):,.2f}.")
    top = resumo.get("top_fluxos", [])[:5]
    if top:
        linhas.append("Top fluxos:")
        for r in top:
            linhas.append(f"- {r.get('Source')} → {r.get('Target')}: {r.get('VALOR')}")
    else:
        linhas.append("Nenhum fluxo retornado para o contexto informado.")
    return "\n".join(linhas)
