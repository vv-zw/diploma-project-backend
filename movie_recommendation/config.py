"""
配置管理模块

提供应用程序的配置管理，支持环境变量和默认配置。
"""
import os
from typing import Dict, List

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency fallback
    load_dotenv = None


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
if load_dotenv:
    load_dotenv(ENV_PATH)


class Config:
    """应用配置类"""
    
    # 获取项目根目录（兼容配置文件在子目录的情况）
    BASE_DIR = BASE_DIR

    # Flask 配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # 服务器配置
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))

    # 数据目录配置
    DATA_DIR = os.path.join(BASE_DIR, "data")
    DATASETS_DIR = os.path.join(DATA_DIR, "datasets")
    USER_DIR = os.path.join(DATA_DIR, "user")
    RECOMMENDATIONS_DIR = os.path.join(DATA_DIR, "recommendations")
    
    # 数据文件路径
    USER_DATA_FILE = os.path.join(USER_DIR, "user_data.json")
    WATCHLIST_FILE = os.path.join(USER_DIR, "watchlist.json")

    # 数据集配置（统一键名）
    DATASET_PATHS: Dict[str, str] = {
        'movie': os.path.join(DATASETS_DIR, "douban_movies.csv"),
        'series': os.path.join(DATASETS_DIR, "douban_series.csv")
    }

    # 推荐结果路径
    RECOMMEND_OUTPUT_PATH: Dict[str, str] = {
        'movie': os.path.join(RECOMMENDATIONS_DIR, "movie_recommendations.json"),
        'series': os.path.join(RECOMMENDATIONS_DIR, "series_recommendations.json")
    }

    # 推荐系统权重配置
    RECOMMENDATION_WEIGHTS: Dict[str, float] = {
        'genre_preference': 0.7,   # 类型偏好权重
        'rating': 0.1,             # 评分权重
        'popularity': 0.02,        # 流行度权重
        'release_year': 0.03,      # 年份权重
        'similarity': 0.05,        # 相似度权重
        'user_preference': 0.1     # 其他用户偏好权重
    }

    # 搜索配置
    SEARCH_THRESHOLD = float(os.getenv('SEARCH_THRESHOLD', 0.6))
    MAX_SEARCH_RESULTS = int(os.getenv('MAX_SEARCH_RESULTS', 30))
    MAX_RECOMMENDATIONS = int(os.getenv('MAX_RECOMMENDATIONS', 20))

    # 负反馈配置
    NEGATIVE_FEEDBACK_PENALTY = 0.3
    BLACKLIST_DURATION = 30  # 天

    # 缓存配置
    CACHE_DIR = os.path.join(BASE_DIR, "cache", "images")
    RECOMMENDATION_CACHE_TIMEOUT = int(os.getenv('RECOMMENDATION_CACHE_TIMEOUT', 300))  # 秒

    # 图片代理配置
    PROXY_TIMEOUT = int(os.getenv('PROXY_TIMEOUT', 15))  # 秒
    ALLOWED_IMAGE_DOMAINS: List[str] = [
        'douban.com',
        'img3.doubanio.com',
        'img9.doubanio.com',
        'movie.douban.com'
    ]

    # 日志配置
    LOG_DIR = os.path.join(BASE_DIR, "logs")
    LOG_FILE = os.path.join(LOG_DIR, "app.log")
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # PostgreSQL 配置
    DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
    DB_ENABLED = os.getenv('DB_ENABLED', 'true').lower() in ('1', 'true', 'yes', 'on')
    PGHOST = os.getenv('PGHOST', '127.0.0.1').strip()
    PGPORT = int(os.getenv('PGPORT', '5432'))
    PGDATABASE = os.getenv('PGDATABASE', 'movie_recommendation').strip()
    PGUSER = os.getenv('PGUSER', 'postgres').strip()
    PGPASSWORD = os.getenv('PGPASSWORD', '')
    PGSCHEMA = os.getenv('PGSCHEMA', 'app').strip() or 'app'

    @classmethod
    def get_database_url(cls) -> str:
        """Return the PostgreSQL connection URL from env vars."""
        if cls.DATABASE_URL:
            return cls.DATABASE_URL
        return (
            f"postgresql://{cls.PGUSER}:{cls.PGPASSWORD}"
            f"@{cls.PGHOST}:{cls.PGPORT}/{cls.PGDATABASE}"
        )

    @classmethod
    def init_app(cls) -> None:
        """初始化应用配置"""
        cls.init_directories()
        cls.validate_config()

    @classmethod
    def init_directories(cls) -> None:
        """初始化必要的目录"""
        directories = [
            cls.DATA_DIR,
            cls.DATASETS_DIR,
            cls.USER_DIR,
            cls.RECOMMENDATIONS_DIR,
            cls.CACHE_DIR,
            cls.LOG_DIR
        ]
        
        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                print(f"⚠️ 创建目录失败 {directory}: {e}")

    @classmethod
    def validate_config(cls) -> None:
        """验证配置的有效性"""
        # 检查数据集文件是否存在
        for dataset_type, path in cls.DATASET_PATHS.items():
            if not os.path.exists(path):
                print(f"⚠️ 数据集文件不存在: {dataset_type} -> {path}")

    @classmethod
    def get_config_info(cls) -> Dict:
        """获取配置信息（用于调试）"""
        return {
            'base_dir': cls.BASE_DIR,
            'debug': cls.DEBUG,
            'host': cls.HOST,
            'port': cls.PORT,
            'datasets': {k: os.path.exists(v) for k, v in cls.DATASET_PATHS.items()},
            'cache_timeout': cls.RECOMMENDATION_CACHE_TIMEOUT,
            'log_level': cls.LOG_LEVEL
        }


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    LOG_LEVEL = 'WARNING'


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


# 配置字典
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env: str = None) -> Config:
    """
    获取配置对象
    
    Args:
        env: 环境名称 (development/production/testing)
        
    Returns:
        Config: 配置对象
    """
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    
    config_class = config_dict.get(env, DevelopmentConfig)
    return config_class


# 自动初始化
try:
    Config.init_app()
except Exception as e:
    print(f"⚠️ 配置初始化警告: {e}")
