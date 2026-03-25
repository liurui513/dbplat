from __future__ import annotations

from pathlib import Path
from typing import Any

from financial_assistant.config import OUTPUT_DIR, PROJECT_ROOT


def _resolve_relative_output(path_text: str) -> Path:
    relative_path = path_text.replace("./", "")
    if relative_path.startswith("result/"):
        return OUTPUT_DIR / relative_path
    return PROJECT_ROOT / relative_path


def validate_answer_payload(answer: dict[str, Any], require_references: bool = False) -> tuple[bool, list[str]]:
    issues: list[str] = []
    content = str(answer.get("content", "")).strip()
    if not content:
        issues.append("content 为空")

    for image in answer.get("image", []) or []:
        if not _resolve_relative_output(image).exists():
            issues.append(f"图表不存在: {image}")

    references = answer.get("references", []) or []
    if require_references and not references:
        issues.append("references 为空")

    for reference in references:
        if not str(reference.get("paper_path", "")).strip():
            issues.append("reference 缺少 paper_path")
        if not str(reference.get("text", "")).strip():
            issues.append("reference 缺少 text")

    return not issues, issues
