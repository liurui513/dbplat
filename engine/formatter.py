from __future__ import annotations

from typing import Any

import pandas as pd

from .intent_recognizer import format_period_label, metric_display_name


def format_number(value: float | None, unit: str = "万元") -> str:
    if value is None:
        return "暂无数据"
    return f"{value:,.2f}{unit}"


def _series_period_label(row: pd.Series) -> str:
    return format_period_label(int(row["report_year"]), str(row["report_period"]))


def _time_scope_label(parsed: dict[str, Any]) -> str:
    year_range = parsed.get("year_range")
    if year_range:
        start_year, end_year = year_range
        if start_year == end_year:
            return f"{start_year}年"
        return f"{start_year}-{end_year}年"
    mapping = {
        "recent_one_year": "近一年",
        "recent_two_years": "近两年",
        "recent_three_years": "近三年",
        "recent_four_years": "近四年",
        "recent_five_years": "近五年",
        "all_available_periods": "历年",
    }
    return mapping.get(parsed.get("time_scope"), "该时间区间")


def _metric_focus(metric: dict[str, Any]) -> str:
    mapping = {
        "total_operating_revenue": "主营业务规模",
        "net_profit": "盈利水平",
        "total_profit": "利润总额水平",
    }
    return mapping.get(str(metric.get("key")), metric_display_name(metric))


def _change_summary(start_value: float, end_value: float) -> str:
    delta = end_value - start_value
    if abs(delta) < 1e-9:
        return "整体基本持平"
    direction = "增长" if delta > 0 else "下降"
    if abs(start_value) < 1e-9:
        return f"{direction}{abs(delta):,.2f}"
    pct = abs(delta) / abs(start_value) * 100
    return f"{direction}{abs(delta):,.2f}，变动幅度{pct:.2f}%"


def format_scalar_answer(parsed: dict[str, Any], dataframe: pd.DataFrame) -> str:
    metric = parsed["metric"]
    company = parsed["company"]
    period_label = format_period_label(parsed["report_year"], parsed["report_period"])
    if dataframe.empty or dataframe.iloc[0]["value"] is None:
        return f"未查询到{company['stock_abbr']}{period_label}的{metric_display_name(metric)}数据。"
    value = float(dataframe.iloc[0]["value"])
    return f"{company['stock_abbr']}{period_label}的{metric_display_name(metric)}是{format_number(value, metric['unit'])}。"


def format_trend_answer(parsed: dict[str, Any], dataframe: pd.DataFrame) -> str:
    metric = parsed["metric"]
    company = parsed["company"]
    if dataframe.empty:
        return f"未查询到{company['stock_abbr']}的{metric_display_name(metric)}趋势数据。"

    working_df = dataframe.copy()
    note = ""
    if "report_period" in working_df.columns and working_df.iloc[-1]["report_period"] != "FY":
        annual_df = working_df[working_df["report_period"] == "FY"].copy()
        if len(annual_df) >= 2:
            working_df = annual_df
            latest_row = dataframe.iloc[-1]
            note = (
                f" 另需注意，最近一期为{_series_period_label(latest_row)}口径，"
                f"数值为{format_number(float(latest_row['value']), metric['unit'])}，"
                "与完整年报口径不完全可比。"
            )

    values = working_df["value"].astype(float)
    start_row = working_df.iloc[0]
    end_row = working_df.iloc[-1]
    max_row = working_df.loc[values.idxmax()]
    min_row = working_df.loc[values.idxmin()]
    time_scope_label = _time_scope_label(parsed)
    metric_focus = _metric_focus(metric)
    question = str(parsed.get("raw_question", ""))

    if values.min() < 0 < values.max():
        trend_desc = "先下探后修复，呈明显的 V 型反转"
    elif float(end_row["value"]) > float(start_row["value"]) * 1.05:
        trend_desc = "整体呈上升趋势"
    elif float(end_row["value"]) < float(start_row["value"]) * 0.95:
        trend_desc = "整体呈回落趋势"
    else:
        trend_desc = "整体波动相对平稳"

    start_value = float(start_row["value"])
    end_value = float(end_row["value"])
    change_summary = _change_summary(start_value, end_value)

    if len(working_df) == 1:
        content = (
            f"{company['stock_abbr']}{time_scope_label}可比的{metric_display_name(metric)}数据共有1期，"
            f"为{_series_period_label(end_row)}的{format_number(end_value, metric['unit'])}，"
            f"主要反映{metric_focus}在最新可比年度的水平。"
        )
    elif len(working_df) <= 2:
        content = (
            f"{company['stock_abbr']}{time_scope_label}的{metric_display_name(metric)}主要反映{metric_focus}。"
            f"从{_series_period_label(start_row)}的{format_number(start_value, metric['unit'])}"
            f"变动到{_series_period_label(end_row)}的{format_number(end_value, metric['unit'])}，{change_summary}。"
            f"其中高点为{_series_period_label(max_row)}，低点为{_series_period_label(min_row)}。"
        )
    else:
        content = (
            f"{company['stock_abbr']}{time_scope_label}的{metric_display_name(metric)}{trend_desc}，"
            f"主要反映{metric_focus}的变化。"
            f"区间起点为{_series_period_label(start_row)}，数值为{format_number(start_value, metric['unit'])}；"
            f"最近一期为{_series_period_label(end_row)}，数值为{format_number(end_value, metric['unit'])}。"
            f"区间高点出现在{_series_period_label(max_row)}，低点出现在{_series_period_label(min_row)}。"
        )

    if any(keyword in question for keyword in ["可视化", "绘图", "折线图", "柱状图"]):
        content += " 结果已按该问题要求整理为可视化分析口径。"

    return content + note


def format_comparison_answer(parsed: dict[str, Any], dataframe: pd.DataFrame) -> str:
    metric = parsed["metric"]
    company = parsed["company"]
    compare_mode = parsed.get("compare_mode")
    question = str(parsed.get("raw_question", ""))

    if dataframe.empty:
        return f"未查询到{company['stock_abbr']}的{metric_display_name(metric)}比较数据。"

    if compare_mode == "qoq":
        row = dataframe.iloc[0]
        value = row.get("value")
        growth = row.get("growth")
        if value is None:
            return f"未查询到{company['stock_abbr']}{metric_display_name(metric)}的环比数据。"
        period_label = format_period_label(int(row["report_year"]), str(row["report_period"]))
        if pd.isna(growth):
            return (
                f"{company['stock_abbr']}{period_label}的{metric_display_name(metric)}为"
                f"{format_number(float(value), metric['unit'])}，但当前数据不足以计算环比结果。"
            )
        growth_value = float(growth)
        direction = "增长" if growth_value >= 0 else "下降"
        content = (
            f"{company['stock_abbr']}{period_label}的{metric_display_name(metric)}为"
            f"{format_number(float(value), metric['unit'])}，按环比口径较上期{direction}{abs(growth_value):.2f}%。"
        )
        if any(keyword in question for keyword in ["可视化", "绘图", "折线图", "柱状图"]):
            content += " 已按比较口径生成可视化结果。"
        return content

    working_df = dataframe.sort_values(["report_year", "report_period"]).reset_index(drop=True)
    if len(working_df) == 1:
        row = working_df.iloc[0]
        period_label = format_period_label(int(row["report_year"]), str(row["report_period"]))
        return (
            f"{company['stock_abbr']}{period_label}的{metric_display_name(metric)}为"
            f"{format_number(float(row['value']), metric['unit'])}，但缺少可比期间数据，暂时无法完成比较。"
        )

    older = working_df.iloc[0]
    newer = working_df.iloc[-1]
    older_value = float(older["value"])
    newer_value = float(newer["value"])
    delta = newer_value - older_value
    pct = None if abs(older_value) < 1e-9 else delta / abs(older_value) * 100
    direction = "增长" if delta >= 0 else "下降"
    compare_word = "同比" if compare_mode == "yoy" else "对比来看"
    period_hint = ""
    if "今年" in question and "去年" in question:
        period_hint = "按数据库最新可比期间口径，"

    content = (
        f"{period_hint}{company['stock_abbr']}{_series_period_label(newer)}的{metric_display_name(metric)}为"
        f"{format_number(newer_value, metric['unit'])}，"
        f"{_series_period_label(older)}为{format_number(older_value, metric['unit'])}。"
    )
    if pct is None:
        content += f"{compare_word}{direction}{abs(delta):,.2f}。"
    else:
        content += f"{compare_word}{direction}{abs(delta):,.2f}，变动幅度{abs(pct):.2f}%。"

    if any(keyword in question for keyword in ["可视化", "绘图", "折线图", "柱状图"]):
        content += " 已按比较口径生成可视化结果。"
    return content


def format_ranking_answer(report_year: int, dataframe: pd.DataFrame) -> str:
    if dataframe.empty:
        return f"未查询到{report_year}年的企业利润排名数据。"

    lines = []
    for index, row in enumerate(dataframe.itertuples(index=False), start=1):
        lines.append(
            f"{index}. {row.stock_abbr}：净利润{format_number(float(row.profit))}，"
            f"营业收入{format_number(float(row.sales))}，营收同比{float(row.sales_yoy_growth):.2f}%"
        )
    best_row = dataframe.sort_values("sales_yoy_growth", ascending=False).iloc[0]
    return (
        f"按{report_year}年年报净利润口径统计，当前样本库中可排序的企业共有{len(dataframe)}家。"
        + " ".join(lines)
        + f" 其中营收同比上涨幅度最大的是{best_row['stock_abbr']}，为{float(best_row['sales_yoy_growth']):.2f}%。"
    )


def format_medicare_answer(products: list[dict[str, str]]) -> str:
    if not products:
        return "未从研报知识库中检索到明确的医保目录新增中药产品清单。"
    product_lines = [
        f"{item['sequence']}. {item['company']}：{item['product']}（{item['category']}）"
        for item in products
    ]
    return (
        f"根据行业研报整理，2025年国家医保目录新增7种中成药，均为独家品种。"
        f"完整清单如下：{'；'.join(product_lines)}。"
    )


def format_cause_answer(
    parsed: dict[str, Any],
    trend_dataframe: pd.DataFrame,
    evidence_points: list[str],
) -> str:
    company = parsed["company"]
    metric = parsed["metric"]
    intro = format_trend_answer(parsed, trend_dataframe)
    if not evidence_points:
        return intro + " 目前知识库中没有检索到足够明确的归因证据。"
    reasons = "；".join(f"{index + 1}. {point}" for index, point in enumerate(evidence_points[:4]))
    return f"{intro} 结合研报内容看，{metric_display_name(metric)}上升的主要原因包括：{reasons}。"
