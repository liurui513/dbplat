from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable, List


def canonical_report_name(name: str) -> str:
    normalized = re.sub(r"\(\d+\)", "", name).strip()
    return normalized.replace("摘要", "")


def report_priority(path: Path) -> tuple[int, int, str]:
    name = path.name
    duplicate_penalty = 1 if re.search(r"\(\d+\)", name) else 0
    summary_penalty = 1 if "摘要" in name else 0
    return summary_penalty, duplicate_penalty, str(path)


def get_all_pdf_files(path_list: Iterable[Path]) -> List[Path]:
    deduped = {}
    for root in path_list:
        root_path = Path(root)
        if not root_path.exists():
            continue
        for pdf_path in root_path.rglob("*.pdf"):
            key = (str(pdf_path.parent), canonical_report_name(pdf_path.name))
            existing = deduped.get(key)
            if existing is None or report_priority(pdf_path) < report_priority(existing):
                deduped[key] = pdf_path
    return sorted(deduped.values(), key=report_priority)


def file_hash(file_path: Path) -> str:
    digest = hashlib.md5()
    with Path(file_path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]
