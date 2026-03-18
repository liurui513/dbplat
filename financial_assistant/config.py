# 【核心配置】数据库、API Key、路径统一配置
import os

# --- 基础路径 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw')
DATA_OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'output')
RESULT_IMG_DIR = os.path.join(DATA_OUTPUT_DIR, 'result')
os.makedirs(RESULT_IMG_DIR, exist_ok=True)

# --- 数据库配置 ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Liurui8196',  # 请修改
    'database': 'financial_db',
    'port': 3306,
    'charset': 'utf8mb4'
}

# --- 大模型配置 (任务二、三需要) ---
# 建议使用国内大模型API (如智谱、通义千问) 或 本地部署模型
LLM_API_KEY = "YOUR_API_KEY"
LLM_MODEL_NAME = "glm-4"  # 或其他模型

# --- 向量数据库配置 (任务三需要) ---
VECTOR_DB_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'vector_db')