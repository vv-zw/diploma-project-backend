from datetime import datetime

from config import Config
from db.connection import is_database_enabled
from db.watchlist_repository import add_watchlist_item, clear_watchlist_items, get_watchlist_items, remove_watchlist_item
from utils.file_utils import safe_read_json, safe_write_json


def manage_watchlist(action, item_id=None, item_type=None, item_data=None):
    """Manage watchlist items with PostgreSQL as the primary source."""
    db_enabled = is_database_enabled()

    if action == 'get':
        if db_enabled:
            return get_watchlist_items(content_type=item_type)

    elif action == 'add':
        if db_enabled:
            return add_watchlist_item(item_id, item_type, item_data)

    elif action == 'remove':
        if db_enabled:
            return remove_watchlist_item(item_id, item_type)

    elif action == 'clear':
        if db_enabled:
            return clear_watchlist_items(content_type=item_type)

    watchlist = safe_read_json(Config.WATCHLIST_FILE, [])

    if action == 'get':
        if item_type:
            return [item for item in watchlist if item.get('type') == item_type]
        return watchlist

    if action == 'add':
        for item in watchlist:
            if item.get('id') == item_id and item.get('type') == item_type:
                return {"status": "exists", "message": "already_in_watchlist"}

        watchlist.append({
            "id": item_id,
            "type": item_type,
            "data": item_data,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        safe_write_json(Config.WATCHLIST_FILE, watchlist)
        return {"status": "success", "message": "watchlist_added"}

    if action == 'remove':
        new_watchlist = [
            item for item in watchlist
            if not (item.get('id') == item_id and item.get('type') == item_type)
        ]
        safe_write_json(Config.WATCHLIST_FILE, new_watchlist)
        return {"status": "success", "message": "watchlist_removed"}

    if action == 'clear':
        if item_type:
            retained = [item for item in watchlist if item.get('type') != item_type]
            deleted_count = len(watchlist) - len(retained)
            safe_write_json(Config.WATCHLIST_FILE, retained)
            return {"status": "success", "message": "watchlist_cleared", "deleted_count": deleted_count}

        safe_write_json(Config.WATCHLIST_FILE, [])
        return {"status": "success", "message": "watchlist_cleared", "deleted_count": len(watchlist)}

    return {"status": "unsupported", "message": "unsupported_action"}
