from __future__ import annotations

import pandas as pd
from sqlalchemy import text


def execute_sql(sql: str, engine):
    try:
        with engine.connect() as conn:
            dataframe = pd.read_sql_query(text(sql), conn)
        if dataframe.empty:
            return "未查询到相关数据。", dataframe
        return dataframe.to_string(index=False), dataframe
    except Exception as exc:  # pragma: no cover - runtime diagnostics
        return f"SQL 执行出错：{exc}", None
