import os
import re
import time
from PyPDF2 import PdfReader
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import REPORT_PATHS, PDF_KEYWORDS
from utils import extract_company_info, to_number

# OCR配置（保持不变）
TESSERACT_PATH = r"D:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"D:\poppler-25.12.0-0\poppler-25.12.0\Library\bin"

class PDFParser:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.company_info = extract_company_info(pdf_path)
        # 修复：从文件名提取年份时，兼容2022年报告（原文件是2022年报，2023年披露）
        if self.company_info["report_year"] == 2023 and "2022" in self.pdf_path:
            self.company_info["report_year"] = 2022
        self.text = self._read_pdf()

    def _read_pdf(self):
        """保持原有逻辑不变"""
        try:
            with open(self.pdf_path, "rb") as f:
                reader = PdfReader(f)
                text = ""
                max_pages = min(50, len(reader.pages))
                for page in reader.pages[:max_pages]:
                    start = time.time()
                    page_text = page.extract_text() or ""
                    if time.time() - start > 5:
                        break
                    text += page_text + "\n"
            
            if text.strip() and len(text) > 100:
                print(f"✅ 文本型PDF，常规提取成功：{os.path.basename(self.pdf_path)}")
                return text
            
            print(f"⚠️  检测到图片型PDF，启用OCR识别：{os.path.basename(self.pdf_path)}")
            return self._ocr_pdf()
            
        except Exception as e:
            print(f"❌ 读取PDF失败：{e}")
            return ""

    def _ocr_pdf(self):
        """保持原有逻辑不变"""
        try:
            import pytesseract
            from pdf2image import convert_from_path
            from PIL import Image
            
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
            images = convert_from_path(
                self.pdf_path,
                poppler_path=POPPLER_PATH,
                first_page=1,
                last_page=10,
                fmt="png",
                thread_count=2
            )
            
            ocr_text = ""
            for idx, img in enumerate(images):
                page_text = pytesseract.image_to_string(img, lang="chi_sim")
                ocr_text += f"\n==== 第{idx+1}页 ====\n" + page_text
            
            print(f"📝 OCR识别结果（前500字符）：\n{ocr_text[:500]}")
            return ocr_text
            
        except ImportError as e:
            print(f"❌ OCR依赖缺失：{e}")
            print("👉 请执行：pip install pytesseract pdf2image pillow")
            return ""
        except Exception as e:
            print(f"❌ OCR识别失败：{e}")
            return ""

    def _extract_section(self, keywords):
        """保持原有逻辑不变"""
        for kw in keywords:
            pattern = re.compile(
                f"{kw}[\\s\\S]{1,10000}?(?=\\n\\s*?[一二三四五六七八九十]{1,2}、|$|\\Z)",
                re.IGNORECASE | re.DOTALL
            )
            match = pattern.search(self.text)
            if match:
                return match.group()
        return ""

    def extract_core_performance(self):
        """修复：精准匹配PDF表格中的核心业绩指标"""
        section = self._extract_section(PDF_KEYWORDS["core_performance"])
        data = self.company_info.copy()
        # 适配PDF中的表格格式（如“营业收入 579,374,501.21”“归属于上市公司股东的净利润 33,459,505.16”）
        rules = {
            "total_revenue": [
                r"营业收入\s+([\d,\.]+)",  # 匹配“营业收入 579,374,501.21”
                r"营业总收入\s+([\d,\.]+)",
                r"营业收入[:：]\s*([\d,\.]+)"
            ],
            "net_profit": [
                r"归属于上市公司股东的净利润\s+([\d,\.]+)",  # 匹配PDF中的核心指标
                r"净利润\s+([\d,\.]+)",
                r"归属于母公司股东的净利润\s+([\d,\.]+)"
            ],
            "net_profit_deduct": [
                r"归属于上市公司股东的扣除非经常性损益的净利润\s+([\d,\.]+)",
                r"扣非净利润\s+([\d,\.]+)"
            ],
            "eps": [
                r"基本每股收益\s+([\d,\.]+)",  # 匹配“基本每股收益 0.0896”
                r"每股收益\s+([\d,\.]+)"
            ],
            "operating_cash_flow": [
                r"经营活动产生的现金流量净额\s+([\d,\.]+)",  # 匹配“经营活动产生的现金流量净额 52,578,993.55”
                r"经营现金流净额\s+([\d,\.]+)"
            ]
        }

        for k, patterns in rules.items():
            value = 0.0
            for pat in patterns:
                m = re.search(pat, section)
                if m:
                    value = to_number(m.group(1))
                    break
            data[k] = value
        return data

    def extract_balance_sheet(self):
        """修复：精准匹配资产负债表表格数据"""
        section = self._extract_section(PDF_KEYWORDS["balance_sheet"])
        data = self.company_info.copy()
        # 适配PDF中的“总资产 1,974,418,631.97”格式
        rules = {
            "total_assets": [
                r"总资产\s+([\d,\.]+)",  # 匹配PDF中的总资产数据
                r"资产总计\s+([\d,\.]+)",
                r"资产总计[:：]\s*([\d,\.]+)"
            ],
            "total_liabilities": [
                r"总负债\s+([\d,\.]+)",
                r"负债总计\s+([\d,\.]+)",
                r"负债总计[:：]\s*([\d,\.]+)"
            ],
            "total_equity": [
                r"归属于上市公司股东的净资产\s+([\d,\.]+)",  # 匹配PDF中的净资产数据
                r"所有者权益合计\s+([\d,\.]+)",
                r"股东权益合计\s+([\d,\.]+)"
            ],
            "monetary_funds": [
                r"货币资金\s+([\d,\.]+)",
                r"货币资金[:：]\s*([\d,\.]+)"
            ],
            "accounts_receivable": [
                r"应收账款\s+([\d,\.]+)",
                r"应收账款[:：]\s*([\d,\.]+)"
            ],
            "inventory": [
                r"存货\s+([\d,\.]+)",
                r"存货[:：]\s*([\d,\.]+)"
            ]
        }

        for k, patterns in rules.items():
            value = 0.0
            for pat in patterns:
                m = re.search(pat, section)
                if m:
                    value = to_number(m.group(1))
                    break
            data[k] = value
        return data

    def extract_income_statement(self):
        """修复：精准匹配利润表表格数据"""
        section = self._extract_section(PDF_KEYWORDS["income_statement"])
        data = self.company_info.copy()
        rules = {
            "operating_revenue": [
                r"营业收入\s+([\d,\.]+)",
                r"营业总收入\s+([\d,\.]+)"
            ],
            "operating_cost": [
                r"营业成本\s+([\d,\.]+)",  # 匹配PDF中的营业成本数据
                r"营业成本[:：]\s*([\d,\.]+)"
            ],
            "operating_profit": [
                r"营业利润\s+([\d,\.]+)",
                r"营业利润[:：]\s*([\d,\.]+)"
            ],
            "total_profit": [
                r"利润总额\s+([\d,\.]+)",
                r"利润总额[:：]\s*([\d,\.]+)"
            ],
            "net_profit_parent": [
                r"归属于上市公司股东的净利润\s+([\d,\.]+)",
                r"归母净利润\s+([\d,\.]+)"
            ]
        }

        for k, patterns in rules.items():
            value = 0.0
            for pat in patterns:
                m = re.search(pat, section)
                if m:
                    value = to_number(m.group(1))
                    break
            data[k] = value
        return data

    def extract_cash_flow(self):
        """修复：精准匹配现金流量表表格数据"""
        section = self._extract_section(PDF_KEYWORDS["cash_flow"])
        data = self.company_info.copy()
        rules = {
            "operating_cash_flow": [
                r"经营活动产生的现金流量净额\s+([\d,\.]+)",
                r"经营现金流\s+([\d,\.]+)"
            ],
            "investing_cash_flow": [
                r"投资活动产生的现金流量净额\s+([\d,\.]+)",
                r"投资现金流\s+([\d,\.]+)"
            ],
            "financing_cash_flow": [
                r"筹资活动产生的现金流量净额\s+([\d,\.]+)",
                r"筹资现金流\s+([\d,\.]+)"
            ],
            "net_cash_flow": [
                r"现金及现金等价物净增加额\s+([\d,\.]+)",
                r"现金净增加额\s+([\d,\.]+)"
            ]
        }

        for k, patterns in rules.items():
            value = 0.0
            for pat in patterns:
                m = re.search(pat, section)
                if m:
                    value = to_number(m.group(1))
                    break
            data[k] = value
        return data

    def parse_all(self):
        return {
            "core_performance": self.extract_core_performance(),
            "balance_sheet": self.extract_balance_sheet(),
            "income_statement": self.extract_income_statement(),
            "cash_flow": self.extract_cash_flow()
        }