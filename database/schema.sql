-- 核心业绩表
CREATE TABLE IF NOT EXISTS core_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_code VARCHAR(20) NOT NULL,
    company_name VARCHAR(100),
    report_year INT,
    total_revenue DECIMAL(20,2),
    net_profit DECIMAL(20,2),
    net_profit_deduct DECIMAL(20,2),
    eps DECIMAL(10,4),
    operating_cash_flow DECIMAL(20,2),
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 资产负债表
CREATE TABLE IF NOT EXISTS balance_sheet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_code VARCHAR(20) NOT NULL,
    company_name VARCHAR(100),
    report_year INT,
    total_assets DECIMAL(20,2),
    total_liabilities DECIMAL(20,2),
    total_equity DECIMAL(20,2),
    monetary_funds DECIMAL(20,2),
    accounts_receivable DECIMAL(20,2),
    inventory DECIMAL(20,2),
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 利润表
CREATE TABLE IF NOT EXISTS income_statement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_code VARCHAR(20) NOT NULL,
    company_name VARCHAR(100),
    report_year INT,
    operating_revenue DECIMAL(20,2),
    operating_cost DECIMAL(20,2),
    operating_profit DECIMAL(20,2),
    total_profit DECIMAL(20,2),
    net_profit_parent DECIMAL(20,2),
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 现金流量表
CREATE TABLE IF NOT EXISTS cash_flow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_code VARCHAR(20) NOT NULL,
    company_name VARCHAR(100),
    report_year INT,
    operating_cash_flow DECIMAL(20,2),
    investing_cash_flow DECIMAL(20,2),
    financing_cash_flow DECIMAL(20,2),
    net_cash_flow DECIMAL(20,2),
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);