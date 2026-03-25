from __future__ import annotations

import re
from typing import Any

from .kb_builder import load_knowledge_index


STOPWORDS = {
    "的",
    "了",
    "和",
    "是",
    "在",
    "与",
    "及",
    "对",
    "做",
    "什么",
    "如何",
    "哪些",
    "情况",
    "原因",
    "分析",
    "进行",
    "显示",
    "一下",
}

DOMAIN_HINTS = [
    "华润三九",
    "金花股份",
    "医保",
    "目录",
    "中药",
    "产品",
    "收入",
    "营收",
    "增长",
    "原因",
    "CHC",
    "新品",
    "渠道",
    "品牌",
    "融合",
    "并购",
    "天士力",
    "昆药",
]


def extract_keywords(text: str) -> list[str]:
    normalized = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]+", " ", text)
    candidates: list[str] = []
    for token in normalized.split():
        if token in STOPWORDS:
            continue
        if len(token) >= 2:
            candidates.append(token)
        if re.fullmatch(r"[\u4e00-\u9fa5]{5,}", token):
            for size in [2, 3, 4]:
                for index in range(0, len(token) - size + 1):
                    piece = token[index : index + size]
                    if piece not in STOPWORDS:
                        candidates.append(piece)
    for hint in DOMAIN_HINTS:
        if hint in text:
            candidates.append(hint)
    return list(dict.fromkeys(candidates))


def _score_document(query_keywords: list[str], document: dict[str, Any]) -> int:
    haystack = "\n".join(
        [
            document.get("title", ""),
            document.get("text", ""),
            str(document.get("metadata", {}).get("stockName", "")),
            str(document.get("metadata", {}).get("industryName", "")),
        ]
    )
    score = 0
    for keyword in query_keywords:
        if keyword in haystack:
            score += 6 if keyword in document.get("title", "") else 3
            score += haystack.count(keyword)
    if "图表" in document.get("text", ""):
        score += 1
    return score


def retrieve_context(
    query: str,
    top_k: int = 5,
    source_type: str | None = None,
) -> list[dict[str, Any]]:
    documents = load_knowledge_index()
    keywords = extract_keywords(query)
    scored = []
    for document in documents:
        if source_type and document.get("source_type") != source_type:
            continue
        score = _score_document(keywords, document)
        if score > 0:
            scored.append((score, document))
    scored.sort(key=lambda item: (-item[0], item[1]["title"], item[1]["page_number"], item[1]["chunk_index"]))
    return [document for _, document in scored[:top_k]]


def extract_medicare_products() -> list[dict[str, str]]:
    query = "2025 医保目录 新增 7个 中药产品 图表8"
    for document in retrieve_context(query, top_k=10, source_type="industry_report"):
        if "图表8：2025年国家医保目录新增7个中药产品" not in document["text"]:
            continue
        matches = re.findall(
            r"\n?\s*(\d)\s+([\u4e00-\u9fa5]+)\s+([\u4e00-\u9fa5A-Za-z0-9·]+)\s+.*?(中药[0-9.]+类)",
            document["text"],
            flags=re.S,
        )
        products = []
        seen = set()
        for sequence, company, product, category in matches:
            key = (company, product)
            if key in seen:
                continue
            seen.add(key)
            products.append(
                {
                    "sequence": sequence,
                    "company": company,
                    "product": product,
                    "category": category,
                    "paper_path": document["relative_path"],
                    "paper_image": "图表8：2025年国家医保目录新增7个中药产品",
                    "text": document["text"],
                }
            )
        if products:
            return products
    return []
