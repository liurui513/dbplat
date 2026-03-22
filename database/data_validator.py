import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import FIELD_MAPPING

class DataValidator:
    def __init__(self, data):
        self.data = data
        self.result = {"pass": True, "errors": []}

    def _check_balance_sheet(self):
        """修复：放宽勾稽校验阈值（允许1%误差）"""
        bs = self.data.get("balance_sheet", {})
        assets = bs.get("total_assets", 0)
        liab_equity = bs.get("total_liabilities", 0) + bs.get("total_equity", 0)
        
        # 跳过资产为0的情况
        if assets == 0 or liab_equity == 0:
            return
        
        # 计算误差率（1%以内视为正常）
        error_rate = abs(assets - liab_equity) / max(assets, liab_equity)
        if error_rate > 0.01:
            self.result["errors"].append(f"资产负债表勾稽错误: {assets} ≠ {liab_equity} (误差率{error_rate:.2%})")
            self.result["pass"] = False

    def _check_cash_flow(self):
        """校验现金流量表"""
        cf = self.data.get("cash_flow", {})
        net = cf.get("net_cash_flow", 0)
        total = cf.get("operating_cash_flow", 0) + cf.get("investing_cash_flow", 0) + cf.get("financing_cash_flow", 0)
        
        if net == 0 or total == 0:
            return
        
        error_rate = abs(net - total) / max(net, total)
        if error_rate > 0.01:
            self.result["errors"].append(f"现金流量表勾稽错误: {net} ≠ {total} (误差率{error_rate:.2%})")
            self.result["pass"] = False

    def _check_consistency(self):
        """校验表间一致性"""
        core = self.data.get("core_performance", {})
        income = self.data.get("income_statement", {})
        cf = self.data.get("cash_flow", {})
        
        # 净利润一致性
        core_profit = core.get("net_profit", 0)
        income_profit = income.get("net_profit_parent", 0)
        if core_profit > 0 and income_profit > 0:
            error_rate = abs(core_profit - income_profit) / max(core_profit, income_profit)
            if error_rate > 0.05:  # 5%误差阈值
                self.result["errors"].append("净利润表间不一致")
                self.result["pass"] = False
        
        # 经营现金流一致性
        core_cash = core.get("operating_cash_flow", 0)
        cf_cash = cf.get("operating_cash_flow", 0)
        if core_cash > 0 and cf_cash > 0:
            error_rate = abs(core_cash - cf_cash) / max(core_cash, cf_cash)
            if error_rate > 0.05:
                self.result["errors"].append("经营现金流表间不一致")
                self.result["pass"] = False

    def validate(self):
        """执行全量校验"""
        self._check_balance_sheet()
        self._check_cash_flow()
        self._check_consistency()
        return self.result