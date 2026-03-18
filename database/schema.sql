CREATE DATABASE IF NOT EXISTS financial_db CHARACTER SET utf8mb4;
USE financial_db;

-- 核心业绩指标表
CREATE TABLE IF NOT EXISTS core_performance_indicators_sheet (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(20),
    stock_abbr VARCHAR(50),
    report_period VARCHAR(20), -- 如 2023FY, 2024Q1
    total_revenue DECIMAL(20, 2),
    total_profit DECIMAL(20, 2),
    net_profit DECIMAL(20, 2),
    -- 其他字段参考附件3...
    UNIQUE KEY unique_record (stock_code, report_period)
);

-- 资产负债表、现金流量表、利润表 类似创建...
-- CREATE TABLE balance_sheet (...);
-- CREATE TABLE cash_flow_sheet (...);
-- CREATE TABLE income_sheet (...);