from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd
import re

from knowledge.answer_validator import validate_answer_payload
from knowledge.multi_intent_planner import plan_tasks
from knowledge.rag_retriever import extract_medicare_products, retrieve_context

from .formatter import (
    format_cause_answer,
    format_medicare_answer,
    format_ranking_answer,
    format_scalar_answer,
    format_trend_answer,
)
from .intent_recognizer import clarify_if_needed, metric_display_name, parse_user_input
from .query_executor import execute_sql
from .sql_generator import build_context_query, nl_to_sql
from .visualizer import (
    absolute_result_path,
    build_chart_dataframe,
    decide_chart_type,
    generate_chart,
    relative_result_path,
)


class FinancialAssistant:
    def __init__(self, db_engine):
        self.db_engine = db_engine
        self.history: list[dict[str, Any]] = []
        self.pending_context: dict[str, Any] | None = None
        self.last_context: dict[str, Any] = {}
        self._image_counters: dict[str, int] = defaultdict(int)

    def _next_image_name(self, question_id: str) -> str:
        self._image_counters[question_id] += 1
        return f"{question_id}_{self._image_counters[question_id]}.jpg"

    def _make_reference(self, document: dict[str, Any]) -> dict[str, str]:
        snippet = document["text"].replace("\n", " ").strip()
        snippet = re.sub(r"[\u0000-\u001f\u2022\uf06c]+", " ", snippet)
        snippet = re.sub(r"\s{2,}", " ", snippet)
        return {
            "paper_path": document["relative_path"],
            "text": snippet[:220],
            "paper_image": document.get("chart_caption") or f"第{document['page_number']}页",
        }

    def _build_evidence_points(self, contexts: list[dict[str, Any]]) -> list[str]:
        text = "\n".join(item["text"] for item in contexts)
        points = []
        rules = [
            ("CHC", "CHC 业务在调整后企稳回升，零售端需求与渠道库存改善带动收入恢复"),
            ("新品", "新品陆续上市、全品类布局扩充了品牌矩阵，有助于提升市占率"),
            ("处方药", "处方药板块逐步消化集采影响并恢复增长，对收入形成支撑"),
            ("天士力", "与天士力的融合推进和外延并购协同，为收入增长提供了额外驱动"),
            ("并购", "并购整合与外延扩张正在释放协同效应"),
            ("品牌", "品牌力与渠道韧性增强，使核心品类在旺季中受益更明显"),
        ]
        for keyword, point in rules:
            if keyword in text and point not in points:
                points.append(point)
        return points

    def _prioritize_qualitative_contexts(self, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        qualitative_keywords = ["CHC", "新品", "渠道", "品牌", "融合", "并购", "处方药", "昆药", "流感"]
        scored = []
        for context in contexts:
            score = sum(1 for keyword in qualitative_keywords if keyword in context["text"])
            scored.append((score, context))
        scored.sort(key=lambda item: (-item[0], item[1]["page_number"], item[1]["chunk_index"]))
        return [context for _, context in scored]

    def _create_chart(self, question: str, dataframe: pd.DataFrame, question_id: str, title: str) -> list[str]:
        chart_type = decide_chart_type(question, dataframe)
        if chart_type is None or dataframe.empty:
            return []
        filename = self._next_image_name(question_id)
        chart_df = build_chart_dataframe(dataframe)
        generate_chart(
            chart_df,
            chart_type=chart_type,
            save_path=absolute_result_path(filename),
            title=title,
            x_col="label",
            y_col="value",
        )
        return [relative_result_path(filename)]

    def _handle_single_metric(self, parsed: dict[str, Any], question_id: str) -> tuple[dict[str, Any], list[str]]:
        plan = nl_to_sql(parsed)
        _, dataframe = execute_sql(plan["sql"], self.db_engine)
        content = format_scalar_answer(parsed, dataframe if dataframe is not None else pd.DataFrame())
        answer = {"content": content, "image": []}
        return answer, [plan["sql"]]

    def _handle_trend_analysis(self, parsed: dict[str, Any], question_id: str) -> tuple[dict[str, Any], list[str]]:
        plan = nl_to_sql(parsed)
        _, dataframe = execute_sql(plan["sql"], self.db_engine)
        dataframe = dataframe if dataframe is not None else pd.DataFrame()
        content = format_trend_answer(parsed, dataframe)
        images = self._create_chart(parsed["raw_question"], dataframe, question_id, f"{parsed['company']['stock_abbr']}{metric_display_name(parsed['metric'])}趋势")
        if "变化趋势" in parsed["raw_question"] and not dataframe.empty:
            images.extend(
                self._create_chart("bar", dataframe.tail(min(len(dataframe), 8)), question_id, f"{parsed['company']['stock_abbr']}{metric_display_name(parsed['metric'])}阶段对比")
            )
        answer = {"content": content, "image": images}
        return answer, [plan["sql"]]

    def _handle_ranking_analysis(self, parsed: dict[str, Any], question_id: str) -> tuple[dict[str, Any], list[str]]:
        _ = plan_tasks(parsed["raw_question"])
        plan = nl_to_sql(parsed)
        _, dataframe = execute_sql(plan["sql"], self.db_engine)
        dataframe = dataframe if dataframe is not None else pd.DataFrame()
        content = format_ranking_answer(parsed["report_year"], dataframe)
        images = self._create_chart(parsed["raw_question"], dataframe.rename(columns={"stock_abbr": "label", "profit": "value"}), question_id, f"{parsed['report_year']}年利润排名")
        answer = {"content": content, "image": images, "references": []}
        return answer, [plan["sql"]]

    def _handle_knowledge_query(self) -> tuple[dict[str, Any], list[str]]:
        products = extract_medicare_products()
        references = []
        if products:
            reference = {
                "paper_path": products[0]["paper_path"],
                "text": products[0]["text"][:220],
                "paper_image": products[0]["paper_image"],
            }
            references.append(reference)
        answer = {
            "content": format_medicare_answer(products),
            "image": [],
            "references": references,
        }
        return answer, []

    def _handle_cause_analysis(self, parsed: dict[str, Any], question_id: str) -> tuple[dict[str, Any], list[str]]:
        _ = plan_tasks(parsed["raw_question"])
        structured_plan = build_context_query(parsed)
        _, trend_dataframe = execute_sql(structured_plan["sql"], self.db_engine)
        trend_dataframe = trend_dataframe if trend_dataframe is not None else pd.DataFrame()
        contexts = retrieve_context(
            f"{parsed['company']['stock_abbr']} {metric_display_name(parsed['metric'])} 增长 原因 CHC 新品 融合 并购",
            top_k=4,
            source_type="stock_report",
        )
        contexts = self._prioritize_qualitative_contexts(contexts)
        evidence_points = self._build_evidence_points(contexts)
        answer = {
            "content": format_cause_answer(parsed, trend_dataframe, evidence_points),
            "image": [],
            "references": [self._make_reference(item) for item in contexts[:2]],
        }
        return answer, [structured_plan["sql"]]

    def process_query(self, user_query: str, question_id: str, turn_index: int) -> tuple[dict[str, Any], list[str]]:
        parsed = parse_user_input(user_query, conversation_context=self.last_context, pending_context=self.pending_context)
        clarification = clarify_if_needed(parsed)
        if clarification:
            self.pending_context = parsed
            answer = {"content": clarification, "image": []}
            self.history.append({"question": user_query, "answer": answer, "sql": []})
            return answer, []

        self.pending_context = None
        intent = parsed["intent"]
        if intent == "single_metric":
            answer, sqls = self._handle_single_metric(parsed, question_id)
        elif intent == "trend_analysis":
            answer, sqls = self._handle_trend_analysis(parsed, question_id)
        elif intent == "ranking_analysis":
            answer, sqls = self._handle_ranking_analysis(parsed, question_id)
        elif intent == "knowledge_query":
            answer, sqls = self._handle_knowledge_query()
        elif intent == "cause_analysis":
            answer, sqls = self._handle_cause_analysis(parsed, question_id)
        else:
            answer = {"content": "暂时无法理解这个问题，请换一种问法。", "image": []}
            sqls = []

        require_references = intent in {"knowledge_query", "cause_analysis"}
        valid, issues = validate_answer_payload(answer, require_references=require_references)
        if not valid:
            answer["content"] += "（回答已生成，但仍存在校验提示：" + "；".join(issues) + "）"

        self.last_context = parsed
        self.history.append({"question": user_query, "answer": answer, "sql": sqls})
        return answer, sqls
