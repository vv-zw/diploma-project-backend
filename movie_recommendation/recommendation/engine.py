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

# ------------ 强制指定config路径（关键修改） ------------
# 直接指定config所在的目录
config_dir = r'D:\pythonProjectmovie，tobacco\movie_recommendation'
sys.path.insert(0, config_dir)

# 手动验证路径
print(f"正在查找config.py于: {config_dir}")
config_file = os.path.join(config_dir, 'config.py')
if os.path.exists(config_file):
    print(f"✅ 找到config.py: {config_file}")
else:
    print(f"❌ 未找到config.py: {config_file}")
    # 列出目录内容帮助排查
    try:
        print("目录内容:")
        for item in os.listdir(config_dir):
            print(f"  - {item}")
    except:
        pass

# 导入config
try:
    from config import Config, init_directories

    print("✅ 成功导入config模块")
except ImportError as e:
    print(f"⚠️ 导入config失败，使用内置配置: {e}")


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
    print("⚠️ TensorFlow/Keras未安装，将使用基于内容的推荐方案")


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


# 数据加载和预处理函数
def load_dataset(recommend_type):
    """从原始CSV加载数据集（优先），降级到推荐结果文件"""
    # 使用项目配置的路径
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
            print(f"✅ 成功加载{len(df)}条数据")
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
        print(f"❌ 数据集文件不存在: {file_path}")

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
                print(f"✅ 成功加载用户数据，偏好数量: {len(user_data.get('preferences', []))}")
            except Exception as e:
                print(f"读取用户数据失败: {e}")
                user_data = {}
    else:
        print(f"❌ 用户数据文件不存在，创建新数据")
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
        print(f"✅ 成功写入JSON: {file_path}")
        return True
    except Exception as e:
        print(f"❌ 写入JSON失败: {e}")
        return False


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
def force_refresh_all_recommendations():
    """强制刷新所有类型的推荐"""
    print("\n=== 强制刷新所有推荐 ===")
    generate_and_save_recommendations('movie', force_refresh=True)
    generate_and_save_recommendations('series', force_refresh=True)
    print("✅ 所有推荐已强制刷新！")


# 初始化目录
init_directories()

# 测试代码
if __name__ == "__main__":
    # 测试强制刷新
    force_refresh_all_recommendations()