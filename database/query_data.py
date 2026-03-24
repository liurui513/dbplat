from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Iterable

try:
    from .config import DB_PATH
except ImportError:  # pragma: no cover
    from database.config import DB_PATH


DEFAULT_TABLES = [
    "core_performance",
    "balance_sheet",
    "income_statement",
    "cash_flow",
]


def _available_tables(conn: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        if row[0] != "sqlite_sequence"
    ]


def preview_table(
    conn: sqlite3.Connection,
    table_name: str,
    limit: int = 5,
    stock_code: str | None = None,
) -> None:
    where_clause = ""
    params: list[object] = []
    if stock_code:
        where_clause = " WHERE stock_code = ? "
        params.append(stock_code)

    row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}{where_clause}", params).fetchone()[0]
    print(f"\n[{table_name}] rows={row_count}")
    if row_count == 0:
        return

    sql = f"""
        SELECT *
        FROM {table_name}
        {where_clause}
        ORDER BY stock_code, report_year,
        CASE report_period
            WHEN 'Q1' THEN 1
            WHEN 'HY' THEN 2
            WHEN 'Q3' THEN 3
            WHEN 'FY' THEN 4
            ELSE 5
        END
        LIMIT ?
    """
    cursor = conn.execute(sql, [*params, limit])
    rows = [dict(row) for row in cursor.fetchall()]
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def query_financial_data(
    db_path: str | Path = DB_PATH,
    tables: Iterable[str] | None = None,
    limit: int = 5,
    stock_code: str | None = None,
) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        available_tables = _available_tables(conn)
        print("available_tables:", ", ".join(available_tables))
        target_tables = list(tables or DEFAULT_TABLES)
        for table_name in target_tables:
            if table_name not in available_tables:
                print(f"\n[{table_name}] not found")
                continue
            preview_table(conn, table_name, limit=limit, stock_code=stock_code)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview parsed financial data from SQLite.")
    parser.add_argument("--db-path", default=str(DB_PATH))
    parser.add_argument("--table", action="append", dest="tables")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--stock-code")
    args = parser.parse_args()

    query_financial_data(
        db_path=args.db_path,
        tables=args.tables,
        limit=args.limit,
        stock_code=args.stock_code,
    )


if __name__ == "__main__":
    main()
