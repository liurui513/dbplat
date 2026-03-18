# 这里需要调用大模型 API
def generate_sql(question, context_schema):
    prompt = f"""
    你是一个SQL专家。基于以下数据库结构：{context_schema}
    请将用户问题转换为MySQL查询语句。
    用户问题: {question}
    只返回SQL语句，不要解释。
    """
    # 调用 LLM API (伪代码)
    # response = call_llm(prompt)
    # return response.text
    return "SELECT total_profit FROM income_sheet WHERE stock_abbr='测试公司'" # 占位