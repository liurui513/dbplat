-- 核心业绩表
CREATE TABLE IF NOT EXISTS core_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_code TEXT NOT NULL,
    company_name TEXT NOT NULL,
    report_year TEXT NOT NULL,
    total_revenue REAL,
    net_profit REAL,
    net_profit_deduct REAL,
    eps REAL,
    operating_cash_flow REAL,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 资产负债表
CREATE TABLE IF NOT EXISTS balance_sheet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_code TEXT NOT NULL,
    company_name TEXT NOT NULL,
    report_year TEXT NOT NULL,
    total_assets REAL,
    total_liabilities REAL,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 利润表
CREATE TABLE IF NOT EXISTS income_statement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_code TEXT NOT NULL,
    company_name TEXT NOT NULL,
    report_year TEXT NOT NULL,
    operating_profit REAL,
    total_profit REAL,
    net_profit REAL,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 现金流量表
CREATE TABLE IF NOT EXISTS cash_flow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_code TEXT NOT NULL,
    company_name TEXT NOT NULL,
    report_year TEXT NOT NULL,
    operating_cash_flow REAL,
    invest_cash_flow REAL,
    finance_cash_flow REAL,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引（提升查询效率）
CREATE INDEX IF NOT EXISTS idx_core_company ON core_performance(company_code, report_year);
CREATE INDEX IF NOT EXISTS idx_balance_company ON balance_sheet(company_code, report_year);
CREATE INDEX IF NOT EXISTS idx_income_company ON income_statement(company_code, report_year);
CREATE INDEX IF NOT EXISTS idx_cash_company ON cash_flow(company_code, report_year);