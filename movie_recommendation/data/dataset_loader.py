import pandas as pd
import os
from config import Config


def safe_read_csv(csv_path):
    try:
        encodings = ['utf-8', 'gbk', 'latin-1']
        df = None

        for encoding in encodings:
            try:
                df = pd.read_csv(csv_path, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue

        if df is None:
            print(f"无法用支持的编码读取CSV文件: {csv_path}")
            return pd.DataFrame()

        df = df.fillna('')
        return df

    except Exception as e:
        print(f"CSV读取错误: {str(e)}")
        return pd.DataFrame()


def load_dataset(content_type):
    """加载指定类型的数据集"""
    dataset_path = Config.DATASET_PATHS.get(content_type)
    if not dataset_path or not os.path.exists(dataset_path):
        print(f"数据集不存在: {dataset_path}")
        return pd.DataFrame()

    return safe_read_csv(dataset_path)


def preprocess_dataset(df):
    """预处理数据集"""
    if df.empty:
        return df

    # 数据预处理
    required_cols = ['id', 'title', 'genres', 'rating', 'cover_url', 'year', 'director', 'actors', 'popularity']
    for col in required_cols:
        if col not in df.columns:
            df[col] = "" if col != 'rating' and col != 'year' and col != 'popularity' else 0.0

    df['rating'] = pd.to_numeric(df['rating'], errors='coerce').fillna(0.0)
    df['year'] = pd.to_numeric(df['year'], errors='coerce').fillna(0)
    df['popularity'] = pd.to_numeric(df['popularity'], errors='coerce').fillna(0.0)

    return df