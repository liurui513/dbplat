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

    if values.min() < 0 < values.max():
        trend_desc = "先下探后修复，呈明显的 V 型反转"
    elif float(end_row["value"]) > float(start_row["value"]) * 1.05:
        trend_desc = "整体呈上升趋势"
    elif float(end_row["value"]) < float(start_row["value"]) * 0.95:
        trend_desc = "整体呈回落趋势"
    else:
        trend_desc = "整体波动相对平稳"

    return (
        f"{company['stock_abbr']}的{metric_display_name(metric)}{trend_desc}。"
        f"区间起点为{_series_period_label(start_row)}，数值为{format_number(float(start_row['value']), metric['unit'])}；"
        f"最近一期为{_series_period_label(end_row)}，数值为{format_number(float(end_row['value']), metric['unit'])}。"
        f"区间高点出现在{_series_period_label(max_row)}，低点出现在{_series_period_label(min_row)}。"
        f"{note}"
    )


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
