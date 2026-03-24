import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.utils import get_all_pdf_files


def test_get_all_pdf_files_prefers_full_report_and_non_duplicate() -> None:
    report_root = Path("virtual_reports")
    duplicate = report_root / "600080_20230428_MMWM(1).pdf"
    primary = report_root / "600080_20230428_MMWM.pdf"
    full_report = report_root / "\u534e\u6da6\u4e09\u4e5d\uff1a2024\u5e74\u534a\u5e74\u5ea6\u62a5\u544a.pdf"
    summary_report = report_root / "\u534e\u6da6\u4e09\u4e5d\uff1a2024\u5e74\u534a\u5e74\u5ea6\u62a5\u544a\u6458\u8981.pdf"
    fake_files = [duplicate, primary, full_report, summary_report]

    with patch.object(Path, "exists", lambda self: self == report_root), patch.object(
        Path,
        "rglob",
        lambda self, pattern: iter(fake_files) if self == report_root and pattern == "*.pdf" else iter(()),
    ):
        selected = {path.name for path in get_all_pdf_files([report_root])}

    assert primary.name in selected
    assert duplicate.name not in selected
    assert full_report.name in selected
    assert summary_report.name not in selected
