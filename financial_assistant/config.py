from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data" / "data"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROCESSED_DIR / "output"
RESULT_DIR = OUTPUT_DIR / "result"
RESULT_IMG_DIR = RESULT_DIR
KNOWLEDGE_CACHE_DIR = PROCESSED_DIR / "knowledge"
LOG_DIR = PROJECT_ROOT / "logs"
DB_PATH = PROJECT_ROOT / "finance_database.db"

for path in [PROCESSED_DIR, OUTPUT_DIR, RESULT_DIR, KNOWLEDGE_CACHE_DIR, LOG_DIR]:
    path.mkdir(parents=True, exist_ok=True)


def _first_match(pattern: str) -> Path:
    matches = sorted(DATA_ROOT.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"未找到匹配文件: {pattern}")
    return matches[0]


ATTACHMENT_4_PATH = _first_match("附件4：问题汇总*.xlsx")
ATTACHMENT_6_PATH = _first_match("附件6：问题汇总*.xlsx")
ATTACHMENT_5_ROOT = _first_match("附件5*")
STOCK_RESEARCH_DIR = ATTACHMENT_5_ROOT / "个股研报"
INDUSTRY_RESEARCH_DIR = ATTACHMENT_5_ROOT / "行业研报"
STOCK_RESEARCH_INFO_PATH = sorted(STOCK_RESEARCH_DIR.parent.glob("个股_研报信息*.xlsx"))[0]
INDUSTRY_RESEARCH_INFO_PATH = sorted(INDUSTRY_RESEARCH_DIR.parent.glob("行业_研报信息*.xlsx"))[0]
RESULT_2_PATH = OUTPUT_DIR / "result_2.xlsx"
RESULT_3_PATH = OUTPUT_DIR / "result_3.xlsx"
KNOWLEDGE_INDEX_PATH = KNOWLEDGE_CACHE_DIR / "knowledge_index.json"


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
USE_REMOTE_LLM = bool(OPENAI_API_KEY)
