from utils.text_utils import extract_keywords, calculate_similarity, parse_natural_language
from data.dataset_loader import load_dataset
from config import Config


def search_in_dataset(df, search_params):
    """在数据集中搜索"""
    results = []
    keywords = search_params.get('keywords', [])

    for _, row in df.iterrows():
        match_score = 0

        # 标题匹配
        title = str(row.get('title', ''))
        title_score = calculate_similarity(' '.join(keywords), title)
        match_score += title_score * 0.5

        # 描述匹配（如果有）
        description = str(row.get('description', ''))
        desc_score = calculate_similarity(' '.join(keywords), description)
        match_score += desc_score * 0.2

        # 类型匹配
        genres = str(row.get('genres', ''))
        genre_score = sum(1 for kw in keywords if kw in genres) / max(len(keywords), 1)
        match_score += genre_score * 0.2

        # 导演/演员匹配
        director = str(row.get('director', ''))
        actors = str(row.get('actors', ''))
        person_score = sum(1 for kw in keywords if kw in director or kw in actors) / max(len(keywords), 1)
        match_score += person_score * 0.1

        if match_score >= Config.SEARCH_THRESHOLD:
            item = row.to_dict()
            item['match_score'] = match_score
            results.append(item)

    return results


def smart_search(query, content_type=None):
    """智能搜索（支持自然语言）"""
    # 解析自然语言查询
    search_params = parse_natural_language(query)

    # 加载相关数据集
    results = []

    if content_type:
        types_to_search = [content_type]
    else:
        types_to_search = ['movie', 'series']

    for c_type in types_to_search:
        df = load_dataset(c_type)
        if df.empty:
            continue

        # 执行搜索
        type_results = search_in_dataset(df, search_params)
        for item in type_results:
            item['content_type'] = c_type
        results.extend(type_results)

    # 按相似度排序
    results.sort(key=lambda x: x.get('match_score', 0), reverse=True)

    # 应用过滤器
    if search_params.get('genres'):
        results = [r for r in results if any(g in r.get('genres', '') for g in search_params['genres'])]

    if search_params.get('year'):
        year = search_params['year']
        results = [r for r in results if str(r.get('year', '')) == str(year)]

    return results[:Config.MAX_SEARCH_RESULTS]


def search_drama_by_name(drama_name):
    """根据剧集名称查询详细信息"""
    from data.dataset_loader import load_dataset

    # 读取CSV文件
    drama_df = load_dataset('series')
    if drama_df.empty:
        return None

    # 搜索匹配的剧集
    best_match = None
    best_score = 0

    for _, row in drama_df.iterrows():
        title = str(row.get('title', '')).strip()
        if not title:
            continue

        # 计算相似度
        similarity = calculate_similarity(drama_name, title)

        # 完全匹配优先
        if drama_name.lower() == title.lower():
            best_match = row
            best_score = 1.0
            break

        # 相似度超过阈值
        if similarity > 0.7 and similarity > best_score:
            best_match = row
            best_score = similarity

    if best_match is not None:
        result = {
            "id": str(best_match.get('id', '')),
            "title": str(best_match.get('title', '')),
            "name": str(best_match.get('name', str(best_match.get('title', '')))),
            "genres": str(best_match.get('genres', '')),
            "rating": str(best_match.get('rating', '')),
            "cover_url": str(best_match.get('cover_url', '')),
            "coverUrl": str(best_match.get('cover_url', '')),
            "year": str(best_match.get('year', '')),
            "director": str(best_match.get('director', '')),
            "actors": str(best_match.get('actors', '')),
            "popularity": str(best_match.get('popularity', '')),
            "similarity_score": best_score,
            "episodes": str(best_match.get('episodes', best_match.get('total_episodes', '未知集数'))),
            "region": str(best_match.get('region', best_match.get('area', '未知地区'))),
            "status": str(best_match.get('status', '完结'))
        }
        return result

    return None


def batch_search_dramas(drama_names):
    """批量查询剧集信息"""
    results = []

    for name in drama_names:
        drama_name = str(name).strip()
        if not drama_name:
            continue

        result = search_drama_by_name(drama_name)
        if result:
            results.append({
                'name_requested': drama_name,
                'matched_title': result['title'],
                'data': result,
                'similarity_score': result['similarity_score']
            })
        else:
            results.append({
                'name_requested': drama_name,
                'matched_title': drama_name,
                'data': None,
                'error': f'未找到该剧集: {drama_name}',
                'similarity_score': 0
            })

    return results