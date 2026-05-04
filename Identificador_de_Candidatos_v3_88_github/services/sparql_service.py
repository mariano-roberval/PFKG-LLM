# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict
import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON


def executar_query(endpoint: str, query: str) -> Dict[str, Any]:
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    return sparql.query().convert()


def query_to_dataframe(endpoint: str, query: str) -> pd.DataFrame:
    data = executar_query(endpoint, query)
    vars_ = data.get("head", {}).get("vars", [])
    rows = []
    for b in data.get("results", {}).get("bindings", []):
        row = {}
        for v in vars_:
            row[v] = b.get(v, {}).get("value", "")
        rows.append(row)
    return pd.DataFrame(rows, columns=vars_)
