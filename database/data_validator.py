from typing import Dict, List, Tuple  # 关键：补充导入 Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinancialDataValidator:
    """财务数据校验器"""

    # 核心指标阈值（避免0值/异常值入库）
    VALIDATION_RULES = {
        "total_revenue": {"min": 0.0, "required": True},
        "net_profit": {"min": 0.0, "required": False},
        "total_assets": {"min": 1000000.0, "required": True},  # 总资产至少100万
        "total_liabilities": {"min": 0.0, "required": True}
    }

    @staticmethod
    def _validate_indicator(value: float, rules: Dict) -> bool:
        """校验单个指标"""
        if rules.get("required") and value <= rules.get("min", 0.0):
            return False
        return True

    def validate_report(self, report_type: str, data: Dict) -> Tuple[bool, List[str]]:
        """校验单张报表数据"""
        errors = []
        # 必选基础信息校验
        basic_fields = ["company_code", "company_name", "report_year"]
        for field in basic_fields:
            if not data.get(field):
                errors.append(f"缺失基础信息：{field}")

        # 财务指标校验
        for indicator, rules in self.VALIDATION_RULES.items():
            if indicator in data:
                value = data[indicator]
                if not self._validate_indicator(value, rules):
                    errors.append(f"{indicator} 数值异常：{value}（最小值要求：{rules['min']}）")

        # 校验结果
        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning(f"[{report_type}] 数据校验失败：{errors}")
        return is_valid, errors

    def validate_all_reports(self, all_reports: Dict[str, Dict]) -> Tuple[bool, Dict[str, List[str]]]:
        """校验所有报表数据"""
        all_errors = {}
        is_all_valid = True

        for report_type, data in all_reports.items():
            is_valid, errors = self.validate_report(report_type, data)
            if errors:
                all_errors[report_type] = errors
                is_all_valid = False

        return is_all_valid, all_errors

def validate_financial_data(all_reports: Dict[str, Dict]) -> Tuple[bool, Dict[str, List[str]]]:
    """便捷调用函数"""
    validator = FinancialDataValidator()
    return validator.validate_all_reports(all_reports)

if __name__ == "__main__":
    # 测试校验
    test_data = {
        "core_performance": {
            "company_code": "600080",
            "company_name": "金花股份",
            "report_year": "2023",
            "total_revenue": 0.0,
            "net_profit": 100000.0
        }
    }
    validator = FinancialDataValidator()
    is_valid, errors = validator.validate_all_reports(test_data)
    print("校验结果：", is_valid, errors)