from __future__ import annotations

import pandas as pd
from sqlalchemy import text


class QueryExecutionError(RuntimeError):
    def __init__(self, sql: str, original_error: Exception) -> None:
        self.sql = sql
        self.original_error = original_error
        super().__init__(f"SQL 执行出错：{original_error}")


def execute_sql(sql: str, engine, raise_on_error: bool = False):
    try:
        with engine.connect() as conn:
            dataframe = pd.read_sql_query(text(sql), conn)
        if dataframe.empty:
            return "未查询到相关数据。", dataframe
        return dataframe.to_string(index=False), dataframe
    except Exception as exc:  # pragma: no cover - runtime diagnostics
        if raise_on_error:
            raise QueryExecutionError(sql, exc) from exc
        return f"SQL 执行出错：{exc}", None
