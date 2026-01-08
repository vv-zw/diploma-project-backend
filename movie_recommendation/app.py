# from flask import Flask, jsonify, request, make_response, send_file
# import os
# import traceback
# from datetime import datetime
# from config import Config
# from utils.file_utils import safe_read_json, safe_write_json
# from utils.image_utils import proxy_image, is_allowed_domain
# from utils.text_utils import calculate_similarity
# from data.dataset_loader import load_dataset, safe_read_csv
# from data.user_manager import init_or_repair_user_data, calculate_count_weights, add_negative_feedback
# from recommendation.engine import generate_and_save_recommendations, generate_personalized_recommendations
# from search.search_engine import smart_search, search_drama_by_name, batch_search_dramas
# from watchlist.manager import manage_watchlist
#
# # Flask应用初始化
# app = Flask(__name__)
# from flask_cors import CORS
#
# CORS(app)  # 解决跨域问题
#
#
# # --------------------------
# # 新增API：获取CSV数据（JSON格式）
# # --------------------------
# @app.route("/api/movies", methods=["GET"])
# def get_movies_data():
#     """获取电影CSV数据（JSON格式）"""
#     try:
#         # 读取CSV文件
#         movie_df = safe_read_csv(Config.DATASET_PATHS['movie'])
#         if movie_df.empty:
#             return jsonify({
#                 "code": 404,
#                 "error": "电影数据文件不存在或为空"
#             }), 404
#
#         # 转换为JSON格式
#         movies_data = movie_df.to_dict('records')
#
#         return jsonify({
#             "code": 0,
#             "data": movies_data,
#             "count": len(movies_data)
#         })
#
#     except Exception as e:
#         print(f"获取电影数据失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({
#             "code": 500,
#             "error": f"服务器错误: {str(e)}"
#         }), 500
#
#
# # --------------------------
# # 新增API：直接下载CSV文件
# # --------------------------
# @app.route("/api/download-csv", methods=["GET"])
# def download_csv():
#     """直接下载CSV文件"""
#     try:
#         csv_path = Config.DATASET_PATHS['movie']
#         if not os.path.exists(csv_path):
#             return jsonify({
#                 "code": 404,
#                 "error": "CSV文件不存在"
#             }), 404
#
#         # 返回CSV文件
#         return send_file(
#             csv_path,
#             mimetype='text/csv',
#             as_attachment=True,
#             download_name='douban_movies.csv'
#         )
#
#     except Exception as e:
#         print(f"下载CSV失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({
#             "code": 500,
#             "error": f"服务器错误: {str(e)}"
#         }), 500
#
#
# # --------------------------
# # 新增API：获取CSV原始文本
# # --------------------------
# @app.route("/api/csv-text", methods=["GET"])
# def get_csv_text():
#     """获取CSV原始文本内容"""
#     try:
#         csv_path = Config.DATASET_PATHS['movie']
#         if not os.path.exists(csv_path):
#             return jsonify({
#                 "code": 404,
#                 "error": "CSV文件不存在"
#             }), 404
#
#         # 读取CSV文件内容
#         encodings = ['utf-8', 'gbk', 'latin-1']
#         csv_content = None
#
#         for encoding in encodings:
#             try:
#                 with open(csv_path, 'r', encoding=encoding) as f:
#                     csv_content = f.read()
#                 break
#             except UnicodeDecodeError:
#                 continue
#
#         if csv_content is None:
#             return jsonify({
#                 "code": 500,
#                 "error": "无法读取CSV文件编码"
#             }), 500
#
#         # 返回原始文本
#         response = make_response(csv_content)
#         response.headers["Content-Type"] = "text/plain; charset=utf-8"
#         return response
#
#     except Exception as e:
#         print(f"获取CSV文本失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({
#             "code": 500,
#             "error": f"服务器错误: {str(e)}"
#         }), 500
#
#
# # --------------------------
# # API接口 - 同步用户数据
# # --------------------------
# @app.route("/sync-user-data", methods=["POST"])
# def sync_user_data():
#     try:
#         # 解析前端数据
#         data = None
#         try:
#             data = request.get_json(force=True)
#             print("方式1解析成功")
#         except:
#             try:
#                 data = json.loads(request.data.decode('utf-8', errors='replace'))
#                 print("方式2解析成功")
#             except Exception as e:
#                 print(f"JSON解析失败: {str(e)}")
#                 return jsonify({"code": 400, "error": "无效的JSON格式"}), 400
#
#         # 验证数据结构
#         if not isinstance(data, dict) or 'preferences' not in data:
#             return jsonify({"code": 400, "error": "缺少preferences字段"}), 400
#
#         preferences = data.get('preferences', [])
#         if not isinstance(preferences, list):
#             return jsonify({"code": 400, "error": "preferences必须是数组"}), 400
#
#         # 验证并规范化偏好数据
#         valid_preferences = []
#         for i, item in enumerate(preferences):
#             if not isinstance(item, dict):
#                 continue
#             item_id = item.get('id', f"item_{i}")
#             name = item.get('name', f"未命名项目_{i}") or item.get('title', f"未命名项目_{i}")
#             genres = item.get('genres', [])
#             if isinstance(genres, str):
#                 genres = [g.strip() for g in genres.split(',') if g.strip()]
#             if not isinstance(genres, list) or not genres:
#                 continue
#
#             # 保留更多信息用于增强推荐
#             valid_preferences.append({
#                 'id': item_id,
#                 'name': name,
#                 'title': name,
#                 'genres': genres,
#                 'rating': item.get('rating', 0),
#                 'cover_url': item.get('cover_url', ''),
#                 'year': item.get('year', 0),
#                 'director': item.get('director', ''),
#                 'actors': item.get('actors', '')
#             })
#
#         print(f"验证后有效数据: {len(valid_preferences)} 条")
#         if not valid_preferences:
#             return jsonify({"code": 400, "error": "无有效偏好数据"}), 400
#
#         # 更新用户数据并检查权重变化
#         old_user_data = init_or_repair_user_data()
#         old_weights = old_user_data.get('count_weights', {})
#         new_weights = calculate_count_weights(valid_preferences)
#         need_update = old_weights != new_weights
#
#         # 保存用户数据
#         user_data = old_user_data
#         user_data['preferences'] = valid_preferences
#         user_data['count_weights'] = new_weights
#         if not safe_write_json(Config.USER_DATA_FILE, user_data):
#             return jsonify({"code": 500, "error": "服务器写入文件失败"}), 500
#
#         # 权重变化时强制更新推荐文件
#         if need_update:
#             generate_and_save_recommendations('movie')
#             generate_and_save_recommendations('series')
#             print(f"权重变化：{old_weights} → {new_weights}，已更新推荐文件")
#         else:
#             print("权重无变化，推荐文件未更新")
#
#         return jsonify({
#             "code": 0,
#             "message": "数据同步成功",
#             "count_weights": new_weights,
#             "saved_preferences_count": len(valid_preferences)
#         })
#
#     except Exception as e:
#         print(f"同步请求处理异常: {str(e)}")
#         traceback.print_exc()
#         return jsonify({"code": 500, "error": f"服务器内部错误: {str(e)}"}), 500
#
#
# # --------------------------
# # API接口 - 获取推荐
# # --------------------------
# @app.route("/get_recommend", methods=["GET"])
# def get_recommend():
#     try:
#         recommend_type = request.args.get('type', 'movie').lower()
#         refresh = request.args.get('refresh', 'false').lower() == 'true'
#         force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
#
#         if recommend_type not in ['movie', 'series']:
#             recommend_type = 'movie'
#
#         # 强制刷新优先级最高，其次是普通刷新，最后是过期检查
#         need_refresh = force_refresh or refresh
#         if not need_refresh:
#             output_path = Config.RECOMMEND_OUTPUT_PATH[recommend_type]
#             if os.path.exists(output_path):
#                 # 缩短过期时间为5分钟，便于测试刷新效果
#                 file_mtime = os.path.getmtime(output_path)
#                 file_age = datetime.now().timestamp() - file_mtime
#                 if file_age > 300:  # 5分钟（原1小时）
#                     need_refresh = True
#             else:
#                 need_refresh = True
#
#         if need_refresh:
#             # 确保生成新的推荐数据
#             generate_and_save_recommendations(recommend_type)
#
#         # 读取推荐数据 - 关键修复：读取 data 字段而不是 recommendations
#         recommend_data = safe_read_json(Config.RECOMMEND_OUTPUT_PATH[recommend_type], {})
#         recommendations = recommend_data.get("data", [])  # 这里改为 data
#
#         # 如果还是空的，直接读取CSV文件返回原始数据（添加随机排序）
#         if not recommendations:
#             import pandas as pd
#             import random
#             csv_path = os.path.join(Config.BASE_DIR, 'data', f'douban_{recommend_type}s.csv')
#             if os.path.exists(csv_path):
#                 df = pd.read_csv(csv_path, encoding='utf-8')
#                 # 随机排序确保每次返回不同结果
#                 df = df.sample(frac=1).reset_index(drop=True)
#                 recommendations = df.head(10).to_dict('records')
#
#         user_data = init_or_repair_user_data()
#
#         return jsonify({
#             "code": 0,
#             "data": recommendations,
#             "count_weights": user_data.get('count_weights', {}),
#             "generated_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # 使用当前时间
#             "refreshed": need_refresh,
#             "algorithm_version": "NCF+TextCNN_v1.0"
#         })
#
#     except Exception as e:
#         print(f"获取推荐失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500
#
# # --------------------------
# # API接口 - 智能搜索
# # --------------------------
# @app.route("/search", methods=["GET"])
# def search():
#     try:
#         query = request.args.get('q', '')
#         content_type = request.args.get('type')
#
#         if not query:
#             return jsonify({"code": 400, "error": "缺少搜索关键词"}), 400
#
#         results = smart_search(query, content_type)
#
#         return jsonify({
#             "code": 0,
#             "query": query,
#             "count": len(results),
#             "results": results
#         })
#
#     except Exception as e:
#         print(f"搜索失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500
#
#
# # --------------------------
# # API接口 - 负反馈
# # --------------------------
# @app.route("/negative-feedback", methods=["POST"])
# def negative_feedback():
#     try:
#         data = request.get_json()
#         item_id = data.get('item_id')
#         item_type = data.get('type', 'movie')
#         reason = data.get('reason', '')
#
#         if not item_id:
#             return jsonify({"code": 400, "error": "缺少项目ID"}), 400
#
#         add_negative_feedback(item_id, item_type, reason)
#
#         # 立即更新推荐
#         generate_and_save_recommendations(item_type)
#
#         return jsonify({
#             "code": 0,
#             "message": "负反馈已记录",
#             "item_id": item_id
#         })
#
#     except Exception as e:
#         print(f"负反馈处理失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500
#
#
# # --------------------------
# # API接口 - 想看清单管理
# # --------------------------
# @app.route("/watchlist", methods=["GET"])
# def get_watchlist():
#     try:
#         content_type = request.args.get('type')
#         watchlist = manage_watchlist('get', None, content_type)
#
#         return jsonify({
#             "code": 0,
#             "count": len(watchlist),
#             "watchlist": watchlist
#         })
#
#     except Exception as e:
#         print(f"获取想看清单失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500
#
#
# @app.route("/watchlist/add", methods=["POST"])
# def add_to_watchlist():
#     try:
#         data = request.get_json()
#         item_id = data.get('item_id')
#         item_type = data.get('type')
#         item_data = data.get('data', {})
#
#         if not item_id or not item_type:
#             return jsonify({"code": 400, "error": "缺少必要参数"}), 400
#
#         result = manage_watchlist('add', item_id, item_type, item_data)
#
#         return jsonify({
#             "code": 0,
#             "message": result['message']
#         })
#
#     except Exception as e:
#         print(f"添加想看清单失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500
#
#
# @app.route("/watchlist/remove", methods=["POST"])
# def remove_from_watchlist():
#     try:
#         data = request.get_json()
#         item_id = data.get('item_id')
#         item_type = data.get('type')
#
#         if not item_id or not item_type:
#             return jsonify({"code": 400, "error": "缺少必要参数"}), 400
#
#         result = manage_watchlist('remove', item_id, item_type)
#
#         return jsonify({
#             "code": 0,
#             "message": result['message']
#         })
#
#     except Exception as e:
#         print(f"移除想看清单失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500
#
#
# # --------------------------
# # API接口 - 刷新推荐
# # --------------------------
# @app.route("/refresh-recommendations", methods=["POST"])
# def refresh_recommendations():
#     try:
#         data = request.get_json()
#         content_type = data.get('type')
#
#         if content_type:
#             generate_and_save_recommendations(content_type)
#         else:
#             generate_and_save_recommendations('movie')
#             generate_and_save_recommendations('series')
#
#         return jsonify({
#             "code": 0,
#             "message": "推荐已刷新",
#             "type": content_type or "all"
#         })
#
#     except Exception as e:
#         print(f"刷新推荐失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500
#
#
# # --------------------------
# # API接口 - 图片代理（增强版）
# # --------------------------
# @app.route("/proxy-image", methods=["GET"])
# def proxy_image_route():
#     try:
#         import imghdr
#         url = request.args.get("url")
#         if not url:
#             return jsonify({"code": 400, "error": "缺少图片URL"}), 400
#
#         image_data = proxy_image(url)
#         if not image_data:
#             return jsonify({"code": 404, "error": "图片获取失败"}), 404
#
#         # 获取文件类型
#         img_type = imghdr.what(None, image_data) or 'jpeg'
#         resp = make_response(image_data)
#         resp.headers["Content-Type"] = f"image/{img_type}"
#         resp.headers["Cache-Control"] = "public, max-age=86400"
#
#         return resp
#
#     except Exception as e:
#         print(f"图片代理失败: {str(e)}")
#         return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500
#
# # --------------------------
# # API接口 - 根据电影名称查询详细信息
# # --------------------------
# @app.route("/api/get-movie-by-name", methods=["POST"])
# def get_movie_by_name():
#     """根据电影名称查询详细信息"""
#     try:
#         data = request.get_json()
#         movie_name = data.get('name', '')
#
#         if not movie_name:
#             return jsonify({
#                 "code": 400,
#                 "error": "缺少电影名称参数"
#             }), 400
#
#         # 读取CSV文件
#         movie_df = safe_read_csv(Config.DATASET_PATHS.get('movie'))
#         if movie_df.empty:
#             return jsonify({
#                 "code": 404,
#                 "error": "电影数据集不存在"
#             }), 404
#
#         # 搜索匹配的电影
#         best_match = None
#         best_score = 0
#
#         for _, row in movie_df.iterrows():
#             title = str(row.get('title', '')).strip()
#             if not title:
#                 continue
#
#             # 计算相似度
#             similarity = calculate_similarity(movie_name, title)
#
#             # 完全匹配优先
#             if movie_name.lower() == title.lower():
#                 best_match = row
#                 best_score = 1.0
#                 break
#
#             # 相似度超过阈值
#             if similarity > 0.7 and similarity > best_score:
#                 best_match = row
#                 best_score = similarity
#
#         if best_match is not None:
#             # 格式化结果（包含电影特有字段）
#             result = {
#                 "id": str(best_match.get('id', '')),
#                 "title": str(best_match.get('title', '')),
#                 "name": str(best_match.get('name', str(best_match.get('title', '')))),  # 兼容name字段
#                 "genres": str(best_match.get('genres', '')),
#                 "rating": str(best_match.get('rating', '')),
#                 "cover_url": str(best_match.get('cover_url', '')),
#                 "coverUrl": str(best_match.get('cover_url', '')),  # 驼峰命名兼容
#                 "year": str(best_match.get('year', '')),
#                 "director": str(best_match.get('director', '')),
#                 "actors": str(best_match.get('actors', '')),
#                 "popularity": str(best_match.get('popularity', '')),
#                 "similarity_score": best_score,
#                 # 电影特有字段
#                 "duration": str(best_match.get('duration', best_match.get('runtime', '未知时长'))),
#                 "country": str(best_match.get('country', best_match.get('region', '未知国家'))),
#                 "language": str(best_match.get('language', '未知语言')),
#                 "release_date": str(best_match.get('release_date', best_match.get('release_time', ''))),
#                 "box_office": str(best_match.get('box_office', '未知票房'))
#             }
#
#             return jsonify({
#                 "code": 0,
#                 "data": result
#             })
#         else:
#             return jsonify({
#                 "code": 404,
#                 "error": f"未找到电影: {movie_name}"
#             }), 404
#
#     except Exception as e:
#         print(f"查询电影失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({
#             "code": 500,
#             "error": f"服务器错误: {str(e)}"
#         }), 500
#
#
# # --------------------------
# # API接口 - 批量查询电影信息
# # --------------------------
# @app.route("/api/get-movies-by-names", methods=["POST"])
# def get_movies_by_names():
#     """批量查询电影信息"""
#     try:
#         data = request.get_json()
#         movie_names = data.get('names', [])
#         only_return_requested = data.get('onlyReturnRequested', True)
#
#         if not isinstance(movie_names, list) or len(movie_names) == 0:
#             return jsonify({
#                 "code": 400,
#                 "error": "电影名称列表不能为空"
#             }), 400
#
#         results = []
#
#         # 读取CSV文件
#         movie_df = safe_read_csv(Config.DATASET_PATHS.get('movie'))
#         if movie_df.empty:
#             # 数据集不存在时返回所有请求名称的错误
#             for name in movie_names:
#                 results.append({
#                     'name_requested': name,
#                     'matched_title': name,
#                     'data': None,
#                     'error': '电影数据集不存在',
#                     'similarity_score': 0
#                 })
#             return jsonify({
#                 'code': 404,
#                 'results': results,
#                 'count': len(results)
#             }), 404
#
#         # 遍历所有要查询的电影名称
#         for name in movie_names:
#             movie_name = str(name).strip()
#             if not movie_name:
#                 continue
#
#             best_match = None
#             best_score = 0
#
#             # 复用单个查询的匹配逻辑
#             for _, row in movie_df.iterrows():
#                 title = str(row.get('title', '')).strip()
#                 if not title:
#                     continue
#
#                 similarity = calculate_similarity(movie_name, title)
#
#                 # 完全匹配优先
#                 if movie_name.lower() == title.lower():
#                     best_match = row
#                     best_score = 1.0
#                     break
#
#                 # 相似度超过阈值
#                 if similarity > 0.7 and similarity > best_score:
#                     best_match = row
#                     best_score = similarity
#
#             # 构建结果项
#             if best_match is not None:
#                 movie_data = {
#                     "id": str(best_match.get('id', '')),
#                     "title": str(best_match.get('title', '')),
#                     "name": str(best_match.get('name', str(best_match.get('title', '')))),
#                     "genres": str(best_match.get('genres', '')),
#                     "rating": str(best_match.get('rating', '')),
#                     "cover_url": str(best_match.get('cover_url', '')),
#                     "coverUrl": str(best_match.get('cover_url', '')),
#                     "year": str(best_match.get('year', '')),
#                     "director": str(best_match.get('director', '')),
#                     "actors": str(best_match.get('actors', '')),
#                     "popularity": str(best_match.get('popularity', '')),
#                     "similarity_score": best_score,
#                     # 电影特有字段
#                     "duration": str(best_match.get('duration', best_match.get('runtime', '未知时长'))),
#                     "country": str(best_match.get('country', best_match.get('region', '未知国家'))),
#                     "language": str(best_match.get('language', '未知语言')),
#                     "release_date": str(best_match.get('release_date', best_match.get('release_time', ''))),
#                     "box_office": str(best_match.get('box_office', '未知票房'))
#                 }
#
#                 results.append({
#                     'name_requested': movie_name,
#                     'matched_title': movie_data['title'],
#                     'data': movie_data,
#                     'similarity_score': best_score
#                 })
#             else:
#                 # 如果只返回请求的，也要保留未找到的记录
#                 if only_return_requested:
#                     results.append({
#                         'name_requested': movie_name,
#                         'matched_title': movie_name,
#                         'data': None,
#                         'error': f'未找到该电影: {movie_name}',
#                         'similarity_score': 0
#                     })
#
#         return jsonify({
#             'code': 0,
#             'results': results,
#             'count': len(results)
#         })
#
#     except Exception as e:
#         print(f"批量查询电影失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({
#             'code': 500,
#             'error': f"服务器错误: {str(e)}",
#             'results': []
#         }), 500
#
#
# # API接口 - 根据剧集名称查询详细信息 (兼容drama命名)
# # --------------------------
# @app.route("/api/get-drama-by-name", methods=["POST"])
# @app.route("/api/get-series-by-name", methods=["POST"])
# def get_drama_by_name():
#     """根据剧集名称查询详细信息（兼容drama和series命名）"""
#     try:
#         data = request.get_json()
#         drama_name = data.get('name', '')
#
#         if not drama_name:
#             return jsonify({
#                 "code": 400,
#                 "error": "缺少剧集名称参数"
#             }), 400
#
#         # 读取CSV文件
#         drama_df = safe_read_csv(Config.DATASET_PATHS.get('series', Config.DATASET_PATHS.get('drama')))
#         if drama_df.empty:
#             return jsonify({
#                 "code": 404,
#                 "error": "剧集数据集不存在"
#             }), 404
#
#         # 搜索匹配的剧集
#         best_match = None
#         best_score = 0
#
#         for _, row in drama_df.iterrows():
#             title = str(row.get('title', '')).strip()
#             if not title:
#                 continue
#
#             # 计算相似度
#             similarity = calculate_similarity(drama_name, title)
#
#             # 完全匹配优先
#             if drama_name.lower() == title.lower():
#                 best_match = row
#                 best_score = 1.0
#                 break
#
#             # 相似度超过阈值
#             if similarity > 0.7 and similarity > best_score:
#                 best_match = row
#                 best_score = similarity
#
#         if best_match is not None:
#             # 格式化结果（包含剧集特有字段）
#             result = {
#                 "id": str(best_match.get('id', '')),
#                 "title": str(best_match.get('title', '')),
#                 "name": str(best_match.get('name', str(best_match.get('title', '')))),  # 兼容name字段
#                 "genres": str(best_match.get('genres', '')),
#                 "rating": str(best_match.get('rating', '')),
#                 "cover_url": str(best_match.get('cover_url', '')),
#                 "coverUrl": str(best_match.get('cover_url', '')),  # 驼峰命名兼容
#                 "year": str(best_match.get('year', '')),
#                 "director": str(best_match.get('director', '')),
#                 "actors": str(best_match.get('actors', '')),
#                 "popularity": str(best_match.get('popularity', '')),
#                 "similarity_score": best_score,
#                 # 剧集特有字段
#                 "episodes": str(best_match.get('episodes', best_match.get('total_episodes', '未知集数'))),
#                 "region": str(best_match.get('region', best_match.get('area', '未知地区'))),
#                 "status": str(best_match.get('status', '完结'))
#             }
#
#             return jsonify({
#                 "code": 0,
#                 "data": result
#             })
#         else:
#             return jsonify({
#                 "code": 404,
#                 "error": f"未找到剧集: {drama_name}"
#             }), 404
#
#     except Exception as e:
#         print(f"查询剧集失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({
#             "code": 500,
#             "error": f"服务器错误: {str(e)}"
#         }), 500
#
#
# # --------------------------
# # API接口 - 批量查询剧集信息 (兼容drama命名)
# # --------------------------
# @app.route("/api/get-dramas-by-names", methods=["POST"])
# @app.route("/api/get-series-by-names", methods=["POST"])
# def get_dramas_by_names():
#     """批量查询剧集信息（兼容drama和series命名）"""
#     try:
#         data = request.get_json()
#         drama_names = data.get('names', [])
#         only_return_requested = data.get('onlyReturnRequested', True)
#
#         if not isinstance(drama_names, list) or len(drama_names) == 0:
#             return jsonify({
#                 "code": 400,
#                 "error": "剧集名称列表不能为空"
#             }), 400
#
#         results = []
#
#         # 读取CSV文件
#         drama_df = safe_read_csv(Config.DATASET_PATHS.get('series', Config.DATASET_PATHS.get('drama')))
#         if drama_df.empty:
#             # 数据集不存在时返回所有请求名称的错误
#             for name in drama_names:
#                 results.append({
#                     'name_requested': name,
#                     'matched_title': name,
#                     'data': None,
#                     'error': '剧集数据集不存在',
#                     'similarity_score': 0
#                 })
#             return jsonify({
#                 'code': 404,
#                 'results': results,
#                 'count': len(results)
#             }), 404
#
#         # 遍历所有要查询的剧集名称
#         for name in drama_names:
#             drama_name = str(name).strip()
#             if not drama_name:
#                 continue
#
#             best_match = None
#             best_score = 0
#
#             # 复用单个查询的匹配逻辑
#             for _, row in drama_df.iterrows():
#                 title = str(row.get('title', '')).strip()
#                 if not title:
#                     continue
#
#                 similarity = calculate_similarity(drama_name, title)
#
#                 # 完全匹配优先
#                 if drama_name.lower() == title.lower():
#                     best_match = row
#                     best_score = 1.0
#                     break
#
#                 # 相似度超过阈值
#                 if similarity > 0.7 and similarity > best_score:
#                     best_match = row
#                     best_score = similarity
#
#             # 构建结果项
#             if best_match is not None:
#                 drama_data = {
#                     "id": str(best_match.get('id', '')),
#                     "title": str(best_match.get('title', '')),
#                     "name": str(best_match.get('name', str(best_match.get('title', '')))),
#                     "genres": str(best_match.get('genres', '')),
#                     "rating": str(best_match.get('rating', '')),
#                     "cover_url": str(best_match.get('cover_url', '')),
#                     "coverUrl": str(best_match.get('cover_url', '')),
#                     "year": str(best_match.get('year', '')),
#                     "director": str(best_match.get('director', '')),
#                     "actors": str(best_match.get('actors', '')),
#                     "popularity": str(best_match.get('popularity', '')),
#                     "similarity_score": best_score,
#                     # 剧集特有字段
#                     "episodes": str(best_match.get('episodes', best_match.get('total_episodes', '未知集数'))),
#                     "region": str(best_match.get('region', best_match.get('area', '未知地区'))),
#                     "status": str(best_match.get('status', '完结'))
#                 }
#
#                 results.append({
#                     'name_requested': drama_name,
#                     'matched_title': drama_data['title'],
#                     'data': drama_data,
#                     'similarity_score': best_score
#                 })
#             else:
#                 # 如果只返回请求的，也要保留未找到的记录
#                 if only_return_requested:
#                     results.append({
#                         'name_requested': drama_name,
#                         'matched_title': drama_name,
#                         'data': None,
#                         'error': f'未找到该剧集: {drama_name}',
#                         'similarity_score': 0
#                     })
#
#         return jsonify({
#             'code': 0,
#             'results': results,
#             'count': len(results)
#         })
#
#     except Exception as e:
#         print(f"批量查询剧集失败: {str(e)}")
#         traceback.print_exc()
#         return jsonify({
#             'code': 500,
#             'error': f"服务器错误: {str(e)}",
#             'results': []
#         }), 500
#
#
# # --------------------------
# # 根路径测试
# # --------------------------
# @app.route("/")
# def index():
#     return """<h1>增强型推荐服务运行中</h1>
#     <p>API端点:</p>
#     <ul>
#         <li>GET /api/movies - 获取电影数据(JSON格式)</li>
#         <li>GET /api/csv-text - 获取CSV原始文本</li>
#         <li>GET /api/download-csv - 下载CSV文件</li>
#         <li>POST /api/get-movie-by-name - 根据电影名查询</li>
#         <li>POST /api/get-movies-by-names - 批量查询电影</li>
#         <li>POST /api/get-series-by-name - 根据剧集名查询</li>
#         <li>POST /api/get-series-by-names - 批量查询剧集</li>
#         <li>POST /sync-user-data - 同步用户数据</li>
#         <li>GET /get_recommend?type=movie - 获取推荐</li>
#         <li>GET /search?q=关键词 - 智能搜索</li>
#         <li>POST /negative-feedback - 提交负反馈</li>
#         <li>POST /watchlist/add - 添加到想看清单</li>
#         <li>GET /watchlist - 获取想看清单</li>
#         <li>POST /refresh-recommendations - 刷新推荐</li>
#         <li>GET /proxy-image?url=图片地址 - 图片代理服务</li>
#     </ul>"""
#
#
# # --------------------------
# # 启动服务
# # --------------------------
# if __name__ == "__main__":
#     import json
#
#     init_or_repair_user_data()
#     print(f"工作目录: {Config.BASE_DIR}")
#     print("初始化推荐文件...")
#     generate_and_save_recommendations('movie')
#     generate_and_save_recommendations('series')
#     app.run(host="0.0.0.0", port=5000, debug=True)


import json
import os
import traceback
import random
from datetime import datetime
from flask import Flask, jsonify, request, make_response, send_file
import pandas as pd
import imghdr  # 移到顶部

# Flask应用初始化
from flask_cors import CORS

# 配置导入容错
try:
    from config import Config

    config_instance = Config()
    print("✅ 成功加载配置文件")
except (ImportError, ModuleNotFoundError) as e:
    print(f"⚠️ 配置文件导入失败: {e}")


    # 创建默认配置
    class DefaultConfig:
        BASE_DIR = os.path.abspath(os.path.dirname(__file__))
        DATASET_PATHS = {
            'movie': os.path.join(BASE_DIR, 'data', 'douban_movies.csv'),
            'series': os.path.join(BASE_DIR, 'data', 'douban_series.csv')
        }
        RECOMMEND_OUTPUT_PATH = {
            'movie': os.path.join(BASE_DIR, 'data', 'movie_recommendations.json'),
            'series': os.path.join(BASE_DIR, 'data', 'series_recommendations.json')
        }
        USER_DATA_FILE = os.path.join(BASE_DIR, 'data', 'user_data.json')
        WATCHLIST_FILE = os.path.join(BASE_DIR, 'data', 'watchlist.json')


    config_instance = DefaultConfig()

# 其他模块导入（添加容错）
try:
    from utils.file_utils import safe_read_json, safe_write_json
    from utils.image_utils import proxy_image, is_allowed_domain
    from utils.text_utils import calculate_similarity
    from data.dataset_loader import load_dataset, safe_read_csv
    from data.user_manager import init_or_repair_user_data, calculate_count_weights, add_negative_feedback
    from recommendation.engine import generate_and_save_recommendations, generate_personalized_recommendations
    from search.search_engine import smart_search, search_drama_by_name, batch_search_dramas
    from watchlist.manager import manage_watchlist

    print("✅ 成功加载所有模块")
except ImportError as e:
    print(f"⚠️ 部分模块导入失败: {e}")


    # 创建占位函数避免崩溃
    def safe_read_json(path, default=None):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default or {}


    def safe_write_json(path, data):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # 更宽松的CORS配置

# 全局配置引用
Config = config_instance


# --------------------------
# 工具函数（避免重复代码）
# --------------------------
def search_item_by_name(item_name, item_type='movie'):
    """通用的项目搜索函数"""
    try:
        # 获取数据集路径
        csv_path = Config.DATASET_PATHS.get(item_type)
        if not os.path.exists(csv_path):
            return None, "数据集不存在"

        # 读取CSV
        df = safe_read_csv(csv_path)
        if df.empty:
            return None, "数据集为空"

        best_match = None
        best_score = 0

        for _, row in df.iterrows():
            title = str(row.get('title', '')).strip()
            if not title:
                continue

            # 计算相似度
            similarity = calculate_similarity(item_name, title)

            # 完全匹配优先
            if item_name.lower() == title.lower():
                best_match = row
                best_score = 1.0
                break

            # 相似度超过阈值
            if similarity > 0.7 and similarity > best_score:
                best_match = row
                best_score = similarity

        if best_match is None:
            return None, "未找到匹配项"

        # 构建结果
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
            "similarity_score": best_score
        }

        # 添加类型特有字段
        if item_type == 'movie':
            result.update({
                "duration": str(best_match.get('duration', best_match.get('runtime', '未知时长'))),
                "country": str(best_match.get('country', best_match.get('region', '未知国家'))),
                "language": str(best_match.get('language', '未知语言')),
                "release_date": str(best_match.get('release_date', best_match.get('release_time', ''))),
                "box_office": str(best_match.get('box_office', '未知票房'))
            })
        else:  # series
            result.update({
                "episodes": str(best_match.get('episodes', best_match.get('total_episodes', '未知集数'))),
                "region": str(best_match.get('region', best_match.get('area', '未知地区'))),
                "status": str(best_match.get('status', '完结'))
            })

        return result, None

    except Exception as e:
        return None, str(e)


# --------------------------
# API接口实现
# --------------------------
@app.route("/api/movies", methods=["GET"])
def get_movies_data():
    """获取电影CSV数据（JSON格式）"""
    try:
        # 读取CSV文件
        movie_df = safe_read_csv(Config.DATASET_PATHS['movie'])
        if movie_df.empty:
            return jsonify({
                "code": 404,
                "error": "电影数据文件不存在或为空"
            }), 404

        # 转换为JSON格式
        movies_data = movie_df.to_dict('records')

        return jsonify({
            "code": 0,
            "data": movies_data,
            "count": len(movies_data)
        })

    except Exception as e:
        print(f"获取电影数据失败: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "error": f"服务器错误: {str(e)}"
        }), 500


@app.route("/api/download-csv", methods=["GET"]) #从后端服务器本地读取已存储的影视数据 CSV 文件
def download_csv():
    """直接下载CSV文件"""
    try:
        csv_type = request.args.get('type', 'movie')
        csv_path = Config.DATASET_PATHS.get(csv_type, Config.DATASET_PATHS['movie'])

        if not os.path.exists(csv_path):
            return jsonify({
                "code": 404,
                "error": f"{csv_type} CSV文件不存在"
            }), 404

        # 返回CSV文件
        return send_file(
            csv_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'douban_{csv_type}s.csv'
        )

    except Exception as e:
        print(f"下载CSV失败: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "error": f"服务器错误: {str(e)}"
        }), 500


@app.route("/api/csv-text", methods=["GET"]) #通过接口返回给前端
def get_csv_text():
    """获取CSV原始文本内容"""
    try:
        csv_type = request.args.get('type', 'movie')
        csv_path = Config.DATASET_PATHS.get(csv_type, Config.DATASET_PATHS['movie'])

        if not os.path.exists(csv_path):
            return jsonify({
                "code": 404,
                "error": f"{csv_type} CSV文件不存在"
            }), 404

        # 读取CSV文件内容
        encodings = ['utf-8', 'gbk', 'latin-1', 'gb2312']
        csv_content = None

        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    csv_content = f.read()
                break
            except (UnicodeDecodeError, Exception):
                continue

        if csv_content is None:
            return jsonify({
                "code": 500,
                "error": "无法读取CSV文件编码"
            }), 500

        # 返回原始文本
        response = make_response(csv_content)
        response.headers["Content-Type"] = "text/plain; charset=utf-8"
        return response

    except Exception as e:
        print(f"获取CSV文本失败: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "error": f"服务器错误: {str(e)}"
        }), 500


@app.route("/sync-user-data", methods=["POST"]) #前端传数据→后端校验清洗→写入后端文件→更新推荐
def sync_user_data():
    try:
        # 解析前端数据
        data = None
        try:
            data = request.get_json(force=True)
        except:
            try:
                data = json.loads(request.data.decode('utf-8', errors='replace'))
            except Exception as e:
                print(f"JSON解析失败: {str(e)}")
                return jsonify({"code": 400, "error": "无效的JSON格式"}), 400

        # 验证数据结构
        if not isinstance(data, dict) or 'preferences' not in data:
            return jsonify({"code": 400, "error": "缺少preferences字段"}), 400

        preferences = data.get('preferences', [])
        if not isinstance(preferences, list):
            return jsonify({"code": 400, "error": "preferences必须是数组"}), 400

        # 验证并规范化偏好数据
        valid_preferences = []
        for i, item in enumerate(preferences):
            if not isinstance(item, dict):
                continue

            item_id = item.get('id', f"item_{i}")
            name = item.get('name', '') or item.get('title', f"未命名项目_{i}")
            genres = item.get('genres', [])

            if isinstance(genres, str):
                genres = [g.strip() for g in genres.split(',') if g.strip()]
            if not isinstance(genres, list) or not genres:
                continue

            # 保留更多信息用于增强推荐
            valid_preferences.append({
                'id': item_id,
                'name': name,
                'title': name,
                'genres': genres,
                'rating': item.get('rating', 0),
                'cover_url': item.get('cover_url', ''),
                'year': item.get('year', 0),
                'director': item.get('director', ''),
                'actors': item.get('actors', ''),
                'plot': item.get('plot', '')
            })

        print(f"验证后有效数据: {len(valid_preferences)} 条")
        if not valid_preferences:
            return jsonify({"code": 400, "error": "无有效偏好数据"}), 400

        # 更新用户数据并检查权重变化
        old_user_data = init_or_repair_user_data()
        old_weights = old_user_data.get('count_weights', {})
        new_weights = calculate_count_weights(valid_preferences)
        need_update = old_weights != new_weights

        # 保存用户数据
        user_data = old_user_data
        user_data['preferences'] = valid_preferences
        user_data['count_weights'] = new_weights
        user_data['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if not safe_write_json(Config.USER_DATA_FILE, user_data):
            return jsonify({"code": 500, "error": "服务器写入文件失败"}), 500

        # 权重变化时强制更新推荐文件
        if need_update:
            generate_and_save_recommendations('movie')
            generate_and_save_recommendations('series')
            print(f"权重变化：{old_weights} → {new_weights}，已更新推荐文件")
        else:
            print("权重无变化，推荐文件未更新")

        return jsonify({
            "code": 0,
            "message": "数据同步成功",
            "count_weights": new_weights,
            "saved_preferences_count": len(valid_preferences),
            "updated_recommendations": need_update
        })

    except Exception as e:
        print(f"同步请求处理异常: {str(e)}")
        traceback.print_exc()
        return jsonify({"code": 500, "error": f"服务器内部错误: {str(e)}"}), 500


@app.route("/get_recommend", methods=["GET"])
def get_recommend():
    try:
        recommend_type = request.args.get('type', 'movie').lower()
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'

        if recommend_type not in ['movie', 'series']:
            recommend_type = 'movie'

        # 强制刷新优先级最高
        need_refresh = force_refresh or refresh
        if not need_refresh:
            output_path = Config.RECOMMEND_OUTPUT_PATH[recommend_type]
            if os.path.exists(output_path):
                # 检查文件是否过期（5分钟）
                file_mtime = os.path.getmtime(output_path)
                file_age = datetime.now().timestamp() - file_mtime
                if file_age > 300:  # 5分钟
                    need_refresh = True
            else:
                need_refresh = True

        if need_refresh:
            generate_and_save_recommendations(recommend_type)

        # 读取推荐数据
        recommend_data = safe_read_json(Config.RECOMMEND_OUTPUT_PATH[recommend_type], {})
        recommendations = recommend_data.get("data", [])

        # 如果还是空的，直接读取CSV文件返回原始数据
        if not recommendations:
            csv_path = Config.DATASET_PATHS.get(recommend_type)
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path, encoding='utf-8')
                # 随机排序确保每次返回不同结果
                df = df.sample(frac=1).reset_index(drop=True)
                recommendations = df.head(10).to_dict('records')

        user_data = init_or_repair_user_data()

        return jsonify({
            "code": 0,
            "data": recommendations,
            "count_weights": user_data.get('count_weights', {}),
            "generated_time": recommend_data.get('generated_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            "refreshed": need_refresh,
            "algorithm_version": recommend_data.get('algorithm_version', "NCF+TextCNN_v1.0")
        })

    except Exception as e:
        print(f"获取推荐失败: {str(e)}")
        traceback.print_exc()
        return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500


@app.route("/search", methods=["GET"])
def search():
    try:
        query = request.args.get('q', '').strip()#获取URL中？后面的参数
        content_type = request.args.get('type')

        if not query:
            return jsonify({"code": 400, "error": "缺少搜索关键词"}), 400

        results = smart_search(query, content_type)

        return jsonify({
            "code": 0,
            "query": query,
            "count": len(results),
            "results": results
        })

    except Exception as e:
        print(f"搜索失败: {str(e)}")
        traceback.print_exc()
        return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500


@app.route("/negative-feedback", methods=["POST"])
def negative_feedback():
    try:
        data = request.get_json() or {}
        item_id = data.get('item_id')
        item_type = data.get('type', 'movie')
        reason = data.get('reason', '')

        if not item_id:
            return jsonify({"code": 400, "error": "缺少项目ID"}), 400

        add_negative_feedback(item_id, item_type, reason)

        # 立即更新推荐
        generate_and_save_recommendations(item_type)

        return jsonify({
            "code": 0,
            "message": "负反馈已记录",
            "item_id": item_id,
            "updated": True
        })

    except Exception as e:
        print(f"负反馈处理失败: {str(e)}")
        traceback.print_exc()
        return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500


# --------------------------
# 想看清单管理接口
# --------------------------
@app.route("/watchlist", methods=["GET"])
def get_watchlist():
    try:
        content_type = request.args.get('type')
        watchlist = manage_watchlist('get', None, content_type)

        return jsonify({
            "code": 0,
            "count": len(watchlist),
            "watchlist": watchlist,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        print(f"获取想看清单失败: {str(e)}")
        traceback.print_exc()
        return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500


@app.route("/watchlist/add", methods=["POST"])
def add_to_watchlist():
    try:
        data = request.get_json() or {}
        item_id = data.get('item_id')
        item_type = data.get('type')
        item_data = data.get('data', {})

        if not item_id or not item_type:
            return jsonify({"code": 400, "error": "缺少必要参数"}), 400

        result = manage_watchlist('add', item_id, item_type, item_data)

        return jsonify({
            "code": 0,
            "message": result.get('message', '添加成功'),
            "item_id": item_id
        })

    except Exception as e:
        print(f"添加想看清单失败: {str(e)}")
        traceback.print_exc()
        return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500


@app.route("/watchlist/remove", methods=["POST"])
def remove_from_watchlist():
    try:
        data = request.get_json() or {}
        item_id = data.get('item_id')
        item_type = data.get('type')

        if not item_id or not item_type:
            return jsonify({"code": 400, "error": "缺少必要参数"}), 400

        result = manage_watchlist('remove', item_id, item_type)

        return jsonify({
            "code": 0,
            "message": result.get('message', '移除成功'),
            "item_id": item_id
        })

    except Exception as e:
        print(f"移除想看清单失败: {str(e)}")
        traceback.print_exc()
        return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500


@app.route("/refresh-recommendations", methods=["POST", "GET"])
def refresh_recommendations():
    try:
        if request.method == 'POST':
            data = request.get_json() or {}
        else:
            data = request.args

        content_type = data.get('type')

        if content_type:
            generate_and_save_recommendations(content_type)
            message = f"{content_type}推荐已刷新"
        else:
            generate_and_save_recommendations('movie')
            generate_and_save_recommendations('series')
            message = "所有推荐已刷新"

        return jsonify({
            "code": 0,
            "message": message,
            "type": content_type or "all",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        print(f"刷新推荐失败: {str(e)}")
        traceback.print_exc()
        return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500


@app.route("/proxy-image", methods=["GET"])
def proxy_image_route():
    try:
        url = request.args.get("url")
        if not url:
            return jsonify({"code": 400, "error": "缺少图片URL"}), 400

        # 检查域名是否允许
        if 'is_allowed_domain' in globals() and not is_allowed_domain(url):
            return jsonify({"code": 403, "error": "图片域名不被允许"}), 403

        image_data = proxy_image(url)
        if not image_data:
            return jsonify({"code": 404, "error": "图片获取失败"}), 404

        # 获取文件类型
        img_type = imghdr.what(None, image_data) or 'jpeg'
        resp = make_response(image_data)
        resp.headers["Content-Type"] = f"image/{img_type}"
        resp.headers["Cache-Control"] = "public, max-age=86400"  # 缓存1天

        return resp

    except Exception as e:
        print(f"图片代理失败: {str(e)}")
        return jsonify({"code": 500, "error": f"服务器错误: {str(e)}"}), 500


# --------------------------
# 电影查询接口
# --------------------------
@app.route("/api/get-movie-by-name", methods=["POST"])
def get_movie_by_name():
    """根据电影名称查询详细信息"""
    try:
        data = request.get_json() or {}
        movie_name = data.get('name', '').strip()

        if not movie_name:
            return jsonify({
                "code": 400,
                "error": "缺少电影名称参数"
            }), 400

        result, error = search_item_by_name(movie_name, 'movie')

        if error:
            return jsonify({
                "code": 404,
                "error": f"未找到电影: {movie_name} ({error})"
            }), 404

        return jsonify({
            "code": 0,
            "data": result
        })

    except Exception as e:
        print(f"查询电影失败: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "error": f"服务器错误: {str(e)}"
        }), 500


@app.route("/api/get-movies-by-names", methods=["POST"])
def get_movies_by_names():
    """批量查询电影信息"""
    try:
        data = request.get_json() or {}
        movie_names = data.get('names', [])
        only_return_requested = data.get('onlyReturnRequested', True)

        if not isinstance(movie_names, list) or len(movie_names) == 0:
            return jsonify({
                "code": 400,
                "error": "电影名称列表不能为空"
            }), 400

        results = []
        for name in movie_names:
            movie_name = str(name).strip()
            if not movie_name:
                continue

            result, error = search_item_by_name(movie_name, 'movie')

            if result:
                results.append({
                    'name_requested': movie_name,
                    'matched_title': result['title'],
                    'data': result,
                    'similarity_score': result['similarity_score']
                })
            elif only_return_requested:
                results.append({
                    'name_requested': movie_name,
                    'matched_title': movie_name,
                    'data': None,
                    'error': f'未找到该电影: {movie_name}',
                    'similarity_score': 0
                })

        return jsonify({
            'code': 0,
            'results': results,
            'count': len(results),
            'success_count': len([r for r in results if r.get('data')])
        })

    except Exception as e:
        print(f"批量查询电影失败: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'code': 500,
            'error': f"服务器错误: {str(e)}",
            'results': []
        }), 500


# --------------------------
# 剧集查询接口
# --------------------------
@app.route("/api/get-drama-by-name", methods=["POST"])
@app.route("/api/get-series-by-name", methods=["POST"])
def get_drama_by_name():
    """根据剧集名称查询详细信息"""
    try:
        data = request.get_json() or {}
        drama_name = data.get('name', '').strip()

        if not drama_name:
            return jsonify({
                "code": 400,
                "error": "缺少剧集名称参数"
            }), 400

        result, error = search_item_by_name(drama_name, 'series')

        if error:
            return jsonify({
                "code": 404,
                "error": f"未找到剧集: {drama_name} ({error})"
            }), 404

        return jsonify({
            "code": 0,
            "data": result
        })

    except Exception as e:
        print(f"查询剧集失败: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "error": f"服务器错误: {str(e)}"
        }), 500


@app.route("/api/get-dramas-by-names", methods=["POST"])
@app.route("/api/get-series-by-names", methods=["POST"])
def get_dramas_by_names():
    """批量查询剧集信息"""
    try:
        data = request.get_json() or {}
        drama_names = data.get('names', [])
        only_return_requested = data.get('onlyReturnRequested', True)

        if not isinstance(drama_names, list) or len(drama_names) == 0:
            return jsonify({
                "code": 400,
                "error": "剧集名称列表不能为空"
            }), 400

        results = []
        for name in drama_names:
            drama_name = str(name).strip()
            if not drama_name:
                continue

            result, error = search_item_by_name(drama_name, 'series')

            if result:
                results.append({
                    'name_requested': drama_name,
                    'matched_title': result['title'],
                    'data': result,
                    'similarity_score': result['similarity_score']
                })
            elif only_return_requested:
                results.append({
                    'name_requested': drama_name,
                    'matched_title': drama_name,
                    'data': None,
                    'error': f'未找到该剧集: {drama_name}',
                    'similarity_score': 0
                })

        return jsonify({
            'code': 0,
            'results': results,
            'count': len(results),
            'success_count': len([r for r in results if r.get('data')])
        })

    except Exception as e:
        print(f"批量查询剧集失败: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'code': 500,
            'error': f"服务器错误: {str(e)}",
            'results': []
        }), 500


# --------------------------
# 系统信息接口
# --------------------------
@app.route("/api/system-info", methods=["GET"])
def system_info():
    """获取系统信息"""
    try:
        user_data = init_or_repair_user_data()
        return jsonify({
            "code": 0,
            "server_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "base_dir": Config.BASE_DIR,
            "preferences_count": len(user_data.get('preferences', [])),
            "movie_dataset_exists": os.path.exists(Config.DATASET_PATHS['movie']),
            "series_dataset_exists": os.path.exists(Config.DATASET_PATHS['series']),
            "api_version": "v2.0"
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "error": str(e)
        }), 500


@app.route("/")
def index():
    return """<h1>增强型推荐服务运行中</h1>
    <p>API版本: v2.0</p>
    <p>API端点:</p>
    <ul>
        <li>GET /api/system-info - 获取系统信息</li>
        <li>GET /api/movies - 获取电影数据(JSON格式)</li>
        <li>GET /api/csv-text?type=movie - 获取CSV原始文本</li>
        <li>GET /api/download-csv?type=movie - 下载CSV文件</li>
        <li>POST /api/get-movie-by-name - 根据电影名查询</li>
        <li>POST /api/get-movies-by-names - 批量查询电影</li>
        <li>POST /api/get-series-by-name - 根据剧集名查询</li>
        <li>POST /api/get-series-by-names - 批量查询剧集</li>
        <li>POST /sync-user-data - 同步用户数据</li>
        <li>GET /get_recommend?type=movie&refresh=true - 获取推荐</li>
        <li>GET /search?q=关键词 - 智能搜索</li>
        <li>POST /negative-feedback - 提交负反馈</li>
        <li>POST /watchlist/add - 添加到想看清单</li>
        <li>GET /watchlist - 获取想看清单</li>
        <li>POST /refresh-recommendations - 刷新推荐</li>
        <li>GET /proxy-image?url=图片地址 - 图片代理服务</li>
    </ul>"""


# --------------------------
# 启动服务
# --------------------------
if __name__ == "__main__":
    # 确保数据目录存在
    os.makedirs(os.path.join(Config.BASE_DIR, 'data'), exist_ok=True)

    init_or_repair_user_data()
    print(f"工作目录: {Config.BASE_DIR}")
    print("初始化推荐文件...")

    # 静默初始化推荐文件
    try:
        generate_and_save_recommendations('movie')
        generate_and_save_recommendations('series')
    except Exception as e:
        print(f"初始化推荐文件警告: {e}")

    # 生产环境建议关闭debug
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)