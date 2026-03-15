# import pandas as pd
# from datetime import datetime
# from config import Config
# from data.dataset_loader import load_dataset, preprocess_dataset
# from data.user_manager import init_or_repair_user_data, calculate_preference_weights
# from recommendation.similarity import calculate_content_similarity
# from recommendation.diversity import apply_diversity_strategy
# from utils.file_utils import safe_write_json
# import random
# import json
#
#
# def calculate_item_score(row, preference_weights, user_data):
#     """计算项目综合得分（强化类型权重）"""
#     score = 0.0
#
#     # 1. 类型偏好得分（大幅提升比重）
#     genre_score = 0.0
#     genres = str(row.get('genres', '')).split(',')
#     for genre in genres:
#         genre = genre.strip()
#         if genre:
#             # 获取用户对该类型的偏好权重
#             genre_weight = preference_weights['genres'].get(genre, 0.0)
#             genre_score += genre_weight
#
#             # 如果类型匹配度高，额外加分
#             if genre_weight > 0.5:
#                 genre_score += genre_weight * 0.3  # 额外30%奖励
#
#     # 类型得分归一化（确保不会过高）
#     max_genre_score = len([g for g in genres if g.strip()]) * 1.3  # 考虑额外奖励的最大值
#     if max_genre_score > 0:
#         genre_score = min(genre_score / max_genre_score, 1.0)
#
#     # 类型偏好占总评分的70%比重
#     score += genre_score * 0.7
#
#     # 2. 导演和演员偏好得分（占10%）
#     director_score = preference_weights['directors'].get(str(row.get('director', '')), 0.0)
#     actor_score = 0.0
#     actors = str(row.get('actors', '')).split(',')[:3]
#     for actor in actors:
#         actor = actor.strip()
#         if actor:
#             actor_score += preference_weights['actors'].get(actor, 0.0)
#
#     person_score = (director_score * 0.7) + (actor_score * 0.3)
#     score += person_score * 0.1
#
#     # 3. 评分得分（归一化到0-1，占10%）
#     rating = float(row.get('rating', 0))
#     rating_score = min(rating / 10, 1.0)
#     score += rating_score * 0.1
#
#     # 4. 内容相似度得分（占5%）
#     similarity_score = calculate_content_similarity(row, user_data)
#     score += similarity_score * 0.05
#
#     # 5. 年份和流行度得分（占5%）
#     current_year = datetime.now().year
#     item_year = int(row.get('year', 0))
#     year_score = 0.0
#     if item_year > 0:
#         year_diff = current_year - item_year
#         year_score = max(0, 1 - (year_diff / 20))
#
#     popularity = float(row.get('popularity', 0))
#     popularity_score = min(popularity / 100, 1.0) if popularity > 0 else 0.5
#
#     temporal_score = (year_score * 0.6) + (popularity_score * 0.4)
#     score += temporal_score * 0.05
#
#     # 应用负反馈惩罚
#     item_id = str(row.get('id', ''))
#     disliked_items = [item['id'] for item in user_data.get('disliked_items', [])]
#     if item_id in disliked_items:
#         score *= (1 - Config.NEGATIVE_FEEDBACK_PENALTY)
#
#     # 类型匹配度特别高的项目额外加分
#     if genre_score > 0.8:
#         score *= 1.2  # 20%额外奖励
#
#     # 添加随机性，确保每次结果有变化
#     score *= (0.95 + random.random() * 0.1)
#
#     return score
#
#
# def generate_personalized_recommendations(recommend_type):
#     """生成个性化推荐（强化类型偏好）"""
#     # 加载数据集（使用原有接口）
#     items_df = load_dataset(recommend_type)
#     if items_df.empty:
#         return [{"id": "0", "title": f"{recommend_type}数据为空", "genres": "", "rating": 0, "cover_url": ""}]
#
#     # 预处理数据
#     items_df = preprocess_dataset(items_df)
#
#     # 获取用户数据
#     user_data = init_or_repair_user_data()
#     user_preferences = user_data.get('preferences', [])
#
#     # 获取黑名单和已推荐列表
#     blacklist = [item['item_id'] for item in user_data.get('blacklist', []) if item.get('item_type') == recommend_type]
#
#     # 获取历史推荐记录，避免重复推荐
#     try:
#         with open(Config.RECOMMEND_OUTPUT_PATH[recommend_type], 'r', encoding='utf-8') as f:
#             old_data = json.load(f)
#             old_recommendations = [item['id'] for item in old_data.get('data', [])]
#             blacklist.extend(old_recommendations[:10])  # 排除最近推荐的10个
#     except:
#         old_recommendations = []
#
#     # 过滤黑名单项目
#     if blacklist and 'id' in items_df.columns:
#         items_df = items_df[~items_df['id'].isin(blacklist)]
#
#     # 无偏好时按类型流行度推荐
#     if not user_preferences or not user_data.get('count_weights'):
#         print(f"无用户偏好数据，返回{recommend_type}类型流行推荐")
#
#         # 统计类型流行度
#         genre_popularity = {}
#         for idx, row in items_df.iterrows():
#             genres = str(row.get('genres', '')).split(',')
#             rating = float(row.get('rating', 0))
#             for genre in genres:
#                 genre = genre.strip()
#                 if genre:
#                     genre_popularity[genre] = genre_popularity.get(genre, 0) + rating
#
#         # 获取最受欢迎的类型
#         if genre_popularity:
#             top_genre = max(genre_popularity.items(), key=lambda x: x[1])[0]
#             # 优先推荐热门类型
#             top_genre_items = items_df[items_df['genres'].str.contains(top_genre, na=False)]
#             if not top_genre_items.empty:
#                 items_df = pd.concat([top_genre_items, items_df[~items_df['genres'].str.contains(top_genre, na=False)]])
#
#         # 随机打乱后取前N个
#         result_df = items_df.sample(frac=1, random_state=random.randint(1, 1000)).sort_values(by='rating',
#                                                                                               ascending=False)
#         return result_df.head(Config.MAX_RECOMMENDATIONS).to_dict('records')
#
#     try:
#         # 获取细粒度偏好权重
#         preference_weights = calculate_preference_weights(user_preferences)
#         print(f"用户类型偏好权重: {preference_weights.get('genres', {})}")
#
#         # 计算综合得分
#         items_df['final_score'] = items_df.apply(
#             lambda row: calculate_item_score(row, preference_weights, user_data),
#             axis=1
#         )
#
#         # 排序并应用多样性策略（但保持类型优先）
#         result = items_df.sort_values(by=['final_score', 'rating'], ascending=[False, False])
#
#         # 确保类型多样性
#         final_result = apply_diversity_strategy(result)
#
#         # 确保每次结果有变化（添加随机抽样）
#         if len(final_result) > Config.MAX_RECOMMENDATIONS + 5:
#             # 从顶部25个中随机选择20个
#             top_candidates = final_result.head(Config.MAX_RECOMMENDATIONS + 5)
#             final_result = top_candidates.sample(n=Config.MAX_RECOMMENDATIONS, random_state=random.randint(1, 1000))
#             final_result = final_result.sort_values(by='final_score', ascending=False)
#
#         return final_result.head(Config.MAX_RECOMMENDATIONS).to_dict('records')
#
#     except Exception as e:
#         print(f"推荐计算错误: {str(e)}")
#         # 出错时返回类型优先的结果
#         result_df = items_df.sample(frac=1, random_state=random.randint(1, 1000)).sort_values(by='rating',
#                                                                                               ascending=False)
#         return result_df.head(Config.MAX_RECOMMENDATIONS).to_dict('records')
#
#
# def generate_and_save_recommendations(recommend_type):
#     """生成并保存推荐结果"""
#     try:
#         # 生成推荐数据
#         recommendations = generate_personalized_recommendations(recommend_type)
#         if not recommendations:
#             print(f"❌ {recommend_type}推荐生成失败，结果为空")
#             return False
#
#         # 获取用户权重用于前端展示
#         user_data = init_or_repair_user_data()
#         count_weights = user_data.get('count_weights', {})
#
#         # 突出显示类型权重
#         if count_weights.get('genres'):
#             # 归一化类型权重
#             total_genres = sum(count_weights['genres'].values())
#             if total_genres > 0:
#                 count_weights['genres'] = {k: round(v / total_genres, 2) for k, v in count_weights['genres'].items()}
#
#         # 准备写入数据
#         output_data = {
#             "code": 0,
#             "user_id": "user_default",
#             "data": recommendations,
#             "count_weights": count_weights,
#             "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#             "refreshed": True,
#             "algorithm_version": "genre_priority_v2"
#         }
#
#         # 写入推荐文件
#         output_path = Config.RECOMMEND_OUTPUT_PATH[recommend_type]
#         if not safe_write_json(output_path, output_data):
#             print(f"❌ {recommend_type}推荐写入文件失败")
#             return False
#
#         print(f"✅ {recommend_type}推荐已更新（类型优先）并保存到 {output_path}")
#         return True
#
#     except Exception as e:
#         print(f"推荐生成与保存失败: {str(e)}")
#         return False


import pandas as pd
import numpy as np
from datetime import datetime
import random
import json
import os
import sys
import hashlib
from db.content_repository import load_content_items_df
from db.feedback_repository import add_negative_feedback_record, get_negative_feedback_ids, get_negative_feedback_records
from db.user_repository import get_user_preferences

# ------------ 强制指定config路径（关键修改） ------------
# 直接指定config所在的目录
config_dir = r'D:\pythonProjectmovie，tobacco\movie_recommendation'
sys.path.insert(0, config_dir)

# 手动验证路径
print(f"正在查找config.py于: {config_dir}")
config_file = os.path.join(config_dir, 'config.py')
if os.path.exists(config_file):
    print(f"[OK] Found config.py: {config_file}")
else:
    print(f"[ERR] Missing config.py: {config_file}")
    # 列出目录内容帮助排查
    try:
        print("目录内容:")
        for item in os.listdir(config_dir):
            print(f"  - {item}")
    except:
        pass

# 导入config
try:
    from config import Config
    
    print("[OK] Imported config module")
except ImportError as e:
    print(f"[WARN] Failed to import config, using builtin fallback: {e}")


    # 内置Config类作为备选
    class Config:
        BASE_DIR = config_dir

        # 数据文件路径
        USER_DATA_FILE = os.path.join(BASE_DIR, "data", "user_data.json")
        WATCHLIST_FILE = os.path.join(BASE_DIR, "data", "watchlist.json")

        # 数据集配置
        DATASET_PATHS = {
            'movie': os.path.join(BASE_DIR, "data", "douban_movies.csv"),
            'series': os.path.join(BASE_DIR, "data", "douban_series.csv")
        }

        # 推荐结果路径
        RECOMMEND_OUTPUT_PATH = {
            'movie': os.path.join(BASE_DIR, "data", "movie_recommendations.json"),
            'series': os.path.join(BASE_DIR, "data", "series_recommendations.json")
        }

        # 权重配置
        RECOMMENDATION_WEIGHTS = {
            'genre_preference': 0.7,
            'rating': 0.1,
            'popularity': 0.02,
            'release_year': 0.03,
            'similarity': 0.05,
            'user_preference': 0.1
        }

        MAX_RECOMMENDATIONS = 20
        NEGATIVE_FEEDBACK_PENALTY = 0.5
        CACHE_DIR = os.path.join(BASE_DIR, "cache", "image_cache")


    def init_directories():
        """初始化必要的目录"""
        data_dir = os.path.join(Config.BASE_DIR, "data")
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(Config.CACHE_DIR, exist_ok=True)
# ------------ 路径配置结束 ------------


# NCF核心依赖
try:
    from tensorflow.keras.models import Model
    from tensorflow.keras.layers import Input, Embedding, Flatten, Dot, Dense, Concatenate, Dropout
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping

    NCF_AVAILABLE = True
except ImportError:
    NCF_AVAILABLE = False
    print("[WARN] TensorFlow/Keras unavailable, using content-based fallback")


try:
    from TextCNN import TextCNN

    TEXTCNN_AVAILABLE = True
except ImportError:
    TEXTCNN_AVAILABLE = False
    print("TextCNN unavailable, fallback to rule-based content similarity.")


class NCFRecommender:
    """神经协同过滤推荐器 - 核心推荐引擎"""

    def __init__(self, user_id="user_default", embedding_size=32):
        self.user_id = user_id
        self.embedding_size = embedding_size
        self.model = None
        self.user2idx = {user_id: 0}  # 当前用户ID映射为0
        self.item2idx = {}
        self.id2item = {}

    def _build_model(self, num_items):
        """构建NCF模型架构（GMF + MLP）"""
        # 输入层
        user_input = Input(shape=(1,), name='user_input')
        item_input = Input(shape=(1,), name='item_input')

        # GMF部分（Generalized Matrix Factorization）
        user_embedding_gmf = Embedding(1, self.embedding_size)(user_input)  # 只有1个用户
        item_embedding_gmf = Embedding(num_items, self.embedding_size)(item_input)
        gmf_vector = Dot(axes=-1)([Flatten()(user_embedding_gmf), Flatten()(item_embedding_gmf)])

        # MLP部分（Multi-Layer Perceptron）
        user_embedding_mlp = Embedding(1, self.embedding_size * 2)(user_input)
        item_embedding_mlp = Embedding(num_items, self.embedding_size * 2)(item_input)
        mlp_vector = Concatenate()([Flatten()(user_embedding_mlp), Flatten()(item_embedding_mlp)])

        # MLP隐藏层
        mlp_vector = Dense(64, activation='relu')(mlp_vector)
        mlp_vector = Dropout(0.2)(mlp_vector)
        mlp_vector = Dense(32, activation='relu')(mlp_vector)

        # 融合GMF和MLP
        concat_vector = Concatenate()([gmf_vector, mlp_vector])
        output = Dense(1, activation='sigmoid', name='prediction')(concat_vector)

        # 编译模型
        self.model = Model(inputs=[user_input, item_input], outputs=output)
        self.model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )

    def prepare_data(self, items_df, user_preferences, user_behavior):
        """准备NCF训练数据"""
        # 构建物品ID映射
        all_items = items_df['id'].unique()
        self.item2idx = {item_id: idx for idx, item_id in enumerate(all_items)}
        self.id2item = {idx: item_id for item_id, idx in self.item2idx.items()}

        # 正样本：用户喜欢/评分高的物品
        positive_items = []
        for pref in user_preferences:
            item_id = pref.get('id')
            if item_id in self.item2idx:
                # 根据评分决定权重（评分>=5为正样本）
                rating = float(pref.get('rating', 5))
                if rating >= 5:
                    positive_items.append(self.item2idx[item_id])

        # 用户行为中的正样本
        for behavior in user_behavior:
            if behavior.get('type') == 'like' and behavior.get('item_id') in self.item2idx:
                positive_items.append(self.item2idx[behavior.get('item_id')])

        # 负样本：用户未交互的物品（负采样）
        interacted_items = set()
        for pref in user_preferences:
            if pref.get('id') in self.item2idx:
                interacted_items.add(self.item2idx[pref.get('id')])

        # 生成负样本（与正样本数量平衡）
        all_item_indices = set(range(len(all_items)))
        negative_candidates = list(all_item_indices - interacted_items)

        # 确保有负样本（即使数量少）
        if not positive_items:
            # 无用户偏好时，随机选择正样本
            positive_items = random.sample(list(all_item_indices), min(5, len(all_item_indices)))

        if negative_candidates:
            negative_items = np.random.choice(
                negative_candidates,
                size=min(len(positive_items) * 2, len(negative_candidates)),
                replace=False
            ).tolist()
        else:
            negative_items = []

        # 构建训练数据
        user_input_data = np.zeros(len(positive_items) + len(negative_items))  # 当前用户ID固定为0
        item_input_data = np.array(positive_items + negative_items)
        labels = np.array([1] * len(positive_items) + [0] * len(negative_items))

        # 打乱数据
        if len(user_input_data) > 0:
            shuffle_indices = np.random.permutation(len(user_input_data))
            return (
                user_input_data[shuffle_indices],
                item_input_data[shuffle_indices],
                labels[shuffle_indices]
            )
        else:
            return np.array([]), np.array([]), np.array([])

    def train(self, items_df, user_preferences, user_behavior):
        """训练NCF模型"""
        if not NCF_AVAILABLE:
            raise ImportError("需要安装TensorFlow/Keras来使用NCF模型")

        # 准备数据
        user_input, item_input, labels = self.prepare_data(items_df, user_preferences, user_behavior)

        if len(user_input) == 0:
            return False

        # 构建模型
        self._build_model(len(self.item2idx))

        # 训练模型（使用早停防止过拟合）
        early_stopping = EarlyStopping(patience=2, restore_best_weights=True)
        self.model.fit(
            [user_input, item_input], labels,
            epochs=8,
            batch_size=8,
            validation_split=0.2,
            callbacks=[early_stopping],
            verbose=0
        )
        return True

    def predict_scores(self, items_df):
        """预测所有物品的评分"""
        if not hasattr(self, 'model') or self.model is None:
            return {}

        # 准备预测数据
        item_indices = np.array(list(self.item2idx.values()))
        user_indices = np.zeros(len(item_indices))  # 当前用户ID固定为0

        # 预测评分
        predictions = self.model.predict([user_indices, item_indices], verbose=0)

        # 构建评分字典
        scores = {}
        for idx, score in zip(item_indices, predictions.flatten()):
            item_id = self.id2item[idx]
            scores[item_id] = float(score)

        return scores


def get_model_cache_dir():
    """Return the directory used to cache recommendation model artifacts."""
    cache_dir = os.path.join(Config.BASE_DIR, 'cache', 'models')
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def build_recommendation_signature(recommend_type, items_df, user_preferences, user_behavior):
    """Build a stable signature for one recommendation context."""
    id_series = items_df['id'].astype(str).tolist() if 'id' in items_df.columns else []
    payload = {
        'recommend_type': recommend_type,
        'dataset_ids': id_series,
        'preferences': user_preferences,
        'behavior': user_behavior,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def get_ncf_cache_path(recommend_type, signature):
    """Return the cache file path for one NCF score artifact."""
    return os.path.join(get_model_cache_dir(), f'ncf_{recommend_type}_{signature}.json')


def load_cached_ncf_scores(recommend_type, signature):
    """Load cached NCF scores if present."""
    cache_path = get_ncf_cache_path(recommend_type, signature)
    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        scores = data.get('scores', {})
        if isinstance(scores, dict) and scores:
            print(f"Loaded cached NCF scores from {cache_path}")
            return normalize_score_map({str(key): float(value) for key, value in scores.items()})
    except Exception as exc:
        print(f"Failed to load cached NCF scores: {exc}")
    return None


def save_cached_ncf_scores(recommend_type, signature, scores):
    """Persist NCF scores to speed up later refresh jobs."""
    if not isinstance(scores, dict) or not scores:
        return

    payload = {
        'recommend_type': recommend_type,
        'signature': signature,
        'generated_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'scores': scores,
    }
    safe_write_json(get_ncf_cache_path(recommend_type, signature), payload)


# 数据加载和预处理函数
def load_dataset(recommend_type):
    """Load dataset from PostgreSQL first, then fall back to CSV files."""
    db_df = load_content_items_df(recommend_type)
    if not db_df.empty:
        print(f"[OK] Loaded {len(db_df)} {recommend_type} rows from PostgreSQL")
        if 'id' not in db_df.columns:
            db_df['id'] = range(len(db_df))
        return db_df

    file_path = Config.DATASET_PATHS.get(recommend_type)
    print(f"加载数据集: {file_path}")

    if os.path.exists(file_path):
        try:
            # 尝试不同编码
            df = pd.read_csv(file_path, encoding='utf-8')
        except:
            try:
                df = pd.read_csv(file_path, encoding='gbk')
            except Exception as e:
                print(f"读取CSV失败: {e}")
                df = pd.DataFrame()

        if not df.empty:
            print(f"[OK] Loaded {len(df)} rows")
            # 确保id列存在
            if 'id' not in df.columns:
                if 'movie_id' in df.columns:
                    df.rename(columns={'movie_id': 'id'}, inplace=True)
                elif 'drama_id' in df.columns:
                    df.rename(columns={'drama_id': 'id'}, inplace=True)
                else:
                    df['id'] = range(len(df))
            return df
    else:
        print(f"[ERR] Dataset file missing: {file_path}")

    # 降级加载推荐结果文件
    file_path = Config.RECOMMEND_OUTPUT_PATH.get(recommend_type)
    if not os.path.exists(file_path):
        return pd.DataFrame()

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return pd.DataFrame(data.get('data', []))


def preprocess_dataset(df):
    """预处理数据集"""
    if df.empty:
        return df

    # 确保必要的列存在
    for col in ['rating', 'year', 'popularity', 'genres', 'director', 'actors', 'title', 'cover_url']:
        if col not in df.columns:
            df[col] = ''

    # 类型转换
    df['rating'] = pd.to_numeric(df['rating'], errors='coerce').fillna(0)
    df['year'] = pd.to_numeric(df['year'], errors='coerce').fillna(0)
    df['popularity'] = pd.to_numeric(df['popularity'], errors='coerce').fillna(0)

    # 确保id是字符串类型
    df['id'] = df['id'].astype(str)

    return df


def init_or_repair_user_data():
    """初始化或修复用户数据"""
    # 使用项目配置的用户数据路径
    user_data_path = Config.USER_DATA_FILE
    print(f"加载用户数据: {user_data_path}")

    if os.path.exists(user_data_path):
        with open(user_data_path, 'r', encoding='utf-8') as f:
            try:
                user_data = json.load(f)
                print(f"[OK] Loaded user data, preferences: {len(user_data.get('preferences', []))}")
            except Exception as e:
                print(f"读取用户数据失败: {e}")
                user_data = {}
    else:
        print("[ERR] User data file missing, creating a new one")
        user_data = {}

    # 确保必要的字段存在
    user_data.setdefault('preferences', [])
    user_data.setdefault('behavior', [])
    user_data.setdefault('blacklist', [])
    user_data.setdefault('disliked_items', [])
    user_data.setdefault('count_weights', {'genres': {}, 'directors': {}, 'actors': {}})
    user_data.setdefault('last_refresh_time', '')

    return user_data


def calculate_preference_weights(user_preferences):
    """计算用户偏好权重（返回计数值而非归一化值）"""
    weights = {'genres': {}, 'directors': {}, 'actors': {}}

    # 统计偏好（返回原始计数值）
    for pref in user_preferences:
        # 统计类型
        genres = str(pref.get('genres', '')).split(',')
        for genre in genres:
            genre = genre.strip()
            if genre and genre.lower() != 'nan':
                weights['genres'][genre] = weights['genres'].get(genre, 0) + 1

        # 统计导演
        director = str(pref.get('director', '')).strip()
        if director and director.lower() != 'nan':
            weights['directors'][director] = weights['directors'].get(director, 0) + 1

        # 统计演员
        actors = str(pref.get('actors', '')).split(',')[:3]
        for actor in actors:
            actor = actor.strip()
            if actor and actor.lower() != 'nan':
                weights['actors'][actor] = weights['actors'].get(actor, 0) + 1

    print(f"计算的权重: {weights}")
    return weights


def sort_weight_map(weight_map, limit=None):
    """Sort a weight dictionary by weight desc, then name asc."""
    if not isinstance(weight_map, dict):
        return {}

    items = sorted(weight_map.items(), key=lambda item: (-item[1], item[0]))
    if isinstance(limit, int) and limit > 0:
        items = items[:limit]
    return {key: value for key, value in items}


def build_recommendation_reason_summary(user_preferences, count_weights, recommend_type):
    """Build concise recommendation reasons for the page header."""
    reasons = []
    top_genres = list(sort_weight_map(count_weights.get('genres', {}), limit=3).keys())
    top_directors = list(sort_weight_map(count_weights.get('directors', {}), limit=2).keys())
    top_actors = list(sort_weight_map(count_weights.get('actors', {}), limit=2).keys())

    if top_genres:
        reasons.append(f"偏好{'、'.join(top_genres)}题材")

    if top_directors:
        reasons.append(f"更常选择{'、'.join(top_directors)}相关作品")

    if top_actors:
        reasons.append(f"关注演员{'、'.join(top_actors)}参演内容")

    ratings = []
    years = []
    for pref in user_preferences:
        try:
            rating = float(pref.get('rating', 0) or 0)
        except (TypeError, ValueError):
            rating = 0.0
        if rating > 0:
            ratings.append(rating)

        try:
            year = int(float(pref.get('year', 0) or 0))
        except (TypeError, ValueError):
            year = 0
        if year > 0:
            years.append(year)

    if ratings:
        avg_rating = sum(ratings) / len(ratings)
        if avg_rating >= 8:
            reasons.append("更常选择高分影片")
        elif avg_rating >= 7:
            reasons.append("偏好口碑较好的内容")

    current_year = datetime.now().year
    recent_years = [year for year in years if year >= current_year - 5]
    if recent_years and len(recent_years) >= max(1, len(years) // 2):
        reasons.append("近期更关注近年的新片风格")

    if not reasons:
        default_reason = "结合你近期的观影偏好生成推荐" if recommend_type == 'movie' else "结合你近期的追剧偏好生成推荐"
        reasons.append(default_reason)

    return reasons[:5]


def normalize_recommendation_item(item, recommend_type):
    """Normalize recommendation fields for stable API output."""
    normalized = dict(item)
    normalized['genres'] = parse_multi_value(normalized.get('genres', []))

    try:
        rating = float(normalized.get('rating', 0) or 0)
    except (TypeError, ValueError):
        rating = 0.0
    normalized['rating'] = round(rating, 1)

    try:
        final_score = float(normalized.get('final_score', 0) or 0)
    except (TypeError, ValueError):
        final_score = 0.0

    final_score = max(0.0, min(final_score, 1.0))
    normalized['final_score'] = round(final_score, 4)
    normalized['recommend_match_score'] = int(round(final_score * 100))
    normalized['type'] = normalized.get('type') or recommend_type
    normalized['content_type'] = normalized.get('content_type') or recommend_type
    normalized['cover_url'] = str(normalized.get('cover_url', '') or '')
    normalized['director'] = str(normalized.get('director', '') or '').strip()
    normalized['actors'] = str(normalized.get('actors', '') or '').strip()
    normalized['title'] = str(normalized.get('title', '') or normalized.get('name', '') or '').strip()
    return normalized


def calculate_content_similarity(row, user_data):
    """计算内容相似度（增强版）"""
    user_preferences = user_data.get('preferences', [])
    if not user_preferences:
        # 无偏好时返回随机相似度，确保结果变化
        return random.uniform(0.4, 0.6)

    # 简单的关键词匹配
    item_genres = set(str(row.get('genres', '')).split(','))
    item_director = str(row.get('director', '')).strip()
    item_actors = set(str(row.get('actors', '')).split(',')[:3])

    similarity_score = 0
    match_count = 0

    for pref in user_preferences:
        pref_genres = set(str(pref.get('genres', '')).split(','))
        pref_director = str(pref.get('director', '')).strip()
        pref_actors = set(str(pref.get('actors', '')).split(',')[:3])

        # 计算匹配度
        genre_match = len(item_genres & pref_genres) / max(len(item_genres), len(pref_genres), 1)
        director_match = 1 if item_director and item_director == pref_director else 0
        actor_match = len(item_actors & pref_actors) / max(len(item_actors), len(pref_actors), 1)

        pref_score = (genre_match * 0.6) + (director_match * 0.2) + (actor_match * 0.2)
        # 添加微小随机扰动，确保结果变化
        pref_score *= random.uniform(0.98, 1.02)
        similarity_score += pref_score
        match_count += 1

    return similarity_score / max(match_count, 1)


def build_item_text(record):
    """Build a compact text field for TextCNN encoding."""
    fields = [
        str(record.get('title', '')).strip(),
        str(record.get('genres', '')).strip(),
        str(record.get('director', '')).strip(),
        str(record.get('actors', '')).strip(),
        str(record.get('plot', '')).strip(),
    ]
    return ' '.join(part for part in fields if part and part.lower() != 'nan')


def normalize_score_map(score_map):
    """Scale scores into [0, 1] while preserving relative ranking."""
    if not score_map:
        return {}

    values = np.array(list(score_map.values()), dtype=float)
    min_value = float(values.min())
    max_value = float(values.max())
    if max_value - min_value < 1e-8:
        return {key: 1.0 for key in score_map}

    return {
        key: float((value - min_value) / (max_value - min_value))
        for key, value in score_map.items()
    }


def cosine_score(vector_a, vector_b):
    """Return cosine similarity normalized into [0, 1]."""
    a = np.asarray(vector_a, dtype=float)
    b = np.asarray(vector_b, dtype=float)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-8:
        return 0.0

    score = float(np.dot(a, b) / denom)
    return max(0.0, min(1.0, (score + 1.0) / 2.0))


def build_textcnn_scores(items_df, user_preferences):
    """Encode item texts and user history, then score candidates by cosine similarity."""
    if not TEXTCNN_AVAILABLE or items_df.empty or not user_preferences:
        return None

    preference_texts = [build_item_text(pref) for pref in user_preferences]
    preference_texts = [text for text in preference_texts if text]
    item_texts = [build_item_text(row) for _, row in items_df.iterrows()]
    item_texts = [text for text in item_texts if text]
    training_texts = list(dict.fromkeys(preference_texts + item_texts))
    if not training_texts:
        return None

    try:
        encoder = TextCNN()
        encoder.fit(training_texts)
    except Exception as exc:
        print(f"TextCNN initialization failed: {exc}")
        return None

    weighted_vectors = []
    for pref in user_preferences:
        text = build_item_text(pref)
        if not text:
            continue
        try:
            vector = encoder.extract_features(text)
        except Exception:
            continue
        weight = max(1.0, float(pref.get('rating', 0) or 0) / 5.0)
        weighted_vectors.append((np.asarray(vector, dtype=float), weight))

    if not weighted_vectors:
        return None

    total_weight = sum(weight for _, weight in weighted_vectors)
    user_vector = sum(vector * weight for vector, weight in weighted_vectors) / max(total_weight, 1e-8)

    raw_scores = {}
    for _, row in items_df.iterrows():
        item_id = str(row.get('id', ''))
        text = build_item_text(row)
        if not item_id or not text:
            continue
        try:
            item_vector = encoder.extract_features(text)
        except Exception:
            continue
        raw_scores[item_id] = cosine_score(user_vector, item_vector)

    return normalize_score_map(raw_scores) if raw_scores else None


def apply_diversity_strategy(df):
    """应用多样性策略（增强版）"""
    max_recs = Config.MAX_RECOMMENDATIONS

    if df.empty:
        return df

    if len(df) <= max_recs:
        return df

    # 按类型分组，确保类型多样性
    genre_groups = {}
    for idx, row in df.iterrows():
        genres = str(row.get('genres', '')).split(',')[0]  # 取主要类型
        genre = genres.strip() or '未知'
        if genre not in genre_groups:
            genre_groups[genre] = []
        genre_groups[genre].append(row)

    # 从每个类型中选择项目（带随机）
    result = []
    genre_list = list(genre_groups.keys())

    # 打乱类型顺序，确保每次结果不同
    random.shuffle(genre_list)

    while len(result) < max_recs and genre_groups:
        for genre in genre_list:
            if len(result) >= max_recs:
                break

            if genre in genre_groups and genre_groups[genre]:
                # 随机选择该类型中的一个项目
                if len(genre_groups[genre]) > 1:
                    selected_idx = random.randint(0, len(genre_groups[genre]) - 1)
                    selected = genre_groups[genre].pop(selected_idx)
                else:
                    selected = genre_groups[genre].pop(0)

                result.append(selected)

                # 移除空类型
                if not genre_groups[genre]:
                    del genre_groups[genre]
                    genre_list.remove(genre)

    # 如果还有空位，补充剩余项目（随机选择）
    if len(result) < max_recs:
        remaining_indices = [r.name for r in result] if result else []
        remaining = df[~df.index.isin(remaining_indices)]

        # 随机选择剩余项目
        if len(remaining) > 0:
            additional = remaining.sample(min(max_recs - len(result), len(remaining)))
            result.extend(additional.to_dict('records'))

    return pd.DataFrame(result[:max_recs])


def safe_write_json(file_path, data):
    """安全写入JSON文件"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[OK] Wrote JSON: {file_path}")
        return True
    except Exception as e:
        print(f"[ERR] Failed to write JSON: {e}")
        return False


def safe_read_json(file_path, default=None):
    """Safely read a JSON file with fallback."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def calculate_item_score(row, preference_weights, user_data, ncf_scores=None):
    """计算项目综合得分（增强版，确保结果变化）"""
    score = 0.0
    item_id = str(row.get('id', ''))

    # 1. NCF预测得分（使用权重配置）
    if ncf_scores and item_id in ncf_scores:
        score += ncf_scores[item_id] * Config.RECOMMENDATION_WEIGHTS.get('similarity', 0.05)
        # 添加随机扰动
        score *= random.uniform(0.95, 1.05)
    else:
        # 回退到内容特征得分（带随机）
        content_sim = calculate_content_similarity(row, user_data)
        score += content_sim * Config.RECOMMENDATION_WEIGHTS.get('similarity', 0.05)

    # 2. 类型偏好得分（使用权重配置）
    genre_score = 0.0
    genres = str(row.get('genres', '')).split(',')
    for genre in genres:
        genre = genre.strip()
        genre_score += preference_weights['genres'].get(genre, 0.0)

    max_genre_score = len([g for g in genres if g.strip()])
    if max_genre_score > 0:
        genre_score = min(genre_score / max_genre_score, 1.0)
    score += genre_score * Config.RECOMMENDATION_WEIGHTS.get('genre_preference', 0.7)

    # 3. 质量得分（评分+年份，使用权重配置）
    rating_score = min(float(row.get('rating', 0)) / 10, 1.0)
    year_score = max(0, 1 - (datetime.now().year - int(row.get('year', 0))) / 20) if row.get('year') else 0.5
    quality_score = (rating_score * 0.7 + year_score * 0.3)
    # 添加随机扰动
    quality_score *= random.uniform(0.9, 1.1)
    score += quality_score * Config.RECOMMENDATION_WEIGHTS.get('rating', 0.1)

    # 4. 内容相似度得分（使用权重配置）
    score += calculate_content_similarity(row, user_data) * Config.RECOMMENDATION_WEIGHTS.get('user_preference', 0.1)

    # 5. 多样性得分（使用权重配置）
    diversity_score = row.get('diversity_score', 0.5)
    score += diversity_score * Config.RECOMMENDATION_WEIGHTS.get('popularity', 0.02)

    # 负反馈惩罚
    if item_id in [item['id'] for item in user_data.get('disliked_items', [])]:
        score *= Config.NEGATIVE_FEEDBACK_PENALTY

    # 最终随机扰动（确保权重不变时结果也变化）
    score *= random.uniform(0.98, 1.02)

    return score


def calculate_item_score(row, preference_weights, user_data, ncf_scores=None, textcnn_scores=None):
    """Blend NCF, TextCNN and rule-based signals with graceful fallback."""
    item_id = str(row.get('id', ''))
    weighted_score = 0.0
    active_weight = 0.0

    ncf_weight = 0.35
    text_weight = 0.30
    genre_weight = 0.20
    quality_weight = 0.10
    diversity_weight = 0.05

    if ncf_scores and item_id in ncf_scores:
        weighted_score += ncf_scores[item_id] * ncf_weight
        active_weight += ncf_weight

    if textcnn_scores and item_id in textcnn_scores:
        weighted_score += textcnn_scores[item_id] * text_weight
        active_weight += text_weight
    else:
        fallback_content = calculate_content_similarity(row, user_data)
        weighted_score += fallback_content * text_weight
        active_weight += text_weight

    genre_score = 0.0
    genres = str(row.get('genres', '')).split(',')
    for genre in genres:
        genre = genre.strip()
        genre_score += preference_weights['genres'].get(genre, 0.0)

    max_genre_score = len([g for g in genres if g.strip()])
    if max_genre_score > 0:
        genre_score = min(genre_score / max_genre_score, 1.0)
    weighted_score += genre_score * genre_weight
    active_weight += genre_weight

    rating_score = min(float(row.get('rating', 0)) / 10, 1.0)
    year_score = max(0, 1 - (datetime.now().year - int(row.get('year', 0))) / 20) if row.get('year') else 0.5
    quality_score = rating_score * 0.7 + year_score * 0.3
    weighted_score += quality_score * quality_weight
    active_weight += quality_weight

    diversity_score = row.get('diversity_score', 0.5)
    weighted_score += diversity_score * diversity_weight
    active_weight += diversity_weight

    score = weighted_score / max(active_weight, 1e-8)

    if item_id in [item['id'] for item in user_data.get('disliked_items', [])]:
        score *= Config.NEGATIVE_FEEDBACK_PENALTY

    return float(score)


def calculate_diversity_score(row, items_df):
    """计算多样性得分"""
    item_genres = set(str(row.get('genres', '')).split(',')) - {''}
    return len(item_genres) / 5  # 归一化到0-1


def generate_personalized_recommendations(recommend_type):
    """生成个性化推荐（确保每次结果变化）"""
    # 设置随机种子（每次调用都使用新的种子）
    random.seed(datetime.now().timestamp())
    print(f"\n开始生成{recommend_type}推荐...")

    # 加载数据集
    items_df = load_dataset(recommend_type)
    if items_df.empty:
        print("❌ 数据集为空")
        return [{"id": "0", "title": f"{recommend_type}数据为空", "genres": "", "rating": 0, "cover_url": ""}]

    items_df = preprocess_dataset(items_df)

    # 获取用户数据
    user_data = init_or_repair_user_data()
    user_preferences = user_data.get('preferences', [])
    user_behavior = user_data.get('behavior', [])

    # 过滤黑名单
    blacklist = [item['item_id'] for item in user_data.get('blacklist', []) if item.get('item_type') == recommend_type]
    if blacklist:
        items_df = items_df[~items_df['id'].isin(blacklist)]
        print(f"应用黑名单过滤后剩余{len(items_df)}条数据")

    # NCF推荐核心逻辑（降低触发门槛）
    ncf_scores = None
    ncf_recommender = None

    # 即使只有少量数据也尝试使用NCF
    if NCF_AVAILABLE:
        try:
            ncf_recommender = NCFRecommender()
            if ncf_recommender.train(items_df, user_preferences, user_behavior):
                ncf_scores = ncf_recommender.predict_scores(items_df)
                print(f"✅ 使用NCF模型生成推荐（基于{len(user_preferences)}个偏好）")
        except Exception as e:
            print(f"⚠️ NCF模型训练失败: {str(e)}")

    # 计算多样性得分
    items_df['diversity_score'] = items_df.apply(
        lambda row: calculate_diversity_score(row, items_df),
        axis=1
    )

    # 获取偏好权重（使用原始计数值）
    preference_weights = calculate_preference_weights(user_preferences)

    # 计算最终得分（带随机扰动）
    items_df['final_score'] = items_df.apply(
        lambda row: calculate_item_score(row, preference_weights, user_data, ncf_scores),
        axis=1
    )

    # 排序（带随机）
    items_df = items_df.sort_values('final_score', ascending=False)

    # 添加随机扰动到排序
    items_df['final_score'] = items_df['final_score'] * np.random.uniform(0.98, 1.02, size=len(items_df))
    items_df = items_df.sort_values('final_score', ascending=False)

    # 应用多样性策略（带随机）
    final_result = apply_diversity_strategy(items_df)

    # 最终随机化（确保结果变化）
    if len(final_result) > 5:
        # 固定Top5保证质量，后面的随机打乱
        top5 = final_result.head(5)
        rest = final_result.iloc[5:].sample(frac=1, random_state=int(datetime.now().timestamp()))
        final_result = pd.concat([top5, rest])

    print(f"✅ 生成{len(final_result)}条推荐结果")
    return final_result.head(Config.MAX_RECOMMENDATIONS).to_dict('records')


def generate_and_save_recommendations(recommend_type, force_refresh=False):
    """生成并保存推荐结果（权重不变时也刷新）"""
    try:
        recommendations = generate_personalized_recommendations(recommend_type)

        # 更新用户最后刷新时间
        user_data = init_or_repair_user_data()
        user_data['last_refresh_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 更新count_weights
        user_data['count_weights'] = calculate_preference_weights(user_data.get('preferences', []))
        safe_write_json(Config.USER_DATA_FILE, user_data)

        output_data = {
            "code": 0,
            "user_id": "user_default",
            "data": recommendations,
            "count_weights": user_data.get('count_weights', {}).get('genres', {}),
            "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "refreshed": True,
            "algorithm_version": "NCF_v2.0",
            "algorithm_type": "Neural Collaborative Filtering with Randomization",
            "refresh_reason": "forced_refresh" if force_refresh else "regular_update"
        }

        output_path = Config.RECOMMEND_OUTPUT_PATH[recommend_type]
        safe_write_json(output_path, output_data)

        print(f"✅ {recommend_type}推荐已更新并保存到 {output_path}")
        return True

    except Exception as e:
        print(f"❌ 推荐生成失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# 新增：强制刷新函数
def generate_personalized_recommendations(recommend_type, force_refresh=False):
    """Generate recommendations with NCF + TextCNN + rule fusion."""
    random.seed(datetime.now().timestamp())
    print(f"\nGenerating {recommend_type} recommendations...")

    items_df = load_dataset(recommend_type)
    if items_df.empty:
        print("Dataset is empty.")
        return [{"id": "0", "title": f"{recommend_type} dataset is empty", "genres": "", "rating": 0, "cover_url": ""}]

    items_df = preprocess_dataset(items_df)

    user_data = init_or_repair_user_data()
    user_preferences = user_data.get('preferences', [])
    user_behavior = user_data.get('behavior', [])

    blacklist = [item['item_id'] for item in user_data.get('blacklist', []) if item.get('item_type') == recommend_type]
    if blacklist:
        items_df = items_df[~items_df['id'].isin(blacklist)]
        print(f"Applied blacklist, remaining items: {len(items_df)}")

    ncf_scores = None
    recommendation_signature = build_recommendation_signature(
        recommend_type,
        items_df,
        user_preferences,
        user_behavior,
    )
    if NCF_AVAILABLE:
        try:
            ncf_scores = load_cached_ncf_scores(recommend_type, recommendation_signature)
            if ncf_scores is None:
                ncf_recommender = NCFRecommender()
                if ncf_recommender.train(items_df, user_preferences, user_behavior):
                    raw_ncf_scores = ncf_recommender.predict_scores(items_df)
                    ncf_scores = normalize_score_map(raw_ncf_scores)
                    save_cached_ncf_scores(recommend_type, recommendation_signature, raw_ncf_scores)
                    print(f"NCF scores ready for {len(user_preferences)} preferences")
        except Exception as exc:
            print(f"NCF training failed: {exc}")

    textcnn_scores = build_textcnn_scores(items_df, user_preferences)
    if textcnn_scores:
        print(f"TextCNN scores ready for {len(user_preferences)} preferences")
    else:
        print("TextCNN unavailable, using rule-based content fallback")

    items_df['diversity_score'] = items_df.apply(
        lambda row: calculate_diversity_score(row, items_df),
        axis=1
    )

    preference_weights = calculate_preference_weights(user_preferences)
    items_df['final_score'] = items_df.apply(
        lambda row: calculate_item_score(row, preference_weights, user_data, ncf_scores, textcnn_scores),
        axis=1
    )

    items_df = items_df.sort_values('final_score', ascending=False)
    items_df['final_score'] = items_df['final_score'] * np.random.uniform(0.98, 1.02, size=len(items_df))
    items_df = items_df.sort_values('final_score', ascending=False)

    final_result = apply_diversity_strategy(items_df)
    if len(final_result) > 5:
        top5 = final_result.head(5)
        rest = final_result.iloc[5:].sample(frac=1, random_state=int(datetime.now().timestamp()))
        final_result = pd.concat([top5, rest])

    print(f"Generated {len(final_result)} recommendations.")
    return final_result.head(Config.MAX_RECOMMENDATIONS).to_dict('records')


def generate_and_save_recommendations(recommend_type, force_refresh=False):
    """Generate and persist recommendations for the API."""
    try:
        recommendations = generate_personalized_recommendations(recommend_type, force_refresh=force_refresh)

        user_data = init_or_repair_user_data()
        user_data['last_refresh_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_data['count_weights'] = calculate_preference_weights(user_data.get('preferences', []))
        safe_write_json(Config.USER_DATA_FILE, user_data)

        output_data = {
            "code": 0,
            "user_id": "user_default",
            "data": recommendations,
            "count_weights": user_data.get('count_weights', {}).get('genres', {}),
            "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "refreshed": True,
            "algorithm_version": "NCF_TextCNN_v3.0",
            "algorithm_type": "NCF + TextCNN + Rule Fusion",
            "refresh_reason": "forced_refresh" if force_refresh else "regular_update"
        }

        output_path = Config.RECOMMEND_OUTPUT_PATH[recommend_type]
        safe_write_json(output_path, output_data)
        print(f"Saved {recommend_type} recommendations to {output_path}")
        return True
    except Exception as exc:
        print(f"Recommendation generation failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def safe_read_csv(file_path):
    """Read CSV with utf-8/gbk fallback."""
    for encoding in ('utf-8', 'gbk'):
        try:
            return pd.read_csv(file_path, encoding=encoding)
        except Exception:
            continue
    return pd.DataFrame()


def parse_multi_value(value):
    """Normalize text/list fields into a clean list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()
    if not text:
        return []

    if text.startswith('[') and text.endswith(']'):
        try:
            parsed = json.loads(text.replace("'", '"'))
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass

    return [part.strip() for part in text.split(',') if part.strip() and part.strip().lower() != 'nan']


def get_dataset_id_sets(force_reload=False):
    """Cache dataset ids for content type inference."""
    if force_reload or not hasattr(get_dataset_id_sets, '_cache'):
        cache = {'movie': set(), 'series': set()}
        for content_type in ('movie', 'series'):
            path = Config.DATASET_PATHS.get(content_type)
            df = safe_read_csv(path) if path and os.path.exists(path) else pd.DataFrame()
            if not df.empty:
                if 'id' not in df.columns:
                    if 'movie_id' in df.columns:
                        df = df.rename(columns={'movie_id': 'id'})
                    elif 'drama_id' in df.columns:
                        df = df.rename(columns={'drama_id': 'id'})
                if 'id' in df.columns:
                    cache[content_type] = set(df['id'].astype(str))
        get_dataset_id_sets._cache = cache
    return get_dataset_id_sets._cache


def infer_content_type(item, dataset_ids=None, default_type='movie'):
    """Infer whether an item belongs to movie or series."""
    explicit_type = str(item.get('content_type') or item.get('type') or '').strip().lower()
    if explicit_type in ('movie', 'series'):
        return explicit_type

    item_id = str(item.get('id', '')).strip()
    dataset_ids = dataset_ids or get_dataset_id_sets()
    if item_id and item_id in dataset_ids.get('movie', set()):
        return 'movie'
    if item_id and item_id in dataset_ids.get('series', set()):
        return 'series'
    return default_type


def normalize_preference_item(item, default_type='movie', dataset_ids=None):
    """Normalize one preference record and attach content_type."""
    item_id = str(item.get('id', '')).strip()
    if not item_id:
        return None

    name = str(item.get('name', '') or item.get('title', '')).strip() or item_id
    content_type = infer_content_type(item, dataset_ids=dataset_ids, default_type=default_type)
    return {
        'id': item_id,
        'name': name,
        'title': str(item.get('title', '') or name).strip() or name,
        'genres': parse_multi_value(item.get('genres', [])),
        'rating': item.get('rating', 0),
        'cover_url': item.get('cover_url', ''),
        'year': item.get('year', 0),
        'director': str(item.get('director', '')).strip(),
        'actors': ', '.join(parse_multi_value(item.get('actors', []))),
        'plot': str(item.get('plot', '')).strip(),
        'content_type': content_type,
    }


def normalize_preferences_payload(preferences):
    """Convert preference payload into movie/series buckets."""
    dataset_ids = get_dataset_id_sets()
    normalized = {'movie': [], 'series': []}

    if isinstance(preferences, dict):
        for content_type in ('movie', 'series'):
            for item in preferences.get(content_type, []) or []:
                if not isinstance(item, dict):
                    continue
                normalized_item = normalize_preference_item(item, default_type=content_type, dataset_ids=dataset_ids)
                if normalized_item:
                    normalized[content_type].append(normalized_item)
        return normalized

    if isinstance(preferences, list):
        for item in preferences:
            if not isinstance(item, dict):
                continue
            normalized_item = normalize_preference_item(item, dataset_ids=dataset_ids)
            if normalized_item:
                normalized[normalized_item['content_type']].append(normalized_item)

    return normalized


def normalize_behavior_payload(behavior):
    """Convert behavior payload into movie/series buckets."""
    dataset_ids = get_dataset_id_sets()
    normalized = {'movie': [], 'series': []}

    if isinstance(behavior, dict):
        for content_type in ('movie', 'series'):
            for event in behavior.get(content_type, []) or []:
                if not isinstance(event, dict):
                    continue
                item_type = infer_content_type(event, dataset_ids=dataset_ids, default_type=content_type)
                event_copy = dict(event)
                event_copy['item_type'] = item_type
                normalized[item_type].append(event_copy)
        return normalized

    if isinstance(behavior, list):
        for event in behavior:
            if not isinstance(event, dict):
                continue
            item_type = infer_content_type({'id': event.get('item_id', ''), **event}, dataset_ids=dataset_ids)
            event_copy = dict(event)
            event_copy['item_type'] = item_type
            normalized[item_type].append(event_copy)
    return normalized


def ensure_count_weight_buckets(count_weights):
    """Ensure movie/series weight buckets exist."""
    empty_weights = {'genres': {}, 'directors': {}, 'actors': {}}
    if isinstance(count_weights, dict) and 'movie' in count_weights and 'series' in count_weights:
        count_weights.setdefault('movie', json.loads(json.dumps(empty_weights)))
        count_weights.setdefault('series', json.loads(json.dumps(empty_weights)))
        return count_weights

    return {
        'movie': json.loads(json.dumps(empty_weights)),
        'series': json.loads(json.dumps(empty_weights)),
    }


def get_preferences_for_type(user_data, recommend_type):
    preferences = normalize_preferences_payload(user_data.get('preferences', {}))
    return preferences.get(recommend_type, [])


def get_behavior_for_type(user_data, recommend_type):
    behavior = normalize_behavior_payload(user_data.get('behavior', {}))
    return behavior.get(recommend_type, [])


def get_count_weights_for_type(user_data, recommend_type):
    count_weights = ensure_count_weight_buckets(user_data.get('count_weights', {}))
    return count_weights.get(recommend_type, {'genres': {}, 'directors': {}, 'actors': {}})


def init_or_repair_user_data():
    """Initialize user data and migrate legacy flat preference structures."""
    user_data_path = Config.USER_DATA_FILE
    print(f"加载用户数据: {user_data_path}")

    if os.path.exists(user_data_path):
        with open(user_data_path, 'r', encoding='utf-8') as f:
            try:
                user_data = json.load(f)
            except Exception as exc:
                print(f"读取用户数据失败: {exc}")
                user_data = {}
    else:
        print("[ERR] User data file missing, creating a new one")
        user_data = {}

    normalized_preferences = normalize_preferences_payload(user_data.get('preferences', {}))
    normalized_behavior = normalize_behavior_payload(user_data.get('behavior', {}))
    count_weights = ensure_count_weight_buckets(user_data.get('count_weights', {}))

    postgres_preferences = get_user_preferences()
    if postgres_preferences.get('movie') or postgres_preferences.get('series'):
        normalized_preferences = {
            'movie': postgres_preferences.get('movie', []),
            'series': postgres_preferences.get('series', []),
        }

    count_weights['movie'] = calculate_preference_weights(normalized_preferences['movie'])
    count_weights['series'] = calculate_preference_weights(normalized_preferences['series'])

    user_data['preferences'] = normalized_preferences
    user_data['behavior'] = normalized_behavior
    user_data.setdefault('blacklist', [])
    user_data.setdefault('disliked_items', [])
    user_data['count_weights'] = count_weights
    user_data.setdefault('last_refresh_time', '')
    user_data.setdefault('last_updated', '')

    print(
        f"[OK] Loaded user data, movie preferences: {len(normalized_preferences['movie'])}, "
        f"series preferences: {len(normalized_preferences['series'])}"
    )

    postgres_disliked_records = get_negative_feedback_records()
    if postgres_disliked_records:
        existing_ids = {str(item.get('id', '')).strip() for item in user_data.get('disliked_items', [])}
        merged = list(user_data.get('disliked_items', []))
        for item in postgres_disliked_records:
            if item['id'] not in existing_ids:
                merged.append(item)
                existing_ids.add(item['id'])
        user_data['disliked_items'] = merged

    return user_data


def calculate_preference_weights(user_preferences):
    """Count genre/director/actor preferences from normalized preference items."""
    weights = {'genres': {}, 'directors': {}, 'actors': {}}
    for pref in user_preferences:
        for genre in parse_multi_value(pref.get('genres', [])):
            weights['genres'][genre] = weights['genres'].get(genre, 0) + 1

        director = str(pref.get('director', '')).strip()
        if director and director.lower() != 'nan':
            weights['directors'][director] = weights['directors'].get(director, 0) + 1

        for actor in parse_multi_value(pref.get('actors', []))[:3]:
            weights['actors'][actor] = weights['actors'].get(actor, 0) + 1

    print(f"计算的权重: {weights}")
    return weights


def calculate_content_similarity(row, user_data):
    """Compute rule-based content similarity against typed user preferences."""
    recommend_type = user_data.get('_active_type', 'movie')
    user_preferences = get_preferences_for_type(user_data, recommend_type)
    if not user_preferences:
        return random.uniform(0.4, 0.6)

    item_genres = set(parse_multi_value(row.get('genres', [])))
    item_director = str(row.get('director', '')).strip()
    item_actors = set(parse_multi_value(row.get('actors', []))[:3])

    similarity_score = 0.0
    match_count = 0
    for pref in user_preferences:
        pref_genres = set(parse_multi_value(pref.get('genres', [])))
        pref_director = str(pref.get('director', '')).strip()
        pref_actors = set(parse_multi_value(pref.get('actors', []))[:3])

        genre_match = len(item_genres & pref_genres) / max(len(item_genres), len(pref_genres), 1)
        director_match = 1.0 if item_director and item_director == pref_director else 0.0
        actor_match = len(item_actors & pref_actors) / max(len(item_actors), len(pref_actors), 1)
        similarity_score += (genre_match * 0.6) + (director_match * 0.2) + (actor_match * 0.2)
        match_count += 1

    return similarity_score / max(match_count, 1)


def add_negative_feedback(item_id, item_type='movie', reason=''):
    """Record negative feedback in user data."""
    user_data = init_or_repair_user_data()
    disliked_items = user_data.get('disliked_items', [])
    item_id = str(item_id).strip()
    add_negative_feedback_record('user_default', item_id, item_type, reason)
    if not any(str(item.get('id', '')).strip() == item_id for item in disliked_items):
        disliked_items.append({
            'id': item_id,
            'item_type': item_type,
            'reason': reason,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    user_data['disliked_items'] = disliked_items
    safe_write_json(Config.USER_DATA_FILE, user_data)
    return True


def get_model_cache_dir():
    """Return the directory used to cache recommendation artifacts."""
    cache_dir = os.path.join(Config.BASE_DIR, 'cache', 'models')
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def build_recommendation_signature(recommend_type, items_df, user_preferences, user_behavior):
    """Build a stable signature for one recommendation context."""
    id_series = items_df['id'].astype(str).tolist() if 'id' in items_df.columns else []
    payload = {
        'recommend_type': recommend_type,
        'dataset_ids': id_series,
        'preferences': user_preferences,
        'behavior': user_behavior,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def get_ncf_cache_path(recommend_type, signature):
    """Return the local cache file path for NCF scores."""
    return os.path.join(get_model_cache_dir(), f'ncf_{recommend_type}_{signature}.json')


def load_cached_ncf_scores(recommend_type, signature):
    """Load cached NCF scores if available."""
    cache_path = get_ncf_cache_path(recommend_type, signature)
    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        scores = data.get('scores', {})
        if isinstance(scores, dict) and scores:
            print(f"Loaded cached NCF scores from {cache_path}")
            return normalize_score_map({str(key): float(value) for key, value in scores.items()})
    except Exception as exc:
        print(f"Failed to load cached NCF scores: {exc}")
    return None


def save_cached_ncf_scores(recommend_type, signature, scores):
    """Persist NCF scores to speed up later refresh jobs."""
    if not isinstance(scores, dict) or not scores:
        return

    payload = {
        'recommend_type': recommend_type,
        'signature': signature,
        'generated_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'scores': scores,
    }
    safe_write_json(get_ncf_cache_path(recommend_type, signature), payload)


def calculate_item_score(row, preference_weights, user_data, ncf_scores=None, textcnn_scores=None):
    """Blend signals while preserving relative genre preference strength."""
    item_id = str(row.get('id', ''))
    weighted_score = 0.0
    active_weight = 0.0

    ncf_weight = 0.30
    text_weight = 0.22
    genre_weight = 0.33
    quality_weight = 0.10
    diversity_weight = 0.05

    if ncf_scores and item_id in ncf_scores:
        weighted_score += ncf_scores[item_id] * ncf_weight
        active_weight += ncf_weight

    if textcnn_scores and item_id in textcnn_scores:
        weighted_score += textcnn_scores[item_id] * text_weight
        active_weight += text_weight
    else:
        fallback_content = calculate_content_similarity(row, user_data)
        weighted_score += fallback_content * text_weight
        active_weight += text_weight

    genre_weights = preference_weights.get('genres', {})
    max_genre_weight = max(genre_weights.values(), default=1.0)
    item_genres = parse_multi_value(row.get('genres', []))
    genre_score_raw = sum(float(genre_weights.get(genre, 0.0)) for genre in item_genres)
    if item_genres:
        genre_score = min(genre_score_raw / (len(item_genres) * max_genre_weight), 1.0)
    else:
        genre_score = 0.0

    primary_genre = item_genres[0] if item_genres else ''
    primary_genre_score = float(genre_weights.get(primary_genre, 0.0)) / max(max_genre_weight, 1.0)
    genre_score = min(1.0, genre_score * 0.8 + primary_genre_score * 0.2)
    weighted_score += genre_score * genre_weight
    active_weight += genre_weight

    rating_score = min(float(row.get('rating', 0) or 0) / 10, 1.0)
    year_score = max(0, 1 - (datetime.now().year - int(row.get('year', 0) or 0)) / 20) if row.get('year') else 0.5
    quality_score = rating_score * 0.75 + year_score * 0.25
    weighted_score += quality_score * quality_weight
    active_weight += quality_weight

    diversity_score = row.get('diversity_score', 0.5)
    weighted_score += diversity_score * diversity_weight
    active_weight += diversity_weight

    score = weighted_score / max(active_weight, 1e-8)
    disliked_ids = get_negative_feedback_ids('user_default', user_data.get('_active_type')) or {
        str(item.get('id', '')).strip()
        for item in user_data.get('disliked_items', [])
        if str(item.get('id', '')).strip()
    }
    if item_id in disliked_ids:
        score *= Config.NEGATIVE_FEEDBACK_PENALTY
    return float(score)


def apply_diversity_strategy(df):
    """Apply a deterministic diversity strategy without random reordering."""
    max_recs = Config.MAX_RECOMMENDATIONS
    if df.empty or len(df) <= max_recs:
        return df

    sorted_df = df.sort_values(['final_score', 'rating'], ascending=[False, False]).copy()
    genre_pick_count = {}
    selected_rows = []

    for _, row in sorted_df.iterrows():
        primary_genres = parse_multi_value(row.get('genres', []))
        primary_genre = primary_genres[0] if primary_genres else 'unknown'
        picked = genre_pick_count.get(primary_genre, 0)

        if picked >= 3 and len(selected_rows) < max_recs - 2:
            continue

        selected_rows.append(row.to_dict())
        genre_pick_count[primary_genre] = picked + 1
        if len(selected_rows) >= max_recs:
            break

    if len(selected_rows) < max_recs:
        selected_ids = {str(row.get('id', '')) for row in selected_rows}
        for _, row in sorted_df.iterrows():
            item_id = str(row.get('id', ''))
            if item_id in selected_ids:
                continue
            selected_rows.append(row.to_dict())
            selected_ids.add(item_id)
            if len(selected_rows) >= max_recs:
                break

    return pd.DataFrame(selected_rows[:max_recs])


def get_score_cache_path(model_name, recommend_type, signature):
    """Return a cache file path for cached score maps."""
    return os.path.join(get_model_cache_dir(), f'{model_name}_{recommend_type}_{signature}.json')


def load_cached_score_map(model_name, recommend_type, signature):
    """Load a cached score map and normalize it."""
    cache_path = get_score_cache_path(model_name, recommend_type, signature)
    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        scores = data.get('scores', {})
        if isinstance(scores, dict) and scores:
            print(f"Loaded cached {model_name} scores from {cache_path}")
            return normalize_score_map({str(key): float(value) for key, value in scores.items()})
    except Exception as exc:
        print(f"Failed to load cached {model_name} scores: {exc}")
    return None


def save_cached_score_map(model_name, recommend_type, signature, scores):
    """Persist a score map for later reuse."""
    if not isinstance(scores, dict) or not scores:
        return

    payload = {
        'model_name': model_name,
        'recommend_type': recommend_type,
        'signature': signature,
        'generated_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'scores': scores,
    }
    safe_write_json(get_score_cache_path(model_name, recommend_type, signature), payload)


def get_current_recommendation_signature(recommend_type):
    """Compute the current signature for one recommendation type."""
    items_df = load_dataset(recommend_type)
    if items_df.empty:
        return ''

    items_df = preprocess_dataset(items_df)
    user_data = init_or_repair_user_data()
    user_preferences = get_preferences_for_type(user_data, recommend_type)
    user_behavior = get_behavior_for_type(user_data, recommend_type)
    return build_recommendation_signature(recommend_type, items_df, user_preferences, user_behavior)


def build_recommendation_reason_summary(user_preferences, count_weights, recommend_type):
    """Build richer recommendation reasons for the page header."""
    reasons = []
    top_genres = list(sort_weight_map(count_weights.get('genres', {}), limit=3).keys())
    top_directors = list(sort_weight_map(count_weights.get('directors', {}), limit=2).keys())
    top_actors = list(sort_weight_map(count_weights.get('actors', {}), limit=2).keys())

    if top_genres:
        reasons.append(f"偏好{'、'.join(top_genres)}题材")
    if len(top_genres) >= 2:
        reasons.append(f"近期兴趣主要集中在{'、'.join(top_genres[:2])}风格")
    if top_directors:
        reasons.append(f"更常选择{'、'.join(top_directors)}相关作品")
    if top_actors:
        reasons.append(f"关注演员{'、'.join(top_actors)}参演内容")

    ratings = []
    years = []
    for pref in user_preferences:
        try:
            rating = float(pref.get('rating', 0) or 0)
        except (TypeError, ValueError):
            rating = 0.0
        if rating > 0:
            ratings.append(rating)

        try:
            year = int(float(pref.get('year', 0) or 0))
        except (TypeError, ValueError):
            year = 0
        if year > 0:
            years.append(year)

    if ratings:
        avg_rating = sum(ratings) / len(ratings)
        if avg_rating >= 8:
            reasons.append("更常选择高分影片")
        elif avg_rating >= 7:
            reasons.append("偏好口碑较好的内容")

    current_year = datetime.now().year
    recent_years = [year for year in years if year >= current_year - 5]
    if recent_years and len(recent_years) >= max(1, len(years) // 2):
        reasons.append("近期更关注近年的新片风格")

    if user_preferences:
        reasons.append(f"本次推荐综合参考了{len(user_preferences)}条历史偏好")

    if not reasons:
        default_reason = "结合你近期的观影偏好生成推荐" if recommend_type == 'movie' else "结合你近期的追剧偏好生成推荐"
        reasons.append(default_reason)

    deduped = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)
    return deduped[:6]


def build_textcnn_scores(items_df, user_preferences, recommend_type=None, signature=None):
    """Encode item texts and user history, then score candidates by cosine similarity."""
    if not TEXTCNN_AVAILABLE or items_df.empty or not user_preferences:
        return None

    if recommend_type and signature:
        cached_scores = load_cached_score_map('textcnn', recommend_type, signature)
        if cached_scores is not None:
            return cached_scores

    preference_texts = [build_item_text(pref) for pref in user_preferences]
    preference_texts = [text for text in preference_texts if text]
    item_texts = [build_item_text(row) for _, row in items_df.iterrows()]
    item_texts = [text for text in item_texts if text]
    training_texts = list(dict.fromkeys(preference_texts + item_texts))
    if not training_texts:
        return None

    try:
        encoder = TextCNN()
        encoder.fit(training_texts)
    except Exception as exc:
        print(f"TextCNN initialization failed: {exc}")
        return None

    weighted_vectors = []
    for pref in user_preferences:
        text = build_item_text(pref)
        if not text:
            continue
        try:
            vector = encoder.extract_features(text)
        except Exception:
            continue
        weight = max(1.0, float(pref.get('rating', 0) or 0) / 5.0)
        weighted_vectors.append((np.asarray(vector, dtype=float), weight))

    if not weighted_vectors:
        return None

    total_weight = sum(weight for _, weight in weighted_vectors)
    user_vector = sum(vector * weight for vector, weight in weighted_vectors) / max(total_weight, 1e-8)

    raw_scores = {}
    for _, row in items_df.iterrows():
        item_id = str(row.get('id', ''))
        text = build_item_text(row)
        if not item_id or not text:
            continue
        try:
            item_vector = encoder.extract_features(text)
        except Exception:
            continue
        raw_scores[item_id] = cosine_score(user_vector, item_vector)

    if recommend_type and signature and raw_scores:
        save_cached_score_map('textcnn', recommend_type, signature, raw_scores)
    return normalize_score_map(raw_scores) if raw_scores else None


def generate_personalized_recommendations(recommend_type, force_refresh=False):
    """Generate recommendations with NCF + TextCNN + typed preference buckets."""
    print(f"\nGenerating {recommend_type} recommendations...")

    items_df = load_dataset(recommend_type)
    if items_df.empty:
        print("Dataset is empty.")
        return [{"id": "0", "title": f"{recommend_type} dataset is empty", "genres": "", "rating": 0, "cover_url": ""}]

    items_df = preprocess_dataset(items_df)

    user_data = init_or_repair_user_data()
    active_user_data = dict(user_data)
    active_user_data['_active_type'] = recommend_type
    user_preferences = get_preferences_for_type(user_data, recommend_type)
    user_behavior = get_behavior_for_type(user_data, recommend_type)

    blacklist = [item['item_id'] for item in user_data.get('blacklist', []) if item.get('item_type') == recommend_type]
    if blacklist:
        items_df = items_df[~items_df['id'].isin(blacklist)]
        print(f"Applied blacklist, remaining items: {len(items_df)}")

    recommendation_signature = build_recommendation_signature(
        recommend_type,
        items_df,
        user_preferences,
        user_behavior,
    )

    ncf_scores = None
    if NCF_AVAILABLE:
        try:
            ncf_scores = load_cached_ncf_scores(recommend_type, recommendation_signature)
            if ncf_scores is None:
                ncf_recommender = NCFRecommender()
                if ncf_recommender.train(items_df, user_preferences, user_behavior):
                    raw_ncf_scores = ncf_recommender.predict_scores(items_df)
                    ncf_scores = normalize_score_map(raw_ncf_scores)
                    save_cached_ncf_scores(recommend_type, recommendation_signature, raw_ncf_scores)
                    print(f"NCF scores ready for {len(user_preferences)} preferences")
        except Exception as exc:
            print(f"NCF training failed: {exc}")

    textcnn_scores = build_textcnn_scores(items_df, user_preferences, recommend_type, recommendation_signature)
    if textcnn_scores:
        print(f"TextCNN scores ready for {len(user_preferences)} preferences")
    else:
        print("TextCNN unavailable, using rule-based content fallback")

    items_df['diversity_score'] = items_df.apply(lambda row: calculate_diversity_score(row, items_df), axis=1)
    preference_weights = calculate_preference_weights(user_preferences)
    items_df['final_score'] = items_df.apply(
        lambda row: calculate_item_score(row, preference_weights, active_user_data, ncf_scores, textcnn_scores),
        axis=1
    )

    final_result = apply_diversity_strategy(items_df)
    final_result = final_result.sort_values(['final_score', 'rating'], ascending=[False, False])

    print(f"Generated {len(final_result)} recommendations.")
    return [
        normalize_recommendation_item(item, recommend_type)
        for item in final_result.head(Config.MAX_RECOMMENDATIONS).to_dict('records')
    ]


def get_candidate_pool_size():
    """Return how many high-score items to keep for refresh rotation."""
    return max(int(Config.MAX_RECOMMENDATIONS) * 3, 30)


def build_candidate_pool(items_df, recommend_type):
    """Keep a larger high-score pool so refresh can rotate content without recomputing."""
    if items_df is None or items_df.empty:
        return []

    sorted_df = items_df.sort_values(['final_score', 'rating'], ascending=[False, False]).copy()
    pool_size = min(len(sorted_df), get_candidate_pool_size())
    pool_records = sorted_df.head(pool_size).to_dict('records')
    return [normalize_recommendation_item(item, recommend_type) for item in pool_records if isinstance(item, dict)]


def pick_refresh_variant(candidate_pool, recommend_type, recent_ids=None):
    """Pick one display batch from the candidate pool while avoiding immediate repeats."""
    if not isinstance(candidate_pool, list) or not candidate_pool:
        return []

    max_recs = int(Config.MAX_RECOMMENDATIONS)
    recent_ids = {str(item_id) for item_id in (recent_ids or []) if str(item_id).strip()}
    available_pool = [item for item in candidate_pool if str(item.get('id', '')) not in recent_ids]
    if len(available_pool) < max_recs:
        available_pool = list(candidate_pool)

    weighted_candidates = []
    for index, item in enumerate(available_pool):
        score = item.get('recommend_match_score', item.get('final_score', 0))
        try:
            numeric_score = float(score)
            if numeric_score > 1:
                numeric_score = numeric_score / 100.0
        except (TypeError, ValueError):
            numeric_score = 0.0

        rank_bonus = max(0.05, 1.0 - (index / max(len(available_pool), 1)) * 0.45)
        weight = max(0.05, numeric_score) * rank_bonus
        weighted_candidates.append((dict(item), weight))

    selected = []
    while weighted_candidates and len(selected) < min(max_recs, len(candidate_pool)):
        total_weight = sum(weight for _, weight in weighted_candidates)
        pick = random.random() * total_weight if total_weight > 0 else 0
        cumulative = 0.0
        chosen_index = 0

        for idx, (_, weight) in enumerate(weighted_candidates):
            cumulative += weight
            if cumulative >= pick:
                chosen_index = idx
                break

        chosen_item, _ = weighted_candidates.pop(chosen_index)
        selected.append(chosen_item)

    selected.sort(
        key=lambda item: (
            float(item.get('recommend_match_score', 0) or 0),
            float(item.get('final_score', 0) or 0),
            float(item.get('rating', 0) or 0),
        ),
        reverse=True,
    )
    return selected[:max_recs]


def rotate_cached_recommendations(recommend_type):
    """Refresh the displayed recommendation batch from the cached candidate pool."""
    output_path = Config.RECOMMEND_OUTPUT_PATH[recommend_type]
    recommend_data = safe_read_json(output_path, {}) if os.path.exists(output_path) else {}
    candidate_pool = recommend_data.get('candidate_pool', [])
    if not isinstance(candidate_pool, list) or not candidate_pool:
        return {'ok': False, 'error': 'missing_candidate_pool'}

    recent_display_ids = recommend_data.get('recent_display_ids', [])
    if not isinstance(recent_display_ids, list):
        recent_display_ids = []

    rotated_data = pick_refresh_variant(candidate_pool, recommend_type, recent_ids=recent_display_ids)
    if not rotated_data:
        return {'ok': False, 'error': 'failed_to_rotate_recommendations'}

    recommend_data['data'] = rotated_data
    recommend_data['generated_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    recommend_data['refresh_reason'] = 'candidate_pool_rotation'
    recommend_data['refreshed'] = True
    recommend_data['rotation_count'] = int(recommend_data.get('rotation_count', 0) or 0) + 1
    recommend_data['recent_display_ids'] = [
        str(item.get('id', ''))
        for item in rotated_data
        if str(item.get('id', '')).strip()
    ]
    safe_write_json(output_path, recommend_data)
    return {
        'ok': True,
        'reused': True,
        'rotated': True,
        'signature': str(recommend_data.get('signature', '') or ''),
    }


def generate_and_save_recommendations(recommend_type, force_refresh=False):
    """Generate and save typed recommendations and weight metadata."""
    try:
        current_signature = get_current_recommendation_signature(recommend_type)
        output_path = Config.RECOMMEND_OUTPUT_PATH[recommend_type]
        existing_data = safe_read_json(output_path, {}) if os.path.exists(output_path) else {}
        cached_signature = str(existing_data.get('signature', '') or '')

        if current_signature and cached_signature == current_signature and not force_refresh:
            existing_data['generated_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            existing_data['refresh_reason'] = 'cache_reused'
            existing_data['refreshed'] = False
            safe_write_json(output_path, existing_data)
            print(f"Reused cached recommendations for {recommend_type}")
            return {
                'ok': True,
                'reused': True,
                'signature': current_signature,
            }

        items_df = load_dataset(recommend_type)
        if items_df.empty:
            return {
                'ok': False,
                'reused': False,
                'error': 'dataset_empty',
            }

        items_df = preprocess_dataset(items_df)

        user_data = init_or_repair_user_data()
        active_user_data = dict(user_data)
        active_user_data['_active_type'] = recommend_type
        user_preferences = get_preferences_for_type(user_data, recommend_type)
        user_behavior = get_behavior_for_type(user_data, recommend_type)

        blacklist = [item['item_id'] for item in user_data.get('blacklist', []) if item.get('item_type') == recommend_type]
        if blacklist:
            items_df = items_df[~items_df['id'].isin(blacklist)]

        recommendation_signature = build_recommendation_signature(
            recommend_type,
            items_df,
            user_preferences,
            user_behavior,
        )

        ncf_scores = None
        if NCF_AVAILABLE:
            try:
                ncf_scores = load_cached_ncf_scores(recommend_type, recommendation_signature)
                if ncf_scores is None:
                    ncf_recommender = NCFRecommender()
                    if ncf_recommender.train(items_df, user_preferences, user_behavior):
                        raw_ncf_scores = ncf_recommender.predict_scores(items_df)
                        ncf_scores = normalize_score_map(raw_ncf_scores)
                        save_cached_ncf_scores(recommend_type, recommendation_signature, raw_ncf_scores)
            except Exception as exc:
                print(f"NCF training failed: {exc}")

        textcnn_scores = build_textcnn_scores(items_df, user_preferences, recommend_type, recommendation_signature)
        items_df['diversity_score'] = items_df.apply(lambda row: calculate_diversity_score(row, items_df), axis=1)
        preference_weights = calculate_preference_weights(user_preferences)
        items_df['final_score'] = items_df.apply(
            lambda row: calculate_item_score(row, preference_weights, active_user_data, ncf_scores, textcnn_scores),
            axis=1
        )

        candidate_pool = build_candidate_pool(items_df, recommend_type)
        recommendations = pick_refresh_variant(candidate_pool, recommend_type)

        user_data['last_refresh_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_data['count_weights'] = {
            'movie': calculate_preference_weights(get_preferences_for_type(user_data, 'movie')),
            'series': calculate_preference_weights(get_preferences_for_type(user_data, 'series')),
        }
        safe_write_json(Config.USER_DATA_FILE, user_data)
        current_weights = get_count_weights_for_type(user_data, recommend_type)
        current_weights = {
            'genres': sort_weight_map(current_weights.get('genres', {})),
            'directors': sort_weight_map(current_weights.get('directors', {})),
            'actors': sort_weight_map(current_weights.get('actors', {})),
        }
        recommend_reasons_summary = build_recommendation_reason_summary(
            get_preferences_for_type(user_data, recommend_type),
            current_weights,
            recommend_type,
        )

        output_data = {
            "code": 0,
            "user_id": "user_default",
            "data": recommendations,
            "count_weights": current_weights,
            "recommend_reasons_summary": recommend_reasons_summary,
            "candidate_pool": candidate_pool,
            "candidate_pool_size": len(candidate_pool),
            "recent_display_ids": [
                str(item.get('id', ''))
                for item in recommendations
                if str(item.get('id', '')).strip()
            ],
            "rotation_count": 0,
            "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "refreshed": True,
            "algorithm_version": "NCF_TextCNN_v3.1",
            "algorithm_type": "NCF + TextCNN + Rule Fusion",
            "refresh_reason": "forced_refresh" if force_refresh else "regular_update",
            "signature": current_signature,
        }

        safe_write_json(output_path, output_data)
        print(f"Saved {recommend_type} recommendations to {output_path}")
        return {
            'ok': True,
            'reused': False,
            'signature': current_signature,
        }
    except Exception as exc:
        print(f"Recommendation generation failed: {exc}")
        import traceback
        traceback.print_exc()
        return {
            'ok': False,
            'reused': False,
            'error': str(exc),
        }


def force_refresh_all_recommendations():
    """强制刷新所有类型的推荐"""
    print("\n=== 强制刷新所有推荐 ===")
    generate_and_save_recommendations('movie', force_refresh=True)
    generate_and_save_recommendations('series', force_refresh=True)
    print("✅ 所有推荐已强制刷新！")


# 测试代码
if __name__ == "__main__":
    # 测试强制刷新
    force_refresh_all_recommendations()
