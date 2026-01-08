from difflib import SequenceMatcher
from typing import List
import re
import jieba

def calculate_similarity(a: str, b: str) -> float:
    """计算文本相似度"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def extract_keywords(text: str) -> List[str]:
    """提取中文关键词"""
    # 使用jieba分词
    words = jieba.lcut(text)
    # 过滤停用词和标点
    stop_words = {'的', '了', '是', '我', '你', '他', '在', '有', '和', '就', '不', '人', '都', '一', '一个', '上',
                  '也', '很', '到', '说', '要', '去', '看', '电影', '电视剧', '剧'}
    keywords = [word for word in words if len(word) > 1 and word not in stop_words and not re.match(r'^\W+$', word)]
    return keywords


def parse_natural_language(query):
    """解析自然语言查询"""
    params = {
        'keywords': [],
        'genres': [],
        'year': None,
        'rating': None,
        'director': None,
        'actor': None
    }

    # 提取关键词
    keywords = extract_keywords(query)
    params['keywords'] = keywords

    # 提取年份（如：2023年、2020）
    year_pattern = r'(\d{4})年?'
    year_match = re.search(year_pattern, query)
    if year_match:
        params['year'] = int(year_match.group(1))

    # 提取类型（如：科幻、动作片）
    genre_keywords = {'科幻', '动作', '喜剧', '爱情', '悬疑', '惊悚', '恐怖', '纪录片', '动画', '冒险', '犯罪', '剧情'}
    for genre in genre_keywords:
        if genre in query:
            params['genres'].append(genre)

    # 提取评分（如：评分8分以上、高分）
    rating_pattern = r'评分(\d+)分'
    rating_match = re.search(rating_pattern, query)
    if rating_match:
        params['rating'] = int(rating_match.group(1))

    return params