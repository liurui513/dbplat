# 财报目录配置
REPORT_PATHS = [
    r"D:\Bigdata\dbplat\data\data\附件2：财务报告\reports-上交所",
    r"D:\Bigdata\dbplat\data\data\附件2：财务报告\reports-深交所"
]

# 数据库配置（SQLite 优先，无需额外服务）
DB_CONFIG = {
    "type": "sqlite",
    "path": r"D:\Bigdata\dbplat\finance_database.db",
    "mysql": {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "Liurui8196",
        "database": "finance_db"
    }
}

# 附件3 字段映射（核心四张表）
FIELD_MAPPING = {
    "core_performance": [
        "company_code", "company_name", "report_year",
        "total_revenue", "net_profit", "net_profit_deduct",
        "eps", "operating_cash_flow"
    ],
    "balance_sheet": [
        "company_code", "company_name", "report_year",
        "total_assets", "total_liabilities", "total_equity",
        "monetary_funds", "accounts_receivable", "inventory"
    ],
    "income_statement": [
        "company_code", "company_name", "report_year",
        "operating_revenue", "operating_cost", "operating_profit",
        "total_profit", "net_profit_parent"
    ],
    "cash_flow": [
        "company_code", "company_name", "report_year",
        "operating_cash_flow", "investing_cash_flow",
        "financing_cash_flow", "net_cash_flow"
    ]
}

# PDF 解析关键词配置
PDF_KEYWORDS = {
    "core_performance": ["主要财务指标", "业绩摘要"],
    "balance_sheet": ["合并资产负债表", "母公司资产负债表"],
    "income_statement": ["合并利润表", "母公司利润表"],
    "cash_flow": ["合并现金流量表", "母公司现金流量表"]
}