from datetime import datetime
from collections import defaultdict, Counter
from utils.file_utils import safe_read_json, safe_write_json
from config import Config

def init_or_repair_user_data():
    default_data = {
        "userId": "user_default",
        "preferences": [],
        "count_weights": {},
        "negative_feedback": [],
        "watch_history": [],
        "liked_items": [],
        "disliked_items": [],
        "blacklist": []
    }

    user_data = safe_read_json(Config.USER_DATA_FILE, default_data)

    # 确保所有字段存在
    for key, default_value in default_data.items():
        if key not in user_data:
            user_data[key] = default_value

    # 清理过期的黑名单
    current_time = datetime.now()
    user_data['blacklist'] = [
        item for item in user_data['blacklist']
        if (current_time - datetime.strptime(item['added_at'], "%Y-%m-%d %H:%M:%S")).days < Config.BLACKLIST_DURATION
    ]

    if user_data != safe_read_json(Config.USER_DATA_FILE):
        safe_write_json(Config.USER_DATA_FILE, user_data)

    return user_data


def calculate_count_weights(preferences):
    """增强版权重计算"""
    tag_counts = defaultdict(int)

    for item in preferences:
        genres = item.get('genres', [])

        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split(',') if g.strip()]
        elif not isinstance(genres, list):
            genres = []

        for genre in genres:
            if genre:
                tag_counts[genre] += 1

    return dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True))


def calculate_preference_weights(preferences):
    """细粒度偏好分析"""
    genre_counter = Counter()
    director_counter = Counter()
    actor_counter = Counter()
    year_counter = Counter()

    for item in preferences:
        # 类型权重
        genres = item.get('genres', '')
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split(',') if g.strip()]
        for genre in genres:
            genre_counter[genre] += 1

        # 导演权重
        director = item.get('director', '')
        if director:
            director_counter[director] += 1

        # 演员权重
        actors = item.get('actors', '')
        if isinstance(actors, str):
            actors = [a.strip() for a in actors.split(',') if a.strip()]
        for actor in actors[:3]:
            actor_counter[actor] += 1

        # 年份权重
        year = item.get('year', 0)
        if year:
            decade = (year // 10) * 10
            year_counter[decade] += 1

    # 归一化权重
    total_genres = sum(genre_counter.values())
    total_directors = sum(director_counter.values())
    total_actors = sum(actor_counter.values())

    weights = {
        'genres': {genre: count / total_genres for genre, count in genre_counter.items()} if total_genres > 0 else {},
        'directors': {director: count / total_directors for director, count in
                      director_counter.items()} if total_directors > 0 else {},
        'actors': {actor: count / total_actors for actor, count in actor_counter.items()} if total_actors > 0 else {},
        'years': year_counter
    }

    return weights


def add_negative_feedback(item_id, item_type, reason=""):
    """添加负反馈"""
    user_data = init_or_repair_user_data()

    feedback_entry = {
        "item_id": item_id,
        "item_type": item_type,
        "reason": reason,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    user_data['negative_feedback'].append(feedback_entry)
    user_data['disliked_items'].append({"id": item_id, "type": item_type})

    # 添加到黑名单
    user_data['blacklist'].append({
        "item_id": item_id,
        "item_type": item_type,
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    safe_write_json(Config.USER_DATA_FILE, user_data)
    return True