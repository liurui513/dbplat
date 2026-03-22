import sqlite3
import logging

DB_PATH = "D:/Bigdata/dbplat/finance_database.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def query_financial_data():
    """查询财务数据库数据"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 支持按列名访问

    try:
        # 1. 查询所有表
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        logger.info("📋 数据库中的表：")
        for table in tables:
            if table != "sqlite_sequence":
                logger.info(f"- {table}")

        # 2. 查询核心业绩表前10条
        logger.info("\n💰 核心业绩表（前10条）：")
        core_cursor = conn.execute("SELECT * FROM core_performance LIMIT 10;")
        # 打印列名
        columns = [desc[0] for desc in core_cursor.description]
        logger.info(f"列名：{' '.join(columns)}")
        # 打印数据
        for row in core_cursor.fetchall():
            row_data = [str(row[col]) for col in columns]
            logger.info(' '.join(row_data))

        # 3. 查询资产负债表前10条
        logger.info("\n📊 资产负债表（前10条）：")
        balance_cursor = conn.execute("SELECT company_code, company_name, total_assets, total_liabilities FROM balance_sheet LIMIT 10;")
        columns = [desc[0] for desc in balance_cursor.description]
        logger.info(f"列名：{' '.join(columns)}")
        for row in balance_cursor.fetchall():
            row_data = [str(row[col]) for col in columns]
            logger.info(' '.join(row_data))

    except Exception as e:
        logger.error(f"查询失败：{str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    query_financial_data()