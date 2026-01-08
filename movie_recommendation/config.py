import os


class Config:
    # 获取项目根目录（兼容配置文件在子目录的情况）
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 数据文件路径
    USER_DATA_FILE = os.path.join(BASE_DIR, "data", "user_data.json")
    WATCHLIST_FILE = os.path.join(BASE_DIR, "data", "watchlist.json")

    # 数据集配置（统一键名）
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
        'genre_preference': 0.7,  # 类型偏好权重
        'rating': 0.1,  # 评分权重
        'popularity': 0.02,  # 流行度权重
        'release_year': 0.03,  # 年份权重
        'similarity': 0.05,  # 相似度权重
        'user_preference': 0.1  # 其他用户偏好权重
    }

    # 搜索配置
    SEARCH_THRESHOLD = 0.6
    MAX_SEARCH_RESULTS = 30
    MAX_RECOMMENDATIONS = 20

    # 负反馈配置
    NEGATIVE_FEEDBACK_PENALTY = 0.3
    BLACKLIST_DURATION = 30  # 天

    # 图片代理配置
    PROXY_TIMEOUT = 15  # 秒
    ALLOWED_IMAGE_DOMAINS = ['douban.com', 'img3.doubanio.com', 'img9.doubanio.com', 'movie.douban.com']
    CACHE_DIR = os.path.join(BASE_DIR, "cache", "image_cache")


# 安全的初始化函数
def init_directories():
    """初始化必要的目录"""
    # 创建数据目录
    data_dir = os.path.join(Config.BASE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)

    # 创建缓存目录
    os.makedirs(Config.CACHE_DIR, exist_ok=True)

    # 创建日志目录
    log_dir = os.path.join(Config.BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)


# 只在主模块执行时初始化
if __name__ == '__main__':
    init_directories()
else:
    # 确保目录存在
    try:
        init_directories()
    except Exception as e:
        print(f"初始化目录时警告: {e}")