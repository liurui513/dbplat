from __future__ import annotations

import sys
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.dialogue_manager import FinancialAssistant
from engine.formatter import format_comparison_answer, format_trend_answer
from engine.intent_recognizer import parse_user_input
from engine.query_executor import QueryExecutionError
from engine.sql_generator import build_comparison_query, build_context_query, build_ranking_query, build_trend_query
from financial_assistant.task_runner import ensure_database
from frontend.app import create_app


def test_parse_user_input_defaults_metric_for_cause_analysis() -> None:
    parsed = parse_user_input("华润三九业绩增长的主要原因是什么")
    assert parsed["intent"] == "cause_analysis"
    assert parsed["company"]["stock_code"] == "000999"
    assert parsed["metric"] is not None
    assert parsed["metric"]["key"] == "net_profit"


def test_parse_user_input_classifies_medicare_industry_impact_as_knowledge_query() -> None:
    parsed = parse_user_input("医保谈判对相关医药行业的影响有哪些？")
    assert parsed["intent"] == "knowledge_query"


def test_parse_user_input_recognizes_recent_two_years_trend_question() -> None:
    parsed = parse_user_input("华润三九近两年的主营业务收入情况")
    assert parsed["intent"] == "trend_analysis"
    assert parsed["time_scope"] == "recent_two_years"
    assert parsed["metric"] is not None
    assert parsed["metric"]["key"] == "total_operating_revenue"


def test_parse_user_input_recognizes_explicit_year_range_trend_question() -> None:
    parsed = parse_user_input("华润三九2023-2024年的净利润情况")
    assert parsed["intent"] == "trend_analysis"
    assert parsed["year_range"] == (2023, 2024)
    assert parsed["metric"] is not None
    assert parsed["metric"]["key"] == "net_profit"


def test_parse_user_input_classifies_comparison_question() -> None:
    parsed = parse_user_input("华润三九今年 vs 去年的主营业务收入对比")
    assert parsed["intent"] == "comparison_analysis"
    assert parsed["compare_mode"] == "yoy"
    assert parsed["metric"] is not None
    assert parsed["metric"]["key"] == "total_operating_revenue"


def test_parse_user_input_classifies_qoq_question() -> None:
    parsed = parse_user_input("华润三九2025Q3净利润环比")
    assert parsed["intent"] == "comparison_analysis"
    assert parsed["compare_mode"] == "qoq"
    assert parsed["report_year"] == 2025
    assert parsed["report_period"] == "Q3"


def test_build_trend_query_recent_three_years_uses_latest_full_year() -> None:
    parsed = {
        "metric": {"table": "income_sheet", "column": "total_operating_revenue"},
        "company": {"stock_code": "000999"},
        "time_scope": "recent_three_years",
    }
    sql = build_trend_query(parsed)["sql"]
    assert "report_period = 'FY'" in sql
    assert "latest_full_year" in sql


def test_build_trend_query_recent_two_years_uses_latest_two_full_years() -> None:
    parsed = {
        "metric": {"table": "income_sheet", "column": "net_profit"},
        "company": {"stock_code": "000999"},
        "time_scope": "recent_two_years",
    }
    sql = build_trend_query(parsed)["sql"]
    assert "report_period = 'FY'" in sql
    assert "max_year - 1" in sql


def test_build_trend_query_explicit_year_range_uses_between() -> None:
    parsed = {
        "metric": {"table": "income_sheet", "column": "net_profit"},
        "company": {"stock_code": "000999"},
        "year_range": (2023, 2024),
        "report_period": None,
    }
    sql = build_trend_query(parsed)["sql"]
    assert "report_period = 'FY'" in sql
    assert "BETWEEN 2023 AND 2024" in sql


def test_build_trend_query_historical_defaults_to_full_years() -> None:
    parsed = {
        "metric": {"table": "income_sheet", "column": "net_profit"},
        "company": {"stock_code": "000999"},
        "time_scope": "all_available_periods",
        "report_period": None,
    }
    sql = build_trend_query(parsed)["sql"]
    assert "report_period = 'FY'" in sql
    assert "ORDER BY report_year" in sql


def test_build_comparison_query_explicit_yoy_uses_same_period_two_years() -> None:
    parsed = {
        "metric": {"key": "net_profit", "table": "income_sheet", "column": "net_profit"},
        "company": {"stock_code": "000999"},
        "compare_mode": "yoy",
        "report_year": 2025,
        "report_period": "Q3",
        "year_range": None,
    }
    sql = build_comparison_query(parsed)["sql"]
    assert "report_period = 'Q3'" in sql
    assert "IN (2024, 2025)" in sql


def test_build_comparison_query_annual_yoy_defaults_to_full_year() -> None:
    parsed = {
        "metric": {"key": "net_profit", "table": "income_sheet", "column": "net_profit"},
        "company": {"stock_code": "000999"},
        "compare_mode": "yoy",
        "report_year": 2024,
        "report_period": None,
        "year_range": None,
    }
    sql = build_comparison_query(parsed)["sql"]
    assert "report_period = 'FY'" in sql
    assert "IN (2023, 2024)" in sql


def test_build_comparison_query_qoq_uses_core_performance_growth_column() -> None:
    parsed = {
        "metric": {"key": "net_profit", "table": "income_sheet", "column": "net_profit"},
        "company": {"stock_code": "000999"},
        "compare_mode": "qoq",
        "report_year": 2025,
        "report_period": "Q3",
    }
    sql = build_comparison_query(parsed)["sql"]
    assert "FROM core_performance" in sql
    assert "net_profit_qoq_growth AS growth" in sql


def test_build_context_query_uses_full_years_only() -> None:
    parsed = {
        "metric": {"table": "income_sheet", "column": "net_profit"},
        "company": {"stock_code": "000999"},
    }
    sql = build_context_query(parsed)["sql"]
    assert "report_period = 'FY'" in sql
    assert "latest_full_year" in sql


def test_build_ranking_query_respects_requested_limit() -> None:
    sql = build_ranking_query({"report_year": 2024, "ranking_limit": 3})["sql"]
    assert "LIMIT 3" in sql


def test_chat_returns_json_when_processing_fails() -> None:
    app = create_app()
    client = app.test_client()

    class BrokenAssistant:
        history: list[dict[str, str]] = []

        def process_query(self, message: str, question_id: str, turn_index: int):
            raise RuntimeError("boom")

    with patch("frontend.app._get_assistant", return_value=BrokenAssistant()):
        response = client.post("/api/chat", json={"message": "测试问题"})

    payload = response.get_json()
    assert response.status_code == 500
    assert payload["ok"] is False
    assert "问题处理失败" in payload["message"]


def test_chat_generates_unique_question_id_per_request() -> None:
    app = create_app()
    client = app.test_client()

    class RecordingAssistant:
        def __init__(self) -> None:
            self.history: list[dict[str, str]] = []
            self.question_ids: list[str] = []

        def process_query(self, message: str, question_id: str, turn_index: int):
            self.question_ids.append(question_id)
            self.history.append({"message": message})
            return {"content": "ok", "image": []}, []

    assistant = RecordingAssistant()

    with patch("frontend.app._get_assistant", return_value=assistant):
        client.post("/api/chat", json={"message": "第一次"})
        client.post("/api/reset-session")
        client.post("/api/chat", json={"message": "第二次"})

    assert len(assistant.question_ids) == 2
    assert assistant.question_ids[0] != assistant.question_ids[1]


def test_knowledge_query_returns_industry_impact_answer() -> None:
    assistant = FinancialAssistant(db_engine=None)
    contexts = [
        {
            "title": "从2025医保谈判看行业风向",
            "relative_path": "./industry/sample.pdf",
            "text": (
                "医保谈判成功率提升，创新导向持续强化，创新药和新机制药物有望通过医保准入实现产品放量、"
                "市场份额提升，并在商保支持下拓宽支付路径。"
            ),
            "chart_caption": "图表1",
            "page_number": 1,
            "chunk_index": 1,
        },
        {
            "title": "医保谈判与中成药准入",
            "relative_path": "./industry/sample.pdf",
            "text": "中成药仍保留一定准入比例，独家品种和差异化产品的竞争力更加突出。",
            "chart_caption": "图表2",
            "page_number": 2,
            "chunk_index": 1,
        },
    ]

    with patch("engine.dialogue_manager.retrieve_context", return_value=contexts):
        answer, sqls = assistant.process_query("医保谈判对相关医药行业的影响有哪些？", "WEB_TEST", 0)

    assert sqls == []
    assert "影响主要体现在" in answer["content"]
    assert "创新药和新机制药物" in answer["content"]
    assert answer["references"]
    assert answer["references"][0]["paper_path"] == "./industry/sample.pdf"


def test_format_trend_answer_mentions_recent_two_years_and_visualization_context() -> None:
    parsed = {
        "raw_question": "华润三九近两年的净利润可视化",
        "time_scope": "recent_two_years",
        "metric": {
            "key": "net_profit",
            "display_name": "净利润",
            "unit": "万元",
        },
        "company": {"stock_abbr": "华润三九"},
    }
    dataframe = pd.DataFrame(
        [
            {"report_year": 2023, "report_period": "FY", "value": 300000.0},
            {"report_year": 2024, "report_period": "FY", "value": 360000.0},
        ]
    )

    content = format_trend_answer(parsed, dataframe)

    assert "近两年" in content
    assert "盈利水平" in content
    assert "可视化分析口径" in content


def test_format_trend_answer_recent_one_year_avoids_duplicate_start_end() -> None:
    parsed = {
        "raw_question": "华润三九近一年的净利润情况",
        "time_scope": "recent_one_year",
        "year_range": None,
        "metric": {
            "key": "net_profit",
            "display_name": "净利润",
            "unit": "万元",
        },
        "company": {"stock_abbr": "华润三九"},
    }
    dataframe = pd.DataFrame(
        [
            {"report_year": 2024, "report_period": "FY", "value": 377774.13},
        ]
    )

    content = format_trend_answer(parsed, dataframe)

    assert "共有1期" in content
    assert "从2024年年度" not in content


def test_format_comparison_answer_yoy_mentions_two_periods() -> None:
    parsed = {
        "raw_question": "华润三九2025Q3净利润同比",
        "compare_mode": "yoy",
        "metric": {
            "key": "net_profit",
            "display_name": "净利润",
            "unit": "万元",
        },
        "company": {"stock_abbr": "华润三九"},
    }
    dataframe = pd.DataFrame(
        [
            {"report_year": 2024, "report_period": "Q3", "value": 250000.0},
            {"report_year": 2025, "report_period": "Q3", "value": 289929.69},
        ]
    )

    content = format_comparison_answer(parsed, dataframe)

    assert "同比" in content
    assert "2025年第三季度" in content
    assert "2024年第三季度" in content


def test_format_comparison_answer_qoq_mentions_growth() -> None:
    parsed = {
        "raw_question": "华润三九最新净利润环比",
        "compare_mode": "qoq",
        "metric": {
            "key": "net_profit",
            "display_name": "净利润",
            "unit": "万元",
        },
        "company": {"stock_abbr": "华润三九"},
    }
    dataframe = pd.DataFrame(
        [
            {"report_year": 2025, "report_period": "Q3", "value": 289929.69, "growth": 12.34},
        ]
    )

    content = format_comparison_answer(parsed, dataframe)

    assert "环比" in content
    assert "增长12.34%" in content


def _create_test_database(db_path: Path, table_names: list[str]) -> None:
    conn = sqlite3.connect(db_path)
    try:
        for table_name in table_names:
            conn.execute(f"CREATE TABLE {table_name} (id INTEGER)")
            conn.execute(f"INSERT INTO {table_name} VALUES (1)")
        conn.commit()
    finally:
        conn.close()


def test_task3_mode_respects_rebuild_knowledge_flag() -> None:
    import financial_assistant.main as assistant_main

    with patch.object(sys, "argv", ["prog", "--mode", "task3"]), patch(
        "financial_assistant.main.run_task3", return_value=Path("result_3.xlsx")
    ) as mock_run_task3:
        assistant_main.main()

    assert mock_run_task3.call_args.kwargs["rebuild_knowledge"] is False


def test_all_mode_forwards_rebuild_knowledge_flag() -> None:
    import financial_assistant.main as assistant_main

    with patch.object(sys, "argv", ["prog", "--mode", "all", "--rebuild-knowledge"]), patch(
        "financial_assistant.main.run_task2", return_value=Path("result_2.xlsx")
    ), patch("financial_assistant.main.run_task3", return_value=Path("result_3.xlsx")) as mock_run_task3:
        assistant_main.main()

    assert mock_run_task3.call_args.kwargs["rebuild_knowledge"] is True


def test_ensure_database_rebuilds_when_required_table_is_missing() -> None:
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp_dir:
        db_path = Path(temp_dir) / "finance.db"
        _create_test_database(db_path, ["core_performance"])

        with patch("financial_assistant.task_runner.DB_PATH", db_path), patch(
            "financial_assistant.task_runner.build_database"
        ) as mock_build_database:
            ensure_database(reset_database=False)

    mock_build_database.assert_called_once_with(db_path=db_path, reset_database=True)


def test_ensure_database_keeps_existing_database_when_all_required_tables_are_present() -> None:
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp_dir:
        db_path = Path(temp_dir) / "finance.db"
        _create_test_database(db_path, ["core_performance", "balance_sheet", "income_statement", "cash_flow"])

        with patch("financial_assistant.task_runner.DB_PATH", db_path), patch(
            "financial_assistant.task_runner.build_database"
        ) as mock_build_database:
            result = ensure_database(reset_database=False)

    assert result == db_path
    mock_build_database.assert_not_called()


def test_process_query_returns_explicit_sql_error_message() -> None:
    assistant = FinancialAssistant(db_engine=object())

    with patch(
        "engine.dialogue_manager.execute_sql",
        side_effect=QueryExecutionError("SELECT 1", RuntimeError("boom")),
    ):
        answer, sqls = assistant.process_query("华润三九2025Q3净利润环比", "WEB_TEST", 0)

    assert sqls == ["SELECT 1"]
    assert "查询执行失败" in answer["content"]
    assert "boom" in answer["content"]
