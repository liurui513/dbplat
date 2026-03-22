import logging

logger = logging.getLogger(__name__)

class FinancialDataValidator:
    def __init__(self):
        self.errors = []  # 记录校验错误

    def validate_all(self, data):
        """全量数据校验：完整性、合理性、逻辑一致性"""
        self.errors.clear()
        # 执行所有校验规则
        checks = [
            self._check_non_empty(data),
            self._check_numeric_consistency(data),
            self._check_balance_relation(data),
            self._check_profit_relation(data)
        ]
        # 输出校验结果
        if self.errors:
            logger.error(f"数据校验失败，错误列表：{self.errors}")
            return False
        logger.info("数据校验通过")
        return all(checks)

    def _check_non_empty(self, data):
        """检查核心字段非空（值>0）"""
        core_fields_map = {
            "core_performance": ["total_revenue", "net_profit"],
            "balance_sheet": ["total_assets", "total_liabilities"],
            "income_statement": ["operating_revenue", "operating_cost"],
            "cash_flow": ["operating_cash_flow"]
        }
        for table, fields in core_fields_map.items():
            for field in fields:
                value = data[table].get(field, 0.0)
                if value <= 0:
                    self.errors.append(f"[{table}] {field} 为空或值≤0（当前值：{value}）")
        return len(self.errors) == 0

    def _check_numeric_consistency(self, data):
        """检查数值合理性（非负、格式正确）"""
        # 总资产、总负债、货币资金等不能为负
        non_negative_fields = [
            ("balance_sheet", "total_assets"),
            ("balance_sheet", "total_liabilities"),
            ("balance_sheet", "monetary_funds"),
            ("balance_sheet", "accounts_receivable"),
            ("balance_sheet", "inventory")
        ]
        for table, field in non_negative_fields:
            value = data[table].get(field, 0.0)
            if value < 0:
                self.errors.append(f"[{table}] {field} 为负数（当前值：{value}）")
        return len(self.errors) == 0

    def _check_balance_relation(self, data):
        """检查资产负债表逻辑：资产总计 ≈ 负债总计 + 所有者权益合计（允许±1%误差）"""
        balance = data["balance_sheet"]
        total_assets = balance.get("total_assets", 0.0)
        total_liab = balance.get("total_liabilities", 0.0)
        total_equity = balance.get("total_equity", 0.0)
        sum_liab_equity = total_liab + total_equity

        if total_assets == 0 or sum_liab_equity == 0:
            return True  # 无数据时跳过
        
        # 计算误差率
        error_rate = abs(total_assets - sum_liab_equity) / total_assets
        if error_rate > 0.01:  # 误差超过1%
            self.errors.append(
                f"资产负债表逻辑错误：资产总计({total_assets}) ≠ 负债总计({total_liab}) + 所有者权益({total_equity})，误差率：{error_rate:.2%}"
            )
        return len(self.errors) == 0

    def _check_profit_relation(self, data):
        """检查利润表逻辑：营业利润 ≤ 利润总额"""
        income = data["income_statement"]
        operating_profit = income.get("operating_profit", 0.0)
        total_profit = income.get("total_profit", 0.0)

        if operating_profit == 0 or total_profit == 0:
            return True
        
        if operating_profit > total_profit + 1e6:  # 允许100万以内误差（非经常性损益）
            self.errors.append(
                f"利润表逻辑错误：营业利润({operating_profit}) > 利润总额({total_profit})"
            )
        return len(self.errors) == 0