import sqlite3
import os
import glob
import logging
from datetime import datetime
from typing import Dict  # 关键：补充导入 Dict
from pdf_parser import parse_pdf_report
from data_validator import validate_financial_data

# 配置
DB_PATH = "D:/Bigdata/dbplat/finance_database.db"
PDF_ROOT_PATH = "D:/Bigdata/dbplat/data/data/附件2：财务报告"
SCHEMA_PATH = "D:/Bigdata/dbplat/database/schema.sql"

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class FinancialDBLoader:
    """财务数据入库加载器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._init_database()

    def _init_database(self):
        """初始化数据库（创建表）"""
        # 删除旧数据库（可选）
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            logger.info(f"已删除旧数据库：{self.db_path}")

        # 连接数据库并执行schema
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")  # 开启外键约束
        try:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            self.conn.executescript(schema_sql)
            self.conn.commit()
            logger.info("✅ 数据库表创建/检查完成")
        except Exception as e:
            logger.error(f"数据库初始化失败：{str(e)}")
            raise

    def _insert_report_data(self, report_type: str, data: Dict):
        """插入单张报表数据"""
        # 定义各表的插入SQL
        insert_sqls = {
            "core_performance": """
                INSERT INTO core_performance 
                (company_code, company_name, report_year, total_revenue, net_profit, 
                 net_profit_deduct, eps, operating_cash_flow)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            "balance_sheet": """
                INSERT INTO balance_sheet 
                (company_code, company_name, report_year, total_assets, total_liabilities)
                VALUES (?, ?, ?, ?, ?)
            """,
            "income_statement": """
                INSERT INTO income_statement 
                (company_code, company_name, report_year, operating_profit, total_profit, net_profit)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
            "cash_flow": """
                INSERT INTO cash_flow 
                (company_code, company_name, report_year, operating_cash_flow, invest_cash_flow, finance_cash_flow)
                VALUES (?, ?, ?, ?, ?, ?)
            """
        }

        sql = insert_sqls.get(report_type)
        if not sql:
            logger.warning(f"未知报表类型：{report_type}")
            return

        # 提取参数
        params = []
        if report_type == "core_performance":
            params = [
                data.get("company_code"), data.get("company_name"), data.get("report_year"),
                data.get("total_revenue"), data.get("net_profit"),
                data.get("net_profit_deduct"), data.get("eps"), data.get("operating_cash_flow")
            ]
        elif report_type == "balance_sheet":
            params = [
                data.get("company_code"), data.get("company_name"), data.get("report_year"),
                data.get("total_assets"), data.get("total_liabilities")
            ]
        elif report_type == "income_statement":
            params = [
                data.get("company_code"), data.get("company_name"), data.get("report_year"),
                data.get("operating_profit"), data.get("total_profit"), data.get("net_profit")
            ]
        elif report_type == "cash_flow":
            params = [
                data.get("company_code"), data.get("company_name"), data.get("report_year"),
                data.get("operating_cash_flow"), data.get("invest_cash_flow"), data.get("finance_cash_flow")
            ]

        # 执行插入
        try:
            self.conn.execute(sql, params)
            logger.debug(f"[{report_type}] 数据插入成功")
        except Exception as e:
            logger.error(f"[{report_type}] 数据插入失败：{str(e)}")
            raise

    # 找到process_pdf_file函数，修改以下部分：
def process_pdf_file(self, pdf_path: str) -> bool:
    try:
        logger.info(f"正在解析：{os.path.basename(pdf_path)}")
        # 1. 解析PDF
        report_data = parse_pdf_report(pdf_path)
        if not report_data:
            logger.error(f"PDF解析无数据：{pdf_path}")
            return False

        # 2. 数据校验（仅警告，不阻断）
        is_valid, errors = validate_financial_data(report_data)
        
        # 3. 核心逻辑：只要有有效数值就入库（即使有警告）
        has_valid_data = False
        for table_data in report_data.values():
            # 检查是否有非0的核心数值
            core_fields = ["total_revenue", "total_assets", "net_profit"]
            if any(table_data.get(field, 0.0) > 0 for field in core_fields):
                has_valid_data = True
                break
        
        if not has_valid_data:
            logger.warning(f"{pdf_path} 无有效财务数据，跳过入库")
            return False
        
        # 4. 插入数据库
        for report_type, data in report_data.items():
            self._insert_report_data(report_type, data)

        self.conn.commit()
        logger.info(f"✅ 处理完成：{pdf_path} | 校验警告：{errors}")
        return True
    except Exception as e:
        self.conn.rollback()
        logger.error(f"处理PDF失败：{pdf_path} | 错误：{e}")
        return False

    
def main():
    """主流程"""
    try:
        # 初始化加载器
        loader = FinancialDBLoader(DB_PATH)
        # 批量处理PDF
        loader.batch_process_pdfs(PDF_ROOT_PATH)
    except Exception as e:
        logger.error(f"程序执行失败：{str(e)}")
        raise
    finally:
        loader.close()

if __name__ == "__main__":
    main()