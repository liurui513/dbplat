from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.intent_recognizer import parse_user_input
from engine.sql_generator import build_context_query, build_ranking_query, build_trend_query
from frontend.app import create_app


def test_parse_user_input_defaults_metric_for_cause_analysis() -> None:
    parsed = parse_user_input("华润三九业绩增长的主要原因是什么")
    assert parsed["intent"] == "cause_analysis"
    assert parsed["company"]["stock_code"] == "000999"
    assert parsed["metric"] is not None
    assert parsed["metric"]["key"] == "net_profit"


def test_build_trend_query_recent_three_years_uses_latest_full_year() -> None:
    parsed = {
        "metric": {"table": "income_sheet", "column": "total_operating_revenue"},
        "company": {"stock_code": "000999"},
        "time_scope": "recent_three_years",
    }
    sql = build_trend_query(parsed)["sql"]
    assert "report_period = 'FY'" in sql
    assert "latest_full_year" in sql


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
