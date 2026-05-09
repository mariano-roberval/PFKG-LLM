# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import pandas as pd
from pyvis.network import Network


def _ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def preparar_fluxos(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Source", "Target", "VALOR", "QTD"])
    d = df.copy()
    for col in ["Source", "Target"]:
        if col not in d.columns:
            d[col] = ""
        d[col] = d[col].astype(str).str.strip()
    valor_col = None
    for cand in ["VALOR", "TOTAL_VL_MERC", "VL_MERC", "VL_DOC", "VL_ITEM", "TOTAL", "valor"]:
        if cand in d.columns:
            valor_col = cand
            break
    d["VALOR"] = pd.to_numeric(d[valor_col], errors="coerce").fillna(0.0) if valor_col else 0.0
    qtd_col = None
    for cand in ["QTD", "QUANTIDADE", "qtd", "COUNT", "count"]:
        if cand in d.columns:
            qtd_col = cand
            break
    d["QTD"] = pd.to_numeric(d[qtd_col], errors="coerce").fillna(1.0) if qtd_col else 1.0
    d = d[(d["Source"] != "") & (d["Target"] != "")].copy()
    return d


def ids_top_n(df: pd.DataFrame, top_n: int = 50) -> list[str]:
    d = preparar_fluxos(df)
    ids: list[str] = []
    for _, r in d.sort_values("VALOR", ascending=False).iterrows():
        ids.append(str(r["Source"]))
        ids.append(str(r["Target"]))
    return list(dict.fromkeys(ids))[: max(1, int(top_n))]


def categorias_nos(df: pd.DataFrame) -> dict[str, str]:
    d = preparar_fluxos(df)
    sources = set(d["Source"].astype(str))
    targets = set(d["Target"].astype(str))
    pares = set(zip(d["Source"].astype(str), d["Target"].astype(str)))
    ciclo = set()
    for s, t in pares:
        if (t, s) in pares:
            ciclo.update([s, t])
    cat = {}
    for n in sources | targets:
        if n in ciclo:
            cat[n] = "circular_ciclo"
        elif n in targets and n not in sources:
            cat[n] = "somente_entrada_target"
        elif n in sources and n not in targets:
            cat[n] = "somente_saida_source"
        else:
            cat[n] = "misto"
    return cat


def cor_categoria(cat: str) -> str:
    return {
        "circular_ciclo": "#1f77b4",
        "somente_entrada_target": "#ff7f0e",
        "somente_saida_source": "#d62728",
        "misto": "#1f77b4",
    }.get(cat, "#1f77b4")


def largura_aresta(row: pd.Series, modo: str = "valor") -> float:
    valor = float(row.get("VALOR", 0) or 0)
    qtd = float(row.get("QTD", 1) or 1)
    vq = valor / max(qtd, 1.0)
    if modo == "qtd":
        return max(1.0, min(24.0, math.log1p(qtd) * 2.2))
    if modo == "valor_qtd":
        return max(1.0, min(24.0, math.log1p(vq) / 1.8))
    return max(1.0, min(24.0, math.log1p(valor) / 1.8))


def gerar_grafo_source_target_html(
    df: pd.DataFrame,
    out_path: str | Path,
    top_n: int = 50,
    modo_espessura: str = "valor",
    max_edges: int = 5000,
) -> Path:
    d = preparar_fluxos(df).sort_values("VALOR", ascending=False).head(max_edges)
    out = _ensure_dir(out_path)
    top_ids = set(ids_top_n(d, top_n))
    cats = categorias_nos(d)
    net = Network(height="820px", width="100%", directed=True, bgcolor="white", font_color="black")
    net.barnes_hut(gravity=-9000, central_gravity=0.2, spring_length=180, spring_strength=0.035, damping=0.55)

    for _, r in d.iterrows():
        s, t = str(r["Source"]), str(r["Target"])
        valor = float(r.get("VALOR", 0) or 0)
        qtd = float(r.get("QTD", 1) or 1)
        vq = valor / max(qtd, 1.0)
        for n in [s, t]:
            cat = cats.get(n, "misto")
            net.add_node(
                n,
                label=n,
                title=f"{n}<br>Categoria: {cat}<br>Top N: {'sim' if n in top_ids else 'não'}",
                color=cor_categoria(cat),
                shape="hexagon" if n in top_ids else "dot",
                size=24 if n in top_ids else 14,
            )
        edge_cat = cats.get(s, "misto")
        is_top = s in top_ids or t in top_ids
        net.add_edge(
            s,
            t,
            arrows="to",
            color=cor_categoria(edge_cat),
            width=largura_aresta(r, modo_espessura),
            label="⬢" if is_top else "",
            title=f"{s} → {t}<br>Valor: {valor:,.2f}<br>Qtd: {qtd:,.0f}<br>Valor/Qtd: {vq:,.2f}<br>Espessura: {modo_espessura}",
        )

    html = net.generate_html()
    legenda = f"""
    <div style='position:fixed;left:16px;bottom:16px;z-index:9999;background:#fff;color:#111;border:1px solid #ccc;border-radius:10px;padding:12px;font-family:Arial;font-size:13px;box-shadow:0 2px 14px rgba(0,0,0,.25)'>
      <b>Legenda — Source → Target</b><br>
      <span style='color:#1f77b4'>●</span> Circular/ciclo ou misto<br>
      <span style='color:#ff7f0e'>●</span> Somente entrada/target<br>
      <span style='color:#d62728'>●</span> Somente saída/source<br>
      ⬢ Top N: nó hexagonal e aresta marcada<br>
      Arestas direcionadas para o Target<br>
      Espessura: <b>{modo_espessura}</b>
    </div>
    """
    html = html.replace("</body>", legenda + "</body>") if "</body>" in html else html + legenda
    out.write_text(html, encoding="utf-8")
    return out


def gerar_sankey_html(df: pd.DataFrame, out_path: str | Path, max_edges: int = 200, metric: str = "VALOR") -> Path:
    d = preparar_fluxos(df).sort_values(metric if metric in preparar_fluxos(df).columns else "VALOR", ascending=False).head(max_edges)
    out = _ensure_dir(out_path)
    if d.empty:
        out.write_text("<html><body><h3>Sem dados para Sankey.</h3></body></html>", encoding="utf-8")
        return out
    nodes = list(dict.fromkeys(d["Source"].astype(str).tolist() + d["Target"].astype(str).tolist()))
    idx = {n: i for i, n in enumerate(nodes)}
    values = d["QTD"].tolist() if metric == "QTD" else (d["VALOR"] / d["QTD"].clip(lower=1)).tolist() if metric == "VALOR_QTD" else d["VALOR"].tolist()
    data = [{
        "type": "sankey",
        "orientation": "h",
        "node": {"pad": 15, "thickness": 14, "line": {"color": "black", "width": 0.4}, "label": nodes},
        "link": {"source": [idx[x] for x in d["Source"].astype(str)], "target": [idx[x] for x in d["Target"].astype(str)], "value": values,
                 "customdata": d[["VALOR", "QTD"]].astype(str).values.tolist(),
                 "hovertemplate": "Valor/Qtd/Fluxo<br>Valor=%{customdata[0]}<br>Qtd=%{customdata[1]}<br>Peso=%{value}<extra></extra>"}
    }]
    html = f"""<!doctype html><html><head><meta charset='utf-8'><script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script></head>
<body style='background:white;color:#111;font-family:Arial,sans-serif'><h3>Sankey Source → Target</h3><div id='sankey' style='width:100%;height:760px'></div>
<script>Plotly.newPlot('sankey', {json.dumps(data, ensure_ascii=False)}, {{title:'Fluxos fiscais — Sankey ({metric})', font:{{size:10}}}}, {{responsive:true}});</script></body></html>"""
    out.write_text(html, encoding="utf-8")
    return out


def gerar_timeline_html(df: pd.DataFrame, out_path: str | Path, date_col: str | None = None) -> Path:
    d = preparar_fluxos(df)
    out = _ensure_dir(out_path)
    if d.empty:
        out.write_text("<html><body><h3>Sem dados para timeline.</h3></body></html>", encoding="utf-8")
        return out
    candidate = date_col or next((c for c in ["PERIODO", "DT_DOC", "DATA", "MES_ANO", "ANO_MES"] if c in d.columns), None)
    if not candidate:
        d["PERIODO_ANALISE"] = "sem_periodo"
        candidate = "PERIODO_ANALISE"
    grp = d.groupby(candidate, as_index=False).agg(VALOR=("VALOR", "sum"), QTD=("QTD", "sum"))
    grp[candidate] = grp[candidate].astype(str)
    data_valor = [{"x": grp[candidate].tolist(), "y": grp["VALOR"].tolist(), "type": "bar", "name": "Valor"}]
    data_qtd = [{"x": grp[candidate].tolist(), "y": grp["QTD"].tolist(), "type": "scatter", "mode": "lines+markers", "name": "Qtd", "yaxis": "y2"}]
    data = data_valor + data_qtd
    layout = {"title": f"Timeline fiscal por {candidate}", "yaxis": {"title": "Valor"}, "yaxis2": {"title": "Qtd", "overlaying": "y", "side": "right"}}
    html = f"""<!doctype html><html><head><meta charset='utf-8'><script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script></head>
<body style='background:white;color:#111;font-family:Arial,sans-serif'><h3>Timeline fiscal</h3><div id='timeline' style='width:100%;height:620px'></div>
<script>Plotly.newPlot('timeline', {json.dumps(data, ensure_ascii=False)}, {json.dumps(layout, ensure_ascii=False)}, {{responsive:true}});</script></body></html>"""
    out.write_text(html, encoding="utf-8")
    return out


def filtrar_fluxos(df: pd.DataFrame, uf: str | None = None, periodo: str | None = None, valor_min: float = 0.0) -> pd.DataFrame:
    d = preparar_fluxos(df)
    if valor_min:
        d = d[d["VALOR"] >= float(valor_min)]
    if uf and uf != "Todos" and "UF" in d.columns:
        d = d[d["UF"].astype(str) == str(uf)]
    periodo_col = next((c for c in ["PERIODO", "DT_DOC", "DATA", "MES_ANO", "ANO_MES"] if c in d.columns), None)
    if periodo and periodo != "Todos" and periodo_col:
        d = d[d[periodo_col].astype(str) == str(periodo)]
    return d.copy()



def _candidatos_set(candidatos: Iterable[str] | pd.DataFrame | None) -> set[str]:
    """Normaliza a lista de candidatos para marcação visual com *."""
    if candidatos is None:
        return set()
    if isinstance(candidatos, pd.DataFrame):
        if candidatos.empty:
            return set()
        col = "CNPJ_CPF" if "CNPJ_CPF" in candidatos.columns else candidatos.columns[0]
        vals = candidatos[col].dropna().astype(str).tolist()
    else:
        vals = [str(x) for x in candidatos]
    return {v.strip() for v in vals if v and v.strip().lower() not in {"nan", "none"}}


def gerar_sankey_grafo_inteiro_html(
    df: pd.DataFrame,
    out_path: str | Path,
    candidatos: Iterable[str] | pd.DataFrame | None = None,
    metric: str = "VALOR",
) -> Path:
    """Gera Sankey do grafo inteiro, agregando Source->Target e marcando candidatos com *.

    Diferente do Sankey exploratório com max_edges, esta função usa todas as arestas
    disponíveis no DataFrame normalizado, agregando pares iguais para reduzir ruído.
    """
    d = preparar_fluxos(df)
    out = _ensure_dir(out_path)
    if d.empty:
        out.write_text("<html><meta charset='utf-8'><body><h3>Sem dados para Sankey do grafo inteiro.</h3></body></html>", encoding="utf-8")
        return out

    d = d.groupby(["Source", "Target"], as_index=False).agg(VALOR=("VALOR", "sum"), QTD=("QTD", "sum"))
    d["VALOR_QTD"] = d["VALOR"] / d["QTD"].clip(lower=1)
    metric = metric if metric in {"VALOR", "QTD", "VALOR_QTD"} else "VALOR"
    d = d.sort_values(metric, ascending=False)

    cand = _candidatos_set(candidatos)
    nodes = list(dict.fromkeys(d["Source"].astype(str).tolist() + d["Target"].astype(str).tolist()))
    labels = [("* " + n) if n in cand else n for n in nodes]
    idx = {n: i for i, n in enumerate(nodes)}
    values = d[metric].astype(float).clip(lower=0.000001).tolist()
    custom = d[["VALOR", "QTD", "VALOR_QTD"]].round(2).astype(str).values.tolist()

    data = [{
        "type": "sankey",
        "orientation": "h",
        "arrangement": "snap",
        "node": {
            "pad": 12,
            "thickness": 12,
            "line": {"color": "black", "width": 0.3},
            "label": labels,
        },
        "link": {
            "source": [idx[x] for x in d["Source"].astype(str)],
            "target": [idx[x] for x in d["Target"].astype(str)],
            "value": values,
            "customdata": custom,
            "hovertemplate": "Source → Target<br>Valor=%{customdata[0]}<br>Qtd=%{customdata[1]}<br>Valor/Qtd=%{customdata[2]}<br>Peso=%{value}<extra></extra>",
        },
    }]
    layout = {
        "title": f"Sankey do grafo inteiro — * indica candidata identificada — peso: {metric}",
        "font": {"size": 10},
        "margin": {"l": 10, "r": 10, "t": 50, "b": 10},
        "paper_bgcolor": "white",
        "plot_bgcolor": "white",
        "font": {"size": 10, "color": "#111"},
    }
    html = f"""<!doctype html><html><head><meta charset='utf-8'>
<script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script></head>
<body>
<h3>Sankey do grafo inteiro</h3>
<p><b>*</b> marca os CNPJ/CPF candidatos identificados nas listas da próxima interação.</p>
<div id='sankey_all' style='width:100%;height:860px'></div>
<script>Plotly.newPlot('sankey_all', {json.dumps(data, ensure_ascii=False)}, {json.dumps(layout, ensure_ascii=False)}, {{responsive:true}});</script>
</body></html>"""
    out.write_text(html, encoding="utf-8")
    return out


def gerar_chord_circular_html(
    df: pd.DataFrame,
    out_path: str | Path,
    candidatos: Iterable[str] | pd.DataFrame | None = None,
    metric: str = "VALOR",
    max_nodes: int = 160,
) -> Path:
    """Gera Chord circular Source->Target em D3.

    Para manter o navegador utilizável, quando o grafo tiver muitos nós, mantém os
    `max_nodes` nós de maior volume agregado e informa isso no HTML.
    """
    d = preparar_fluxos(df)
    out = _ensure_dir(out_path)
    if d.empty:
        out.write_text("<html><meta charset='utf-8'><body><h3>Sem dados para Chord circular.</h3></body></html>", encoding="utf-8")
        return out

    d = d.groupby(["Source", "Target"], as_index=False).agg(VALOR=("VALOR", "sum"), QTD=("QTD", "sum"))
    d["VALOR_QTD"] = d["VALOR"] / d["QTD"].clip(lower=1)
    metric = metric if metric in {"VALOR", "QTD", "VALOR_QTD"} else "VALOR"

    volume = pd.concat([
        d.groupby("Source")[metric].sum(),
        d.groupby("Target")[metric].sum(),
    ], axis=1).fillna(0).sum(axis=1).sort_values(ascending=False)
    all_nodes_count = int(len(volume))
    keep = set(volume.head(max(1, int(max_nodes))).index.astype(str))
    d_plot = d[d["Source"].astype(str).isin(keep) & d["Target"].astype(str).isin(keep)].copy()
    nodes = list(volume.head(max(1, int(max_nodes))).index.astype(str))
    idx = {n: i for i, n in enumerate(nodes)}
    matrix = [[0.0 for _ in nodes] for __ in nodes]
    tooltip = {}
    for _, r in d_plot.iterrows():
        s, t = str(r["Source"]), str(r["Target"])
        if s in idx and t in idx:
            val = float(r.get(metric, 0) or 0)
            matrix[idx[s]][idx[t]] += val
            tooltip[f"{idx[s]}-{idx[t]}"] = {
                "source": s,
                "target": t,
                "valor": float(r.get("VALOR", 0) or 0),
                "qtd": float(r.get("QTD", 0) or 0),
                "valor_qtd": float(r.get("VALOR_QTD", 0) or 0),
            }
    cand = _candidatos_set(candidatos)
    labels = [("* " + n) if n in cand else n for n in nodes]
    payload = {
        "nodes": nodes,
        "labels": labels,
        "matrix": matrix,
        "tooltip": tooltip,
        "metric": metric,
        "total_nodes": all_nodes_count,
        "shown_nodes": len(nodes),
    }
    html = f"""<!doctype html><html><head><meta charset='utf-8'>
<script src='https://cdn.jsdelivr.net/npm/d3@7'></script>
<style>
body {{ font-family: Arial, sans-serif; margin: 0; background: white; color: #111; }}
#wrap {{ padding: 12px; }}
#chart {{ width: 100%; height: 900px; }}
.tooltip {{ position:absolute; pointer-events:none; background:#fff; color:#111; border:1px solid #ccc; border-radius:8px; padding:8px; font-size:12px; box-shadow:0 2px 10px rgba(0,0,0,.3); opacity:0; }}
.small {{ color:#333; font-size:13px; }}
</style></head><body><div id='wrap'>
<h3>Chord circular Source → Target</h3>
<div class='small'><b>*</b> marca candidatas identificadas. Nós exibidos: {len(nodes)} de {all_nodes_count}. Peso: {metric}.</div>
<div id='chart'></div><div id='tip' class='tooltip'></div></div>
<script>
const payload = {json.dumps(payload, ensure_ascii=False)};
const width = Math.min(window.innerWidth - 30, 1100), height = 880;
const outerRadius = Math.min(width, height) * 0.42;
const innerRadius = outerRadius - 18;
const svg = d3.select('#chart').append('svg').attr('viewBox', [-width/2, -height/2, width, height]);
const tip = d3.select('#tip');
const chord = d3.chordDirected().padAngle(0.025).sortSubgroups(d3.descending).sortChords(d3.descending)(payload.matrix);
const color = d3.scaleOrdinal(d3.schemeTableau10);
const arc = d3.arc().innerRadius(innerRadius).outerRadius(outerRadius);
const ribbon = d3.ribbonArrow().radius(innerRadius - 1).padAngle(0.004);
svg.append('g').selectAll('path').data(chord.groups).join('path')
  .attr('fill', d => color(d.index)).attr('stroke', d => d3.rgb(color(d.index)).darker())
  .attr('d', arc).append('title').text(d => payload.labels[d.index] + '\\nTotal: ' + d.value.toLocaleString('pt-BR'));
svg.append('g').attr('fill-opacity', 0.72).selectAll('path').data(chord).join('path')
  .attr('d', ribbon)
  .attr('fill', d => color(d.source.index))
  .attr('stroke', d => d3.rgb(color(d.source.index)).darker())
  .on('mousemove', function(event, d) {{
    const key = d.source.index + '-' + d.target.index;
    const x = payload.tooltip[key] || {{source: payload.nodes[d.source.index], target: payload.nodes[d.target.index]}};
    tip.style('opacity', 1).style('left', (event.pageX+12)+'px').style('top', (event.pageY+12)+'px')
      .html('<b>' + x.source + ' → ' + x.target + '</b><br>Valor: ' + Number(x.valor||0).toLocaleString('pt-BR') + '<br>Qtd: ' + Number(x.qtd||0).toLocaleString('pt-BR') + '<br>Valor/Qtd: ' + Number(x.valor_qtd||0).toLocaleString('pt-BR'));
  }})
  .on('mouseout', () => tip.style('opacity', 0));
svg.append('g').selectAll('text').data(chord.groups).join('text')
  .each(d => {{ d.angle = (d.startAngle + d.endAngle) / 2; }})
  .attr('dy', '.35em')
  .attr('transform', d => `rotate(${{d.angle * 180 / Math.PI - 90}}) translate(${{outerRadius + 8}}) ${{d.angle > Math.PI ? 'rotate(180)' : ''}}`)
  .attr('text-anchor', d => d.angle > Math.PI ? 'end' : null)
  .attr('font-size', '9px').attr('fill', '#111')
  .text(d => payload.labels[d.index]);
</script></body></html>"""
    out.write_text(html, encoding="utf-8")
    return out



def sugerir_faixas_valor_histograma(df: pd.DataFrame, n_faixas: int = 5) -> list[dict]:
    """Sugere faixas de VALOR por bins de histograma de largura regular.

    Retorna lista de dicts: {min, max, nome, qtd, valor_total}.
    As faixas são fechadas no limite inferior e abertas no superior, exceto a última.
    """
    d = preparar_fluxos(df)
    if d.empty or "VALOR" not in d.columns:
        return []
    valores = pd.to_numeric(d["VALOR"], errors="coerce").fillna(0.0)
    valores = valores[valores >= 0]
    if valores.empty:
        return []
    vmin = float(valores.min())
    vmax = float(valores.max())
    n = max(1, int(n_faixas or 1))
    if vmax <= vmin:
        qtd = int(len(d))
        return [{"min": vmin, "max": vmax, "nome": f"Faixa 01 — {vmin:,.2f} a {vmax:,.2f}", "qtd": qtd, "valor_total": float(valores.sum())}]
    passo = (vmax - vmin) / n
    faixas = []
    for i in range(n):
        a = vmin + i * passo
        b = vmax if i == n - 1 else vmin + (i + 1) * passo
        if i == n - 1:
            mask = (d["VALOR"] >= a) & (d["VALOR"] <= b)
        else:
            mask = (d["VALOR"] >= a) & (d["VALOR"] < b)
        sub = d[mask]
        faixas.append({
            "min": float(a),
            "max": float(b),
            "nome": f"Faixa {i+1:02d} — {a:,.2f} a {b:,.2f}",
            "qtd": int(len(sub)),
            "valor_total": float(sub["VALOR"].sum()) if not sub.empty else 0.0,
        })
    return faixas


def faixas_para_texto(faixas: list[dict]) -> str:
    """Serializa faixas para edição manual no Streamlit.

    Formato por linha: nome|min|max
    Exemplo: Alto valor|100000|500000
    """
    linhas = []
    for f in faixas:
        nome = str(f.get("nome", "Faixa"))
        a = float(f.get("min", 0) or 0)
        b = float(f.get("max", 0) or 0)
        linhas.append(f"{nome}|{a:.2f}|{b:.2f}")
    return "\n".join(linhas)


def parse_faixas_valor(texto: str) -> list[dict]:
    """Lê faixas editáveis no formato nome|min|max ou min|max|nome."""
    faixas: list[dict] = []
    for i, raw in enumerate(str(texto or "").splitlines(), start=1):
        linha = raw.strip()
        if not linha or linha.startswith("#"):
            continue
        partes = [p.strip() for p in linha.split("|")]
        try:
            if len(partes) >= 3:
                # preferido: nome|min|max; alternativo: min|max|nome
                try:
                    a = float(partes[0].replace(".", "").replace(",", "."))
                    b = float(partes[1].replace(".", "").replace(",", "."))
                    nome = partes[2]
                except ValueError:
                    nome = partes[0]
                    a = float(partes[1].replace(".", "").replace(",", "."))
                    b = float(partes[2].replace(".", "").replace(",", "."))
            elif len(partes) == 2:
                nome = f"Faixa {i:02d}"
                a = float(partes[0].replace(".", "").replace(",", "."))
                b = float(partes[1].replace(".", "").replace(",", "."))
            else:
                continue
            if b < a:
                a, b = b, a
            faixas.append({"nome": nome or f"Faixa {i:02d}", "min": float(a), "max": float(b)})
        except Exception:
            continue
    return faixas


def gerar_sankey_grafo_inteiro_por_faixas_htmls(
    df: pd.DataFrame,
    out_dir: str | Path,
    faixas: list[dict],
    candidatos: Iterable[str] | pd.DataFrame | None = None,
    metric: str = "VALOR",
) -> tuple[list[Path], pd.DataFrame]:
    """Gera um HTML Sankey para cada faixa de VALOR.

    As faixas são definidas por min/max sobre a coluna VALOR, independentemente
    da métrica de peso escolhida para o Sankey.
    """
    d = preparar_fluxos(df)
    out_base = Path(out_dir)
    out_base.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    resumo_rows = []
    if d.empty or not faixas:
        empty = out_base / "sankey_faixas_sem_dados.html"
        empty.write_text("<html><meta charset='utf-8'><body style='background:white;color:#111'><h3>Sem dados/faixas para Sankey segmentado.</h3></body></html>", encoding="utf-8")
        return [empty], pd.DataFrame(columns=["faixa", "min", "max", "arestas", "sources", "targets", "valor_total", "html"])

    for i, f in enumerate(faixas, start=1):
        a = float(f.get("min", 0) or 0)
        b = float(f.get("max", 0) or 0)
        nome = str(f.get("nome") or f"Faixa {i:02d}")
        if i == len(faixas):
            sub = d[(d["VALOR"] >= a) & (d["VALOR"] <= b)].copy()
        else:
            sub = d[(d["VALOR"] >= a) & (d["VALOR"] < b)].copy()
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in nome)[:80] or f"faixa_{i:02d}"
        out_path = out_base / f"sankey_grafo_inteiro_faixa_{i:02d}_{safe}.html"
        if sub.empty:
            html = f"""<!doctype html><html><head><meta charset='utf-8'></head><body style='background:white;color:#111;font-family:Arial,sans-serif'>
<h3>Sankey segmentado — {nome}</h3><p>Faixa: {a:,.2f} a {b:,.2f}</p><p>Sem arestas nesta faixa.</p></body></html>"""
            out_path.write_text(html, encoding="utf-8")
        else:
            gerar_sankey_grafo_inteiro_html(sub, out_path, candidatos=candidatos, metric=metric)
            html = out_path.read_text(encoding="utf-8", errors="ignore")
            bloco = f"<h4>Segmento por faixa de valor: {nome}</h4><p>Faixa considerada: {a:,.2f} a {b:,.2f}. Arestas: {len(sub)}. Valor total: {float(sub['VALOR'].sum()):,.2f}.</p>"
            html = html.replace("<h3>Sankey do grafo inteiro</h3>", f"<h3>Sankey do grafo inteiro — {nome}</h3>" + bloco)
            out_path.write_text(html, encoding="utf-8")
        paths.append(out_path)
        resumo_rows.append({
            "faixa": nome,
            "min": a,
            "max": b,
            "arestas": int(len(sub)),
            "sources": int(sub["Source"].nunique()) if not sub.empty else 0,
            "targets": int(sub["Target"].nunique()) if not sub.empty else 0,
            "valor_total": float(sub["VALOR"].sum()) if not sub.empty else 0.0,
            "html": str(out_path),
        })
    resumo = pd.DataFrame(resumo_rows)
    try:
        resumo.to_csv(out_base / "resumo_sankey_faixas.csv", index=False, encoding="utf-8-sig")
    except Exception:
        pass
    return paths, resumo



def gerar_sankey_source_target_por_faixas_htmls(
    df: pd.DataFrame,
    out_dir: str | Path,
    faixas: list[dict],
    candidatos: Iterable[str] | pd.DataFrame | None = None,
    metric: str = "VALOR",
    max_edges: int = 500,
) -> tuple[list[Path], pd.DataFrame]:
    """Gera Sankey Source→Target por faixas de VALOR.

    Diferente da versão anterior, esta rotina NÃO cria HTML para faixas vazias.
    Uma faixa só aparece no resumo e no seletor se houver pelo menos uma aresta
    Source→Target cujo VALOR esteja dentro do intervalo definido.
    """
    d = preparar_fluxos(df)
    out_base = Path(out_dir)
    out_base.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    resumo_rows = []

    if d.empty or not faixas:
        resumo = pd.DataFrame(columns=["faixa", "min", "max", "arestas", "sources", "targets", "valor_total", "html"])
        try:
            resumo.to_csv(out_base / "resumo_sankey_source_target_faixas.csv", index=False, encoding="utf-8-sig")
        except Exception:
            pass
        return [], resumo

    cand = _candidatos_set(candidatos)

    for i, f in enumerate(faixas, start=1):
        a = float(f.get("min", 0) or 0)
        b = float(f.get("max", 0) or 0)
        nome = str(f.get("nome") or f"Faixa {i:02d}")
        if b < a:
            a, b = b, a

        if i == len(faixas):
            sub = d[(d["VALOR"] >= a) & (d["VALOR"] <= b)].copy()
        else:
            sub = d[(d["VALOR"] >= a) & (d["VALOR"] < b)].copy()

        # Regra solicitada: faixa sem aresta não gera HTML.
        if sub.empty:
            continue

        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in nome)[:80] or f"faixa_{i:02d}"
        out_path = out_base / f"sankey_source_target_faixa_{i:02d}_{safe}.html"
        gerar_sankey_html(sub, out_path, max_edges=max_edges, metric=metric)
        html = out_path.read_text(encoding="utf-8", errors="ignore")
        bloco = f"""
<div style='font-family:Arial,sans-serif;margin:8px 0;padding:8px;border:1px solid #ddd;background:#fff'>
  <b>Segmento Source→Target por faixa:</b> {nome}<br>
  Faixa considerada: {a:,.2f} a {b:,.2f}<br>
  Arestas: {len(sub)} | Sources: {sub['Source'].nunique()} | Targets: {sub['Target'].nunique()} | Valor total: {float(sub['VALOR'].sum()):,.2f}<br>
  Candidatas marcadas com * nos rótulos dos nós quando presentes.
</div>
"""
        # Marca candidatas nos labels de nós do HTML Plotly, sem alterar os dados originais.
        for c in cand:
            if not c:
                continue
            html = html.replace(f'"{c}"', f'"{c} *"')
        html = html.replace("<h3>Sankey Source → Target</h3>", f"<h3>Sankey Source → Target — {nome}</h3>" + bloco)
        out_path.write_text(html, encoding="utf-8")

        paths.append(out_path)
        resumo_rows.append({
            "faixa": nome,
            "min": a,
            "max": b,
            "arestas": int(len(sub)),
            "sources": int(sub["Source"].nunique()),
            "targets": int(sub["Target"].nunique()),
            "valor_total": float(sub["VALOR"].sum()),
            "html": str(out_path),
        })

    resumo = pd.DataFrame(resumo_rows, columns=["faixa", "min", "max", "arestas", "sources", "targets", "valor_total", "html"])
    try:
        resumo.to_csv(out_base / "resumo_sankey_source_target_faixas.csv", index=False, encoding="utf-8-sig")
    except Exception:
        pass
    return paths, resumo
