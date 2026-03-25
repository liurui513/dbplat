from __future__ import annotations


def plan_tasks(complex_question: str) -> list[dict[str, object]]:
    question = complex_question.strip()
    if "top10" in question.lower() or "最高" in question:
        return [
            {"step": 1, "intent": "query_company_ranking", "description": "查询指定年份的利润排名"},
            {"step": 2, "intent": "query_growth_metrics", "description": "补充利润与营收同比信息", "depends_on": 1},
            {"step": 3, "intent": "summary_ranking", "description": "汇总排名并找出同比涨幅最大企业", "depends_on": 2},
        ]
    if "原因" in question or "归因" in question:
        return [
            {"step": 1, "intent": "query_structured_metric", "description": "从结构化数据库中确认财务趋势"},
            {"step": 2, "intent": "retrieve_research_context", "description": "从研报中检索可能的驱动因素", "depends_on": 1},
            {"step": 3, "intent": "generate_attribution", "description": "整合结构化数据与研报证据生成归因分析", "depends_on": 2},
        ]
    if "医保" in question or "研报" in question:
        return [
            {"step": 1, "intent": "retrieve_knowledge", "description": "从知识库检索相关材料"},
            {"step": 2, "intent": "summarize_knowledge", "description": "整理检索结果并输出可解释回答", "depends_on": 1},
        ]
    return [{"step": 1, "intent": "single_query", "description": "执行单一结构化查询"}]
