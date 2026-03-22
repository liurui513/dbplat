import os
import re
import hashlib

def get_all_pdf_files(path_list):
    """遍历目录，返回所有PDF文件路径"""
    pdf_files = []
    for path in path_list:
        if not os.path.exists(path):
            print(f"目录不存在: {path}")
            continue
        for root, _, files in os.walk(path):
            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, file))
    return pdf_files

def extract_company_info(file_path):
    """从文件名提取公司代码、年份、名称"""
    filename = os.path.basename(file_path)
    code_match = re.search(r"(\d{6})", filename)
    year_match = re.search(r"(\d{4})", filename)
    
    company_code = code_match.group(1) if code_match else ""
    report_year = int(year_match.group(1)) if year_match else 0
    
    # 可扩展的公司名称映射
    name_map = {
        "000999": "华润三九",
        "600080": "金花股份"
    }
    company_name = name_map.get(company_code, "未知公司")
    
    return {
        "company_code": company_code,
        "company_name": company_name,
        "report_year": report_year
    }

def to_number(value):
    """将带千分位/单位的字符串转为浮点数"""
    if not value:
        return 0.0
    num_str = re.sub(r"[^\d\.]", "", str(value))
    try:
        return float(num_str)
    except ValueError:
        return 0.0

def file_hash(file_path):
    """生成文件MD5哈希，用于去重"""
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:16]