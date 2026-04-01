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


def _comparable_period(parsed: dict[str, Any]) -> str:
    return str(parsed.get("report_period") or "FY")


def _recent_full_year_query(metric: dict[str, Any], company: dict[str, Any], period: str, recent_years: int) -> str:
    year_offset = max(recent_years - 1, 0)
    return f"""
WITH latest_full_year AS (
    SELECT MAX(report_year) AS max_year
    FROM {metric['table']}
    WHERE stock_code = '{company['stock_code']}'
      AND report_period = '{period}'
      AND {metric['column']} IS NOT NULL
)
SELECT stock_code, stock_abbr, report_year, report_period, {metric['column']} AS value
FROM {metric['table']}
WHERE stock_code = '{company['stock_code']}'
  AND report_period = '{period}'
  AND report_year >= (SELECT max_year - {year_offset} FROM latest_full_year)
ORDER BY report_year;
""".strip()


def _explicit_year_range_query(
    metric: dict[str, Any],
    company: dict[str, Any],
    period: str,
    start_year: int,
    end_year: int,
) -> str:
    return f"""
SELECT stock_code, stock_abbr, report_year, report_period, {metric['column']} AS value
FROM {metric['table']}
WHERE stock_code = '{company['stock_code']}'
  AND report_period = '{period}'
  AND report_year BETWEEN {start_year} AND {end_year}
ORDER BY report_year;
""".strip()


def _historical_query(metric: dict[str, Any], company: dict[str, Any], period: str) -> str:
    return f"""
SELECT stock_code, stock_abbr, report_year, report_period, {metric['column']} AS value
FROM {metric['table']}
WHERE stock_code = '{company['stock_code']}'
  AND report_period = '{period}'
ORDER BY report_year;
""".strip()


def _latest_comparable_period_cte(metric: dict[str, Any], company: dict[str, Any], period: str | None = None) -> str:
    period_filter = f"AND report_period = '{period}'" if period else ""
    return f"""
WITH latest_period AS (
    SELECT report_year, report_period
    FROM {metric['table']}
    WHERE stock_code = '{company['stock_code']}'
      AND {metric['column']} IS NOT NULL
      {period_filter}
    ORDER BY report_year DESC, {PERIOD_ORDER_SQL} DESC
    LIMIT 1
)
""".strip()


def _latest_year_for_period_cte(metric: dict[str, Any], company: dict[str, Any], period: str) -> str:
    return f"""
WITH latest_year AS (
    SELECT MAX(report_year) AS max_year
    FROM {metric['table']}
    WHERE stock_code = '{company['stock_code']}'
      AND report_period = '{period}'
      AND {metric['column']} IS NOT NULL
)
""".strip()


def build_comparison_query(parsed: dict[str, Any]) -> dict[str, Any]:
    metric = parsed["metric"]
    company = parsed["company"]
    compare_mode = parsed.get("compare_mode")
    period = _comparable_period(parsed)
    year_range = parsed.get("year_range")
    report_year = parsed.get("report_year")

    if compare_mode == "qoq":
        qoq_specs = {
            "total_operating_revenue": ("total_operating_revenue", "operating_revenue_qoq_growth"),
            "net_profit": ("net_profit_10k_yuan", "net_profit_qoq_growth"),
        }
        value_column, growth_column = qoq_specs.get(metric["key"], (None, None))
        if value_column is None or growth_column is None:
            return {"sql": "", "metric": metric, "comparison_mode": compare_mode}
        if report_year is not None and parsed.get("report_period") is not None:
            sql = f"""
SELECT stock_code, stock_abbr, report_year, report_period, {value_column} AS value, {growth_column} AS growth
FROM core_performance
WHERE stock_code = '{company['stock_code']}'
  AND report_year = {report_year}
  AND report_period = '{parsed['report_period']}';
""".strip()
        else:
            sql = f"""
SELECT stock_code, stock_abbr, report_year, report_period, {value_column} AS value, {growth_column} AS growth
FROM core_performance
WHERE stock_code = '{company['stock_code']}'
  AND {growth_column} IS NOT NULL
ORDER BY report_year DESC, {PERIOD_ORDER_SQL} DESC
LIMIT 1;
""".strip()
        return {"sql": sql, "metric": metric, "comparison_mode": compare_mode}

    if year_range is not None:
        sql = _explicit_year_range_query(metric, company, period, year_range[0], year_range[1])
        return {"sql": sql, "metric": metric, "comparison_mode": compare_mode}

    if report_year is not None:
        sql = f"""
SELECT stock_code, stock_abbr, report_year, report_period, {metric['column']} AS value
FROM {metric['table']}
WHERE stock_code = '{company['stock_code']}'
  AND report_period = '{period}'
  AND report_year IN ({report_year - 1}, {report_year})
ORDER BY report_year;
""".strip()
        return {"sql": sql, "metric": metric, "comparison_mode": compare_mode}

    if parsed.get("report_period") is not None:
        cte = _latest_year_for_period_cte(metric, company, parsed["report_period"])
        sql = f"""
{cte}
SELECT stock_code, stock_abbr, report_year, report_period, {metric['column']} AS value
FROM {metric['table']}
WHERE stock_code = '{company['stock_code']}'
  AND report_period = '{parsed['report_period']}'
  AND report_year IN ((SELECT max_year - 1 FROM latest_year), (SELECT max_year FROM latest_year))
ORDER BY report_year;
""".strip()
        return {"sql": sql, "metric": metric, "comparison_mode": compare_mode}

    cte = _latest_comparable_period_cte(metric, company)
    sql = f"""
{cte}
SELECT stock_code, stock_abbr, report_year, report_period, {metric['column']} AS value
FROM {metric['table']}
WHERE stock_code = '{company['stock_code']}'
  AND report_period = (SELECT report_period FROM latest_period)
  AND report_year IN ((SELECT report_year - 1 FROM latest_period), (SELECT report_year FROM latest_period))
ORDER BY report_year;
""".strip()
    return {"sql": sql, "metric": metric, "comparison_mode": compare_mode}


def build_trend_query(parsed: dict[str, Any]) -> dict[str, Any]:
    metric = parsed["metric"]
    company = parsed["company"]
    time_scope = parsed.get("time_scope")
    year_range = parsed.get("year_range")
    period = _comparable_period(parsed)
    recent_year_mapping = {
        "recent_one_year": 1,
        "recent_two_years": 2,
        "recent_three_years": 3,
        "recent_four_years": 4,
        "recent_five_years": 5,
    }

    if year_range is not None:
        sql = _explicit_year_range_query(metric, company, period, year_range[0], year_range[1])
    elif time_scope in recent_year_mapping:
        sql = _recent_full_year_query(metric, company, period, recent_year_mapping[time_scope])
    elif time_scope == "all_available_periods":
        sql = _historical_query(metric, company, period)
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
    if intent == "comparison_analysis":
        return build_comparison_query(parsed)
    if intent == "trend_analysis":
        return build_trend_query(parsed)
    if intent == "ranking_analysis":
        return build_ranking_query(parsed)
    if intent == "cause_analysis":
        return build_context_query(parsed)
    return {"sql": ""}
