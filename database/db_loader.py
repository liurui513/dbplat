import os
import sqlite3
import logging
import time
from pdf_parser import PDFParser
from data_validator import FinancialDataValidator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("db_loader.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 数据库文件路径
DB_PATH = r"D:\Bigdata\dbplat\finance_database.db"

class DBLoader:
    def __init__(self, pdf_root_dir):
        self.pdf_root_dir = pdf_root_dir
        self.failed_files = []
        self.conn = None
        self._init_db()  # 初始化数据库

    def _init_db(self):
        """初始化数据库：创建表结构（若不存在）"""
        try:
            # 连接SQLite数据库（不存在则自动创建）
            self.conn = sqlite3.connect(DB_PATH)
            self.conn.execute("PRAGMA foreign_keys = ON")  # 开启外键约束
            cursor = self.conn.cursor()

            # 1. 创建核心业绩表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS core_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_code TEXT NOT NULL,
                company_name TEXT NOT NULL,
                report_year TEXT NOT NULL,
                total_revenue REAL DEFAULT 0.0,
                net_profit REAL DEFAULT 0.0,
                net_profit_deduct REAL DEFAULT 0.0,
                eps REAL DEFAULT 0.0,
                operating_cash_flow REAL DEFAULT 0.0,
                create_time TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_code, report_year)
            )
            """)

            # 2. 创建资产负债表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS balance_sheet (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_code TEXT NOT NULL,
                company_name TEXT NOT NULL,
                report_year TEXT NOT NULL,
                total_assets REAL DEFAULT 0.0,
                total_liabilities REAL DEFAULT 0.0,
                total_equity REAL DEFAULT 0.0,
                monetary_funds REAL DEFAULT 0.0,
                accounts_receivable REAL DEFAULT 0.0,
                inventory REAL DEFAULT 0.0,
                create_time TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_code, report_year)
            )
            """)

            # 3. 创建利润表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS income_statement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_code TEXT NOT NULL,
                company_name TEXT NOT NULL,
                report_year TEXT NOT NULL,
                operating_revenue REAL DEFAULT 0.0,
                operating_cost REAL DEFAULT 0.0,
                operating_profit REAL DEFAULT 0.0,
                total_profit REAL DEFAULT 0.0,
                net_profit_parent REAL DEFAULT 0.0,
                create_time TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_code, report_year)
            )
            """)

            # 4. 创建现金流量表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cash_flow (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_code TEXT NOT NULL,
                company_name TEXT NOT NULL,
                report_year TEXT NOT NULL,
                operating_cash_flow REAL DEFAULT 0.0,
                investing_cash_flow REAL DEFAULT 0.0,
                financing_cash_flow REAL DEFAULT 0.0,
                net_cash_flow REAL DEFAULT 0.0,
                create_time TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_code, report_year)
            )
            """)

            self.conn.commit()
            logger.info("✅ 数据库表创建/检查完成")

        except Exception as e:
            logger.error(f"数据库初始化失败：{str(e)}", exc_info=True)
            raise

    def _get_all_pdf_files(self):
        """递归获取所有PDF文件（包括子目录）"""
        pdf_files = []
        for root, dirs, files in os.walk(self.pdf_root_dir):
            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, file))
        return pdf_files

    def _insert_to_db(self, financial_data):
        """将校验后的财务数据入库（支持更新重复数据）"""
        try:
            cursor = self.conn.cursor()
            create_time = time.strftime("%Y-%m-%d %H:%M:%S")

            # 1. 核心业绩表（INSERT OR REPLACE 避免重复）
            core = financial_data["core_performance"]
            cursor.execute("""
            INSERT OR REPLACE INTO core_performance 
            (company_code, company_name, report_year, total_revenue, net_profit, 
             net_profit_deduct, eps, operating_cash_flow, create_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                core["company_code"], core["company_name"], core["report_year"],
                core["total_revenue"], core["net_profit"], core["net_profit_deduct"],
                core["eps"], core["operating_cash_flow"], create_time
            ))

            # 2. 资产负债表
            balance = financial_data["balance_sheet"]
            cursor.execute("""
            INSERT OR REPLACE INTO balance_sheet 
            (company_code, company_name, report_year, total_assets, total_liabilities, 
             total_equity, monetary_funds, accounts_receivable, inventory, create_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                balance["company_code"], balance["company_name"], balance["report_year"],
                balance["total_assets"], balance["total_liabilities"], balance["total_equity"],
                balance["monetary_funds"], balance["accounts_receivable"], balance["inventory"],
                create_time
            ))

            # 3. 利润表
            income = financial_data["income_statement"]
            cursor.execute("""
            INSERT OR REPLACE INTO income_statement 
            (company_code, company_name, report_year, operating_revenue, operating_cost, 
             operating_profit, total_profit, net_profit_parent, create_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                income["company_code"], income["company_name"], income["report_year"],
                income["operating_revenue"], income["operating_cost"], income["operating_profit"],
                income["total_profit"], income["net_profit_parent"], create_time
            ))

            # 4. 现金流量表
            cash = financial_data["cash_flow"]
            cursor.execute("""
            INSERT OR REPLACE INTO cash_flow 
            (company_code, company_name, report_year, operating_cash_flow, investing_cash_flow, 
             financing_cash_flow, net_cash_flow, create_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cash["company_code"], cash["company_name"], cash["report_year"],
                cash["operating_cash_flow"], cash["investing_cash_flow"], cash["financing_cash_flow"],
                cash["net_cash_flow"], create_time
            ))

            self.conn.commit()
            logger.info("数据成功入库")

        except Exception as e:
            self.conn.rollback()
            logger.error(f"数据入库失败：{str(e)}", exc_info=True)
            raise

    def load_single_pdf(self, pdf_path):
        """处理单个PDF文件：解析→校验→入库"""
        try:
            # 1. 解析PDF
            parser = PDFParser(pdf_path)
            financial_data = parser.extract_financial_data()
            if not financial_data:
                logger.warning(f"PDF解析无数据：{pdf_path}")
                return False

            # 2. 数据校验
            validator = FinancialDataValidator()
            if not validator.validate_all(financial_data):
                logger.warning(f"数据校验失败：{pdf_path}")
                return False

            # 3. 数据入库
            self._insert_to_db(financial_data)
            return True

        except Exception as e:
            logger.error(f"处理单个PDF失败：{pdf_path}，错误={str(e)}", exc_info=True)
            return False

    def load_all(self):
        """批量处理所有PDF文件"""
        # 获取所有PDF文件
        pdf_files = self._get_all_pdf_files()
        total = len(pdf_files)
        logger.info(f"📁 共发现 {total} 个PDF文件")
        logger.info("="*50)

        # 逐个处理
        for idx, pdf_path in enumerate(pdf_files, 1):
            logger.info(f"[{idx}/{total}] 正在处理：{pdf_path}")
            try:
                success = self.load_single_pdf(pdf_path)
                if success:
                    logger.info(f"✅ 处理完成：{pdf_path} | 成功入库4张表")
                else:
                    self.failed_files.append(pdf_path)
                    logger.warning(f"❌ 处理失败：{pdf_path} | 未入库")
            except Exception as e:
                self.failed_files.append(pdf_path)
                logger.error(f"❌ 处理异常：{pdf_path}，错误={str(e)}", exc_info=True)
                continue

        # 处理完成汇总
        logger.info("="*50)
        logger.info(f"📊 处理汇总：成功 {total - len(self.failed_files)} 个 | 失败 {len(self.failed_files)} 个")
        if self.failed_files:
            logger.warning(f"❌ 失败文件列表：{self.failed_files}")

        # 关闭数据库连接
        if self.conn:
            self.conn.close()

if __name__ == "__main__":
    # 配置PDF根目录（包含上交所/深交所子目录）
    PDF_ROOT_DIR = r"D:\Bigdata\dbplat\data\data\附件2：财务报告"
    
    # 初始化并执行批量加载
    loader = DBLoader(PDF_ROOT_DIR)
    loader.load_all()