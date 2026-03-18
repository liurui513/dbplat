import matplotlib.pyplot as plt
import pandas as pd
from config import RESULT_IMG_DIR

def plot_data(df, chart_type, question_id, index):
    filename = f"{question_id}_{index}.jpg"
    filepath = f"./result/{filename}" # 相对路径，符合题目要求
    save_path = f"{RESULT_IMG_DIR}/{filename}"
    
    plt.figure(figsize=(10, 6))
    if chart_type == 'line':
        plt.plot(df['report_period'], df['value'], marker='o')
    elif chart_type == 'bar':
        plt.bar(df['report_period'], df['value'])
    
    plt.title(f"Chart for {question_id}")
    plt.savefig(save_path)
    plt.close()
    return filepath