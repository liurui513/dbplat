from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd
import re

from knowledge.answer_validator import validate_answer_payload
from knowledge.multi_intent_planner import plan_tasks
from knowledge.rag_retriever import extract_medicare_products, retrieve_context

from .formatter import (
    format_comparison_answer,
    format_cause_answer,
    format_medicare_answer,
    format_ranking_answer,
    format_scalar_answer,
    format_trend_answer,
)
from .intent_recognizer import clarify_if_needed, metric_display_name, parse_user_input
from .query_executor import QueryExecutionError, execute_sql
from .sql_generator import build_comparison_query, build_context_query, nl_to_sql
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

    def _is_medicare_product_question(self, question: str) -> bool:
        return "医保目录" in question or ("中药" in question and any(keyword in question for keyword in ["产品", "新增", "清单"]))

    def _prioritize_industry_contexts(self, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        industry_keywords = [
            "成功率",
            "创新导向",
            "放量",
            "市场份额",
            "新机制",
            "创新药",
            "商保",
            "中成药",
            "独家品种",
            "价格降幅",
        ]
        scored = []
        for context in contexts:
            score = sum(2 for keyword in industry_keywords if keyword in context["text"])
            if "医保谈判" in context.get("title", ""):
                score += 3
            scored.append((score, context))
        scored.sort(key=lambda item: (-item[0], item[1]["page_number"], item[1]["chunk_index"]))
        return [context for _, context in scored]

    def _build_industry_impact_points(self, contexts: list[dict[str, Any]]) -> list[str]:
        text = "\n".join(item["text"] for item in contexts)
        points = []
        rules = [
            (
                ["成功率", "纳入"],
                "医保谈判成功率提升，优质药品进入目录的确定性增强，行业准入效率继续改善。",
            ),
            (
                ["放量", "市场份额", "渗透率"],
                "通过医保准入后，相关产品更容易实现放量、提升市场份额，并增强患者可及性。",
            ),
            (
                ["创新导向", "新机制", "创新药", "ADC", "siRNA", "TCE"],
                "医保谈判继续向创新药和新机制药物倾斜，强化了行业研发升级和产品结构优化的方向。",
            ),
            (
                ["商保", "商业保险"],
                "商保支付与医保谈判形成补充，有助于高价值创新药拓宽支付路径和商业化空间。",
            ),
            (
                ["中成药", "中药", "独家品种"],
                "中成药仍保留一定准入比例，但更强调独家品种和差异化能力，利好具备特色中药资产的企业。",
            ),
            (
                ["价格降幅", "降幅", "-60%"],
                "医保准入通常伴随较大的价格让渡，企业需要在放量机会与利润率之间做好平衡。",
            ),
        ]
        for keywords, point in rules:
            if any(keyword in text for keyword in keywords) and point not in points:
                points.append(point)
        return points

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

    def _is_visualization_request(self, question: str) -> bool:
        return any(keyword in question for keyword in ["可视化", "绘图", "折线图", "柱状图"])

    def _handle_single_metric(self, parsed: dict[str, Any], question_id: str) -> tuple[dict[str, Any], list[str]]:
        plan = nl_to_sql(parsed)
        _, dataframe = execute_sql(plan["sql"], self.db_engine, raise_on_error=True)
        content = format_scalar_answer(parsed, dataframe if dataframe is not None else pd.DataFrame())
        answer = {"content": content, "image": []}
        return answer, [plan["sql"]]

    def _handle_trend_analysis(self, parsed: dict[str, Any], question_id: str) -> tuple[dict[str, Any], list[str]]:
        plan = nl_to_sql(parsed)
        _, dataframe = execute_sql(plan["sql"], self.db_engine, raise_on_error=True)
        dataframe = dataframe if dataframe is not None else pd.DataFrame()
        content = format_trend_answer(parsed, dataframe)
        images = self._create_chart(parsed["raw_question"], dataframe, question_id, f"{parsed['company']['stock_abbr']}{metric_display_name(parsed['metric'])}趋势")
        if "变化趋势" in parsed["raw_question"] and not dataframe.empty:
            images.extend(
                self._create_chart("bar", dataframe.tail(min(len(dataframe), 8)), question_id, f"{parsed['company']['stock_abbr']}{metric_display_name(parsed['metric'])}阶段对比")
            )
        if images and self._is_visualization_request(parsed["raw_question"]):
            content += f" 已生成{len(images)}张图表。"
        answer = {"content": content, "image": images}
        return answer, [plan["sql"]]

    def _handle_comparison_analysis(self, parsed: dict[str, Any], question_id: str) -> tuple[dict[str, Any], list[str]]:
        plan = build_comparison_query(parsed)
        if not plan["sql"]:
            answer = {
                "content": f"当前仅支持主营业务收入和净利润的环比比较，暂不支持{metric_display_name(parsed['metric'])}的环比问法。",
                "image": [],
            }
            return answer, []
        _, dataframe = execute_sql(plan["sql"], self.db_engine, raise_on_error=True)
        dataframe = dataframe if dataframe is not None else pd.DataFrame()
        content = format_comparison_answer(parsed, dataframe)
        images = self._create_chart(parsed["raw_question"], dataframe, question_id, f"{parsed['company']['stock_abbr']}{metric_display_name(parsed['metric'])}比较")
        if images and self._is_visualization_request(parsed["raw_question"]):
            content += f" 已生成{len(images)}张图表。"
        answer = {"content": content, "image": images}
        return answer, [plan["sql"]]

    def _handle_ranking_analysis(self, parsed: dict[str, Any], question_id: str) -> tuple[dict[str, Any], list[str]]:
        _ = plan_tasks(parsed["raw_question"])
        plan = nl_to_sql(parsed)
        _, dataframe = execute_sql(plan["sql"], self.db_engine, raise_on_error=True)
        dataframe = dataframe if dataframe is not None else pd.DataFrame()
        content = format_ranking_answer(parsed["report_year"], dataframe)
        images = self._create_chart(parsed["raw_question"], dataframe.rename(columns={"stock_abbr": "label", "profit": "value"}), question_id, f"{parsed['report_year']}年利润排名")
        answer = {"content": content, "image": images, "references": []}
        return answer, [plan["sql"]]

    def _handle_knowledge_query(self, parsed: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        question = parsed["raw_question"]
        if self._is_medicare_product_question(question):
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

        query = question
        if "医保谈判" not in query:
            query += " 医保谈判"
        if "医药行业" not in query and "行业" not in query:
            query += " 医药行业"
        contexts = retrieve_context(query, top_k=4, source_type="industry_report")
        contexts = self._prioritize_industry_contexts(contexts)
        impact_points = self._build_industry_impact_points(contexts)
        if impact_points:
            cleaned_points = [point.rstrip("。") for point in impact_points[:4]]
            content = "结合行业研报，医保谈判对相关医药行业的影响主要体现在：" + "；".join(
                f"{index + 1}. {point}" for index, point in enumerate(cleaned_points)
            ) + "。"
        elif contexts:
            content = (
                "结合行业研报，医保谈判会同时影响药品准入、价格体系和市场放量节奏，"
                "并持续强化创新药与差异化品种的竞争优势。"
            )
        else:
            content = "目前知识库中未检索到足够明确的医保谈判行业影响资料。"
        answer = {
            "content": content,
            "image": [],
            "references": [self._make_reference(item) for item in contexts[:2]],
        }
        return answer, []

    def _handle_cause_analysis(self, parsed: dict[str, Any], question_id: str) -> tuple[dict[str, Any], list[str]]:
        _ = plan_tasks(parsed["raw_question"])
        structured_plan = build_context_query(parsed)
        _, trend_dataframe = execute_sql(structured_plan["sql"], self.db_engine, raise_on_error=True)
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
        query_failed = False
        try:
            if intent == "single_metric":
                answer, sqls = self._handle_single_metric(parsed, question_id)
            elif intent == "comparison_analysis":
                answer, sqls = self._handle_comparison_analysis(parsed, question_id)
            elif intent == "trend_analysis":
                answer, sqls = self._handle_trend_analysis(parsed, question_id)
            elif intent == "ranking_analysis":
                answer, sqls = self._handle_ranking_analysis(parsed, question_id)
            elif intent == "knowledge_query":
                answer, sqls = self._handle_knowledge_query(parsed)
            elif intent == "cause_analysis":
                answer, sqls = self._handle_cause_analysis(parsed, question_id)
            else:
                answer = {"content": "暂时无法理解这个问题，请换一种问法。", "image": []}
                sqls = []
        except QueryExecutionError as exc:
            query_failed = True
            answer = {"content": f"查询执行失败：{exc.original_error}", "image": []}
            sqls = [exc.sql] if exc.sql else []

        require_references = not query_failed and intent in {"knowledge_query", "cause_analysis"}
        valid, issues = validate_answer_payload(answer, require_references=require_references)
        if not valid:
            answer["content"] += "（回答已生成，但仍存在校验提示：" + "；".join(issues) + "）"

        self.last_context = parsed
        self.history.append({"question": user_query, "answer": answer, "sql": sqls})
        return answer, sqls
