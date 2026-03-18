def plan_tasks(complex_question):
    # 调用大模型拆解问题
    # 输入: "2024年利润最高的top10企业是哪些？这些企业的销售额同比是多少？"
    # 输出: [
    #   {"step": 1, "intent": "query_top10_profit", "sql": "..."},
    #   {"step": 2, "intent": "query_sales_growth", "depends_on": 1}
    # ]
    pass