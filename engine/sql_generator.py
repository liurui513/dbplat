from __future__ import annotations

from typing import Any


PERIOD_ORDER_SQL = """
CASE report_period
    WHEN 'Q1' THEN 1
    WHEN 'HY' THEN 2
    WHEN 'Q3' THEN 3
    WHEN 'FY' THEN 4
    ELSE 5
END
""".strip()


def build_point_query(parsed: dict[str, Any]) -> dict[str, Any]:
    metric = parsed["metric"]
    company = parsed["company"]
    report_year = parsed["report_year"]
    report_period = parsed["report_period"]
    sql = f"""
SELECT stock_code, stock_abbr, report_year, report_period, {metric['column']} AS value
FROM {metric['table']}
WHERE stock_code = '{company['stock_code']}'
  AND report_year = {report_year}
  AND report_period = '{report_period}';
""".strip()
    return {"sql": sql, "metric": metric}


def build_trend_query(parsed: dict[str, Any]) -> dict[str, Any]:
    metric = parsed["metric"]
    company = parsed["company"]
    time_scope = parsed.get("time_scope")

    if time_scope == "recent_three_years":
        sql = f"""
WITH latest_full_year AS (
    SELECT MAX(report_year) AS max_year
    FROM {metric['table']}
    WHERE stock_code = '{company['stock_code']}'
      AND report_period = 'FY'
      AND {metric['column']} IS NOT NULL
)
SELECT stock_code, stock_abbr, report_year, report_period, {metric['column']} AS value
FROM {metric['table']}
WHERE stock_code = '{company['stock_code']}'
  AND report_period = 'FY'
  AND report_year >= (SELECT max_year - 2 FROM latest_full_year)
ORDER BY report_year;
""".strip()
    else:
        sql = f"""
SELECT stock_code, stock_abbr, report_year, report_period, {metric['column']} AS value
FROM {metric['table']}
WHERE stock_code = '{company['stock_code']}'
ORDER BY report_year, {PERIOD_ORDER_SQL};
""".strip()

    return {"sql": sql, "metric": metric}


def build_ranking_query(parsed: dict[str, Any]) -> dict[str, Any]:
    report_year = parsed["report_year"]
    ranking_limit = max(1, int(parsed.get("ranking_limit", 10)))
    sql = f"""
SELECT
    stock_code,
    stock_abbr,
    report_year,
    report_period,
    net_profit AS profit,
    total_operating_revenue AS sales,
    net_profit_yoy_growth AS profit_yoy_growth,
    operating_revenue_yoy_growth AS sales_yoy_growth
FROM income_sheet
WHERE report_year = {report_year}
  AND report_period = 'FY'
ORDER BY profit DESC
LIMIT {ranking_limit};
""".strip()
    return {"sql": sql}


def build_context_query(parsed: dict[str, Any]) -> dict[str, Any]:
    metric = parsed["metric"]
    company = parsed["company"]
    sql = f"""
WITH latest_full_year AS (
    SELECT MAX(report_year) AS max_year
    FROM {metric['table']}
    WHERE stock_code = '{company['stock_code']}'
      AND report_period = 'FY'
      AND {metric['column']} IS NOT NULL
)
SELECT report_year, report_period, {metric['column']} AS value
FROM {metric['table']}
WHERE stock_code = '{company['stock_code']}'
  AND report_period = 'FY'
  AND report_year >= (SELECT max_year - 2 FROM latest_full_year)
ORDER BY report_year;
""".strip()
    return {"sql": sql, "metric": metric}


def nl_to_sql(parsed: dict[str, Any]) -> dict[str, Any]:
    intent = parsed.get("intent")
    if intent == "single_metric":
        return build_point_query(parsed)
    if intent == "trend_analysis":
        return build_trend_query(parsed)
    if intent == "ranking_analysis":
        return build_ranking_query(parsed)
    if intent == "cause_analysis":
        return build_context_query(parsed)
    return {"sql": ""}
