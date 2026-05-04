# -*- coding: utf-8 -*-
from __future__ import annotations

import os
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import sys
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from services.sparql_service import query_to_dataframe
from services.graph_rag_service import (
    GraphRAGConfig,
    responder_graph_rag,
    montar_query_fluxos,
    normalizar_lista_cnpj_cpf,
    diagnosticar_ids_no_kg,
)
from services.candidate_analysis import (
    gerar_listas_avancadas,
    salvar_listas,
    normalizar_df_fluxos,
    calcular_score_risco,
    exportar_excel,
    exportar_pdf_resumo,
)
from services.graph_html import gerar_grafo_html
from services.visual_analytics import (
    gerar_grafo_source_target_html,
    gerar_sankey_source_target_por_faixas_htmls,
    sugerir_faixas_valor_histograma,
    faixas_para_texto,
    parse_faixas_valor,
    gerar_chord_circular_html,
    gerar_timeline_html,
    filtrar_fluxos,
    ids_top_n,
)

APP_VERSION = "v3.87-sankey-source-target-faixas"
OUTPUT_DIR = ROOT / "output"
LOG_DIR = ROOT / "logs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
CONVERSAS_JSONL = LOG_DIR / "conversas_agentes.jsonl"


def dataframe_stretch(df: pd.DataFrame, **kwargs):
    try:
        return st.dataframe(df, width="stretch", **kwargs)
    except TypeError:
        return st.dataframe(df, use_container_width=True, **kwargs)


def registrar_conversa_agente(agente: str, mensagem: str, tipo: str = "info", extra: dict | None = None) -> None:
    registro = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agente": str(agente),
        "tipo": str(tipo),
        "mensagem": str(mensagem),
        "extra": extra or {},
    }
    with CONVERSAS_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def carregar_conversas_jsonl(path: Path = CONVERSAS_JSONL) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["timestamp", "agente", "tipo", "mensagem", "extra"])
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                rows.append({"timestamp": "", "agente": "sistema", "tipo": "raw", "mensagem": line, "extra": {}})
    return pd.DataFrame(rows)


def exibir_html_arquivo(path_html: str | Path, height: int = 820) -> None:
    p = Path(path_html)
    if not p.exists():
        st.warning(f"HTML não encontrado: {p}")
        return
    st.success(f"HTML gerado em: {p}")
    try:
        st.download_button("Baixar HTML do grafo", data=p.read_bytes(), file_name=p.name, mime="text/html")
    except Exception:
        pass
    try:
        if hasattr(st, "iframe"):
            st.iframe(p.resolve().as_uri(), height=height)
            return
    except Exception as e:
        st.caption(f"Não foi possível abrir com st.iframe: {e}")
    try:
        import streamlit.components.v1 as components
        components.html(p.read_text(encoding="utf-8", errors="ignore"), height=height, scrolling=True)
        return
    except Exception as e:
        st.caption(f"Não foi possível abrir com components.html: {e}")
    st.markdown(f"Abra manualmente no navegador: `{p.resolve()}`")


def ids_nao_retornados(ids_alvo: list[str], df_diag: pd.DataFrame) -> list[str]:
    if not ids_alvo:
        return []
    if df_diag is None or df_diag.empty or "CNPJ_CPF" not in df_diag.columns:
        return ids_alvo
    encontrados = set(df_diag["CNPJ_CPF"].astype(str))
    return sorted(set(ids_alvo) - encontrados)


def resumo_execucao(df_norm: pd.DataFrame, df_score: pd.DataFrame | None = None) -> dict:
    d = normalizar_df_fluxos(df_norm)
    return {
        "arestas": int(len(d)),
        "sources_distintos": int(d["Source"].nunique()) if "Source" in d.columns and not d.empty else 0,
        "targets_distintos": int(d["Target"].nunique()) if "Target" in d.columns and not d.empty else 0,
        "valor_total": float(d["VALOR"].sum()) if "VALOR" in d.columns and not d.empty else 0.0,
        "candidatos_score": int(len(df_score)) if df_score is not None else 0,
    }


st.set_page_config(page_title="Identificador de Candidatos — SBBD", layout="wide")
st.title("🔎 Identificador de Candidatos — Graph RAG Fiscal")
st.caption(f"Versão {APP_VERSION} — GraphDB/SPARQL, Graph RAG, CrewAI/Ollama seguros, NetworkX, score de risco, Excel/PDF e grafo avançado")

aba_cfg, aba_exec, aba_dash, aba_visual, aba_grafo, aba_rag, aba_conv = st.tabs([
    "Configuração",
    "Execução/Análise e Consulta",
    "Dashboard SBBD",
    "Visual Analytics",
    "Grafo HTML",
    "Graph RAG",
    "Conversas dos Agentes",
])

with aba_cfg:
    endpoint = st.text_input("Endpoint GraphDB/SPARQL", value="http://localhost:7202/repositories/KG_EFD_Demo")
    threshold = st.number_input("Threshold de valor", min_value=0.0, value=30000.0, step=1000.0)
    top_n = st.number_input("Top N maiores valores", min_value=1, max_value=10000, value=50, step=1)
    limit = st.number_input("Limite SPARQL", min_value=10, max_value=100000, value=2000, step=100)
    st.markdown("### LLM / Agentes")
    usar_ollama = st.checkbox("Habilitar Ollama", value=False)
    usar_crewai = st.checkbox("Habilitar CrewAI", value=False, help="Requer `pip install crewai`. A telemetria é desabilitada para evitar erro de thread no Streamlit.")
    ollama_model = st.text_input("Modelo Ollama/CrewAI", value="llama3.1")
    ollama_base_url = st.text_input("Base URL Ollama", value="http://localhost:11434")
    st.info("Falhas de CrewAI/Ollama são tratadas como aviso; a análise SPARQL continua e usa síntese determinística.")

with aba_exec:
    st.subheader("Consulta, listas e score de risco")
    cnpj_cpf = st.text_input("CNPJ/CPF alvo opcional", value="")
    lista_cnpj_cpf_texto = st.text_area("Lista de CNPJ/CPF para análise/carga", value="", height=140)
    ids_alvo = normalizar_lista_cnpj_cpf(lista_cnpj_cpf_texto)
    ids_alvo += [x for x in normalizar_lista_cnpj_cpf(cnpj_cpf) if x not in ids_alvo]
    ids_alvo = sorted(set(ids_alvo))

    if cnpj_cpf or lista_cnpj_cpf_texto:
        if ids_alvo:
            st.success(f"{len(ids_alvo)} CPF/CNPJ válido(s) informado(s).")
            with st.expander("Ver CPF/CNPJ normalizados", expanded=False):
                dataframe_stretch(pd.DataFrame({"CNPJ_CPF": ids_alvo}))
        else:
            st.warning("Nenhum CPF/CNPJ válido foi informado. Use CPF com 11 dígitos ou CNPJ com 14 dígitos.")

    query_default = montar_query_fluxos(cnpj_cpf=cnpj_cpf, lista_cnpj_cpf=lista_cnpj_cpf_texto, threshold=threshold, limit=int(limit))
    query = st.text_area("SPARQL", value=query_default, height=280)

    if st.button("Executar Análise e Gerar Listas", type="primary"):
        registrar_conversa_agente("Coordenador", "Iniciando análise SBBD.", "inicio", {"ids_alvo": ids_alvo, "threshold": threshold})
        if (cnpj_cpf or lista_cnpj_cpf_texto) and not ids_alvo:
            st.error("Entrada inválida: não há CPF/CNPJ válido.")
            registrar_conversa_agente("Validador", "Entrada sem CPF/CNPJ válido.", "erro")
            st.stop()

        if ids_alvo:
            try:
                df_diag = diagnosticar_ids_no_kg(endpoint, ids_alvo)
                st.session_state["df_diagnostico_ids"] = df_diag
                if df_diag.empty:
                    st.warning("Nenhum CPF/CNPJ informado foi localizado no KG como Source/Target.")
                else:
                    st.info("Diagnóstico dos CPF/CNPJ informados no KG:")
                    dataframe_stretch(df_diag)
                    faltantes = ids_nao_retornados(ids_alvo, df_diag)
                    if faltantes:
                        st.warning(f"CPF/CNPJ não localizados no KG: {', '.join(faltantes)}")
            except Exception as e:
                st.warning(f"Diagnóstico falhou: {type(e).__name__}: {e}")

        try:
            df = query_to_dataframe(endpoint, query)
            st.session_state["df_fluxos"] = df
            st.success(f"Consulta executada: {len(df)} linhas.")
            registrar_conversa_agente("SPARQL", f"Consulta executada com {len(df)} linhas.", "sucesso")
        except Exception as e:
            df = pd.DataFrame()
            st.error(f"Falha na consulta SPARQL: {type(e).__name__}: {e}")
            registrar_conversa_agente("SPARQL", f"Falha: {type(e).__name__}: {e}", "erro")

        try:
            df_norm = normalizar_df_fluxos(df)
            listas, df_final = gerar_listas_avancadas(df_norm, threshold=threshold, top_n=int(top_n))
            df_score = calcular_score_risco(df_norm, listas)
            salvar_listas(listas, df_final, OUTPUT_DIR)
            st.session_state["df_fluxos_normalizado"] = df_norm
            st.session_state["listas"] = listas
            st.session_state["df_final"] = df_final
            st.session_state["df_score"] = df_score
            st.success(f"Listas e score gerados. Lista final: {len(df_final)} CNPJ/CPF; score: {len(df_score)} candidatos.")
        except Exception as e:
            st.error(f"Falha ao gerar listas/score: {type(e).__name__}: {e}")
            registrar_conversa_agente("Listas", f"Falha: {type(e).__name__}: {e}", "erro")

        try:
            html = gerar_grafo_html(df, OUTPUT_DIR / "grafo_interacao.html", top_n=int(top_n), max_edges=int(min(max(int(limit), 100), 5000)))
            st.session_state["html_grafo"] = html
            st.success("Grafo HTML gerado.")
        except Exception as e:
            st.error(f"Falha ao gerar grafo HTML: {type(e).__name__}: {e}")

        try:
            resumo = resumo_execucao(st.session_state.get("df_fluxos_normalizado", pd.DataFrame()), st.session_state.get("df_score"))
            xlsx = exportar_excel(st.session_state.get("df_fluxos", pd.DataFrame()), st.session_state.get("listas", {}), st.session_state.get("df_final", pd.DataFrame()), st.session_state.get("df_score", pd.DataFrame()), OUTPUT_DIR / "relatorio_identificador_sbbd.xlsx")
            pdf = exportar_pdf_resumo(st.session_state.get("df_score", pd.DataFrame()), resumo, OUTPUT_DIR / "relatorio_identificador_sbbd.pdf")
            st.session_state["xlsx_relatorio"] = xlsx
            st.session_state["pdf_relatorio"] = pdf
            st.success("Relatórios Excel/PDF gerados.")
        except Exception as e:
            st.warning(f"Exportação Excel/PDF falhou: {type(e).__name__}: {e}")

    if "df_fluxos" in st.session_state:
        st.write("### Resultado SPARQL")
        df_show = st.session_state["df_fluxos"]
        if df_show.empty:
            st.info("A consulta SPARQL não retornou linhas para os parâmetros atuais.")
        dataframe_stretch(df_show)

    if "listas" in st.session_state:
        st.write("### Listas da próxima interação")
        for nome, lista in st.session_state["listas"].items():
            with st.expander(f"{nome} ({len(lista)})", expanded=False):
                dataframe_stretch(pd.DataFrame({"CNPJ_CPF": lista}))
        st.write("### Lista final consolidada")
        dataframe_stretch(st.session_state["df_final"])

    if "df_score" in st.session_state:
        st.write("### Score de risco")
        dataframe_stretch(st.session_state["df_score"])

    colx, colp = st.columns(2)
    if "xlsx_relatorio" in st.session_state and Path(st.session_state["xlsx_relatorio"]).exists():
        colx.download_button("Baixar relatório Excel", data=Path(st.session_state["xlsx_relatorio"]).read_bytes(), file_name="relatorio_identificador_sbbd.xlsx")
    if "pdf_relatorio" in st.session_state and Path(st.session_state["pdf_relatorio"]).exists():
        colp.download_button("Baixar relatório PDF", data=Path(st.session_state["pdf_relatorio"]).read_bytes(), file_name="relatorio_identificador_sbbd.pdf")

with aba_dash:
    st.subheader("Dashboard SBBD")
    dfn = st.session_state.get("df_fluxos_normalizado", pd.DataFrame())
    score = st.session_state.get("df_score", pd.DataFrame())
    resumo = resumo_execucao(dfn, score)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Arestas", resumo["arestas"])
    c2.metric("Sources", resumo["sources_distintos"])
    c3.metric("Targets", resumo["targets_distintos"])
    c4.metric("Valor total", f"{resumo['valor_total']:,.2f}")
    if not dfn.empty and "VALOR" in dfn.columns:
        st.write("#### Top fluxos por valor")
        top_fluxos = dfn.sort_values("VALOR", ascending=False).head(int(top_n))[["Source", "Target", "VALOR"]]
        dataframe_stretch(top_fluxos)
        chart_df = top_fluxos.copy(); chart_df["Fluxo"] = chart_df["Source"].astype(str) + " → " + chart_df["Target"].astype(str)
        st.bar_chart(chart_df.set_index("Fluxo")["VALOR"])
    if not score.empty:
        st.write("#### Top candidatos por score")
        dataframe_stretch(score.head(int(top_n)))
        try:
            st.bar_chart(score.head(int(top_n)).set_index("CNPJ_CPF")["score_risco"])
        except Exception:
            pass

with aba_visual:
    st.subheader("Visual Analytics completo")
    dfn_base = st.session_state.get("df_fluxos_normalizado", pd.DataFrame())
    if dfn_base.empty:
        st.info("Execute a análise para habilitar Sankey, timeline e grafo Source→Target.")
    else:
        cols_f = st.columns(4)
        uf_opts = ["Todos"]
        if "UF" in dfn_base.columns:
            uf_opts += sorted(dfn_base["UF"].dropna().astype(str).unique().tolist())
        periodo_col = next((c for c in ["PERIODO", "DT_DOC", "DATA", "MES_ANO", "ANO_MES"] if c in dfn_base.columns), None)
        periodo_opts = ["Todos"]
        if periodo_col:
            periodo_opts += sorted(dfn_base[periodo_col].dropna().astype(str).unique().tolist())
        uf_sel = cols_f[0].selectbox("UF", uf_opts)
        periodo_sel = cols_f[1].selectbox("Período", periodo_opts)
        metric_sel = cols_f[2].selectbox("Espessura/peso", ["valor", "qtd", "valor_qtd"], index=0)
        valor_min = cols_f[3].number_input("Valor mínimo", min_value=0.0, value=0.0, step=1000.0)
        dfv = filtrar_fluxos(dfn_base, uf=uf_sel, periodo=periodo_sel, valor_min=valor_min)
        st.caption(f"Fluxos após filtros: {len(dfv)}")
        cva1, cva2, cva3, cva4 = st.columns(4)
        cva1.metric("Arestas", len(dfv))
        cva2.metric("Sources", dfv["Source"].nunique() if "Source" in dfv.columns else 0)
        cva3.metric("Targets", dfv["Target"].nunique() if "Target" in dfv.columns else 0)
        cva4.metric("Valor", f"{float(dfv['VALOR'].sum() if 'VALOR' in dfv.columns else 0):,.2f}")

        st.markdown("### Grafo Source → Target")
        html_st = gerar_grafo_source_target_html(
            dfv,
            OUTPUT_DIR / "visual_graph_source_target.html",
            top_n=int(top_n),
            modo_espessura=metric_sel,
            max_edges=int(min(max(int(limit), 100), 5000)),
        )
        exibir_html_arquivo(html_st, height=860)

        metric_map = {"valor": "VALOR", "qtd": "QTD", "valor_qtd": "VALOR_QTD"}

        st.markdown("### Sankey Source → Target por faixas de valores")
        st.caption("O Sankey do grafo inteiro foi removido. Agora a segmentação por faixa é aplicada somente ao Sankey Source→Target; faixas sem arestas são ignoradas e não geram HTML vazio.")
        col_bins_a, col_bins_b = st.columns([1, 3])
        n_faixas_sankey = col_bins_a.number_input("Número de faixas sugeridas", min_value=1, max_value=20, value=5, step=1)
        faixas_sugeridas = sugerir_faixas_valor_histograma(dfn_base, int(n_faixas_sankey))
        df_faixas_sug = pd.DataFrame(faixas_sugeridas)
        if not df_faixas_sug.empty:
            col_bins_b.write("Resumo das faixas sugeridas pelo histograma")
            dataframe_stretch(df_faixas_sug[["nome", "min", "max", "qtd", "valor_total"]])
        texto_default = faixas_para_texto(faixas_sugeridas)
        texto_faixas = st.text_area(
            "Editar faixas do Sankey Source→Target — formato: nome|min|max",
            value=texto_default,
            height=180,
            help="Uma faixa por linha. Ex.: Baixo valor|0|30000. Também aceita min|max|nome.",
        )
        faixas_editadas = parse_faixas_valor(texto_faixas)
        if st.button("Gerar HTMLs Sankey Source→Target por faixa de valor"):
            paths_faixas, resumo_faixas = gerar_sankey_source_target_por_faixas_htmls(
                dfv,
                OUTPUT_DIR / "sankey_source_target_faixas",
                faixas_editadas,
                candidatos=st.session_state.get("df_final", pd.DataFrame()),
                metric=metric_map.get(metric_sel, "VALOR"),
            )
            st.session_state["sankey_faixas_paths"] = [str(x) for x in paths_faixas]
            st.session_state["sankey_faixas_resumo"] = resumo_faixas
            st.success(f"Gerados {len(paths_faixas)} HTML(s) de Sankey Source→Target por faixa com arestas.")

        if "sankey_faixas_resumo" in st.session_state:
            st.write("#### Resumo dos Sankeys Source→Target por faixa")
            dataframe_stretch(st.session_state["sankey_faixas_resumo"])
        if "sankey_faixas_paths" in st.session_state and st.session_state["sankey_faixas_paths"]:
            opcoes_sankey_faixa = st.session_state["sankey_faixas_paths"]
            escolhido_sankey_faixa = st.selectbox("Abrir Sankey Source→Target segmentado", opcoes_sankey_faixa, format_func=lambda x: Path(x).name)
            exibir_html_arquivo(escolhido_sankey_faixa, height=920)


        st.markdown("### Timeline de fluxos")
        html_timeline = gerar_timeline_html(dfv, OUTPUT_DIR / "visual_timeline_fluxos.html")
        exibir_html_arquivo(html_timeline, height=700)

        st.markdown("### Ranking visual de risco")
        score_v = st.session_state.get("df_score", pd.DataFrame())
        if not score_v.empty:
            dataframe_stretch(score_v.head(int(top_n)))
            try:
                st.bar_chart(score_v.head(int(top_n)).set_index("CNPJ_CPF")["score_risco"])
            except Exception:
                pass
        else:
            st.info("Score ainda não gerado.")


with aba_grafo:
    st.subheader("Grafo HTML avançado")
    st.caption("Legenda: azul=circular/ciclo; laranja=somente entrada/target; vermelho=somente saída/source; Top N usa formato hexagonal/⬢; misto usa azul.")
    if "html_grafo" in st.session_state:
        st.code(str(st.session_state["html_grafo"]))
        exibir_html_arquivo(st.session_state["html_grafo"])

        st.markdown("### Chord circular")
        dfn_chord = st.session_state.get("df_fluxos_normalizado", pd.DataFrame())
        if dfn_chord.empty:
            st.info("Não há dados normalizados para gerar o Chord circular.")
        else:
            metric_chord = st.selectbox("Peso do Chord circular", ["VALOR", "QTD", "VALOR_QTD"], index=0)
            max_nodes_chord = st.number_input("Máximo de nós no Chord", min_value=20, max_value=1000, value=160, step=20)
            html_chord = gerar_chord_circular_html(
                dfn_chord,
                OUTPUT_DIR / "grafo_chord_circular.html",
                candidatos=st.session_state.get("df_final", pd.DataFrame()),
                metric=metric_chord,
                max_nodes=int(max_nodes_chord),
            )
            exibir_html_arquivo(html_chord, height=940)
    else:
        st.info("Execute a análise para gerar o grafo HTML e o Chord circular.")

with aba_rag:
    st.subheader("Graph RAG com SPARQL + CrewAI/Ollama opcional")
    pergunta = st.text_area("Pergunta", value="Quais são os principais candidatos para próxima carga e por quê?", height=120)
    alvo_rag = st.text_input("CNPJ/CPF alvo para contexto Graph RAG", value="")
    lista_rag = st.text_area("Lista de CNPJ/CPF para contexto Graph RAG", value="", height=120)
    if st.button("Executar Graph RAG"):
        cfg = GraphRAGConfig(
            endpoint_url=endpoint,
            threshold=threshold,
            usar_ollama=usar_ollama,
            usar_crewai=usar_crewai,
            ollama_model=ollama_model,
            ollama_base_url=ollama_base_url,
            ollama_url=ollama_base_url.rstrip("/") + "/api/generate",
        )
        try:
            out = responder_graph_rag(cfg, pergunta, cnpj_cpf=alvo_rag, lista_cnpj_cpf=lista_rag)
            mecanismo = out.get("mecanismo", "deterministico")
            status_llm = out.get("status_llm", "desconhecido")
            avisos_llm = out.get("avisos", []) or []
            if status_llm.startswith("fallback"):
                st.warning("LLM/Agentes indisponíveis ou com falha. A análise SPARQL foi concluída e a resposta determinística foi usada.")
                with st.expander("Detalhes técnicos", expanded=False):
                    for aviso in avisos_llm:
                        st.write(f"- {aviso}")
            elif status_llm == "ok":
                st.success("LLM/Agentes executado com sucesso.")
            else:
                st.info("LLM/Agentes desabilitado. Usando resposta determinística.")
            st.caption(f"Mecanismo: {mecanismo} | Status LLM: {status_llm}")
            st.markdown(out["resposta"].replace("\n", "  \n"))
            st.markdown("### Contexto recuperado")
            dataframe_stretch(out["contexto"]["df"])

            st.markdown("### HTML Source → Target do contexto Graph RAG")
            df_ctx = normalizar_df_fluxos(out["contexto"]["df"])
            if df_ctx.empty:
                st.info("O contexto Graph RAG não trouxe arestas Source→Target para desenhar.")
            else:
                modo_rag = st.selectbox("Espessura da aresta do contexto", ["valor", "qtd", "valor_qtd"], key="modo_espessura_rag")
                html_rag = gerar_grafo_source_target_html(
                    df_ctx,
                    OUTPUT_DIR / "graph_rag_source_target.html",
                    top_n=int(top_n),
                    modo_espessura=modo_rag,
                    max_edges=1000,
                )
                exibir_html_arquivo(html_rag, height=860)
            registrar_conversa_agente("Graph RAG", out["resposta"], "resposta", {"mecanismo": mecanismo, "status_llm": status_llm, "avisos": avisos_llm})
        except Exception as e:
            st.error(f"Falha no Graph RAG: {type(e).__name__}: {e}")
            registrar_conversa_agente("Graph RAG", f"Falha: {type(e).__name__}: {e}", "erro")

with aba_conv:
    st.subheader("Conversas dos Agentes")
    st.caption(f"Arquivo: {CONVERSAS_JSONL}")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Atualizar conversas"):
            st.session_state["df_conversas"] = carregar_conversas_jsonl()
    with col_b:
        if st.button("Limpar conversas"):
            CONVERSAS_JSONL.unlink(missing_ok=True)
            st.session_state["df_conversas"] = carregar_conversas_jsonl()
            st.success("Conversas removidas.")
    df_conv = st.session_state.get("df_conversas", carregar_conversas_jsonl())
    if df_conv.empty:
        st.info("Ainda não há conversas/logs de agentes registrados.")
    else:
        filtro_agente = st.multiselect("Filtrar por agente", sorted(df_conv["agente"].dropna().astype(str).unique().tolist())) if "agente" in df_conv.columns else []
        df_view = df_conv.copy()
        if filtro_agente:
            df_view = df_view[df_view["agente"].astype(str).isin(filtro_agente)]
        dataframe_stretch(df_view)
        st.download_button("Baixar conversas JSONL", data=CONVERSAS_JSONL.read_text(encoding="utf-8") if CONVERSAS_JSONL.exists() else "", file_name="conversas_agentes.jsonl", mime="application/jsonl")
