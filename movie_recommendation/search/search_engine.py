from config import Config
from data.dataset_loader import load_dataset
from db.content_repository import (
    find_content_item_by_name as find_content_item_by_name_db,
    find_content_items_by_names as find_content_items_by_names_db,
    search_content_items as search_content_items_db,
)
from utils.text_utils import calculate_similarity, parse_natural_language


def search_in_dataset(df, search_params):
    """Fallback CSV search kept for compatibility when DB is unavailable."""
    results = []
    keywords = search_params.get('keywords', [])
    keyword_text = ' '.join(keywords).strip()

    for _, row in df.iterrows():
        match_score = 0

        title = str(row.get('title', ''))
        if keyword_text:
            match_score += calculate_similarity(keyword_text, title) * 0.5

        description = str(row.get('description', '') or row.get('plot', ''))
        if keyword_text:
            match_score += calculate_similarity(keyword_text, description) * 0.2

        genres = str(row.get('genres', ''))
        genre_score = sum(1 for kw in keywords if kw in genres) / max(len(keywords), 1)
        match_score += genre_score * 0.2

        director = str(row.get('director', ''))
        actors = str(row.get('actors', ''))
        person_score = sum(1 for kw in keywords if kw in director or kw in actors) / max(len(keywords), 1)
        match_score += person_score * 0.1

        if match_score >= Config.SEARCH_THRESHOLD:
            item = row.to_dict()
            item['match_score'] = match_score
            item['similarity_score'] = match_score
            results.append(item)

    return results


def _apply_search_filters(results, search_params):
    filtered = list(results or [])

    if search_params.get('genres'):
        filtered = [r for r in filtered if any(g in str(r.get('genres', '')) for g in search_params['genres'])]

    if search_params.get('year'):
        year = str(search_params['year'])
        filtered = [r for r in filtered if str(r.get('year', '')) == year]

    return filtered


def _finalize_item(item, content_type=None):
    normalized = dict(item or {})
    normalized['id'] = str(normalized.get('id', '') or '')
    normalized['title'] = str(normalized.get('title', '') or normalized.get('name', '') or '')
    normalized['name'] = str(normalized.get('name', '') or normalized['title'])
    normalized['cover_url'] = str(normalized.get('cover_url', '') or normalized.get('coverUrl', '') or '')
    normalized['coverUrl'] = normalized['cover_url']
    normalized['content_type'] = normalized.get('content_type') or content_type or normalized.get('type', '')
    if 'match_score' in normalized and 'similarity_score' not in normalized:
        normalized['similarity_score'] = normalized['match_score']
    return normalized


def smart_search(query, content_type=None):
    """Database-first smart search with CSV fallback."""
    search_params = parse_natural_language(query)

    db_results = search_content_items_db(query, content_type=content_type, limit=Config.MAX_SEARCH_RESULTS)
    if db_results:
        db_results = [_finalize_item(item, content_type) for item in db_results]
        db_results = _apply_search_filters(db_results, search_params)
        return db_results[:Config.MAX_SEARCH_RESULTS]

    results = []
    types_to_search = [content_type] if content_type else ['movie', 'series']

    for c_type in types_to_search:
        df = load_dataset(c_type)
        if df.empty:
            continue
        type_results = search_in_dataset(df, search_params)
        for item in type_results:
            item['content_type'] = c_type
            item['type'] = c_type
        results.extend(type_results)

    results.sort(key=lambda x: x.get('match_score', 0), reverse=True)
    results = [_finalize_item(item, item.get('content_type')) for item in results]
    results = _apply_search_filters(results, search_params)
    return results[:Config.MAX_SEARCH_RESULTS]


def search_item_by_name(item_name, item_type='movie'):
    """Find the best-matching single item, preferring DB search."""
    db_result = find_content_item_by_name_db(item_name, content_type=item_type)
    if db_result:
        return _finalize_item(db_result, item_type)

    df = load_dataset(item_type)
    if df.empty:
        return None

    best_match = None
    best_score = 0
    normalized_name = str(item_name or '').strip()

    for _, row in df.iterrows():
        title = str(row.get('title', '')).strip()
        if not title:
            continue

        similarity = calculate_similarity(normalized_name, title)
        if normalized_name.lower() == title.lower():
            best_match = row
            best_score = 1.0
            break

        if similarity > 0.7 and similarity > best_score:
            best_match = row
            best_score = similarity

    if best_match is None:
        return None

    result = best_match.to_dict()
    result['similarity_score'] = best_score
    result['match_score'] = best_score
    return _finalize_item(result, item_type)


def batch_search_items_by_names(item_names, item_type='movie'):
    """Batch version of single-item search."""
    db_results = find_content_items_by_names_db(item_names, content_type=item_type)
    if db_results:
        normalized_results = []
        for entry in db_results:
            item = entry.get('data')
            normalized_results.append({
                'name_requested': entry.get('name_requested', ''),
                'matched_title': entry.get('matched_title', ''),
                'data': _finalize_item(item, item_type) if item else None,
                'similarity_score': entry.get('similarity_score', 0),
            })
        return normalized_results

    results = []
    for raw_name in item_names or []:
        normalized_name = str(raw_name or '').strip()
        if not normalized_name:
            continue

        result = search_item_by_name(normalized_name, item_type)
        if result:
            results.append({
                'name_requested': normalized_name,
                'matched_title': result['title'],
                'data': result,
                'similarity_score': result.get('similarity_score', result.get('match_score', 0)),
            })
        else:
            results.append({
                'name_requested': normalized_name,
                'matched_title': normalized_name,
                'data': None,
                'error': f'未找到该内容: {normalized_name}',
                'similarity_score': 0,
            })
    return results


def search_drama_by_name(drama_name):
    return search_item_by_name(drama_name, 'series')


def batch_search_dramas(drama_names):
    return batch_search_items_by_names(drama_names, 'series')
