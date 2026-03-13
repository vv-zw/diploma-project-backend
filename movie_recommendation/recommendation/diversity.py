# import pandas as pd
# from collections import defaultdict
# from config import Config
#
#
# def apply_diversity_strategy(df):
#     """应用多样性策略，确保推荐类型多样化"""
#     if df.empty:
#         return df
#
#     # 按类型分组
#     genre_groups = defaultdict(list)
#     for _, row in df.iterrows():
#         genres = str(row.get('genres', '')).split(',')
#         main_genre = genres[0].strip() if genres else '其他'
#         genre_groups[main_genre].append(row)
#
#     # 轮流从不同类型中选择
#     result = []
#     genre_list = list(genre_groups.keys())
#     max_items_per_genre = Config.MAX_RECOMMENDATIONS // max(len(genre_list), 1) + 2
#
#     # 确保主要类型有足够的代表
#     for i in range(max_items_per_genre):
#         for genre in genre_list:
#             if i < len(genre_groups[genre]):
#                 result.append(genre_groups[genre][i])
#
#     # 转换回DataFrame
#     if result:
#         return pd.DataFrame(result)
#     return df


import pandas as pd
from collections import defaultdict
import os
import sys

# ------------ 修复配置导入 ------------
# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 尝试导入配置，如果失败则创建默认配置
try:
    from config import Config
    config_instance = Config()
    print("[OK] Loaded config")
except (ImportError, ModuleNotFoundError) as e:
    print(f"[WARN] Failed to load config: {e}, using default config")


    # 创建默认配置类
    class DefaultConfig:
        MAX_RECOMMENDATIONS = 20
        DIVERSITY_ENABLED = True
        DIVERSITY_WEIGHT = 0.3


    config_instance = DefaultConfig()


def apply_diversity_strategy(df):
    """应用多样性策略，确保推荐类型多样化"""
    if df.empty:
        return df

    # 获取最大推荐数量（从配置或使用默认值）
    max_recs = getattr(config_instance, 'MAX_RECOMMENDATIONS', 20)

    # 检查是否启用多样性策略
    diversity_enabled = getattr(config_instance, 'DIVERSITY_ENABLED', True)
    if not diversity_enabled:
        return df.head(max_recs)

    # 按类型分组（处理空值和异常格式）
    genre_groups = defaultdict(list)
    for idx, row in df.iterrows():
        # 安全获取类型信息
        genres = str(row.get('genres', '')).strip()
        if not genres or genres.lower() in ['nan', 'none', '未知']:
            main_genre = '其他'
        else:
            genre_list = [g.strip() for g in genres.split(',') if g.strip()]
            main_genre = genre_list[0] if genre_list else '其他'

        genre_groups[main_genre].append(row)

    # 确保至少有一个类型分组
    if not genre_groups:
        return df.head(max_recs)

    # 轮流从不同类型中选择，控制总数
    result = []
    genre_list = list(genre_groups.keys())
    genre_index = {genre: 0 for genre in genre_list}  # 记录每个类型的当前索引

    # 循环获取直到达到最大数量或所有类型都取完
    while len(result) < max_recs:
        added = False

        for genre in genre_list:
            if len(result) >= max_recs:
                break

            # 如果当前类型还有未取的项
            if genre_index[genre] < len(genre_groups[genre]):
                result.append(genre_groups[genre][genre_index[genre]])
                genre_index[genre] += 1
                added = True

        # 如果一轮下来没有添加任何项，说明所有类型都取完了
        if not added:
            break

    # 转换回DataFrame并保持原始索引和列
    if result:
        # 确保返回的DataFrame列与输入一致
        result_df = pd.DataFrame(result)
        # 重新索引以保持连续性
        result_df = result_df.reset_index(drop=True)
        return result_df.head(max_recs)

    return df.head(max_recs)


# 测试代码
if __name__ == "__main__":
    # 创建测试数据
    test_data = {
        'id': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'title': [f'电影{i}' for i in range(1, 11)],
        'genres': ['科幻,动作', '科幻', '动作', '喜剧', '喜剧', '爱情', '爱情', '悬疑', '悬疑', ''],
        'rating': [8.5, 8.2, 7.9, 9.0, 8.8, 7.5, 7.3, 8.7, 8.4, 6.0]
    }

    test_df = pd.DataFrame(test_data)

    # 应用多样性策略
    result_df = apply_diversity_strategy(test_df)

    print("原始数据:")
    print(test_df[['id', 'title', 'genres']])
    print("\n应用多样性策略后:")
    print(result_df[['id', 'title', 'genres']])
    print(f"\n推荐数量: {len(result_df)}")
    print(f"类型分布: {result_df['genres'].value_counts().to_dict()}")
