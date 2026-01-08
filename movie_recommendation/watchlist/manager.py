from datetime import datetime
from utils.file_utils import safe_read_json, safe_write_json
from config import Config

def manage_watchlist(action, item_id=None, item_type=None, item_data=None):
    """管理想看清单"""
    watchlist = safe_read_json(Config.WATCHLIST_FILE, [])

    if action == 'get':
        if item_type:
            return [item for item in watchlist if item.get('type') == item_type]
        return watchlist

    elif action == 'add':
        # 检查是否已存在
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

    elif action == 'remove':
        new_watchlist = [item for item in watchlist if
                         not (item.get('id') == item_id and item.get('type') == item_type)]
        safe_write_json(Config.WATCHLIST_FILE, new_watchlist)
        return {"status": "success", "message": "已从想看清单移除"}