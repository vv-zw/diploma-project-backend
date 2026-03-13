# API 接口说明

## 基础信息

- Base URL: `http://127.0.0.1:5000`
- Content-Type: `application/json`

统一响应格式：

```json
{
  "code": 0,
  "message": "",
  "data": {},
  "error": ""
}
```

说明：
- `code = 0` 表示成功
- 非 `0` 表示失败

## 1. 推荐接口

### 1.1 获取缓存推荐

```http
GET /get_recommend?type=movie
```

参数：
- `type`: `movie` 或 `series`，默认 `movie`

当前语义：
- 只读取缓存推荐结果
- 不会同步触发模型刷新

响应示例：

```json
{
  "code": 0,
  "type": "movie",
  "data": [
    {
      "id": "1292052",
      "title": "肖申克的救赎",
      "score": 0.91,
      "rating": "9.7"
    }
  ],
  "algorithm_version": "NCF_TextCNN_v3.0",
  "generated_time": "2026-03-13 15:25:44",
  "count_weights": {
    "genres": {
      "悬疑": 5,
      "喜剧": 6
    },
    "directors": {},
    "actors": {}
  }
}
```

### 1.2 创建刷新任务

```http
POST /refresh-recommendations
```

请求体：

```json
{
  "type": "movie"
}
```

说明：
- 不同步返回推荐结果
- 只创建后台任务并立即返回 `job_id`

响应示例：

```json
{
  "code": 0,
  "type": "movie",
  "job_id": "refresh_movie_20260313_152900_ab12cd34",
  "status": "queued"
}
```

### 1.3 查询刷新状态

```http
GET /refresh-status?job_id=refresh_movie_20260313_152900_ab12cd34
```

状态值：
- `queued`
- `running`
- `done`
- `failed`

响应示例：

```json
{
  "code": 0,
  "job_id": "refresh_movie_20260313_152900_ab12cd34",
  "type": "movie",
  "status": "done",
  "error": ""
}
```

推荐前端流程：
1. 调用 `POST /refresh-recommendations`
2. 轮询 `GET /refresh-status`
3. 状态为 `done` 后调用 `GET /get_recommend`

## 2. 用户数据同步

### 2.1 同步用户偏好和行为

```http
POST /sync-user-data
```

请求体示例：

```json
{
  "preferences": [
    {
      "id": "1292052",
      "title": "肖申克的救赎",
      "genres": ["剧情", "犯罪"],
      "rating": 9.7,
      "content_type": "movie"
    },
    {
      "id": "30181230",
      "title": "漫长的季节",
      "genres": ["悬疑", "剧情"],
      "content_type": "series"
    }
  ],
  "behavior": []
}
```

当前后端会将数据归一化为分桶结构：

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

响应示例：

```json
{
  "code": 0,
  "message": "数据同步成功",
  "saved_preferences_count": 12,
  "count_weights": {
    "movie": {
      "genres": {
        "悬疑": 5
      },
      "directors": {},
      "actors": {}
    },
    "series": {
      "genres": {
        "剧情": 3
      },
      "directors": {},
      "actors": {}
    }
  },
  "updated_recommendations": true
}
```

## 3. 搜索接口

### 3.1 搜索电影或剧集

```http
GET /search?q=悬疑&type=movie
```

参数：
- `q`: 搜索关键词
- `type`: `movie` 或 `series`

响应示例：

```json
{
  "code": 0,
  "query": "悬疑",
  "count": 5,
  "results": [
    {
      "id": "1292052",
      "title": "肖申克的救赎",
      "similarity": 0.82
    }
  ]
}
```

## 4. 想看清单

### 4.1 获取想看清单

```http
GET /watchlist?type=movie
```

### 4.2 添加到想看清单

```http
POST /watchlist/add
```

请求体示例：

```json
{
  "item_id": "1292052",
  "type": "movie",
  "data": {
    "title": "肖申克的救赎",
    "rating": "9.7"
  }
}
```

### 4.3 从想看清单移除

```http
POST /watchlist/remove
```

请求体示例：

```json
{
  "item_id": "1292052",
  "type": "movie"
}
```

## 5. 负反馈

### 5.1 提交负反馈

```http
POST /negative-feedback
```

请求体示例：

```json
{
  "item_id": "1292052",
  "type": "movie",
  "reason": "不喜欢这类题材"
}
```

说明：
- 负反馈会被写入用户数据
- 推荐排序时会对相关项目施加惩罚

## 6. 其他接口

### 6.1 根据名称查询电影

```http
POST /api/get-movie-by-name
POST /api/get-movies-by-names
```

### 6.2 根据名称查询剧集

```http
POST /api/get-series-by-name
POST /api/get-series-by-names
```

### 6.3 数据文件接口

```http
GET /api/movies
GET /api/csv-text?type=movie
GET /api/download-csv?type=movie
```

### 6.4 图片代理

```http
GET /proxy-image?url=https://...
```

## 7. 当前推荐实现说明

推荐主链路：

```text
NCF + TextCNN + rule features
```

当前融合公式：

```text
final_score =
0.35 * ncf_score +
0.30 * textcnn_score +
0.20 * genre_score +
0.10 * quality_score +
0.05 * diversity_score
```

当前降级策略：
- `NCF + TextCNN + 规则分`
- `NCF + 规则内容相似度 + 规则分`
- `TextCNN + 规则分`
- `规则内容推荐 + 多样性重排`

## 8. 注意事项

1. `GET /get_recommend` 不再支持通过查询参数同步刷新推荐。
2. 刷新推荐必须通过 `POST /refresh-recommendations` + `GET /refresh-status` 完成。
3. 电影和剧集的偏好、行为、权重是分桶维护的。
4. 如果某一类型没有足够偏好数据，系统会退回到较弱的内容推荐链路。
