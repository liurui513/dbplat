from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from financial_assistant.config import RESULT_IMG_DIR


plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False


def _period_label(row: pd.Series) -> str:
    if "report_year" in row and "report_period" in row:
        return f"{int(row['report_year'])}{row['report_period']}"
    if "label" in row:
        return str(row["label"])
    return str(row.name)


def decide_chart_type(question: str, dataframe: pd.DataFrame) -> str | None:
    if dataframe.empty:
        return None
    lowered = question.lower()
    if "top" in lowered or "排名" in question or "最高" in question:
        return "bar"
    if any(keyword in question for keyword in ["趋势", "变化", "可视化", "绘图", "折线图"]):
        return "line"
    if len(dataframe) <= 10:
        return "bar"
    return "line"


def generate_chart(
    dataframe: pd.DataFrame,
    chart_type: str,
    save_path: str | Path,
    title: str,
    x_col: str,
    y_col: str,
) -> None:
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(10, 6))
    if chart_type == "bar":
        plt.bar(dataframe[x_col], dataframe[y_col], color="#2f6db3")
    else:
        plt.plot(dataframe[x_col], dataframe[y_col], marker="o", linewidth=2, color="#d9485f")

    plt.title(title)
    plt.xticks(rotation=35, ha="right")
    plt.tight_layout()
    plt.savefig(save_path, dpi=180)
    plt.close()


def build_chart_dataframe(dataframe: pd.DataFrame, label_column: str | None = None, value_column: str = "value") -> pd.DataFrame:
    chart_df = dataframe.copy()
    if label_column and label_column in chart_df.columns:
        chart_df["label"] = chart_df[label_column].astype(str)
    elif "label" in chart_df.columns:
        chart_df["label"] = chart_df["label"].astype(str)
    elif {"report_year", "report_period"}.issubset(chart_df.columns):
        chart_df["label"] = chart_df.apply(_period_label, axis=1)
    elif "stock_abbr" in chart_df.columns:
        chart_df["label"] = chart_df["stock_abbr"].astype(str)
    else:
        chart_df["label"] = chart_df.index.astype(str)
    chart_df["value"] = chart_df[value_column].astype(float)
    return chart_df[["label", "value"]]


def relative_result_path(filename: str) -> str:
    return f"./result/{filename}"


def absolute_result_path(filename: str) -> Path:
    return RESULT_IMG_DIR / filename
