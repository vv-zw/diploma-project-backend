# 电影推荐系统后端

基于 Flask 的电影/剧集推荐后端，当前实现采用 `NCF + TextCNN + 规则特征融合` 的混合推荐方案，并提供面向微信小程序的缓存读取、异步刷新、搜索、想看清单和负反馈接口。

## 当前实现

- 推荐主链路：`NCF + TextCNN + genre/quality/diversity`
- 降级链路：
  - `NCF + TextCNN + 规则分`
  - `NCF + 规则内容相似度 + 规则分`
  - `TextCNN + 规则分`
  - `规则内容推荐 + 多样性重排`
- 推荐读取与刷新解耦：
  - `GET /get_recommend` 只读缓存结果
  - `POST /refresh-recommendations` 异步创建刷新任务
  - `GET /refresh-status` 轮询任务状态
- 用户偏好按内容类型分桶：
  - `preferences.movie`
  - `preferences.series`
  - `count_weights.movie`
  - `count_weights.series`

## 推荐流程

1. 加载电影或剧集数据集。
2. 读取用户偏好、行为、黑名单和负反馈。
3. 只使用当前内容类型对应的偏好桶参与推荐。
4. 计算 `NCF` 协同过滤分。
5. 计算 `TextCNN` 文本语义相似度分。
6. 计算规则特征分：
   - `genre_score`
   - `quality_score`
   - `diversity_score`
7. 融合得到最终排序分：

```text
final_score =
0.35 * ncf_score +
0.30 * textcnn_score +
0.20 * genre_score +
0.10 * quality_score +
0.05 * diversity_score
```

8. 应用负反馈惩罚、黑名单过滤和多样性重排。
9. 将结果写入 `data/recommendations/*.json`。

## 项目结构

```text
movie_recommendation/
  app.py
  config.py
  recommendation/
    engine.py
    similarity.py
    diversity.py
  TextCNN.py
  NeuralCollaborativeFiltering.py

data/
  datasets/
  recommendations/
  user/

docs/
  API.md
  ARCHITECTURE.md
```

## 快速开始

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python movie_recommendation/app.py
```

服务默认运行在 `http://127.0.0.1:5000`。

## 核心接口

- `GET /get_recommend?type=movie`
  - 读取当前缓存推荐
- `POST /refresh-recommendations`
  - 异步创建推荐刷新任务
- `GET /refresh-status?job_id=...`
  - 查询刷新任务状态
- `POST /sync-user-data`
  - 同步用户偏好与行为数据
- `GET /search?q=...&type=movie`
  - 搜索电影或剧集

详细说明见 [docs/API.md](/d:/pythonProjectmovie，tobacco/docs/API.md)。

## 小程序刷新逻辑

当前小程序页面采用异步刷新流程：

1. 进入页面时调用 `GET /get_recommend` 读取缓存推荐。
2. 点击“刷新”后调用 `POST /refresh-recommendations`。
3. 前端拿到 `job_id` 后轮询 `GET /refresh-status`。
4. 状态为 `done` 后再次调用 `GET /get_recommend`。
5. 当前页面直接更新推荐列表，不需要退出重进。

## 文档

- 架构说明：[docs/ARCHITECTURE.md](/d:/pythonProjectmovie，tobacco/docs/ARCHITECTURE.md)
- 接口说明：[docs/API.md](/d:/pythonProjectmovie，tobacco/docs/API.md)
- 使用说明：[使用说明.md](/d:/pythonProjectmovie，tobacco/使用说明.md)
- 实验报告：[reports/my_report/report.md](/d:/pythonProjectmovie，tobacco/reports/my_report/report.md)
