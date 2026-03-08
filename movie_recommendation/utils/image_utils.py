import requests
import os
import hashlib
from urllib.parse import urlparse
from flask import make_response
from config import Config


def detect_image_type(image_data):
    """检测图片类型（替代 imghdr，兼容 Python 3.13+）"""
    if not image_data:
        return 'jpeg'
    
    if image_data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    elif image_data[:3] == b'\xff\xd8\xff':
        return 'jpeg'
    elif image_data[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'
    elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
        return 'webp'
    elif image_data[:2] == b'BM':
        return 'bmp'
    else:
        return 'jpeg'  # 默认

def is_allowed_domain(url):
    """检查URL域名是否在允许列表中"""
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        # 检查是否是允许的域名或子域名
        for allowed_domain in Config.ALLOWED_IMAGE_DOMAINS:
            if domain == allowed_domain or domain.endswith(f'.{allowed_domain}'):
                return True
        return False
    except:
        return False


def proxy_image(url):
    """代理获取图片"""
    try:
        if not url or not is_allowed_domain(url):
            return None

        # 生成缓存文件名
        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_path = os.path.join(Config.CACHE_DIR, f"{url_hash}.img")

        # 检查缓存
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    image_data = f.read()
                return image_data
            except:
                os.remove(cache_path)

        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://movie.douban.com/',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

        # 发送请求获取图片
        response = requests.get(
            url,
            headers=headers,
            timeout=Config.PROXY_TIMEOUT,
            stream=True,
            verify=False
        )
        response.raise_for_status()

        # 获取图片数据
        image_data = response.content

        # 保存到缓存
        try:
            with open(cache_path, 'wb') as f:
                f.write(image_data)
        except:
            pass

        return image_data

    except requests.exceptions.RequestException as e:
        print(f"图片获取失败: {str(e)}")
        return None