import json
import os
import traceback
from config import Config

def safe_read_json(file_path, default_value=None):
    try:
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return default_value

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                print(f"文件为空: {file_path}")
                return default_value

        return json.loads(content)

    except json.JSONDecodeError as e:
        print(f"JSON解析错误 ({file_path}): {str(e)}")
        return default_value
    except Exception as e:
        print(f"读取文件错误 ({file_path}): {str(e)}")
        traceback.print_exc()
        return default_value


def safe_write_json(file_path, data):
    try:
        dir_path = os.path.dirname(file_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"写入文件错误 ({file_path}): {str(e)}")
        traceback.print_exc()
        return False