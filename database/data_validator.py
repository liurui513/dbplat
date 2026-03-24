from __future__ import annotations

import logging
from typing import Dict, List, Tuple

try:
    from .config import COMMON_COLUMNS, load_table_columns
except ImportError:  # pragma: no cover
    from database.config import COMMON_COLUMNS, load_table_columns


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


TABLE_REQUIRED_FIELDS = {
    "core_performance": ["total_operating_revenue", "net_profit_10k_yuan", "eps"],
    "balance_sheet": ["asset_total_assets", "liability_total_liabilities", "equity_total_equity"],
    "cash_flow": ["net_cash_flow", "operating_cf_net_amount"],
    "income_statement": ["total_operating_revenue", "net_profit", "total_profit"],
}


class FinancialDataValidator:
    def __init__(self) -> None:
        self.table_columns = load_table_columns()

    def _validate_common_fields(self, table_name: str, data: Dict[str, object]) -> List[str]:
        errors = []
        for field_name in COMMON_COLUMNS:
            if data.get(field_name) in {None, ""}:
                errors.append(f"ERROR: {table_name} 缺少基础字段 {field_name}")
        return errors

    def _validate_payload(self, table_name: str, data: Dict[str, object]) -> List[str]:
        warnings = []
        metric_fields = [field for field in self.table_columns[table_name] if field not in COMMON_COLUMNS and field != "serial_number"]
        populated_fields = [field for field in metric_fields if data.get(field) is not None]
        if not populated_fields:
            warnings.append(f"WARN: {table_name} 未提取到有效财务字段")
        return warnings

    def _validate_required_metrics(self, table_name: str, data: Dict[str, object]) -> List[str]:
        warnings = []
        if not any(data.get(field_name) is not None for field_name in TABLE_REQUIRED_FIELDS[table_name]):
            warnings.append(f"WARN: {table_name} 核心字段均为空")
        return warnings

    def _validate_consistency(self, table_name: str, data: Dict[str, object]) -> List[str]:
        warnings = []

        if table_name == "balance_sheet":
            total_assets = data.get("asset_total_assets")
            total_liabilities = data.get("liability_total_liabilities")
            ratio = data.get("asset_liability_ratio")
            if total_assets is not None and total_assets <= 0:
                warnings.append("ERROR: 资产负债表总资产必须大于 0")
            if total_assets and total_liabilities is not None and ratio is not None:
                calc_ratio = round(total_liabilities / total_assets * 100, 4)
                if abs(calc_ratio - ratio) > 0.5:
                    warnings.append("WARN: 资产负债率与总资产/总负债不一致")

        if table_name == "cash_flow":
            net_cash_flow = data.get("net_cash_flow")
            operating_cf = data.get("operating_cf_net_amount")
            operating_ratio = data.get("operating_cf_ratio_of_net_cf")
            if net_cash_flow and operating_cf is not None and operating_ratio is not None:
                calc_ratio = round((operating_cf * 10000) / net_cash_flow * 100, 4)
                if abs(calc_ratio - operating_ratio) > 0.5:
                    warnings.append("WARN: 经营现金流占比与净现金流不一致")

        if table_name == "core_performance":
            revenue = data.get("total_operating_revenue")
            gross_margin = data.get("gross_profit_margin")
            if revenue is not None and revenue <= 0:
                warnings.append("WARN: 核心业绩表营业总收入为空或非正数")
            if gross_margin is not None and not (-100 <= gross_margin <= 100):
                warnings.append("WARN: 销售毛利率超出合理区间")

        return warnings

    def validate_report(self, table_name: str, data: Dict[str, object]) -> Tuple[bool, List[str]]:
        issues: List[str] = []
        issues.extend(self._validate_common_fields(table_name, data))
        issues.extend(self._validate_payload(table_name, data))
        issues.extend(self._validate_required_metrics(table_name, data))
        issues.extend(self._validate_consistency(table_name, data))
        is_valid = not any(message.startswith("ERROR:") for message in issues)
        return is_valid, issues

    def validate_all_reports(self, reports: Dict[str, Dict[str, object]]) -> Tuple[bool, Dict[str, List[str]]]:
        all_issues: Dict[str, List[str]] = {}
        overall_valid = True

        for table_name, data in reports.items():
            is_valid, issues = self.validate_report(table_name, data)
            if issues:
                all_issues[table_name] = issues
            overall_valid = overall_valid and is_valid

        return overall_valid, all_issues


def validate_financial_data(reports: Dict[str, Dict[str, object]]) -> Tuple[bool, Dict[str, List[str]]]:
    validator = FinancialDataValidator()
    return validator.validate_all_reports(reports)
