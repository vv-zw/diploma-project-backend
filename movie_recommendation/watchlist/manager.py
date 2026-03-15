from datetime import datetime

from config import Config
from db.watchlist_repository import add_watchlist_item, get_watchlist_items, remove_watchlist_item
from utils.file_utils import safe_read_json, safe_write_json


def manage_watchlist(action, item_id=None, item_type=None, item_data=None):
    """Manage watchlist items with PostgreSQL first and JSON fallback."""
    if action == 'get':
        db_items = get_watchlist_items(content_type=item_type)
        if db_items:
            return db_items

    elif action == 'add':
        db_result = add_watchlist_item(item_id, item_type, item_data)
        if db_result.get('status') in ('success', 'exists'):
            return db_result

    elif action == 'remove':
        db_result = remove_watchlist_item(item_id, item_type)
        if db_result.get('status') == 'success':
            return db_result

    watchlist = safe_read_json(Config.WATCHLIST_FILE, [])

    if action == 'get':
        if item_type:
            return [item for item in watchlist if item.get('type') == item_type]
        return watchlist

    if action == 'add':
        for item in watchlist:
            if item.get('id') == item_id and item.get('type') == item_type:
                return {"status": "exists", "message": "已在想看清单中"}

        watchlist.append({
            "id": item_id,
            "type": item_type,
            "data": item_data,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        safe_write_json(Config.WATCHLIST_FILE, watchlist)
        return {"status": "success", "message": "已添加到想看清单"}

    if action == 'remove':
        new_watchlist = [
            item for item in watchlist
            if not (item.get('id') == item_id and item.get('type') == item_type)
        ]
        safe_write_json(Config.WATCHLIST_FILE, new_watchlist)
        return {"status": "success", "message": "已从想看清单移除"}

    return {"status": "unsupported", "message": "unsupported_action"}
