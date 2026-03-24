from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List

try:
    from .config import DB_PATH, REPORT_PATHS, SCHEMA_PATH, load_table_columns
    from .data_validator import validate_financial_data
    from .pdf_parser import parse_pdf_report
    from .utils import get_all_pdf_files
except ImportError:  # pragma: no cover
    from database.config import DB_PATH, REPORT_PATHS, SCHEMA_PATH, load_table_columns
    from database.data_validator import validate_financial_data
    from database.pdf_parser import parse_pdf_report
    from database.utils import get_all_pdf_files


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class FinancialDBLoader:
    def __init__(self, db_path: str | Path = DB_PATH, reset_database: bool = True):
        self.db_path = Path(db_path)
        self.table_columns = load_table_columns()
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_database(reset_database=reset_database)

    def _init_database(self, reset_database: bool = True) -> None:
        if reset_database and self.db_path.exists():
            self.conn.close()
            self.db_path.unlink()
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row

        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        self.conn.executescript(schema_sql)
        self.conn.commit()
        logger.info("数据库初始化完成: %s", self.db_path)

    def _financial_fields(self, table_name: str) -> List[str]:
        return [field for field in self.table_columns[table_name] if field not in {"serial_number", "stock_code", "stock_abbr", "report_period", "report_year"}]

    def _has_payload(self, table_name: str, row: Dict[str, object]) -> bool:
        return any(row.get(field_name) is not None for field_name in self._financial_fields(table_name))

    def _build_upsert_sql(self, table_name: str) -> str:
        columns = [field for field in self.table_columns[table_name] if field != "serial_number"]
        placeholders = ", ".join("?" for _ in columns)
        update_columns = [field for field in columns if field not in {"stock_code", "stock_abbr", "report_period", "report_year"}]
        update_clause = ", ".join(
            f"{field}=COALESCE(excluded.{field}, {table_name}.{field})" for field in update_columns
        )
        return f"""
            INSERT INTO {table_name} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(stock_code, report_year, report_period)
            DO UPDATE SET
                stock_abbr=excluded.stock_abbr,
                {update_clause}
        """

    def _insert_report_data(self, table_name: str, row: Dict[str, object]) -> None:
        columns = [field for field in self.table_columns[table_name] if field != "serial_number"]
        sql = self._build_upsert_sql(table_name)
        params = [row.get(column) for column in columns]
        self.conn.execute(sql, params)

    def process_pdf_file(self, pdf_path: str | Path) -> bool:
        pdf_path = Path(pdf_path)
        logger.info("开始处理: %s", pdf_path.name)

        try:
            reports = parse_pdf_report(pdf_path)
            is_valid, issues = validate_financial_data(reports)
            for table_name, messages in issues.items():
                for message in messages:
                    logger.warning("[%s] %s | %s", table_name, pdf_path.name, message)

            inserted_tables = 0
            for table_name, row in reports.items():
                if not self._has_payload(table_name, row):
                    continue
                self._insert_report_data(table_name, row)
                inserted_tables += 1

            if inserted_tables == 0:
                logger.warning("未写入任何数据: %s", pdf_path.name)
                return False

            self.conn.commit()
            logger.info("处理完成: %s | 写入表数=%s | 校验通过=%s", pdf_path.name, inserted_tables, is_valid)
            return True
        except Exception:
            self.conn.rollback()
            logger.exception("处理失败: %s", pdf_path)
            return False

    def batch_process_pdfs(self, report_paths: Iterable[Path] = REPORT_PATHS) -> Dict[str, int]:
        pdf_files = get_all_pdf_files(report_paths)
        stats = {"total": len(pdf_files), "success": 0, "failed": 0}

        for pdf_file in pdf_files:
            if self.process_pdf_file(pdf_file):
                stats["success"] += 1
            else:
                stats["failed"] += 1

        self.update_quarter_over_quarter_growth()
        self.conn.commit()
        logger.info("批量处理结束: %s", stats)
        return stats

    def update_quarter_over_quarter_growth(self) -> None:
        cursor = self.conn.execute(
            """
            SELECT serial_number, stock_code, report_year, report_period,
                   total_operating_revenue, net_profit_10k_yuan
            FROM core_performance
            ORDER BY stock_code, report_year, CASE report_period
                WHEN 'Q1' THEN 1
                WHEN 'HY' THEN 2
                WHEN 'Q3' THEN 3
                WHEN 'FY' THEN 4
                ELSE 5
            END
            """
        )

        grouped: Dict[tuple[str, int], Dict[str, sqlite3.Row]] = {}
        for row in cursor.fetchall():
            grouped.setdefault((row["stock_code"], row["report_year"]), {})[row["report_period"]] = row

        order = ["Q1", "HY", "Q3", "FY"]
        for rows_by_period in grouped.values():
            revenue_quarter_values: Dict[str, float] = {}
            profit_quarter_values: Dict[str, float] = {}
            revenue_previous_cumulative = None
            profit_previous_cumulative = None

            for period in order:
                row = rows_by_period.get(period)
                if row is None:
                    continue

                revenue_cumulative = row["total_operating_revenue"]
                profit_cumulative = row["net_profit_10k_yuan"]

                if revenue_cumulative is not None:
                    if period == "Q1" or revenue_previous_cumulative is None:
                        revenue_quarter_values[period] = revenue_cumulative
                    else:
                        revenue_quarter_values[period] = revenue_cumulative - revenue_previous_cumulative
                    revenue_previous_cumulative = revenue_cumulative

                if profit_cumulative is not None:
                    if period == "Q1" or profit_previous_cumulative is None:
                        profit_quarter_values[period] = profit_cumulative
                    else:
                        profit_quarter_values[period] = profit_cumulative - profit_previous_cumulative
                    profit_previous_cumulative = profit_cumulative

            for index, period in enumerate(order):
                row = rows_by_period.get(period)
                if row is None or index == 0:
                    continue
                previous_period = order[index - 1]
                revenue_qoq = self._safe_growth(
                    revenue_quarter_values.get(period),
                    revenue_quarter_values.get(previous_period),
                )
                profit_qoq = self._safe_growth(
                    profit_quarter_values.get(period),
                    profit_quarter_values.get(previous_period),
                )

                self.conn.execute(
                    """
                    UPDATE core_performance
                    SET operating_revenue_qoq_growth = ?,
                        net_profit_qoq_growth = ?
                    WHERE serial_number = ?
                    """,
                    (revenue_qoq, profit_qoq, row["serial_number"]),
                )

    @staticmethod
    def _safe_growth(current: float | None, previous: float | None) -> float | None:
        if current is None or previous is None or abs(previous) < 1e-9 or current * previous < 0:
            return None
        return round((current - previous) / abs(previous) * 100, 4)

    def close(self) -> None:
        if self.conn:
            self.conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse financial report PDFs into SQLite.")
    parser.add_argument("--db-path", default=str(DB_PATH))
    parser.add_argument("--keep-database", action="store_true", help="Append into existing database instead of recreating it.")
    args = parser.parse_args()

    loader = FinancialDBLoader(db_path=args.db_path, reset_database=not args.keep_database)
    try:
        stats = loader.batch_process_pdfs()
        print(stats)
    finally:
        loader.close()


if __name__ == "__main__":
    main()
