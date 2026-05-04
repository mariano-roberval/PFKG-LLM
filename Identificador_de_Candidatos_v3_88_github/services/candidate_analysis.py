# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple, Any
import re
import math
import pandas as pd

ID_RE = re.compile(r"^(\d{11}|\d{14})$")


def _serie_id_valido(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series(dtype=bool)
    return s.astype(str).str.replace(r"\D", "", regex=True).str.match(ID_RE, na=False).astype(bool)


def _limpar_id(x: Any) -> str:
    return re.sub(r"\D", "", str(x or ""))


def normalizar_df_fluxos(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame(columns=["Source", "Target", "VALOR"])
    d = df.copy()
    for c in ["Source", "Target"]:
        if c not in d.columns:
            d[c] = ""
        d[c] = d[c].map(_limpar_id)

    valor_col = None
    for cand in ["VALOR", "TOTAL_VL_MERC", "VL_MERC", "VL_DOC", "VL_ITEM", "TOTAL", "valor"]:
        if cand in d.columns:
            valor_col = cand
            break
    d["VALOR"] = pd.to_numeric(d[valor_col], errors="coerce").fillna(0.0) if valor_col else 0.0

    if "QTD" in d.columns:
        d["QTD"] = pd.to_numeric(d["QTD"], errors="coerce").fillna(1).astype(int)
    else:
        d["QTD"] = 1

    mask = _serie_id_valido(d["Source"]) | _serie_id_valido(d["Target"])
    return d.loc[mask].copy()


def detectar_categorias(df: pd.DataFrame, threshold: float = 30000.0, top_n: int = 50) -> Tuple[Dict[str, List[str]], pd.DataFrame]:
    d = normalizar_df_fluxos(df)
    nomes = [
        "01_estrutural_entradas_saidas_circulares_carrossel",
        "02_outliers_burst_sem_lista_01",
        "03_90pct_threshold_sem_anteriores_sem_top3",
        "04_topN_global",
        "05_topN_source",
        "06_topN_target",
        "07_topN_periodo",
        "08_topN_uf",
    ]
    if d.empty:
        return {k: [] for k in nomes}, pd.DataFrame({"CNPJ_CPF": []})

    sources = set(d.loc[_serie_id_valido(d["Source"]), "Source"])
    targets = set(d.loc[_serie_id_valido(d["Target"]), "Target"])
    entradas = targets - sources
    saidas = sources - targets

    pares = set(zip(d["Source"], d["Target"]))
    circulares = set()
    for s, t in pares:
        if s and t and (t, s) in pares:
            circulares.update([s, t])

    # Carrossel: nós com grau anormalmente alto ou que participam de ciclos simples.
    grau_s = d.groupby("Source").size()
    grau_t = d.groupby("Target").size()
    grau = grau_s.add(grau_t, fill_value=0)
    lim_carrossel = max(3.0, float(grau.mean() + 2 * grau.std())) if len(grau) > 1 else 3.0
    carrossel = set(grau[grau >= lim_carrossel].index.astype(str))
    try:
        import networkx as nx
        G = nx.DiGraph()
        for _, r in d.iterrows():
            if r["Source"] and r["Target"]:
                G.add_edge(str(r["Source"]), str(r["Target"]), weight=float(r["VALOR"]))
        for cyc in nx.simple_cycles(G):
            if 3 <= len(cyc) <= 8:
                carrossel.update(str(x) for x in cyc)
    except Exception:
        pass

    lista1 = {x for x in (entradas | saidas | circulares | carrossel) if ID_RE.match(str(x))}

    std = float(d["VALOR"].std()) if len(d) > 1 else 0.0
    lim_outlier = float(d["VALOR"].mean()) + 2 * std
    out_df = d[d["VALOR"] > lim_outlier]
    outliers = set(out_df["Source"]) | set(out_df["Target"])

    burst = set()
    periodo_col = "PERIODO" if "PERIODO" in d.columns else ("DT_DOC" if "DT_DOC" in d.columns else None)
    if periodo_col:
        burst_base = d.groupby(["Source", periodo_col]).size().reset_index(name="qtd")
        lim_burst = max(10, int(burst_base["qtd"].mean() + 2 * burst_base["qtd"].std())) if len(burst_base) > 1 else 10
        burst = set(burst_base[burst_base["qtd"] >= lim_burst]["Source"])
    lista2 = {x for x in (outliers | burst) - lista1 if ID_RE.match(str(x))}

    top3_ids = set()
    for _, r in d.sort_values("VALOR", ascending=False).head(3).iterrows():
        top3_ids.update([str(r.get("Source", "")), str(r.get("Target", ""))])
    cand90 = d[d["VALOR"] >= float(threshold) * 0.9]
    lista3 = {
        x for x in (set(cand90["Source"]) | set(cand90["Target"])) - lista1 - lista2 - top3_ids
        if ID_RE.match(str(x))
    }

    def top_ids(df_in: pd.DataFrame, n: int) -> List[str]:
        if df_in is None or df_in.empty:
            return []
        dd = df_in.copy()
        if "VALOR" in dd.columns:
            dd["VALOR"] = pd.to_numeric(dd["VALOR"], errors="coerce").fillna(0.0)
            dd = dd.sort_values("VALOR", ascending=False)
        ids: List[str] = []
        for _, r in dd.iterrows():
            ids.extend([str(r.get("Source", "")), str(r.get("Target", ""))])
        ids = [x for x in ids if ID_RE.match(str(x))]
        return list(dict.fromkeys(ids))[:max(0, int(n))]

    lista4 = top_ids(d, top_n)
    df_src = d.groupby("Source", as_index=False)["VALOR"].sum(); df_src["Target"] = ""
    lista5 = top_ids(df_src, top_n)
    df_tgt = d.groupby("Target", as_index=False)["VALOR"].sum(); df_tgt["Source"] = ""
    lista6 = top_ids(df_tgt, top_n)

    lista7: List[str] = []
    if periodo_col:
        for _, g in d.groupby(periodo_col):
            lista7.extend(top_ids(g, top_n))
        lista7 = list(dict.fromkeys(lista7))[:top_n]

    lista8: List[str] = []
    uf_col = "UF" if "UF" in d.columns else None
    if uf_col:
        for _, g in d.groupby(uf_col):
            lista8.extend(top_ids(g, top_n))
        lista8 = list(dict.fromkeys(lista8))[:top_n]

    listas = {
        "01_estrutural_entradas_saidas_circulares_carrossel": sorted(lista1),
        "02_outliers_burst_sem_lista_01": sorted(lista2),
        "03_90pct_threshold_sem_anteriores_sem_top3": sorted(lista3),
        "04_topN_global": sorted(set(lista4)),
        "05_topN_source": sorted(set(lista5)),
        "06_topN_target": sorted(set(lista6)),
        "07_topN_periodo": sorted(set(lista7)),
        "08_topN_uf": sorted(set(lista8)),
    }
    final = sorted(set().union(*[set(v) for v in listas.values()]))
    return listas, pd.DataFrame({"CNPJ_CPF": final})


def gerar_listas_avancadas(df: pd.DataFrame, threshold: float, top_n: int = 50):
    return detectar_categorias(df, threshold, top_n)


def calcular_score_risco(df: pd.DataFrame, listas: Dict[str, List[str]] | None = None) -> pd.DataFrame:
    d = normalizar_df_fluxos(df)
    if d.empty:
        return pd.DataFrame(columns=["CNPJ_CPF", "score_risco", "valor_total", "qtd_fluxos", "papel", "motivos"])
    listas = listas or {}
    categorias = {k: set(v) for k, v in listas.items()}
    rows = []
    ids = sorted(set(d["Source"]) | set(d["Target"]))
    for ident in ids:
        if not ID_RE.match(str(ident)):
            continue
        out = d[d["Source"] == ident]
        inn = d[d["Target"] == ident]
        valor_total = float(out["VALOR"].sum() + inn["VALOR"].sum())
        qtd = int(len(out) + len(inn))
        papel = "misto"
        if len(out) and not len(inn): papel = "somente_saida"
        elif len(inn) and not len(out): papel = "somente_entrada"
        motivos = []
        score = 0.0
        if ident in categorias.get("01_estrutural_entradas_saidas_circulares_carrossel", set()):
            score += 35; motivos.append("estrutura/entrada-saida/ciclo/carrossel")
        if ident in categorias.get("02_outliers_burst_sem_lista_01", set()):
            score += 30; motivos.append("outlier/burst")
        if ident in categorias.get("03_90pct_threshold_sem_anteriores_sem_top3", set()):
            score += 15; motivos.append(">=90% threshold")
        if ident in categorias.get("04_topN_global", set()):
            score += 20; motivos.append("topN global")
        score += min(15.0, math.log10(max(valor_total, 1.0)) * 2.0)
        score += min(10.0, math.log10(max(qtd, 1)) * 4.0)
        rows.append({"CNPJ_CPF": ident, "score_risco": round(min(score, 100.0), 2), "valor_total": round(valor_total, 2), "qtd_fluxos": qtd, "papel": papel, "motivos": "; ".join(motivos) or "valor/fluxo"})
    return pd.DataFrame(rows).sort_values(["score_risco", "valor_total"], ascending=[False, False])


def salvar_listas(listas: Dict[str, List[str]], df_final: pd.DataFrame, out_dir: str | Path = "output") -> None:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    for nome, lista in listas.items():
        pd.DataFrame({"CNPJ_CPF": lista}).to_csv(out / f"lista_{nome}.csv", index=False, encoding="utf-8-sig")
        (out / f"lista_{nome}.txt").write_text("\n".join(lista), encoding="utf-8")
    if df_final is None:
        df_final = pd.DataFrame({"CNPJ_CPF": []})
    df_final.to_csv(out / "lista_final_proxima_interacao.csv", index=False, encoding="utf-8-sig")
    (out / "lista_final_proxima_interacao.txt").write_text("\n".join(df_final["CNPJ_CPF"].astype(str).tolist()), encoding="utf-8")


def exportar_excel(df_fluxos: pd.DataFrame, listas: Dict[str, List[str]], df_final: pd.DataFrame, df_score: pd.DataFrame, out_path: str | Path) -> Path:
    out_path = Path(out_path); out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        normalizar_df_fluxos(df_fluxos).to_excel(writer, sheet_name="fluxos", index=False)
        df_score.to_excel(writer, sheet_name="score_risco", index=False)
        df_final.to_excel(writer, sheet_name="lista_final", index=False)
        for nome, lista in listas.items():
            pd.DataFrame({"CNPJ_CPF": lista}).to_excel(writer, sheet_name=nome[:31], index=False)
    return out_path


def exportar_pdf_resumo(df_score: pd.DataFrame, resumo: Dict[str, Any], out_path: str | Path) -> Path:
    out_path = Path(out_path); out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(out_path), pagesize=A4)
        w, h = A4; y = h - 50
        c.setFont("Helvetica-Bold", 14); c.drawString(40, y, "Identificador de Candidatos - Resumo SBBD")
        y -= 30; c.setFont("Helvetica", 10)
        for k, v in resumo.items():
            c.drawString(40, y, f"{k}: {v}"); y -= 16
        y -= 10; c.setFont("Helvetica-Bold", 11); c.drawString(40, y, "Top candidatos por score")
        y -= 18; c.setFont("Helvetica", 8)
        for _, r in df_score.head(25).iterrows():
            txt = f"{r['CNPJ_CPF']} | score={r['score_risco']} | valor={r['valor_total']} | {r['motivos']}"
            c.drawString(40, y, txt[:115]); y -= 12
            if y < 50:
                c.showPage(); y = h - 50; c.setFont("Helvetica", 8)
        c.save()
    except Exception:
        # Fallback texto com extensão .pdf para não quebrar automação; avisar no app.
        out_path.write_text("Resumo PDF indisponível: instale reportlab.\n" + df_score.head(50).to_string(index=False), encoding="utf-8")
    return out_path
