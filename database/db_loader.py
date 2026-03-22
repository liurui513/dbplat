import sqlite3
import pymysql
import sys
import os
import time

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import DB_CONFIG, FIELD_MAPPING, REPORT_PATHS
from pdf_parser import PDFParser
from data_validator import DataValidator
from utils import get_all_pdf_files

class DBLoader:
    def __init__(self):
        self.conn = self._connect()
        self.cursor = self.conn.cursor()
        # 关键修复：初始化时强制建表（确保表存在）
        self._create_tables()

    def _connect(self):
        """连接数据库，兼容SQLite/MariaDB"""
        if DB_CONFIG["type"] == "sqlite":
            # SQLite兼容配置：关闭同步、开启外键
            conn = sqlite3.connect(DB_CONFIG["path"])
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA synchronous = OFF")
            return conn
        elif DB_CONFIG["type"] == "mysql":
            return pymysql.connect(
                host=DB_CONFIG["mysql"]["host"],
                port=DB_CONFIG["mysql"]["port"],
                user=DB_CONFIG["mysql"]["user"],
                password=DB_CONFIG["mysql"]["password"],
                database=DB_CONFIG["mysql"]["database"],
                charset="utf8mb4"
            )
        raise ValueError("不支持的数据库类型：仅支持sqlite/mysql")

    def _create_tables(self):
        """强制创建四张核心表（兼容SQLite）"""
        # 核心业绩表（修复SQLite的TIMESTAMP兼容问题）
        self.cursor.execute("""
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
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 资产负债表
        self.cursor.execute("""
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
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 利润表
        self.cursor.execute("""
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
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 现金流量表
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS cash_flow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_code VARCHAR(20) NOT NULL,
            company_name VARCHAR(100),
            report_year INT,
            operating_cash_flow DECIMAL(20,2),
            investing_cash_flow DECIMAL(20,2),
            financing_cash_flow DECIMAL(20,2),
            net_cash_flow DECIMAL(20,2),
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        self.conn.commit()
        print("✅ 数据库表创建/检查完成")

    def insert(self, table, data):
        """插入单表数据（添加异常重试）"""
        if table not in FIELD_MAPPING:
            print(f"❌ 无效表名：{table}")
            return False
        
        fields = FIELD_MAPPING[table]
        # 兼容SQLite/MySQL占位符
        placeholders = ", ".join(["?"] * len(fields)) if DB_CONFIG["type"] == "sqlite" else ", ".join(["%s"] * len(fields))
        sql = f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders})"
        values = [data.get(f, 0) for f in fields]
        
        # 重试机制（防止临时锁表）
        for retry in range(3):
            try:
                self.cursor.execute(sql, values)
                self.conn.commit()
                return True
            except Exception as e:
                self.conn.rollback()
                if retry == 2:  # 最后一次重试失败
                    print(f"❌ 插入{table}失败：{e}")
                    return False
                time.sleep(0.1)

    def load_single_pdf(self, pdf_path):
        """处理单个PDF（添加超时/异常捕获）"""
        try:
            # 超时保护：解析超过10秒则跳过
            start_time = time.time()
            parser = PDFParser(pdf_path)
            if time.time() - start_time > 10:
                print(f"⚠️  PDF解析超时：{pdf_path}")
                return 0
            
            data = parser.parse_all()
            validator = DataValidator(data)
            validate_result = validator.validate()
            
            if not validate_result["pass"]:
                print(f"⚠️  校验不通过：{pdf_path} | 错误：{validate_result['errors']}")
            
            # 插入数据
            success = 0
            for table in FIELD_MAPPING:
                if self.insert(table, data[table]):
                    success += 1
            
            print(f"✅ 处理完成：{pdf_path} | 成功入库{success}张表")
            return success
        
        except Exception as e:
            print(f"❌ 处理失败：{pdf_path} | 错误：{str(e)[:100]}")
            return 0

    def load_all(self):
        """批量处理所有PDF"""
        pdfs = get_all_pdf_files(REPORT_PATHS)
        print(f"\n📁 共发现 {len(pdfs)} 个PDF文件")
        print("="*50)
        
        total_success = 0
        total_files = len(pdfs)
        
        for idx, pdf in enumerate(pdfs, 1):
            print(f"\n[{idx}/{total_files}] 正在处理：{pdf}")
            success = self.load_single_pdf(pdf)
            total_success += 1 if success > 0 else 0
        
        # 关闭连接
        self.conn.close()
        
        # 输出汇总
        print("\n" + "="*50)
        print(f"📊 处理汇总：成功{total_success}个 | 失败{total_files-total_success}个")

if __name__ == "__main__":
    # 初始化并运行
    loader = DBLoader()
    loader.load_all()