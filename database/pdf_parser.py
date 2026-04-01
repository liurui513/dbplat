from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import pdfplumber

try:
    from .config import FIELD_PRECISION, PERIOD_KEYWORDS, load_company_master
    from .ocr_backend import OCRPageResult, get_ocr_backend, get_ocr_settings
except ImportError:  # pragma: no cover
    from database.config import FIELD_PRECISION, PERIOD_KEYWORDS, load_company_master
    from database.ocr_backend import OCRPageResult, get_ocr_backend, get_ocr_settings


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CORE_TEXT_ALIASES = {
    "total_operating_revenue_raw": ["营业总收入", "营业收入"],
    "net_profit_raw": ["归属于上市公司股东的净利润"],
    "net_profit_excl_non_recurring_raw": [
        "归属于上市公司股东的扣除非经常性损益的净利润",
        "扣除非经常性损益后的净利润",
    ],
    "operating_cash_flow_raw": ["经营活动产生的现金流量净额"],
    "asset_total_assets_raw": ["总资产"],
    "net_assets_raw": ["归属于上市公司股东的净资产", "归属于上市公司股东的所有者权益"],
    "eps": ["基本每股收益（元／股）", "基本每股收益(元/股)", "基本每股收益"],
    "roe": ["加权平均净资产收益率（%）", "加权平均净资产收益率(%)"],
    "roe_weighted_excl_non_recurring": [
        "扣除非经常性损益后的加权平均净资产收益率（%）",
        "扣除非经常性损益后的加权平均净资产收益率(%)",
    ],
}

STATEMENT_ALIASES = {
    "balance_sheet": {
        "asset_cash_and_cash_equivalents": ["货币资金"],
        "asset_accounts_receivable": ["应收账款"],
        "asset_inventory": ["存货"],
        "asset_trading_financial_assets": ["交易性金融资产"],
        "asset_construction_in_progress": ["在建工程"],
        "asset_total_assets": ["资产总计", "总资产"],
        "liability_accounts_payable": ["应付账款"],
        "liability_advance_from_customers": ["预收款项"],
        "liability_total_liabilities": ["负债合计", "总负债"],
        "liability_contract_liabilities": ["合同负债"],
        "liability_short_term_loans": ["短期借款"],
        "equity_unappropriated_profit": ["未分配利润"],
        "equity_total_equity": ["所有者权益合计", "股东权益合计", "归属于母公司所有者权益合计"],
        "_share_capital": ["实收资本", "股本"],
    },
    "income_statement": {
        "total_operating_revenue": ["营业总收入", "营业收入"],
        "operating_expense_cost_of_sales": ["营业成本"],
        "operating_expense_selling_expenses": ["销售费用"],
        "operating_expense_administrative_expenses": ["管理费用"],
        "operating_expense_financial_expenses": ["财务费用"],
        "operating_expense_rnd_expenses": ["研发费用"],
        "operating_expense_taxes_and_surcharges": ["税金及附加"],
        "total_operating_expenses": ["营业总成本"],
        "operating_profit": ["营业利润"],
        "total_profit": ["利润总额"],
        "net_profit": ["净利润"],
        "other_income": ["其他收益"],
        "asset_impairment_loss": ["资产减值损失"],
        "credit_impairment_loss": ["信用减值损失"],
    },
    "cash_flow": {
        "net_cash_flow": ["现金及现金等价物净增加额", "净现金流"],
        "operating_cf_net_amount": ["经营活动产生的现金流量净额"],
        "operating_cf_cash_from_sales": ["销售商品、提供劳务收到的现金"],
        "investing_cf_net_amount": ["投资活动产生的现金流量净额"],
        "investing_cf_cash_for_investments": ["投资支付的现金"],
        "investing_cf_cash_from_investment_recovery": ["收回投资收到的现金"],
        "financing_cf_cash_from_borrowing": ["取得借款收到的现金"],
        "financing_cf_cash_for_debt_repayment": ["偿还债务支付的现金"],
        "financing_cf_net_amount": ["筹资活动产生的现金流量净额"],
    },
}

STATEMENT_START_MARKERS = {
    "balance_sheet": "合并资产负债表",
    "income_statement": "合并利润表",
    "cash_flow": "合并现金流量表",
}

STATEMENT_END_MARKERS = {
    "balance_sheet": "母公司资产负债表",
    "income_statement": "母公司利润表",
    "cash_flow": "母公司现金流量表",
}

NUMERIC_TOKEN_PATTERN = re.compile(
    r"(?:-?\d[\d,]*(?:\.\d+)?|不适用|增加-?\d+(?:\.\d+)?个?百分点|减少-?\d+(?:\.\d+)?个?百分点)"
)
NOTE_PATTERN = re.compile(r"^(?:[一二三四五六七八九十\d]+、\d+|\d+|十七、\d+|[一二三四五六七八九十]+、\d+)$")


def normalize_label(label: str) -> str:
    text = (label or "").replace("\n", "").replace(" ", "")
    text = text.replace("（", "(").replace("）", ")").replace("／", "/")
    text = re.sub(r"^[（(][一二三四五六七八九十]+[）)]", "", text)
    text = re.sub(r"^[一二三四五六七八九十]+、", "", text)
    text = re.sub(r"^(?:其中|加|减)[:：]", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[“”\"'：:·\-\u2014]", "", text)
    return text


def build_alias_index() -> Dict[str, Dict[str, str]]:
    alias_index: Dict[str, Dict[str, str]] = {}
    for section, field_aliases in STATEMENT_ALIASES.items():
        alias_index[section] = {}
        for field_name, aliases in field_aliases.items():
            for alias in aliases:
                alias_index[section][normalize_label(alias)] = field_name
    return alias_index


STATEMENT_ALIAS_INDEX = build_alias_index()
CORE_ALIAS_INDEX = {
    normalize_label(alias): field_name
    for field_name, aliases in CORE_TEXT_ALIASES.items()
    for alias in aliases
}
ALL_KNOWN_LABELS = set(CORE_ALIAS_INDEX) | {
    alias
    for section_aliases in STATEMENT_ALIAS_INDEX.values()
    for alias in section_aliases
}


def is_note_reference(value: str) -> bool:
    cell = (value or "").strip()
    return bool(cell) and bool(NOTE_PATTERN.match(cell))


def parse_numeric(value: Optional[str], blank_as_zero: bool = False) -> Optional[float]:
    if value is None:
        return 0.0 if blank_as_zero else None
    text = str(value).strip()
    if not text:
        return 0.0 if blank_as_zero else None
    text = text.replace(",", "").replace("，", "").replace(" ", "")
    text = text.replace("（", "(").replace("）", ")")
    if text in {"-", "--", "—", "不适用"}:
        return None if not blank_as_zero else 0.0
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if not cleaned:
        return None if not blank_as_zero else 0.0
    try:
        number = float(cleaned)
    except ValueError:
        return None if not blank_as_zero else 0.0
    return -number if negative else number


def parse_growth(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"不适用", "-", "--", "—"}:
        return None
    if "增加" in text and "百分点" in text:
        return parse_numeric(text.replace("增加", "").replace("个百分点", ""))
    if "减少" in text and "百分点" in text:
        numeric = parse_numeric(text.replace("减少", "").replace("个百分点", ""))
        return -numeric if numeric is not None else None
    return parse_numeric(text)


def safe_growth(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None:
        return None
    if abs(previous) < 1e-9 or current * previous < 0:
        return None
    return (current - previous) / abs(previous) * 100


def to_10k_yuan(value: Optional[float]) -> Optional[float]:
    return None if value is None else value / 10000


def safe_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or abs(denominator) < 1e-9:
        return None
    return numerator / denominator * 100


def round_value(field_name: str, value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    precision = FIELD_PRECISION.get(field_name, 2)
    return round(value, precision)


def choose_growth_value(primary: Optional[float], fallback: Optional[float]) -> Optional[float]:
    if primary is None:
        return fallback
    if abs(primary) > 1000 and fallback is not None:
        return fallback
    return primary


def detect_report_period(filename: str, first_page_text: str, fallback_text: str = "") -> Optional[str]:
    def match_period(text: str) -> Optional[str]:
        if not text:
            return None
        for report_period, keywords in PERIOD_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return report_period
        return None

    first_page_window = "\n".join((first_page_text or "").splitlines()[:40])
    for candidate in (filename, first_page_window):
        report_period = match_period(candidate)
        if report_period:
            return report_period
    return match_period(fallback_text)


class FinancialReportParser:
    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.company_master = load_company_master()
        self.ocr_backend = get_ocr_backend()
        self.ocr_settings = get_ocr_settings()
        self._ocr_cache: Dict[int, OCRPageResult] = {}

    def _ocr_page_result(self, page_index: int) -> OCRPageResult | None:
        if self.ocr_backend is None:
            return None
        if page_index not in self._ocr_cache:
            try:
                self._ocr_cache[page_index] = self.ocr_backend.extract_page(self.pdf_path, page_index)
            except Exception as exc:  # pragma: no cover - runtime diagnostics
                logger.warning("OCR fallback failed for %s page %s: %s", self.pdf_path.name, page_index + 1, exc)
                self._ocr_cache[page_index] = OCRPageResult(text="", tables=[])
        return self._ocr_cache[page_index]

    def _page_text(self, pdf: pdfplumber.PDF, page_index: int) -> str:
        page = pdf.pages[page_index]
        text = (page.extract_text() or "").strip()
        if self.ocr_backend is None:
            return text

        if self.ocr_settings.fallback_only and len(text) >= self.ocr_settings.min_text_length:
            return text

        ocr_result = self._ocr_page_result(page_index)
        ocr_text = (ocr_result.text if ocr_result else "").strip()
        return ocr_text or text

    def _extract_text(self, pdf: pdfplumber.PDF, pages: Optional[int] = None) -> str:
        page_count = pages if pages is not None else len(pdf.pages)
        return "\n".join(self._page_text(pdf, page_index) for page_index in range(page_count))

    def _parse_metadata(self, pdf: pdfplumber.PDF) -> Dict[str, object]:
        first_page_text = self._page_text(pdf, 0)
        first_pages_text = self._extract_text(pdf, pages=min(5, len(pdf.pages)))
        filename = self.pdf_path.name
        metadata = {
            "stock_code": None,
            "stock_abbr": None,
            "company_name": None,
            "exchange": None,
            "report_period": None,
            "report_year": None,
        }

        code_match = re.search(r"(?:证券代码|公司代码)[:：]?\s*(\d{6})", first_pages_text)
        if not code_match:
            code_match = re.search(r"(\d{6})", filename)
        if code_match:
            metadata["stock_code"] = code_match.group(1)

        abbr_match = re.search(r"(?:证券简称|公司简称)[:：]?\s*([A-Za-z0-9\u4e00-\u9fa5]+)", first_pages_text)
        if abbr_match:
            metadata["stock_abbr"] = abbr_match.group(1).strip()

        for record in self.company_master["by_name"].values():
            company_name = record["company_name"]
            if company_name and company_name in first_pages_text:
                metadata["company_name"] = company_name
                metadata["stock_abbr"] = metadata["stock_abbr"] or record["stock_abbr"]
                metadata["stock_code"] = metadata["stock_code"] or record["stock_code"]
                metadata["exchange"] = record["exchange"]
                break

        if metadata["stock_code"]:
            reference = self.company_master["by_code"].get(str(metadata["stock_code"]))
            if reference:
                metadata["stock_abbr"] = reference["stock_abbr"]
                metadata["company_name"] = metadata["company_name"] or reference["company_name"]
                metadata["exchange"] = reference["exchange"]

        if metadata["stock_abbr"] and not metadata["stock_code"]:
            reference = self.company_master["by_abbr"].get(str(metadata["stock_abbr"]))
            if reference:
                metadata["stock_code"] = reference["stock_code"]
                metadata["company_name"] = reference["company_name"]
                metadata["exchange"] = reference["exchange"]

        report_text = f"{filename}\n{first_pages_text}"
        metadata["report_period"] = detect_report_period(filename, first_page_text, report_text)

        year_match = re.search(r"(20\d{2})\s*年", report_text)
        if year_match:
            metadata["report_year"] = int(year_match.group(1))

        return metadata

    def _extract_tables(self, pdf: pdfplumber.PDF, page_index: int) -> list[list[list[Optional[str]]]]:
        page = pdf.pages[page_index]
        tables = page.extract_tables() or []
        if tables:
            return tables
        tables = page.extract_tables(
            table_settings={
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "snap_tolerance": 3,
                "join_tolerance": 3,
            }
        ) or []
        if tables:
            return tables

        ocr_result = self._ocr_page_result(page_index)
        if ocr_result and ocr_result.tables:
            return ocr_result.tables
        return []

    def _normalize_cell(self, cell: Optional[str]) -> str:
        return "" if cell is None else str(cell).replace("\n", "").strip()

    def _row_label_fragment(self, cells: list[str]) -> str:
        parts = []
        for cell in cells:
            if not cell:
                continue
            if is_note_reference(cell):
                continue
            if re.fullmatch(r"-?\d[\d,]*(?:\.\d+)?%?", cell):
                continue
            parts.append(cell)
        return "".join(parts)

    def _row_numeric_values(self, cells: list[str]) -> list[float]:
        values: list[float] = []
        for cell in cells:
            numeric = parse_numeric(cell)
            if numeric is not None:
                values.append(numeric)
        return values

    def _row_numeric_tokens(self, cells: list[str]) -> list[str]:
        tokens: list[str] = []
        for cell in cells:
            if not cell:
                continue
            tokens.extend(re.findall(r"-?\d[\d,]*(?:\.\d+)?%?", cell))
        return tokens

    def _iter_compound_rows(self, table: Iterable[Iterable[Optional[str]]]) -> Iterable[Tuple[str, list[float], list[str]]]:
        rows = [[self._normalize_cell(cell) for cell in row] for row in table]
        index = 0

        while index < len(rows):
            cells = rows[index]
            label = self._row_label_fragment(cells)
            numeric_values = self._row_numeric_values(cells)
            numeric_tokens = self._row_numeric_tokens(cells)

            if not label or label == "项目":
                index += 1
                continue

            normalized_label = normalize_label(label)
            needs_continuation = any(alias.startswith(normalized_label) for alias in ALL_KNOWN_LABELS) and normalized_label not in ALL_KNOWN_LABELS
            if normalized_label not in ALL_KNOWN_LABELS and not needs_continuation:
                index += 1
                continue

            next_index = index + 1
            while needs_continuation and next_index < len(rows):
                next_cells = rows[next_index]
                next_label = self._row_label_fragment(next_cells)
                next_values = self._row_numeric_values(next_cells)
                if next_values:
                    break
                if next_label:
                    label += next_label
                    normalized_label = normalize_label(label)
                    if normalized_label in ALL_KNOWN_LABELS:
                        next_index += 1
                        break
                next_index += 1

            yield label, numeric_values, numeric_tokens
            index = next_index if next_index > index else index + 1

    def _iter_table_rows(self, table: Iterable[Iterable[Optional[str]]]) -> Iterable[Tuple[str, Optional[float], Optional[float]]]:
        for label, numeric_values, _ in self._iter_compound_rows(table):
            current = numeric_values[0] if numeric_values else None
            previous = numeric_values[1] if len(numeric_values) > 1 else None
            yield label, current, previous

    def _extract_statement_values(
        self, pdf: pdfplumber.PDF
    ) -> Tuple[Dict[str, Dict[str, Optional[float]]], Dict[str, Dict[str, Optional[float]]]]:
        current_values = {section: {} for section in STATEMENT_ALIASES}
        previous_values = {section: {} for section in STATEMENT_ALIASES}
        current_section: Optional[str] = None

        for page_index, _ in enumerate(pdf.pages):
            page_text = self._page_text(pdf, page_index)

            for section, marker in STATEMENT_START_MARKERS.items():
                if marker in page_text:
                    current_section = section
                    break

            if current_section:
                for table in self._extract_tables(pdf, page_index):
                    for label, current, previous in self._iter_table_rows(table):
                        field_name = STATEMENT_ALIAS_INDEX[current_section].get(normalize_label(label))
                        if not field_name or field_name in current_values[current_section]:
                            continue
                        current_values[current_section][field_name] = current
                        previous_values[current_section][field_name] = previous

            if current_section and STATEMENT_END_MARKERS[current_section] in page_text:
                current_section = None

        return current_values, previous_values

    def _fill_missing_statement_values(
        self,
        pdf: pdfplumber.PDF,
        current_values: Dict[str, Dict[str, Optional[float]]],
        previous_values: Dict[str, Dict[str, Optional[float]]],
    ) -> None:
        for page_index, _ in enumerate(pdf.pages):
            for table in self._extract_tables(pdf, page_index):
                for label, current, previous in self._iter_table_rows(table):
                    normalized_label = normalize_label(label)
                    for section, alias_index in STATEMENT_ALIAS_INDEX.items():
                        field_name = alias_index.get(normalized_label)
                        if not field_name or field_name in current_values[section]:
                            continue
                        current_values[section][field_name] = current
                        previous_values[section][field_name] = previous

    def _label_pattern(self, label: str) -> str:
        return r"\s*".join(re.escape(char) for char in label)

    def _extract_metric_tokens(self, text: str, aliases: Iterable[str]) -> list[str]:
        normalized_text = re.sub(r"[ \t]+", " ", text)
        for alias in aliases:
            pattern = re.compile(
                self._label_pattern(alias)
                + r"(?P<body>(?:\s+(?:-?\d[\d,]*(?:\.\d+)?|不适用|增加-?\d+(?:\.\d+)?个?百分点|减少-?\d+(?:\.\d+)?个?百分点)){1,6})"
            )
            match = pattern.search(normalized_text)
            if match:
                return NUMERIC_TOKEN_PATTERN.findall(match.group("body"))
        return []

    def _select_text_metric(self, tokens: list[str], report_period: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if not tokens:
            return None, None, None

        if report_period in {"Q1", "HY", "Q3"} and len(tokens) >= 4:
            current = parse_numeric(tokens[2])
            growth = parse_growth(tokens[3])
            previous = None
        elif len(tokens) >= 3:
            current = parse_numeric(tokens[0])
            previous = parse_numeric(tokens[1])
            growth = parse_growth(tokens[2])
        elif len(tokens) >= 1:
            current = parse_numeric(tokens[0])
            previous = None
            growth = None
        else:
            return None, None, None

        return current, previous, growth

    def _extract_text_metrics(
        self, pdf: pdfplumber.PDF, report_period: str
    ) -> Tuple[Dict[str, Optional[float]], Dict[str, Optional[float]], Dict[str, Optional[float]]]:
        first_text = self._extract_text(pdf, pages=min(10, len(pdf.pages)))
        current_metrics: Dict[str, Optional[float]] = {}
        previous_metrics: Dict[str, Optional[float]] = {}
        growth_metrics: Dict[str, Optional[float]] = {}

        for field_name, aliases in CORE_TEXT_ALIASES.items():
            tokens = self._extract_metric_tokens(first_text, aliases)
            current, previous, growth = self._select_text_metric(tokens, report_period)
            current_metrics[field_name] = current
            previous_metrics[field_name] = previous
            growth_metrics[field_name] = growth

        return current_metrics, previous_metrics, growth_metrics

    def _select_core_table_metric(self, tokens: list[str], report_period: str) -> Tuple[Optional[float], Optional[float]]:
        if not tokens:
            return None, None

        if report_period == "Q3" and len(tokens) >= 4:
            return parse_numeric(tokens[2]), parse_growth(tokens[3])
        if report_period == "FY" and len(tokens) >= 4:
            return parse_numeric(tokens[0]), parse_growth(tokens[3])
        if report_period in {"Q1", "HY"} and len(tokens) >= 2:
            return parse_numeric(tokens[0]), parse_growth(tokens[-1])
        if len(tokens) >= 3:
            return parse_numeric(tokens[0]), parse_growth(tokens[2])
        if len(tokens) >= 1:
            return parse_numeric(tokens[0]), None
        return None, None

    def _extract_core_table_metrics(
        self, pdf: pdfplumber.PDF, report_period: str
    ) -> Tuple[Dict[str, Optional[float]], Dict[str, Optional[float]]]:
        current_metrics: Dict[str, Optional[float]] = {}
        growth_metrics: Dict[str, Optional[float]] = {}

        for page_index in range(min(10, len(pdf.pages))):
            for table in self._extract_tables(pdf, page_index):
                for label, _, numeric_tokens in self._iter_compound_rows(table):
                    field_name = CORE_ALIAS_INDEX.get(normalize_label(label))
                    if not field_name or field_name in current_metrics:
                        continue
                    current, growth = self._select_core_table_metric(numeric_tokens, report_period)
                    current_metrics[field_name] = current
                    growth_metrics[field_name] = growth

        return current_metrics, growth_metrics

    def _build_common_fields(self, metadata: Dict[str, object]) -> Dict[str, object]:
        return {
            "stock_code": metadata["stock_code"],
            "stock_abbr": metadata["stock_abbr"],
            "report_period": metadata["report_period"],
            "report_year": metadata["report_year"],
        }

    def _build_core_performance(
        self,
        metadata: Dict[str, object],
        statement_current: Dict[str, Dict[str, Optional[float]]],
        statement_previous: Dict[str, Dict[str, Optional[float]]],
        text_current: Dict[str, Optional[float]],
        text_growth: Dict[str, Optional[float]],
    ) -> Dict[str, object]:
        income_current = statement_current["income_statement"]
        income_previous = statement_previous["income_statement"]
        balance_current = statement_current["balance_sheet"]
        cash_current = statement_current["cash_flow"]

        share_capital = balance_current.get("_share_capital")
        total_revenue_raw = income_current.get("total_operating_revenue") or text_current.get("total_operating_revenue_raw")
        total_revenue_previous = income_previous.get("total_operating_revenue")
        net_profit_raw = text_current.get("net_profit_raw") or income_current.get("net_profit")
        net_assets_raw = text_current.get("net_assets_raw") or balance_current.get("equity_total_equity")
        operating_cash_flow_raw = cash_current.get("operating_cf_net_amount") or text_current.get("operating_cash_flow_raw")

        row = self._build_common_fields(metadata)
        row.update(
            {
                "eps": text_current.get("eps"),
                "total_operating_revenue": to_10k_yuan(total_revenue_raw),
                "operating_revenue_yoy_growth": choose_growth_value(
                    text_growth.get("total_operating_revenue_raw"),
                    safe_growth(total_revenue_raw, total_revenue_previous),
                ),
                "operating_revenue_qoq_growth": None,
                "net_profit_10k_yuan": to_10k_yuan(net_profit_raw),
                "net_profit_yoy_growth": choose_growth_value(
                    text_growth.get("net_profit_raw"),
                    safe_growth(net_profit_raw, income_previous.get("net_profit")),
                ),
                "net_profit_qoq_growth": None,
                "net_asset_per_share": None if not share_capital or not net_assets_raw else net_assets_raw / share_capital,
                "roe": text_current.get("roe"),
                "operating_cf_per_share": None
                if not share_capital or not operating_cash_flow_raw
                else operating_cash_flow_raw / share_capital,
                "net_profit_excl_non_recurring": to_10k_yuan(text_current.get("net_profit_excl_non_recurring_raw")),
                "net_profit_excl_non_recurring_yoy": choose_growth_value(
                    text_growth.get("net_profit_excl_non_recurring_raw"),
                    None,
                ),
                "gross_profit_margin": None,
                "net_profit_margin": None,
                "roe_weighted_excl_non_recurring": text_current.get("roe_weighted_excl_non_recurring"),
            }
        )

        cost_of_sales = income_current.get("operating_expense_cost_of_sales")
        net_profit_statement = income_current.get("net_profit")
        if total_revenue_raw:
            if cost_of_sales is not None:
                row["gross_profit_margin"] = safe_ratio(total_revenue_raw - cost_of_sales, total_revenue_raw)
            if net_profit_statement is not None:
                row["net_profit_margin"] = safe_ratio(net_profit_statement, total_revenue_raw)

        return {field_name: round_value(field_name, value) if isinstance(value, float) else value for field_name, value in row.items()}

    def _build_balance_sheet(
        self,
        metadata: Dict[str, object],
        statement_current: Dict[str, Dict[str, Optional[float]]],
        statement_previous: Dict[str, Dict[str, Optional[float]]],
        text_current: Dict[str, Optional[float]],
        text_growth: Dict[str, Optional[float]],
    ) -> Dict[str, object]:
        current = statement_current["balance_sheet"]
        previous = statement_previous["balance_sheet"]
        total_assets = current.get("asset_total_assets") or text_current.get("asset_total_assets_raw")
        total_assets_previous = previous.get("asset_total_assets")
        total_liabilities = current.get("liability_total_liabilities")
        total_liabilities_previous = previous.get("liability_total_liabilities")

        row = self._build_common_fields(metadata)
        row.update(
            {
                "asset_cash_and_cash_equivalents": to_10k_yuan(current.get("asset_cash_and_cash_equivalents")),
                "asset_accounts_receivable": to_10k_yuan(current.get("asset_accounts_receivable")),
                "asset_inventory": to_10k_yuan(current.get("asset_inventory")),
                "asset_trading_financial_assets": to_10k_yuan(current.get("asset_trading_financial_assets")),
                "asset_construction_in_progress": to_10k_yuan(current.get("asset_construction_in_progress")),
                "asset_total_assets": to_10k_yuan(total_assets),
                "asset_total_assets_yoy_growth": choose_growth_value(
                    text_growth.get("asset_total_assets_raw"),
                    safe_growth(total_assets, total_assets_previous),
                ),
                "liability_accounts_payable": to_10k_yuan(current.get("liability_accounts_payable")),
                "liability_advance_from_customers": to_10k_yuan(current.get("liability_advance_from_customers")),
                "liability_total_liabilities": to_10k_yuan(total_liabilities),
                "liability_total_liabilities_yoy_growth": safe_growth(total_liabilities, total_liabilities_previous),
                "liability_contract_liabilities": to_10k_yuan(current.get("liability_contract_liabilities")),
                "liability_short_term_loans": to_10k_yuan(current.get("liability_short_term_loans")),
                "asset_liability_ratio": safe_ratio(total_liabilities, total_assets),
                "equity_unappropriated_profit": to_10k_yuan(current.get("equity_unappropriated_profit")),
                "equity_total_equity": to_10k_yuan(current.get("equity_total_equity")),
            }
        )

        return {field_name: round_value(field_name, value) if isinstance(value, float) else value for field_name, value in row.items()}

    def _build_cash_flow(
        self,
        metadata: Dict[str, object],
        statement_current: Dict[str, Dict[str, Optional[float]]],
        statement_previous: Dict[str, Dict[str, Optional[float]]],
    ) -> Dict[str, object]:
        current = statement_current["cash_flow"]
        previous = statement_previous["cash_flow"]
        net_cash_flow = current.get("net_cash_flow")
        operating_cf = current.get("operating_cf_net_amount")
        investing_cf = current.get("investing_cf_net_amount")
        financing_cf = current.get("financing_cf_net_amount")

        row = self._build_common_fields(metadata)
        row.update(
            {
                "net_cash_flow": round_value("net_cash_flow", net_cash_flow),
                "net_cash_flow_yoy_growth": round_value("net_cash_flow_yoy_growth", safe_growth(net_cash_flow, previous.get("net_cash_flow"))),
                "operating_cf_net_amount": to_10k_yuan(operating_cf),
                "operating_cf_ratio_of_net_cf": safe_ratio(operating_cf, net_cash_flow),
                "operating_cf_cash_from_sales": to_10k_yuan(current.get("operating_cf_cash_from_sales")),
                "investing_cf_net_amount": to_10k_yuan(investing_cf),
                "investing_cf_ratio_of_net_cf": safe_ratio(investing_cf, net_cash_flow),
                "investing_cf_cash_for_investments": to_10k_yuan(current.get("investing_cf_cash_for_investments")),
                "investing_cf_cash_from_investment_recovery": to_10k_yuan(current.get("investing_cf_cash_from_investment_recovery")),
                "financing_cf_cash_from_borrowing": to_10k_yuan(current.get("financing_cf_cash_from_borrowing")),
                "financing_cf_cash_for_debt_repayment": to_10k_yuan(current.get("financing_cf_cash_for_debt_repayment")),
                "financing_cf_net_amount": to_10k_yuan(financing_cf),
                "financing_cf_ratio_of_net_cf": safe_ratio(financing_cf, net_cash_flow),
            }
        )

        return {field_name: round_value(field_name, value) if isinstance(value, float) else value for field_name, value in row.items()}

    def _build_income_statement(
        self,
        metadata: Dict[str, object],
        statement_current: Dict[str, Dict[str, Optional[float]]],
        statement_previous: Dict[str, Dict[str, Optional[float]]],
        text_growth: Dict[str, Optional[float]],
    ) -> Dict[str, object]:
        current = statement_current["income_statement"]
        previous = statement_previous["income_statement"]
        total_revenue = current.get("total_operating_revenue")
        net_profit = current.get("net_profit")

        row = self._build_common_fields(metadata)
        row.update(
            {
                "net_profit": to_10k_yuan(net_profit),
                "net_profit_yoy_growth": choose_growth_value(
                    text_growth.get("net_profit_raw"),
                    safe_growth(net_profit, previous.get("net_profit")),
                ),
                "other_income": to_10k_yuan(current.get("other_income")),
                "total_operating_revenue": to_10k_yuan(total_revenue),
                "operating_revenue_yoy_growth": choose_growth_value(
                    text_growth.get("total_operating_revenue_raw"),
                    safe_growth(total_revenue, previous.get("total_operating_revenue")),
                ),
                "operating_expense_cost_of_sales": to_10k_yuan(current.get("operating_expense_cost_of_sales")),
                "operating_expense_selling_expenses": to_10k_yuan(current.get("operating_expense_selling_expenses")),
                "operating_expense_administrative_expenses": to_10k_yuan(current.get("operating_expense_administrative_expenses")),
                "operating_expense_financial_expenses": to_10k_yuan(current.get("operating_expense_financial_expenses")),
                "operating_expense_rnd_expenses": to_10k_yuan(current.get("operating_expense_rnd_expenses")),
                "operating_expense_taxes_and_surcharges": to_10k_yuan(current.get("operating_expense_taxes_and_surcharges")),
                "total_operating_expenses": to_10k_yuan(current.get("total_operating_expenses")),
                "operating_profit": to_10k_yuan(current.get("operating_profit")),
                "total_profit": to_10k_yuan(current.get("total_profit")),
                "asset_impairment_loss": to_10k_yuan(current.get("asset_impairment_loss")),
                "credit_impairment_loss": to_10k_yuan(current.get("credit_impairment_loss")),
            }
        )

        return {field_name: round_value(field_name, value) if isinstance(value, float) else value for field_name, value in row.items()}

    def parse_all_reports(self) -> Dict[str, Dict[str, object]]:
        with pdfplumber.open(str(self.pdf_path)) as pdf:
            metadata = self._parse_metadata(pdf)
            statement_current, statement_previous = self._extract_statement_values(pdf)
            self._fill_missing_statement_values(pdf, statement_current, statement_previous)
            text_current, _, text_growth = self._extract_text_metrics(pdf, str(metadata["report_period"]))
            table_current, table_growth = self._extract_core_table_metrics(pdf, str(metadata["report_period"]))

        for field_name, value in table_current.items():
            if value is not None:
                text_current[field_name] = value
        for field_name, value in table_growth.items():
            if value is not None:
                text_growth[field_name] = value

        return {
            "core_performance": self._build_core_performance(metadata, statement_current, statement_previous, text_current, text_growth),
            "balance_sheet": self._build_balance_sheet(metadata, statement_current, statement_previous, text_current, text_growth),
            "cash_flow": self._build_cash_flow(metadata, statement_current, statement_previous),
            "income_statement": self._build_income_statement(metadata, statement_current, statement_previous, text_growth),
        }


def parse_pdf_report(pdf_path: str | Path) -> Dict[str, Dict[str, object]]:
    parser = FinancialReportParser(pdf_path)
    parsed = parser.parse_all_reports()
    logger.info("解析完成: %s", pdf_path)
    return parsed
