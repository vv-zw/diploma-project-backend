# API 接口文档

## 基础信息

- **Base URL**: `http://localhost:5000`
- **API Version**: v2.0
- **Content-Type**: `application/json`

## 响应格式

所有 API 响应遵循统一格式：

```json
{
  "code": 0,           // 0 表示成功，非 0 表示错误
  "data": {},          // 响应数据
  "message": "",       // 消息说明（可选）
  "error": ""          // 错误信息（仅在失败时）
}
```

## API 端点

### 1. 系统信息

#### 1.1 获取服务首页

```
GET /
```

返回服务状态和可用 API 列表。

#### 1.2 获取系统信息

```
GET /api/system-info
```

**响应示例**：
```json
{
  "code": 0,
  "server_time": "2024-03-08 10:30:00",
  "base_dir": "/path/to/project",
  "preferences_count": 10,
  "movie_dataset_exists": true,
  "series_dataset_exists": true,
  "api_version": "v2.0"
}
```

---

### 2. 数据管理

#### 2.1 获取电影数据

```
GET /api/movies
```

返回所有电影数据的 JSON 格式。

**响应示例**：
```json
{
  "code": 0,
  "data": [
    {
      "id": "1",
      "title": "肖申克的救赎",
      "rating": "9.7",
      "year": "1994",
      "genres": "剧情,犯罪"
    }
  ],
  "count": 1000
}
```

#### 2.2 获取 CSV 原始文本

```
GET /api/csv-text?type=movie
```

**参数**：
- `type` (可选): `movie` 或 `series`，默认 `movie`

返回 CSV 文件的原始文本内容。

#### 2.3 下载 CSV 文件

```
GET /api/download-csv?type=movie
```

**参数**：
- `type` (可选): `movie` 或 `series`，默认 `movie`

直接下载 CSV 文件。

---

### 3. 电影查询

#### 3.1 根据电影名查询

```
POST /api/get-movie-by-name
```

**请求体**：
```json
{
  "name": "肖申克的救赎"
}
```

**响应示例**：
```json
{
  "code": 0,
  "data": {
    "id": "1",
    "title": "肖申克的救赎",
    "name": "肖申克的救赎",
    "genres": "剧情,犯罪",
    "rating": "9.7",
    "year": "1994",
    "director": "弗兰克·德拉邦特",
    "actors": "蒂姆·罗宾斯,摩根·弗里曼",
    "duration": "142分钟",
    "country": "美国",
    "similarity_score": 1.0
  }
}
```

#### 3.2 批量查询电影

```
POST /api/get-movies-by-names
```

**请求体**：
```json
{
  "names": ["肖申克的救赎", "阿甘正传"],
  "onlyReturnRequested": true
}
```

**响应示例**：
```json
{
  "code": 0,
  "results": [
    {
      "name_requested": "肖申克的救赎",
      "matched_title": "肖申克的救赎",
      "data": { /* 电影详情 */ },
      "similarity_score": 1.0
    }
  ],
  "count": 2,
  "success_count": 2
}
```

---

### 4. 剧集查询

#### 4.1 根据剧集名查询

```
POST /api/get-series-by-name
POST /api/get-drama-by-name  (别名)
```

**请求体**：
```json
{
  "name": "权力的游戏"
}
```

**响应示例**：
```json
{
  "code": 0,
  "data": {
    "id": "1",
    "title": "权力的游戏",
    "genres": "剧情,奇幻,冒险",
    "rating": "9.3",
    "episodes": "73",
    "region": "美国",
    "status": "完结"
  }
}
```

#### 4.2 批量查询剧集

```
POST /api/get-series-by-names
POST /api/get-dramas-by-names  (别名)
```

请求格式同批量查询电影。

---

### 5. 推荐系统

#### 5.1 获取推荐

```
GET /get_recommend?type=movie&refresh=false&force_refresh=false
```

**参数**：
- `type` (可选): `movie` 或 `series`，默认 `movie`
- `refresh` (可选): 是否刷新推荐，默认 `false`
- `force_refresh` (可选): 是否强制刷新，默认 `false`

**响应示例**：
```json
{
  "code": 0,
  "data": [
    {
      "id": "1",
      "title": "肖申克的救赎",
      "rating": "9.7",
      "score": 0.95
    }
  ],
  "count_weights": {
    "剧情": 0.4,
    "犯罪": 0.3
  },
  "generated_time": "2024-03-08 10:30:00",
  "refreshed": false,
  "algorithm_version": "NCF+TextCNN_v1.0"
}
```

#### 5.2 同步用户偏好数据

```
POST /sync-user-data
```

**请求体**：
```json
{
  "preferences": [
    {
      "id": "1",
      "name": "肖申克的救赎",
      "genres": ["剧情", "犯罪"],
      "rating": 9.7,
      "year": 1994
    }
  ]
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "数据同步成功",
  "count_weights": {
    "剧情": 0.5,
    "犯罪": 0.5
  },
  "saved_preferences_count": 1,
  "updated_recommendations": true
}
```

#### 5.3 刷新推荐

```
POST /refresh-recommendations
GET /refresh-recommendations?type=movie
```

**请求体** (POST):
```json
{
  "type": "movie"  // 可选，不传则刷新所有
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "movie推荐已刷新",
  "type": "movie",
  "timestamp": "2024-03-08 10:30:00"
}
```

---

### 6. 搜索

#### 6.1 智能搜索

```
GET /search?q=肖申克&type=movie
```

**参数**：
- `q` (必需): 搜索关键词
- `type` (可选): `movie` 或 `series`

**响应示例**：
```json
{
  "code": 0,
  "query": "肖申克",
  "count": 5,
  "results": [
    {
      "id": "1",
      "title": "肖申克的救赎",
      "similarity": 0.95
    }
  ]
}
```

---

### 7. 想看清单

#### 7.1 获取想看清单

```
GET /watchlist?type=movie
```

**参数**：
- `type` (可选): `movie` 或 `series`

**响应示例**：
```json
{
  "code": 0,
  "count": 5,
  "watchlist": [
    {
      "id": "1",
      "title": "肖申克的救赎",
      "added_time": "2024-03-08 10:00:00"
    }
  ],
  "timestamp": "2024-03-08 10:30:00"
}
```

#### 7.2 添加到想看清单

```
POST /watchlist/add
```

**请求体**：
```json
{
  "item_id": "1",
  "type": "movie",
  "data": {
    "title": "肖申克的救赎",
    "rating": "9.7"
  }
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "添加成功",
  "item_id": "1"
}
```

#### 7.3 从想看清单移除

```
POST /watchlist/remove
```

**请求体**：
```json
{
  "item_id": "1",
  "type": "movie"
}
```

---

### 8. 反馈

#### 8.1 提交负反馈

```
POST /negative-feedback
```

**请求体**：
```json
{
  "item_id": "1",
  "type": "movie",
  "reason": "不喜欢这类题材"
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "负反馈已记录",
  "item_id": "1",
  "updated": true
}
```

---

### 9. 图片代理

#### 9.1 图片代理服务

```
GET /proxy-image?url=https://img3.doubanio.com/view/photo/s_ratio_poster/public/p480747492.jpg
```

**参数**：
- `url` (必需): 图片 URL

返回图片二进制数据，Content-Type 为 `image/jpeg` 或 `image/png`。

---

## 错误码

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 注意事项

1. 所有 POST 请求的 Content-Type 必须为 `application/json`
2. 图片代理服务仅支持豆瓣域名的图片
3. 推荐结果会缓存 5 分钟，可通过 `refresh` 参数强制刷新
4. 批量查询接口建议每次不超过 50 个项目
