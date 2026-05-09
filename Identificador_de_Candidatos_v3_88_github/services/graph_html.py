# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import json
import html
import pandas as pd
from pyvis.network import Network


def _safe_id(x) -> str:
    return str(x or "").strip()


def classificar_nos(df: pd.DataFrame, top_ids: set[str] | None = None) -> dict:
    """
    Classifica nós para colorização automática:
    - ciclo: existe A->B e B->A
    - somente_target: aparece apenas como destino
    - somente_source: aparece apenas como origem
    - topN: pertence à lista de destaque Top N
    - misto: demais casos
    """
    if df is None or df.empty:
        return {}
    d = df.copy()
    d["Source"] = d.get("Source", "").astype(str)
    d["Target"] = d.get("Target", "").astype(str)
    pares = set((str(s), str(t)) for s, t in zip(d["Source"], d["Target"]) if str(s) and str(t))
    sources = set(d["Source"].dropna().astype(str))
    targets = set(d["Target"].dropna().astype(str))
    top_ids = set(top_ids or [])
    classes = {}
    for n in sorted((sources | targets) - {"", "nan", "None"}):
        tem_ciclo = any((b, a) in pares for a, b in pares if a == n or b == n)
        if n in top_ids:
            classes[n] = "topN"
        elif tem_ciclo:
            classes[n] = "ciclo"
        elif n in targets and n not in sources:
            classes[n] = "somente_target"
        elif n in sources and n not in targets:
            classes[n] = "somente_source"
        else:
            classes[n] = "misto"
    return classes


def cor_por_classe(classe: str) -> str:
    # Legenda solicitada:
    # ciclo/circular = azul; somente target/entrada = laranja;
    # somente source/saída = vermelho; misto = azul se não houver outra cor.
    return {
        "topN": "#1f77b4",
        "ciclo": "#1f77b4",
        "somente_target": "#ff7f0e",
        "somente_source": "#d62728",
        "misto": "#1f77b4",
    }.get(classe, "#1f77b4")


def _hex_to_rgb(cor: str) -> tuple[int, int, int]:
    cor = (cor or "#1f77b4").strip().lstrip("#")
    if len(cor) != 6:
        cor = "1f77b4"
    return int(cor[0:2], 16), int(cor[2:4], 16), int(cor[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(v))):02x}" for v in rgb)


def misturar_com_azul(cor: str, peso_azul: float = 0.35) -> str:
    """Mistura a cor base com azul para destacar Top N sem perder a categoria."""
    r1, g1, b1 = _hex_to_rgb(cor)
    r2, g2, b2 = _hex_to_rgb("#1f77b4")
    p = max(0.0, min(1.0, float(peso_azul)))
    return _rgb_to_hex((r1 * (1 - p) + r2 * p, g1 * (1 - p) + g2 * p, b1 * (1 - p) + b2 * p))


def classificar_aresta(s: str, t: str, pares: set[tuple[str, str]], sources: set[str], targets: set[str]) -> str:
    """Classificação da aresta para legenda e cor.

    Prioridade:
    1. Circular/ciclo: existe s->t e t->s.
    2. Somente entrada/target: destino aparece apenas como target.
    3. Somente saída/source: origem aparece apenas como source.
    4. Misto: demais casos.
    """
    if (t, s) in pares:
        return "ciclo"
    if t in targets and t not in sources:
        return "somente_target"
    if s in sources and s not in targets:
        return "somente_source"
    return "misto"


def _extrair_top_ids(df: pd.DataFrame, top_n: int = 50) -> set[str]:
    if df is None or df.empty:
        return set()
    d = df.copy()
    if "VALOR" not in d.columns:
        return set()
    d["VALOR"] = pd.to_numeric(d["VALOR"], errors="coerce").fillna(0.0)
    ids = []
    for _, r in d.sort_values("VALOR", ascending=False).head(max(1, int(top_n))).iterrows():
        ids.append(str(r.get("Source", "")))
        ids.append(str(r.get("Target", "")))
    return {x for x in ids if x and x.lower() not in {"nan", "none"}}


def _inject_controls(pyvis_html: str, titulo: str, resumo: dict) -> str:
    """Adiciona legenda, filtros client-side e botões de física ao HTML gerado pelo PyVis."""
    resumo_json = html.escape(json.dumps(resumo, ensure_ascii=False), quote=True)
    painel = f"""
    <style>
      .pfkg-panel {{
        font-family: Arial, sans-serif; padding: 10px 14px; margin: 8px 0 10px 0;
        border: 1px solid #ddd; border-radius: 12px; background: #fafafa;
      }}
      .pfkg-panel h2 {{ margin: 0 0 8px 0; font-size: 18px; }}
      .pfkg-legend span {{ display:inline-block; margin: 4px 12px 4px 0; font-size: 13px; }}
      .pfkg-dot {{ width:12px; height:12px; display:inline-block; border-radius:50%; margin-right:5px; vertical-align:middle; }}
      .pfkg-controls button, .pfkg-controls input {{ margin: 4px; padding: 6px 8px; border-radius: 8px; border: 1px solid #bbb; }}
      .pfkg-controls button {{ cursor:pointer; background:#fff; }}
    </style>
    <div class="pfkg-panel">
      <h2>{html.escape(titulo)}</h2>
      <div class="pfkg-legend">
        <span><i class="pfkg-dot" style="background:#1f77b4"></i>Circular / ciclo</span>
        <span><i class="pfkg-dot" style="background:#ff7f0e"></i>Somente entrada / target</span>
        <span><i class="pfkg-dot" style="background:#d62728"></i>Somente saída / source</span>
        <span><i class="pfkg-dot" style="background:#1f77b4"></i>Top N: aresta marcada com ⬢ e nó hexagonal</span>
        <span><i class="pfkg-dot" style="background:#1f77b4"></i>Misto: azul quando não houver cor dominante</span>
      </div>
      <div class="pfkg-controls">
        <input id="pfkgSearch" placeholder="Filtrar nó..." onkeyup="pfkgFilterNodes()" />
        <button onclick="pfkgShowAll()">Mostrar todos</button>
        <button onclick="pfkgOnlyClass('topN')">Só Top N</button>
        <button onclick="pfkgOnlyClass('ciclo')">Só ciclos</button>
        <button onclick="pfkgOnlyClass('somente_source')">Só saídas</button>
        <button onclick="pfkgOnlyClass('somente_target')">Só entradas</button>
        <button onclick="network.startSimulation()">Ativar física</button>
        <button onclick="network.stopSimulation()">Congelar</button>
      </div>
      <small id="pfkgResumo" data-resumo="{resumo_json}"></small>
    </div>
    """
    script = """
    <script type="text/javascript">
      function pfkgAllNodes(){ return nodes.get(); }
      function pfkgConnectedVisible(nodeId, visibleIds){
        var connected = network.getConnectedNodes(nodeId) || [];
        for (var i=0; i<connected.length; i++){ if(visibleIds.has(String(connected[i]))) return true; }
        return visibleIds.has(String(nodeId));
      }
      function pfkgApplyVisible(visibleIds){
        var updNodes = [];
        nodes.get().forEach(function(n){ updNodes.push({id:n.id, hidden: !visibleIds.has(String(n.id))}); });
        nodes.update(updNodes);
        var updEdges = [];
        edges.get().forEach(function(e){
          updEdges.push({id:e.id, hidden: !(visibleIds.has(String(e.from)) && visibleIds.has(String(e.to)))});
        });
        edges.update(updEdges);
      }
      function pfkgShowAll(){
        var ids = new Set(nodes.get().map(function(n){return String(n.id);}));
        pfkgApplyVisible(ids);
      }
      function pfkgOnlyClass(cls){
        var ids = new Set();
        nodes.get().forEach(function(n){ if(n.group === cls || n.pfkg_class === cls){ ids.add(String(n.id)); } });
        var expanded = new Set(ids);
        nodes.get().forEach(function(n){ if(pfkgConnectedVisible(n.id, ids)){ expanded.add(String(n.id)); } });
        pfkgApplyVisible(expanded);
      }
      function pfkgFilterNodes(){
        var q = (document.getElementById('pfkgSearch').value || '').toLowerCase().trim();
        if(!q){ pfkgShowAll(); return; }
        var ids = new Set();
        nodes.get().forEach(function(n){
          var label = String(n.label || n.id || '').toLowerCase();
          if(label.indexOf(q) >= 0){ ids.add(String(n.id)); }
        });
        var expanded = new Set(ids);
        nodes.get().forEach(function(n){ if(pfkgConnectedVisible(n.id, ids)){ expanded.add(String(n.id)); } });
        pfkgApplyVisible(expanded);
      }
    </script>
    """
    pyvis_html = pyvis_html.replace("<body>", "<body>" + painel, 1)
    pyvis_html = pyvis_html.replace("</body>", script + "</body>", 1)
    return pyvis_html


def gerar_grafo_html(
    df: pd.DataFrame,
    path: str | Path = "output/grafo_interacao.html",
    titulo: str = "Grafo da Interação",
    top_n: int = 50,
    max_edges: int = 2000,
) -> str:
    """Gera HTML avançado do grafo com cores automáticas, legenda, filtros e destaque Top N."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if df is None or df.empty:
        path.write_text(
            f"<html><meta charset='utf-8'><body><h2>{html.escape(titulo)}</h2>"
            "<p>Sem dados para gerar grafo.</p></body></html>",
            encoding="utf-8",
        )
        return str(path)

    d = df.copy()
    for c in ["Source", "Target"]:
        if c not in d.columns:
            d[c] = ""
        d[c] = d[c].astype(str)
    if "VALOR" not in d.columns:
        d["VALOR"] = 0.0
    d["VALOR"] = pd.to_numeric(d["VALOR"], errors="coerce").fillna(0.0)
    d = d[(d["Source"].astype(str) != "") & (d["Target"].astype(str) != "")].copy()
    d = d.sort_values("VALOR", ascending=False).head(max_edges)

    top_ids = _extrair_top_ids(d, top_n=top_n)
    classes = classificar_nos(d, top_ids=top_ids)

    net = Network(height="780px", width="100%", directed=True, notebook=False, cdn_resources="in_line")
    net.barnes_hut(gravity=-25000, central_gravity=0.2, spring_length=180, spring_strength=0.04)
    net.set_options('''
    var options = {
      "nodes": {"font": {"size": 14}, "borderWidth": 1},
      "edges": {"arrows": {"to": {"enabled": true, "scaleFactor": 0.6}}, "smooth": {"type": "dynamic"}},
      "interaction": {"hover": true, "navigationButtons": true, "keyboard": true},
      "physics": {"stabilization": {"iterations": 120}}
    }
    ''')

    # Métricas por nó para tooltip.
    valor_saida = d.groupby("Source")["VALOR"].sum().to_dict()
    valor_entrada = d.groupby("Target")["VALOR"].sum().to_dict()
    grau_saida = d.groupby("Source").size().to_dict()
    grau_entrada = d.groupby("Target").size().to_dict()

    top_edges = set()
    for _, r in d.sort_values("VALOR", ascending=False).head(max(1, int(top_n))).iterrows():
        top_edges.add((str(r.get("Source", "")), str(r.get("Target", ""))))

    for n, cls in classes.items():
        cor = cor_por_classe(cls)
        is_top = n in top_ids
        title = (
            f"<b>{html.escape(n)}</b><br>Classe: {html.escape(cls)}"
            f"<br>Top N: {'sim' if is_top else 'não'}"
            f"<br>Saída: {float(valor_saida.get(n, 0.0)):,.2f}"
            f"<br>Entrada: {float(valor_entrada.get(n, 0.0)):,.2f}"
            f"<br>Grau saída: {int(grau_saida.get(n, 0))}"
            f"<br>Grau entrada: {int(grau_entrada.get(n, 0))}"
        )
        size = 16 + min(30, (grau_saida.get(n, 0) + grau_entrada.get(n, 0)) * 1.5)
        # O vis-network não desenha aresta em formato de hexágono; para representar
        # Top N visualmente usamos nó hexagonal (ou fallback para diamond, conforme
        # versão do vis-network) e marcador ⬢ na aresta Top N.
        shape = "hexagon" if is_top else "dot"
        net.add_node(n, label=n, color=cor, title=title, group=cls, pfkg_class=cls, size=size, shape=shape)

    pares = set((str(s), str(t)) for s, t in zip(d["Source"], d["Target"]) if str(s) and str(t))
    sources = set(d["Source"].dropna().astype(str))
    targets = set(d["Target"].dropna().astype(str))

    vmax = max(float(d["VALOR"].max()), 1.0)
    for i, (_, r) in enumerate(d.iterrows()):
        s, t = str(r["Source"]), str(r["Target"])
        v = float(r.get("VALOR", 0) or 0)
        if s and t:
            classe_aresta = classificar_aresta(s, t, pares, sources, targets)
            cor = cor_por_classe(classe_aresta)
            is_top_edge = (s, t) in top_edges
            if is_top_edge:
                cor = misturar_com_azul(cor, 0.35)
            width = max(1.0, 1.0 + 9.0 * v / vmax) + (2.0 if is_top_edge else 0.0)
            label = "⬢" if is_top_edge else ""
            title = (
                f"{html.escape(s)} → {html.escape(t)}<br>Valor: {v:,.2f}"
                f"<br>Classe: {html.escape(classe_aresta)}"
                f"<br>Top N: {'sim' if is_top_edge else 'não'}"
            )
            net.add_edge(
                s, t, value=width, width=width, color=cor, label=label,
                font={"align": "middle", "size": 18, "color": cor},
                title=title, pfkg_class=classe_aresta, pfkg_topN=is_top_edge
            )

    # PyVis save_graph usa open() sem encoding em algumas versões; no Windows isso pode
    # cair em cp1252 e gerar UnicodeEncodeError. Portanto, geramos o HTML em memória
    # e gravamos explicitamente em UTF-8.
    raw = net.generate_html(notebook=False)
    resumo = {
        "arestas": int(len(d)),
        "nos": int(len(classes)),
        "top_n": int(top_n),
        "max_edges": int(max_edges),
        "valor_total": float(d["VALOR"].sum()),
    }
    path.write_text(_inject_controls(raw, titulo, resumo), encoding="utf-8", errors="xmlcharrefreplace")
    return str(path)
