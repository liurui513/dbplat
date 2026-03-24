diff --git a/d:\Bigdata\dbplat\database\schema.sql b/d:\Bigdata\dbplat\database\schema.sql
new file mode 100644
--- /dev/null
+++ b/d:\Bigdata\dbplat\database\schema.sql
@@ -0,0 +1,113 @@
+CREATE TABLE IF NOT EXISTS core_performance (
+    serial_number INTEGER PRIMARY KEY AUTOINCREMENT,
+    stock_code TEXT NOT NULL,
+    stock_abbr TEXT NOT NULL,
+    eps REAL,
+    total_operating_revenue REAL,
+    operating_revenue_yoy_growth REAL,
+    operating_revenue_qoq_growth REAL,
+    net_profit_10k_yuan REAL,
+    net_profit_yoy_growth REAL,
+    net_profit_qoq_growth REAL,
+    net_asset_per_share REAL,
+    roe REAL,
+    operating_cf_per_share REAL,
+    net_profit_excl_non_recurring REAL,
+    net_profit_excl_non_recurring_yoy REAL,
+    gross_profit_margin REAL,
+    net_profit_margin REAL,
+    roe_weighted_excl_non_recurring REAL,
+    report_period TEXT NOT NULL,
+    report_year INTEGER NOT NULL,
+    UNIQUE(stock_code, report_year, report_period)
+);
+
+CREATE TABLE IF NOT EXISTS balance_sheet (
+    serial_number INTEGER PRIMARY KEY AUTOINCREMENT,
+    stock_code TEXT NOT NULL,
+    stock_abbr TEXT NOT NULL,
+    asset_cash_and_cash_equivalents REAL,
+    asset_accounts_receivable REAL,
+    asset_inventory REAL,
+    asset_trading_financial_assets REAL,
+    asset_construction_in_progress REAL,
+    asset_total_assets REAL,
+    asset_total_assets_yoy_growth REAL,
+    liability_accounts_payable REAL,
+    liability_advance_from_customers REAL,
+    liability_total_liabilities REAL,
+    liability_total_liabilities_yoy_growth REAL,
+    liability_contract_liabilities REAL,
+    liability_short_term_loans REAL,
+    asset_liability_ratio REAL,
+    equity_unappropriated_profit REAL,
+    equity_total_equity REAL,
+    report_period TEXT NOT NULL,
+    report_year INTEGER NOT NULL,
+    UNIQUE(stock_code, report_year, report_period)
+);
+
+CREATE TABLE IF NOT EXISTS cash_flow (
+    serial_number INTEGER PRIMARY KEY AUTOINCREMENT,
+    stock_code TEXT NOT NULL,
+    stock_abbr TEXT NOT NULL,
+    net_cash_flow REAL,
+    net_cash_flow_yoy_growth REAL,
+    operating_cf_net_amount REAL,
+    operating_cf_ratio_of_net_cf REAL,
+    operating_cf_cash_from_sales REAL,
+    investing_cf_net_amount REAL,
+    investing_cf_ratio_of_net_cf REAL,
+    investing_cf_cash_for_investments REAL,
+    investing_cf_cash_from_investment_recovery REAL,
+    financing_cf_cash_from_borrowing REAL,
+    financing_cf_cash_for_debt_repayment REAL,
+    financing_cf_net_amount REAL,
+    financing_cf_ratio_of_net_cf REAL,
+    report_period TEXT NOT NULL,
+    report_year INTEGER NOT NULL,
+    UNIQUE(stock_code, report_year, report_period)
+);
+
+CREATE TABLE IF NOT EXISTS income_statement (
+    serial_number INTEGER PRIMARY KEY AUTOINCREMENT,
+    stock_code TEXT NOT NULL,
+    stock_abbr TEXT NOT NULL,
+    net_profit REAL,
+    net_profit_yoy_growth REAL,
+    other_income REAL,
+    total_operating_revenue REAL,
+    operating_revenue_yoy_growth REAL,
+    operating_expense_cost_of_sales REAL,
+    operating_expense_selling_expenses REAL,
+    operating_expense_administrative_expenses REAL,
+    operating_expense_financial_expenses REAL,
+    operating_expense_rnd_expenses REAL,
+    operating_expense_taxes_and_surcharges REAL,
+    total_operating_expenses REAL,
+    operating_profit REAL,
+    total_profit REAL,
+    asset_impairment_loss REAL,
+    credit_impairment_loss REAL,
+    report_period TEXT NOT NULL,
+    report_year INTEGER NOT NULL,
+    UNIQUE(stock_code, report_year, report_period)
+);
+
+CREATE INDEX IF NOT EXISTS idx_core_company_period
+    ON core_performance(stock_code, report_year, report_period);
+CREATE INDEX IF NOT EXISTS idx_balance_company_period
+    ON balance_sheet(stock_code, report_year, report_period);
+CREATE INDEX IF NOT EXISTS idx_cash_company_period
+    ON cash_flow(stock_code, report_year, report_period);
+CREATE INDEX IF NOT EXISTS idx_income_company_period
+    ON income_statement(stock_code, report_year, report_period);
+
+CREATE VIEW IF NOT EXISTS core_performance_indicators_sheet AS
+SELECT * FROM core_performance;
+
+CREATE VIEW IF NOT EXISTS income_sheet AS
+SELECT * FROM income_statement;
+
+CREATE VIEW IF NOT EXISTS cash_flow_sheet AS
+SELECT * FROM cash_flow;
