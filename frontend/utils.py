from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from financial_assistant.config import (
    DB_PATH,
    KNOWLEDGE_INDEX_PATH,
    RESULT_2_PATH,
    RESULT_3_PATH,
    RESULT_DIR,
)


def pretty_print_answer(answer_payload: dict, sqls: Iterable[str]) -> str:
    lines = [f"回答: {answer_payload.get('content', '')}"]
    images = answer_payload.get("image", []) or []
    references = answer_payload.get("references", []) or []
    if sqls:
        lines.append("SQL:")
        lines.extend(sqls)
    if images:
        lines.append("图表:")
        lines.extend(images)
    if references:
        lines.append("引用:")
        for reference in references:
            lines.append(f"{reference.get('paper_path', '')} | {reference.get('paper_image', '')}")
    return "\n".join(lines)


def _browser_image_path(image_path: str) -> str:
    normalized = (image_path or "").replace("\\", "/")
    if normalized.startswith("./result/"):
        return "/result/" + Path(normalized).name
    if normalized.startswith("result/"):
        return "/result/" + Path(normalized).name
    return normalized


def normalize_answer_payload(answer_payload: dict[str, Any], sqls: Iterable[str]) -> dict[str, Any]:
    references = []
    for reference in answer_payload.get("references", []) or []:
        references.append(
            {
                "paper_path": reference.get("paper_path", ""),
                "paper_image": reference.get("paper_image", ""),
                "text": reference.get("text", ""),
            }
        )
    return {
        "content": answer_payload.get("content", ""),
        "images": [_browser_image_path(path) for path in (answer_payload.get("image", []) or [])],
        "references": references,
        "sql": list(sqls or []),
    }


def _safe_row_count(conn: sqlite3.Connection, table_name: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
    except sqlite3.DatabaseError:
        return 0


def project_overview() -> dict[str, Any]:
    db_path = Path(DB_PATH)
    database_ready = db_path.exists()
    tables = {
        "core_performance": 0,
        "balance_sheet": 0,
        "income_statement": 0,
        "cash_flow": 0,
    }
    years: list[int] = []

    if database_ready:
        conn = sqlite3.connect(db_path)
        try:
            for table_name in tables:
                tables[table_name] = _safe_row_count(conn, table_name)
            year_rows = conn.execute(
                "SELECT DISTINCT report_year FROM core_performance ORDER BY report_year"
            ).fetchall()
            years = [int(row[0]) for row in year_rows]
        except sqlite3.DatabaseError:
            database_ready = False
        finally:
            conn.close()

    return {
        "database_ready": database_ready,
        "db_path": str(db_path),
        "tables": tables,
        "years": years,
        "result_2_exists": RESULT_2_PATH.exists(),
        "result_3_exists": RESULT_3_PATH.exists(),
        "chart_count": len(list(RESULT_DIR.glob("*.jpg"))) + len(list(RESULT_DIR.glob("*.png"))),
        "knowledge_ready": KNOWLEDGE_INDEX_PATH.exists(),
    }


def example_questions() -> list[str]:
    return [
        "华润三九近三年的主营业务收入情况做可视化绘图",
        "2024年利润最高的top10企业有哪些？",
        "华润三九业绩增长的主要原因是什么？",
        "医保谈判对相关医药行业的影响有哪些？",
    ]
