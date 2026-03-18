import pymysql
from config import DB_CONFIG
from database.pdf_parser import parse_pdf_file  # 假设你写了解析函数
from database.data_validator import validate_data # 假设你写了校验函数

def init_db():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    with open('database/schema.sql', 'r', encoding='utf-8') as f:
        sql_script = f.read()
    cursor.execute(sql_script)
    conn.commit()
    conn.close()
    print("✅ 数据库初始化完成")

def process_and_load(pdf_path):
    print(f" 处理文件: {pdf_path}")
    # 1. 解析
    data_dict = parse_pdf_file(pdf_path) 
    # 2. 校验
    if not validate_data(data_dict):
        print("⚠️ 数据校验未通过，跳过入库")
        return
    
    # 3. 入库 (以核心指标表为例)
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    try:
        sql = """INSERT INTO core_performance_indicators_sheet 
                 (stock_code, stock_abbr, report_period, total_revenue, total_profit, net_profit) 
                 VALUES (%s, %s, %s, %s, %s, %s)
                 ON DUPLICATE KEY UPDATE total_revenue=VALUES(total_revenue)"""
        cursor.execute(sql, (
            data_dict['stock_code'], data_dict['stock_abbr'], data_dict['period'],
            data_dict['revenue'], data_dict['profit'], data_dict['net_profit']
        ))
        conn.commit()
        print("✅ 入库成功")
    except Exception as e:
        print(f"❌ 入库失败: {e}")
        conn.rollback()
    finally:
        conn.close()