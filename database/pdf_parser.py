import pdfplumber
import re
import logging
from typing import Dict, List
import pandas as pd

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 预定义公司代码映射（解决华润三九代码缺失问题）
COMPANY_CODE_MAP = {
    "金花股份": "600080",
    "华润三九": "000999"
}

# 财务指标关键词映射（覆盖赛题要求的核心字段）
INDICATOR_MAP = {
    "营业收入": "total_revenue",
    "营业总收入": "total_revenue",
    "净利润": "net_profit",
    "归属于母公司股东的净利润": "net_profit",
    "扣除非经常性损益的净利润": "net_profit_deduct",
    "基本每股收益": "eps",
    "资产总计": "total_assets",
    "负债总计": "total_liabilities",
    "经营活动产生的现金流量净额": "operating_cash_flow",
    "营业利润": "operating_profit",
    "利润总额": "total_profit"
}

class FinancialReportParser:
    """适配赛题的财报解析器（提取表格数据）"""
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.pdf = pdfplumber.open(pdf_path)
        self.company_info = self._parse_company_info()
        self.report_data = {}

    def _parse_company_info(self) -> Dict[str, str]:
        """解析公司信息（名称+代码+年份）"""
        info = {"company_code": "", "company_name": "", "report_year": ""}
        filename = self.pdf_path.split("\\")[-1]
        
        # 1. 匹配公司名称
        for name in COMPANY_CODE_MAP.keys():
            if name in filename:
                info["company_name"] = name
                info["company_code"] = COMPANY_CODE_MAP[name]
                break
        
        # 2. 匹配年份（2022-2025）
        year_match = re.search(r"(202[2-5])", filename)
        if not year_match:
            # 从PDF文本兜底匹配
            first_page_text = self.pdf.pages[0].extract_text()
            year_match = re.search(r"(202[2-5])年", first_page_text)
        if year_match:
            info["report_year"] = year_match.group(1)
        
        return info

    def _clean_numeric(self, value: str) -> float:
        """清洗数值（处理万/亿/逗号/空格）"""
        if pd.isna(value) or value == "" or value == "-":
            return 0.0
        
        # 去除非数字字符（保留小数点、万、亿）
        clean_val = re.sub(r"[^\d\.万亿]", "", str(value).strip())
        multiplier = 1.0
        
        # 处理单位
        if "亿" in clean_val:
            multiplier = 1e8
            clean_val = clean_val.replace("亿", "")
        elif "万" in clean_val:
            multiplier = 1e4
            clean_val = clean_val.replace("万", "")
        
        # 转换为数值
        try:
            return float(clean_val.replace(",", "")) * multiplier
        except:
            return 0.0

    def _extract_table_data(self) -> Dict[str, float]:
        """提取所有表格中的财务指标"""
        indicator_values = {}
        
        # 遍历前30页（财报核心数据在前30页）
        for page_num in range(min(30, len(self.pdf.pages))):
            page = self.pdf.pages[page_num]
            tables = page.extract_tables()
            
            for table in tables:
                # 转换为DataFrame便于处理
                df = pd.DataFrame(table)
                # 遍历表格行，匹配指标
                for _, row in df.iterrows():
                    if len(row) < 2:
                        continue
                    # 第一列是指标名，第二列是数值
                    indicator_name = str(row[0]).strip()
                    indicator_value = str(row[1]).strip()
                    
                    # 匹配目标指标
                    for key, field in INDICATOR_MAP.items():
                        if key in indicator_name and field not in indicator_values:
                            clean_val = self._clean_numeric(indicator_value)
                            indicator_values[field] = clean_val
                            logger.info(f"解析到[{self.company_info['company_name']}] {key} = {clean_val}")
        
        return indicator_values

    def parse_all_reports(self) -> Dict[str, Dict]:
        """解析四大报表（适配赛题字段要求）"""
        table_data = self._extract_table_data()
        
        # 核心业绩表
        self.report_data["core_performance"] = {
            **self.company_info,
            "total_revenue": table_data.get("total_revenue", 0.0),
            "net_profit": table_data.get("net_profit", 0.0),
            "net_profit_deduct": table_data.get("net_profit_deduct", 0.0),
            "eps": table_data.get("eps", 0.0),
            "operating_cash_flow": table_data.get("operating_cash_flow", 0.0)
        }
        
        # 资产负债表
        self.report_data["balance_sheet"] = {
            **self.company_info,
            "total_assets": table_data.get("total_assets", 0.0),
            "total_liabilities": table_data.get("total_liabilities", 0.0)
        }
        
        # 利润表
        self.report_data["income_statement"] = {
            **self.company_info,
            "operating_profit": table_data.get("operating_profit", 0.0),
            "total_profit": table_data.get("total_profit", 0.0),
            "net_profit": table_data.get("net_profit", 0.0)
        }
        
        # 现金流量表
        self.report_data["cash_flow"] = {
            **self.company_info,
            "operating_cash_flow": table_data.get("operating_cash_flow", 0.0),
            "invest_cash_flow": table_data.get("invest_cash_flow", 0.0),
            "finance_cash_flow": table_data.get("finance_cash_flow", 0.0)
        }
        
        self.pdf.close()
        return self.report_data

def parse_pdf_report(pdf_path: str) -> Dict[str, Dict]:
    """便捷调用函数"""
    try:
        parser = FinancialReportParser(pdf_path)
        return parser.parse_all_reports()
    except Exception as e:
        logger.error(f"解析{pdf_path}失败：{e}")
        return {}

if __name__ == "__main__":
    # 测试单个PDF
    test_pdf = "D:/Bigdata/dbplat/data/data/附件2：财务报告/reports-深交所/华润三九：2022年年度报告.pdf"
    data = parse_pdf_report(test_pdf)
    logger.info(f"测试解析结果：{data}")