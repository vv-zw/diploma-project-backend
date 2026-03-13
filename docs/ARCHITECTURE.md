# 系统架构说明

## 1. 架构概览

当前系统是一个面向电影和剧集推荐场景的 Flask 后端，核心目标是：

- 提供缓存可读的推荐结果
- 通过异步任务刷新推荐，避免前端同步阻塞
- 为电影和剧集分别维护用户偏好和统计权重
- 以 `NCF + TextCNN + 规则特征` 的混合方案生成推荐结果

整体链路分为四层：

1. 接口层：Flask 路由，接收小程序请求
2. 业务层：推荐、搜索、想看清单、负反馈处理
3. 模型层：NCF、TextCNN、规则内容相似度、多样性重排
4. 存储层：CSV 数据集、用户 JSON、推荐结果 JSON

## 2. 主要模块

### 2.1 接口层

入口文件：
- [app.py](/d:/pythonProjectmovie，tobacco/movie_recommendation/app.py)

主要职责：
- 读取缓存推荐
- 创建异步刷新任务
- 查询刷新任务状态
- 同步用户偏好和行为数据
- 提供搜索、想看清单、负反馈等接口

### 2.2 推荐引擎

核心文件：
- [engine.py](/d:/pythonProjectmovie，tobacco/movie_recommendation/recommendation/engine.py)

主要职责：
- 初始化和修复用户数据结构
- 将偏好按 `movie/series` 分桶
- 计算类型权重 `count_weights`
- 调用 NCF 和 TextCNN 计算推荐分数
- 进行负反馈惩罚和多样性重排
- 输出并缓存推荐结果

### 2.3 模型层

相关文件：
- [NeuralCollaborativeFiltering.py](/d:/pythonProjectmovie，tobacco/movie_recommendation/NeuralCollaborativeFiltering.py)
- [TextCNN.py](/d:/pythonProjectmovie，tobacco/movie_recommendation/TextCNN.py)
- [similarity.py](/d:/pythonProjectmovie，tobacco/movie_recommendation/recommendation/similarity.py)
- [diversity.py](/d:/pythonProjectmovie，tobacco/movie_recommendation/recommendation/diversity.py)

职责划分：
- `NCF`：学习用户与项目的隐式交互偏好
- `TextCNN`：从标题、类型、导演、演员、简介等文本中提取语义特征
- `similarity.py`：当 TextCNN 不可用时，提供规则内容相似度
- `diversity.py`：防止推荐结果过度集中在同一类型

## 3. 推荐架构

### 3.1 主链路

当前主链路是并行融合，而不是二选一：

```text
NCF score
    \
     +--> final_score --> sort --> diversity re-rank --> cache
    /
TextCNN score
    +
rule features
```

最终分数：

```text
final_score =
0.35 * ncf_score +
0.30 * textcnn_score +
0.20 * genre_score +
0.10 * quality_score +
0.05 * diversity_score
```

附加处理：
- 负反馈惩罚
- 黑名单过滤
- 多样性重排

### 3.2 降级链路

系统保留平滑降级策略：

1. `NCF + TextCNN + 规则分`
2. `NCF + 规则内容相似度 + 规则分`
3. `TextCNN + 规则分`
4. `规则内容推荐 + 多样性重排`

含义是：
- `TextCNN` 不可用时，退回到手工内容相似度
- `NCF` 不可用时，仍可基于文本和规则继续推荐
- 两者都不可用时，系统仍能输出可用结果

## 4. 用户数据结构

用户数据文件：
- [user_data.json](/d:/pythonProjectmovie，tobacco/data/user/user_data.json)

当前采用按内容类型分桶的结构：

```json
{
  "preferences": {
    "movie": [],
    "series": []
  },
  "behavior": {
    "movie": [],
    "series": []
  },
  "count_weights": {
    "movie": {
      "genres": {},
      "directors": {},
      "actors": {}
    },
    "series": {
      "genres": {},
      "directors": {},
      "actors": {}
    }
  }
}
```

这样可以保证：
- 电影推荐只使用电影偏好
- 剧集推荐只使用剧集偏好
- 不再出现剧集沿用电影统计权重的问题

## 5. 刷新架构

### 5.1 设计目标

旧实现的问题是：
- `GET /get_recommend` 既负责读取结果，也可能同步跑模型
- 前端刷新必须等待模型训练和推理完成
- 当推荐生成耗时增加时，小程序容易超时

当前实现将“读取推荐”和“刷新推荐”拆开。

### 5.2 当前接口职责

- `GET /get_recommend`
  - 只读取缓存推荐 JSON
  - 快速返回当前可用结果

- `POST /refresh-recommendations`
  - 创建后台刷新任务
  - 返回 `job_id`

- `GET /refresh-status`
  - 查询任务状态
  - 支持 `queued`、`running`、`done`、`failed`

### 5.3 后台任务模型

当前使用轻量级后台线程执行刷新任务：

1. 前端发起刷新
2. 后端生成 `job_id`
3. 后台线程调用推荐引擎重新生成并写入缓存
4. 前端轮询任务状态
5. 刷新完成后重新读取缓存推荐

这套设计的优点是：
- 前端不再同步阻塞
- 模型执行时间对页面稳定性影响更小
- 接口语义更清晰

## 6. 前端联动

相关页面：
- [movieRecommend.js](/d:/pythonProjectmovie，tobacco/微信小程序/pages/movieRecommend/movieRecommend.js)
- [showRecommend.js](/d:/pythonProjectmovie，tobacco/微信小程序/pages/showRecommend/showRecommend.js)

当前刷新逻辑：

1. 页面进入时调用 `GET /get_recommend`
2. 点击刷新后调用 `POST /refresh-recommendations`
3. 保存 `job_id`
4. 轮询 `GET /refresh-status`
5. 状态变为 `done` 后再次调用 `GET /get_recommend`
6. 直接覆盖当前列表

因此：
- 电影页刷新后会在当前页直接更新
- 剧集页刷新后也会在当前页直接更新
- 不需要退出后再重新进入页面

## 7. 存储结构

主要数据文件：

- 数据集
  - [douban_movies.csv](/d:/pythonProjectmovie，tobacco/data/datasets/douban_movies.csv)
  - [douban_series.csv](/d:/pythonProjectmovie，tobacco/data/datasets/douban_series.csv)
- 用户数据
  - [user_data.json](/d:/pythonProjectmovie，tobacco/data/user/user_data.json)
- 推荐缓存
  - [movie_recommendations.json](/d:/pythonProjectmovie，tobacco/data/recommendations/movie_recommendations.json)
  - [series_recommendations.json](/d:/pythonProjectmovie，tobacco/data/recommendations/series_recommendations.json)

推荐结果是缓存产物，供前端直接读取；刷新任务负责更新这些缓存文件。

## 8. 当前约束与后续方向

当前实现已经完成：
- 混合推荐主链路
- 异步刷新
- 电影/剧集偏好分桶
- 小程序当前页即时更新

后续仍可继续优化：
- 将后台线程替换为更稳定的任务队列
- 为 TextCNN item embedding 增加持久化缓存
- 为 NCF 和 TextCNN 增加离线训练与模型复用
- 补充 `compare.py` 对新主链路的离线评估
