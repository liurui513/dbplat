from __future__ import annotations

import re
from typing import Any

from database.config import load_company_master


METRIC_SPECS = [
    {
        "key": "total_profit",
        "display_name": "利润总额",
        "table": "income_sheet",
        "column": "total_profit",
        "unit": "万元",
        "keywords": ["利润总额", "总利润"],
    },
    {
        "key": "total_operating_revenue",
        "display_name": "主营业务收入",
        "table": "income_sheet",
        "column": "total_operating_revenue",
        "unit": "万元",
        "keywords": ["主营业务收入", "营业总收入", "营业收入", "营收", "销售额"],
    },
    {
        "key": "net_profit",
        "display_name": "净利润",
        "table": "income_sheet",
        "column": "net_profit",
        "unit": "万元",
        "keywords": ["归母净利润", "净利润", "利润", "业绩"],
    },
]

METRIC_BY_KEY = {metric["key"]: metric for metric in METRIC_SPECS}
DEFAULT_CAUSE_METRIC_KEY = "net_profit"

PERIOD_LABELS = {
    "Q1": "第一季度",
    "HY": "半年度",
    "Q3": "第三季度",
    "FY": "年度",
}


def _company_records() -> list[dict[str, str]]:
    master = load_company_master()
    records = list(master["by_code"].values())
    return sorted(records, key=lambda item: max(len(item["stock_abbr"]), len(item["company_name"])), reverse=True)


def metric_display_name(metric: dict[str, Any]) -> str:
    return str(metric["display_name"])


def format_period_label(report_year: int | None, report_period: str | None) -> str:
    if report_year is None or report_period is None:
        return "指定报告期间"
    return f"{report_year}年{PERIOD_LABELS.get(report_period, report_period)}"


def detect_company(text: str) -> dict[str, str] | None:
    match = re.search(r"\b(\d{6})\b", text)
    if match:
        stock_code = match.group(1)
        record = load_company_master()["by_code"].get(stock_code)
        if record:
            return record

    for record in _company_records():
        if record["stock_abbr"] and record["stock_abbr"] in text:
            return record
        if record["company_name"] and record["company_name"] in text:
            return record
    return None


def detect_metric(text: str) -> dict[str, Any] | None:
    for metric in METRIC_SPECS:
        if any(keyword in text for keyword in metric["keywords"]):
            return metric
    if "业绩" in text:
        return METRIC_BY_KEY[DEFAULT_CAUSE_METRIC_KEY]
    return None


def detect_period(text: str) -> tuple[int | None, str | None]:
    year_match = re.search(r"(20\d{2})", text)
    report_year = int(year_match.group(1)) if year_match else None

    if any(token in text for token in ["第一季度", "一季度", "Q1", "1季度"]):
        return report_year, "Q1"
    if any(token in text for token in ["半年度", "半年报", "中报", "半年"]):
        return report_year, "HY"
    if any(token in text for token in ["第三季度", "三季度", "Q3", "3季度"]):
        return report_year, "Q3"
    if any(token in text for token in ["年度", "年报"]):
        return report_year, "FY"
    return report_year, None


def detect_time_scope(text: str) -> str | None:
    if any(token in text for token in ["近一年", "最近一年", "近1年", "最近1年", "过去一年"]):
        return "recent_one_year"
    if any(token in text for token in ["近两年", "最近两年", "近2年", "最近2年", "过去两年"]):
        return "recent_two_years"
    if any(token in text for token in ["近三年", "最近三年"]):
        return "recent_three_years"
    if any(token in text for token in ["近四年", "最近四年", "近4年", "最近4年"]):
        return "recent_four_years"
    if any(token in text for token in ["近五年", "最近五年", "近5年", "最近5年"]):
        return "recent_five_years"
    if any(token in text for token in ["近几年", "近年来", "近年", "历年"]):
        return "all_available_periods"
    return None


def detect_year_range(text: str) -> tuple[int, int] | None:
    patterns = [
        r"(20\d{2})\s*年?\s*[-~—–]\s*(20\d{2})\s*年?",
        r"(20\d{2})\s*年?\s*(?:到|至)\s*(20\d{2})\s*年?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        start_year = int(match.group(1))
        end_year = int(match.group(2))
        if start_year > end_year:
            start_year, end_year = end_year, start_year
        return start_year, end_year
    return None


def detect_compare_mode(text: str) -> str | None:
    lowered = text.lower()
    if "环比" in text or "较上期" in text or "上一期" in text:
        return "qoq"
    if "同比" in text or "上年同期" in text or "去年同期" in text or ("今年" in text and "去年" in text):
        return "yoy"
    if any(keyword in text for keyword in ["对比", "比较", "相比"]) or "vs" in lowered:
        return "compare"
    return None


def detect_ranking_limit(text: str) -> int:
    lowered = text.lower()
    patterns = [
        r"top\s*(\d+)",
        r"前\s*(\d+)\s*名?",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered if "top" in pattern else text)
        if match:
            return max(1, int(match.group(1)))
    return 10


def classify_intent(text: str, metric: dict[str, Any] | None) -> str:
    lowered = text.lower()
    year_range = detect_year_range(text)
    compare_mode = detect_compare_mode(text)
    if "原因" in text or "归因" in text or "为什么" in text:
        return "cause_analysis"
    has_medicare_topic = any(keyword in text for keyword in ["医保目录", "医保谈判", "医保准入"])
    asks_products = ("产品有哪些" in text and "中药" in text) or ("新增" in text and "中药" in text)
    asks_industry_impact = has_medicare_topic and any(
        keyword in text
        for keyword in ["影响", "医药行业", "行业", "行业风向", "创新导向", "支付", "商保"]
    )
    if "医保目录" in text or asks_products or asks_industry_impact:
        return "knowledge_query"
    if compare_mode is not None:
        return "comparison_analysis"
    if re.search(r"top\s*\d+", lowered) or "最高" in text or "排名" in text or re.search(r"前\s*\d+", text):
        return "ranking_analysis"
    if any(keyword in text for keyword in ["趋势", "变化", "可视化", "绘图", "折线图", "柱状图"]) or detect_time_scope(text) or year_range:
        return "trend_analysis"
    if metric is not None:
        return "single_metric"
    return "unknown"


def merge_with_context(
    parsed: dict[str, Any],
    conversation_context: dict[str, Any] | None = None,
    pending_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = dict(parsed)
    for context in [pending_context or {}, conversation_context or {}]:
        if merged.get("company") is None and context.get("company") is not None:
            merged["company"] = context["company"]
        if merged.get("metric") is None and context.get("metric") is not None:
            merged["metric"] = context["metric"]
        if merged.get("report_year") is None and context.get("report_year") is not None:
            merged["report_year"] = context["report_year"]
        if merged.get("report_period") is None and context.get("report_period") is not None:
            merged["report_period"] = context["report_period"]
        if merged.get("time_scope") is None and context.get("time_scope") is not None:
            merged["time_scope"] = context["time_scope"]
        if merged.get("year_range") is None and context.get("year_range") is not None:
            merged["year_range"] = context["year_range"]
        if merged.get("compare_mode") is None and context.get("compare_mode") is not None:
            merged["compare_mode"] = context["compare_mode"]
        if merged.get("ranking_limit") is None and context.get("ranking_limit") is not None:
            merged["ranking_limit"] = context["ranking_limit"]

    if merged.get("intent") == "cause_analysis" and merged.get("metric") is None:
        merged["metric"] = METRIC_BY_KEY[DEFAULT_CAUSE_METRIC_KEY]
    if merged.get("intent") == "unknown" and merged.get("metric") is not None:
        merged["intent"] = "single_metric"
    return merged


def parse_user_input(
    user_input: str,
    conversation_context: dict[str, Any] | None = None,
    pending_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metric = detect_metric(user_input)
    report_year, report_period = detect_period(user_input)
    parsed = {
        "raw_question": user_input,
        "company": detect_company(user_input),
        "metric": metric,
        "report_year": report_year,
        "report_period": report_period,
        "time_scope": detect_time_scope(user_input),
        "year_range": detect_year_range(user_input),
        "compare_mode": detect_compare_mode(user_input),
        "ranking_limit": detect_ranking_limit(user_input),
    }
    parsed["intent"] = classify_intent(user_input, metric)
    parsed = merge_with_context(parsed, conversation_context=conversation_context, pending_context=pending_context)
    return parsed


def clarify_if_needed(parsed: dict[str, Any]) -> str | None:
    intent = parsed.get("intent")
    if intent == "single_metric":
        if parsed.get("company") is None:
            return "请问你想查询哪一家公司的数据？"
        if parsed.get("metric") is None:
            return "请问你想查询哪一个财务指标？"
        if parsed.get("report_year") is None or parsed.get("report_period") is None:
            return "请问你想查询哪一个报告期间的数据？例如 2025 年第三季度。"
    if intent == "trend_analysis" and parsed.get("company") is None:
        return "请先告诉我你想分析哪一家公司的趋势数据。"
    if intent == "cause_analysis" and parsed.get("company") is None:
        return "请先告诉我你想分析哪一家公司的业绩原因。"
    if intent == "ranking_analysis" and parsed.get("report_year") is None:
        return "请补充要排名的年份，例如 2024 年利润最高的企业。"
    if intent == "comparison_analysis":
        if parsed.get("company") is None:
            return "请先告诉我你想比较哪一家公司。"
        if parsed.get("metric") is None:
            return "请补充要比较的财务指标，例如净利润或主营业务收入。"
    return None
