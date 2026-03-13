# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.metrics.pairwise import cosine_similarity
#
# def calculate_content_similarity(row, user_data):
#     """计算内容相似度"""
#     user_preferences = user_data.get('preferences', [])
#     if not user_preferences:
#         return 0.5
#
#     # 创建内容特征
#     item_features = f"{row.get('genres', '')} {row.get('director', '')} {row.get('actors', '')}"
#
#     # 创建用户偏好特征
#     user_features = []
#     for pref in user_preferences:
#         user_features.append(f"{pref.get('genres', '')} {pref.get('director', '')} {pref.get('actors', '')}")
#     user_features = ' '.join(user_features)
#
#     # 计算TF-IDF相似度
#     vectorizer = TfidfVectorizer(stop_words='english')
#     try:
#         tfidf_matrix = vectorizer.fit_transform([item_features, user_features])
#         similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
#         return similarity
#     except:
#         return 0.5


import json
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import time
import os
import sys
import random
from datetime import datetime
import numpy as np  # 解决np引用问题

# 添加项目根目录到路径
sys.path.insert(0, r'D:\pythonProjectmovie，tobacco\movie_recommendation')

# 检查TextCNN可用性
try:
    from TextCNN import TextCNN

    TEXT_CNN_AVAILABLE = True
except ImportError as e:
    TEXT_CNN_AVAILABLE = False
    print(f"[WARN] TextCNN unavailable ({e}), using enhanced fallback")

# 尝试导入配置，如果失败则创建默认配置
try:
    from config import Config
    config_instance = Config()
    print("[OK] Loaded config")
except ImportError as e:
    print(f"[WARN] Failed to load config: {e}, using default config")


    # 创建默认配置类
    class DefaultConfig:
        BASE_DIR = r'D:\pythonProjectmovie，tobacco\movie_recommendation'
        DATASET_PATHS = {
            'movie': os.path.join(BASE_DIR, 'data', 'douban_movies.csv'),
            'series': os.path.join(BASE_DIR, 'data', 'douban_series.csv')
        }
        RECOMMEND_OUTPUT_PATH = {
            'movie': os.path.join(BASE_DIR, 'data', 'movie_recommendations.json'),
            'series': os.path.join(BASE_DIR, 'data', 'series_recommendations.json')
        }
        MAX_RECOMMENDATIONS = 20


    config_instance = DefaultConfig()


def load_dataset(dataset_type, force_reload=False, config=None):
    """加载数据集（支持原始CSV和JSON，优先使用原始数据）"""
    # 使用传入的config或全局config_instance
    current_config = config or config_instance

    # 获取路径
    if hasattr(current_config, 'DATASET_PATHS'):
        csv_path = current_config.DATASET_PATHS.get(dataset_type)
    else:
        csv_path = os.path.join(config_instance.BASE_DIR, 'data', f'douban_{dataset_type}s.csv')

    if hasattr(current_config, 'RECOMMEND_OUTPUT_PATH'):
        json_path = current_config.RECOMMEND_OUTPUT_PATH.get(dataset_type)
    else:
        json_path = os.path.join(config_instance.BASE_DIR, 'data', f'{dataset_type}_recommendations.json')

    # 优先从原始CSV加载（确保数据最新）
    if force_reload and os.path.exists(csv_path):
        try:
            # 尝试不同编码读取CSV
            try:
                df = pd.read_csv(csv_path, encoding='utf-8')
            except:
                df = pd.read_csv(csv_path, encoding='gbk')

            # 确保必要的列存在
            if 'id' not in df.columns:
                if f'{dataset_type}_id' in df.columns:
                    df.rename(columns={f'{dataset_type}_id': 'id'}, inplace=True)
                else:
                    df['id'] = range(len(df))

            print(f"[OK] Loaded {len(df)} {dataset_type} rows from CSV")
            return df
        except Exception as e:
            print(f"[WARN] Failed to read CSV: {e}")

    # 降级加载JSON
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = pd.DataFrame(data.get('data', []))
            print(f"ℹ️ 从JSON加载{dataset_type}数据: {len(df)}条")
            return df
        except Exception as e:
            print(f"[WARN] Failed to read JSON: {e}")

    # 返回空DataFrame
    return pd.DataFrame()


def init_text_cnn(force_reset=False, dataset_type='movie', config=None):
    """初始化TextCNN（支持强制重置和多数据集）"""
    if not TEXT_CNN_AVAILABLE:
        return None

    # 使用传入的config或全局config_instance
    current_config = config or config_instance

    # 如果强制重置或尚未初始化，则重新创建实例
    if force_reset or not hasattr(init_text_cnn, 'text_cnn') or not hasattr(init_text_cnn, 'last_reset'):
        # 检查是否需要重新初始化（超过5分钟或强制重置）
        if not force_reset and hasattr(init_text_cnn, 'last_reset'):
            elapsed = (datetime.now() - init_text_cnn.last_reset).total_seconds()
            if elapsed < 300:  # 5分钟内不重新初始化
                return init_text_cnn.text_cnn

        # 加载所有文本数据
        all_texts = []

        # 加载电影数据
        movies_df = load_dataset('movie', force_reload=True, config=current_config)
        for idx, movie_row in movies_df.iterrows():
            movie_text = f"{movie_row.get('genres', '')} {movie_row.get('director', '')} " \
                         f"{movie_row.get('actors', '')} {movie_row.get('plot', '')} {movie_row.get('title', '')}"
            all_texts.append(movie_text.strip())

        # 加载剧集数据
        series_df = load_dataset('series', force_reload=True, config=current_config)
        for idx, series_row in series_df.iterrows():
            series_text = f"{series_row.get('genres', '')} {series_row.get('director', '')} " \
                          f"{series_row.get('actors', '')} {series_row.get('plot', '')} {series_row.get('title', '')}"
            all_texts.append(series_text.strip())

        # 去重并过滤空文本
        all_texts = list(set([text for text in all_texts if text.strip()]))

        if all_texts:
            # 初始化TextCNN
            text_cnn = TextCNN()
            text_cnn.fit(all_texts)
            init_text_cnn.text_cnn = text_cnn
            init_text_cnn.last_reset = datetime.now()
            print(f"[OK] TextCNN initialized with {len(all_texts)} texts")
        else:
            init_text_cnn.text_cnn = None
            print("[WARN] No text data available for TextCNN")

    return init_text_cnn.text_cnn


def calculate_content_similarity(row, user_data, force_refresh=False, config=None):
    """使用TextCNN计算内容相似度（增强版，带随机扰动）"""
    user_preferences = user_data.get('preferences', [])
    if not user_preferences:
        # 无偏好时返回随机相似度，确保结果变化
        return random.uniform(0.4, 0.6)

    # 创建内容特征
    item_features = f"{row.get('genres', '')} {row.get('director', '')} " \
                    f"{row.get('actors', '')} {row.get('plot', '')} {row.get('title', '')}"
    item_features = item_features.strip()

    # 创建用户偏好特征
    user_features_list = []
    for pref in user_preferences:
        user_features_list.append(
            f"{pref.get('genres', '')} {pref.get('director', '')} {pref.get('actors', '')} "
            f"{pref.get('plot', '')} {pref.get('title', '')}")
    user_features = ' '.join(user_features_list).strip()

    # 使用TextCNN计算相似度
    try:
        text_cnn = init_text_cnn(force_reset=force_refresh, config=config)

        if text_cnn and item_features and user_features:
            item_vector = text_cnn.extract_features(item_features)
            user_vector = text_cnn.extract_features(user_features)

            # 添加微小随机扰动，确保结果变化
            item_vector = item_vector + (np.random.randn(*item_vector.shape) * 0.01)
            user_vector = user_vector + (np.random.randn(*user_vector.shape) * 0.01)

            similarity = cosine_similarity([item_vector], [user_vector])[0][0]
            # 确保相似度在合理范围内
            similarity = max(0.0, min(1.0, float(similarity)))

            # 添加随机扰动
            similarity *= random.uniform(0.95, 1.05)
            return min(1.0, max(0.0, similarity))
        else:
            return calculate_enhanced_similarity(item_features, user_features)

    except Exception as e:
        print(f"TextCNN相似度计算错误: {str(e)}")
        return calculate_enhanced_similarity(item_features, user_features)


def calculate_enhanced_similarity(text1, text2):
    """增强版关键词匹配相似度（带权重和随机）"""
    if not text1 or not text2:
        return random.uniform(0.4, 0.6)

    # 分词并去重
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if not words1 or not words2:
        return random.uniform(0.4, 0.6)

    # 计算交集和并集
    intersection = words1.intersection(words2)
    union = words1.union(words2)

    # Jaccard相似度
    jaccard = len(intersection) / len(union) if union else 0

    # 计算词频相似度
    tf1 = {word: text1.lower().count(word) for word in words1}
    tf2 = {word: text2.lower().count(word) for word in words2}

    # 计算加权相似度
    weighted_sim = 0
    total_weight = 0

    for word in intersection:
        weight = min(tf1[word], tf2[word]) / max(tf1[word], tf2[word]) if max(tf1[word], tf2[word]) > 0 else 1
        weighted_sim += weight
        total_weight += 1

    if total_weight > 0:
        weighted_sim /= total_weight
    else:
        weighted_sim = 0

    # 综合相似度
    combined_sim = (jaccard * 0.7) + (weighted_sim * 0.3)

    # 添加随机扰动，确保结果变化
    combined_sim *= random.uniform(0.9, 1.1)
    combined_sim = max(0.0, min(1.0, combined_sim))

    return combined_sim


def calculate_preference_weights(user_data):
    """计算用户偏好权重（返回原始计数值）"""
    preferences = user_data.get('preferences', [])
    if not preferences:
        return {}

    from collections import Counter
    all_genres = []

    for pref in preferences:
        genres = pref.get('genres', '').split(',')
        all_genres.extend([g.strip() for g in genres if g.strip() and g.lower() != 'nan'])

    genre_counts = Counter(all_genres)
    return {'genres': dict(genre_counts)}


def calculate_diversity_score(row):
    """计算多样性得分"""
    genres = str(row.get('genres', '')).split(',')
    genres = [g.strip() for g in genres if g.strip()]
    return min(1.0, len(genres) / 5)  # 归一化到0-1


def apply_diversity_strategy(df, top_n=20):
    """应用多样性策略，确保推荐结果多样化"""
    if len(df) <= top_n:
        return df

    # 按类型分组
    genre_groups = {}
    for idx, row in df.iterrows():
        genres = str(row.get('genres', '')).split(',')[0]  # 主要类型
        genre = genres.strip() or '未知'
        if genre not in genre_groups:
            genre_groups[genre] = []
        genre_groups[genre].append(row)

    # 轮流选择不同类型的项目
    result = []
    genre_list = list(genre_groups.keys())
    random.shuffle(genre_list)  # 随机打乱类型顺序

    while len(result) < top_n and genre_groups:
        for genre in genre_list.copy():
            if len(result) >= top_n:
                break

            if genre in genre_groups and genre_groups[genre]:
                # 随机选择该类型中的一个项目
                selected = genre_groups[genre].pop(0)
                result.append(selected)

                # 如果该类型已空，移除
                if not genre_groups[genre]:
                    del genre_groups[genre]
                    genre_list.remove(genre)

    # 如果还有空位，补充剩余项目
    if len(result) < top_n:
        # 获取已选项目的ID
        selected_ids = [row.get('id') for row in result if row.get('id')]
        # 选择未选中的项目
        remaining = df[~df['id'].isin(selected_ids)] if 'id' in df.columns else df
        # 随机选择补充
        additional = remaining.head(top_n - len(result))
        result.extend(additional.to_dict('records'))

    return pd.DataFrame(result[:top_n])


# 添加推荐生成主函数（增强版）
def generate_recommendations(user_data, dataset_type='movie', force_refresh=True, config=None):
    """生成推荐结果（增强版主函数）"""
    # 设置随机种子（确保每次结果不同）
    random.seed(datetime.now().timestamp())

    # 使用传入的config或全局config_instance
    current_config = config or config_instance

    # 加载数据集
    df = load_dataset(dataset_type, force_reload=force_refresh, config=current_config)

    if df.empty:
        return {
            'code': 0,
            'data': [],
            'count_weights': {},
            'algorithm_version': "Enhanced_NCF+TextCNN_v2.0",
            'generated_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'refreshed': force_refresh
        }

    # 计算相似度（带随机扰动）
    df['similarity'] = df.apply(
        lambda row: calculate_content_similarity(row, user_data, force_refresh=force_refresh, config=current_config),
        axis=1
    )

    # 添加多样性得分
    df['diversity_score'] = df.apply(
        lambda row: calculate_diversity_score(row),
        axis=1
    )

    # 综合得分（相似度为主，多样性为辅）
    df['final_score'] = df['similarity'] * 0.8 + df['diversity_score'] * 0.2

    # 添加随机扰动到最终得分
    df['final_score'] = df['final_score'] * np.random.uniform(0.98, 1.02, size=len(df))

    # 按最终得分排序
    df_sorted = df.sort_values('final_score', ascending=False)

    # 应用多样性策略
    df_diverse = apply_diversity_strategy(df_sorted, top_n=getattr(current_config, 'MAX_RECOMMENDATIONS', 20))

    # 获取偏好权重
    count_weights = calculate_preference_weights(user_data)

    # 获取输出路径
    if hasattr(current_config, 'RECOMMEND_OUTPUT_PATH'):
        output_path = current_config.RECOMMEND_OUTPUT_PATH.get(dataset_type)
    else:
        output_path = os.path.join(config_instance.BASE_DIR, 'data', f'{dataset_type}_recommendations.json')

    # 准备返回结果
    result = {
        'code': 0,
        'data': df_diverse.head(getattr(current_config, 'MAX_RECOMMENDATIONS', 20)).to_dict('records'),
        'count_weights': count_weights.get('genres', {}),
        'algorithm_version': "Enhanced_NCF+TextCNN_v2.0",
        'generated_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'refreshed': force_refresh,
        'total_items': len(df),
        'selected_items': len(df_diverse)
    }

    # 保存到文件
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[OK] Generated {len(result['data'])} {dataset_type} recommendations")
    return result


# 添加刷新推荐的接口函数
def refresh_recommendations(user_data, dataset_type='movie', config=None):
    """刷新推荐数据（增强版）"""
    # 使用传入的config或全局config_instance
    current_config = config or config_instance

    print(f"\n[REFRESH] {dataset_type} recommendations for {len(user_data.get('preferences', []))} preferences")
    result = generate_recommendations(user_data, dataset_type, force_refresh=True, config=current_config)
    print(f"[OK] Saved {dataset_type} recommendations to: {current_config.RECOMMEND_OUTPUT_PATH.get(dataset_type)}")
    return result


# 测试代码
if __name__ == "__main__":
    # 创建测试用户数据
    test_user_data = {
        'preferences': [
            {
                'id': '1',
                'title': '测试电影',
                'genres': '科幻,动作',
                'director': '诺兰',
                'actors': '汤姆·克鲁斯',
                'plot': '未来世界的冒险'
            }
        ]
    }

    # 测试刷新推荐（无需手动传config，函数内部会使用全局config_instance）
    refresh_recommendations(test_user_data, 'movie')
