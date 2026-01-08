import requests
import json
import time
import random
import pandas as pd
import os
from datetime import datetime
import argparse

# --------------------------
# 配置参数（区分电影和电视剧）
# --------------------------
# 电影标签（经测试有效）
MOVIE_TAGS = ['悬疑', '喜剧', '科幻', '动作', '爱情']
# 电视剧标签（选用豆瓣电视剧热门标签，提高成功率）
SERIES_TAGS = ['国产剧', '美剧','韩剧', '剧情', '热门','爱情','悬疑']

# 爬取控制参数
MAX_ITEMS_PER_TAG = 200  # 单类型最大爬取量（电视剧降低频率）
BATCH_SIZE = 10  # 单次请求数量（电视剧减少单次请求）
REQUEST_DELAY_MOVIE = (1, 3)  # 电影请求间隔（秒）
REQUEST_DELAY_SERIES = (5, 8)  # 电视剧请求间隔（更长，避免反爬）
RETRY_LIMIT = 3  # 失败重试次数

# 输出文件路径
OUTPUT_MOVIE_CSV = 'douban_movies.csv'
OUTPUT_SERIES_CSV = 'douban_series.csv'


# --------------------------
# 核心工具函数
# --------------------------
def get_headers(content_type):
    """根据内容类型返回不同请求头（电视剧强化伪装）"""
    # 电视剧请求头（模拟登录用户，更贴近真实浏览）
    if content_type == 'series':
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/127.0"
        ]
        return {
            'Referer': 'https://movie.douban.com/tv/',  # 电视剧专区来源
            'User-Agent': random.choice(user_agents),
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',  # 模拟AJAX请求
            'Cookie': 'bid=kQj836TsAiY; ap_v=0,6.0; _pk_ref.100001.4cf6=%5B%22%22%2C%22%22%2C1752288150%2C%22https%3A%2F%2Fwww.doubao.com%2F%22%5D; _pk_id.100001.4cf6=fe6e4c2709fab2a8.1752288150.; _pk_ses.100001.4cf6=1; __utma=30149280.1100051166.1752288150.1752288150.1752288150.1; __utmb=30149280.0.10.1752288150; __utmc=30149280; __utmz=30149280.1752288150.1.1.utmcsr=doubao.com|utmccn=(referral)|utmcmd=referral|utmcct=/; __utma=223695111.129584487.1752288150.1752288150.1752288150.1; __utmb=223695111.0.10.1752288150; __utmc=223695111; __utmz=223695111.1752288150.1.1.utmcsr=doubao.com|utmccn=(referral)|utmcmd=referral|utmcct=/',  # 替换为自己的Cookie
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive'
        }
    # 电影请求头（保持原有配置）
    else:
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ]
        return {
            'Referer': 'https://movie.douban.com/',
            'User-Agent': random.choice(user_agents),
            'Accept': 'application/json, text/plain, */*'
        }


def fetch_items(content_type, tag, start):
    """请求单页数据（区分电影和电视剧接口）"""
    # 电视剧接口使用type=tv和sort=rank（评分排序更稳定）
    if content_type == 'movie':
        url = f"https://movie.douban.com/j/search_subjects?type=movie&tag={tag}&sort=recommend&page_limit={BATCH_SIZE}&page_start={start}"
    else:
        url = f"https://movie.douban.com/j/search_subjects?type=tv&tag={tag}&sort=rank&page_limit={BATCH_SIZE}&page_start={start}"

    for retry in range(RETRY_LIMIT):
        try:
            headers = get_headers(content_type)
            response = requests.get(url, headers=headers, timeout=15)  # 延长超时时间

            # 检查状态码（200为正常）
            if response.status_code != 200:
                print(
                    f"[{content_type}][{tag}] 第{start}条开始 - 状态码错误：{response.status_code}，重试第{retry + 1}次...")
                time.sleep(2 ** retry)  # 指数退避等待
                continue

            # 解析响应数据
            data = response.json()
            if 'subjects' not in data:
                print(f"[{content_type}][{tag}] 第{start}条开始 - 无数据字段，重试第{retry + 1}次...")
                return None

            # 打印调试信息（确认是否返回数据）
            if len(data['subjects']) == 0:
                print(f"[{content_type}][{tag}] 第{start}条开始 - 该批次无数据")
            else:
                print(f"[{content_type}][{tag}] 第{start}条开始 - 成功获取{len(data['subjects'])}条数据")

            return data['subjects']

        except requests.exceptions.Timeout:
            print(f"[{content_type}][{tag}] 第{start}条开始 - 请求超时，重试第{retry + 1}次...")
        except json.JSONDecodeError:
            print(f"[{content_type}][{tag}] 第{start}条开始 - 数据解析失败，重试第{retry + 1}次...")
        except Exception as e:
            print(f"[{content_type}][{tag}] 第{start}条开始 - 错误：{str(e)}，重试第{retry + 1}次...")

        time.sleep(2 ** retry)  # 重试前等待

    print(f"[{content_type}][{tag}] 第{start}条开始 - 超过最大重试次数，放弃该批次")
    return None


# --------------------------
# 爬取主函数
# --------------------------
def crawl_content(content_type):
    """爬取指定类型（电影/电视剧）数据"""
    # 初始化参数
    if content_type == 'movie':
        tags = MOVIE_TAGS
        output_file = OUTPUT_MOVIE_CSV
        item_type_name = "电影"
        delay_range = REQUEST_DELAY_MOVIE
    else:
        tags = SERIES_TAGS
        output_file = OUTPUT_SERIES_CSV
        item_type_name = "电视剧"
        delay_range = REQUEST_DELAY_SERIES

    items = []
    seen_ids = set()  # 用于去重

    # 加载历史数据（避免重复爬取）
    if os.path.exists(output_file):
        existing_df = pd.read_csv(output_file)
        seen_ids = set(existing_df['id'].astype(str))
        items = existing_df.to_dict('records')
        print(f"检测到历史{item_type_name}数据，已加载 {len(seen_ids)} 条")

    # 遍历标签爬取
    for tag in tags:
        print(f"\n===== 开始爬取【{tag}】类型{item_type_name} =====")
        start = 0
        tag_count = 0  # 记录当前标签爬取数量

        while start < MAX_ITEMS_PER_TAG and tag_count < MAX_ITEMS_PER_TAG:
            # 获取当前批次数据
            subjects = fetch_items(content_type, tag, start)
            if not subjects:
                break  # 无数据则终止当前标签

            # 处理数据（去重+提取字段）
            new_count = 0
            for item in subjects:
                item_id = item['id']
                if item_id in seen_ids:
                    continue  # 跳过已爬取的ID

                # 提取字段（确保与推荐系统兼容）
                items.append({
                    'id': item_id,
                    'title': item['title'],
                    'genres': tag,  # 标签作为类型（简化处理）
                    'rating': item['rate'] if item['rate'] else '0.0',  # 处理无评分
                    'cover_url': item['cover'],  # 封面图URL
                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # 爬取时间
                    'type': content_type  # 区分电影/电视剧
                })

                seen_ids.add(item_id)
                new_count += 1
                tag_count += 1

            # 状态更新
            print(f"[{tag}] 累计爬取：{tag_count}条（本批次新增{new_count}条），总累计：{len(seen_ids)}条")

            # 准备下一批次
            start += BATCH_SIZE

            # 随机延迟（电视剧间隔更长）
            delay = random.uniform(*delay_range)
            print(f"等待{delay:.2f}秒后继续...")
            time.sleep(delay)

            # 达到最大数量则停止
            if tag_count >= MAX_ITEMS_PER_TAG:
                print(f"[{tag}] 已达到单类型最大爬取量（{MAX_ITEMS_PER_TAG}条）")
                break

        print(f"===== 【{tag}】类型{item_type_name}爬取完成，共新增{tag_count}条 =====")

    # 保存数据（处理空数据情况）
    if not items:
        print(f"警告：未爬取到任何{item_type_name}数据，可能被反爬限制")
        return

    # 转换为DataFrame并保存
    df = pd.DataFrame(items)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')

    # 打印数据概览（动态适配存在的列）
    print(f"\n===== {item_type_name}数据爬取完成 =====")
    print(f"总数据量：{len(df)}条，已保存至 {output_file}")
    print("数据示例：")
    print(df[['id', 'title', 'genres', 'rating']].head())


# --------------------------
# 入口函数
# --------------------------
if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='豆瓣电影/电视剧爬虫')
    parser.add_argument('--type', type=str, default='both',
                        choices=['movie', 'series', 'both'],
                        help='爬取类型：movie（电影）、series（电视剧）、both（两者）')
    args = parser.parse_args()

    # 执行爬取
    if args.type == 'movie' or args.type == 'both':
        print("===== 开始爬取电影数据 =====")
        crawl_content('movie')

    if args.type == 'series' or args.type == 'both':
        print("\n===== 开始爬取电视剧数据 =====")
        crawl_content('series')

    print("\n所有爬取任务已完成！")