import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.pdf_parser import choose_growth_value, detect_report_period


def test_detect_report_period_prefers_filename_over_fallback_text() -> None:
    filename = "\u534e\u6da6\u4e09\u4e5d\uff1a2023\u5e74\u5e74\u5ea6\u62a5\u544a\u6458\u8981.pdf"
    first_page_text = "\u534e\u6da6\u4e09\u4e5d 2023 \u5e74\u5e74\u5ea6\u62a5\u544a\u6458\u8981"
    fallback_text = "\u524d\u6b21\u534a\u5e74\u5ea6\u62a5\u544a\u76f8\u5173\u6570\u636e"

    assert detect_report_period(filename, first_page_text, fallback_text) == "FY"


def test_detect_report_period_uses_first_page_for_sse_style_filename() -> None:
    filename = "600080_20230428_MMWM.pdf"
    first_page_text = "\u91d1\u82b1\u80a1\u4efd 2022 \u5e74\u5e74\u5ea6\u62a5\u544a"

    assert detect_report_period(filename, first_page_text) == "FY"


def test_choose_growth_value_uses_fallback_for_spurious_amounts() -> None:
    assert choose_growth_value(15544401735.35, 36.83) == 36.83


def test_choose_growth_value_keeps_large_but_valid_percentages() -> None:
    assert choose_growth_value(411.92, 12.5) == 411.92
