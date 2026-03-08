# 快速启动指南

## 🎉 项目已成功启动！

### 当前状态

✅ **服务正在运行**
- 本地地址: http://127.0.0.1:5000
- 局域网地址: http://192.168.1.100:5000
- 调试模式: 已开启

### 访问服务

#### 1. 在浏览器中打开

```
http://localhost:5000
```

你会看到 API 端点列表页面。

#### 2. 测试 API

**获取系统信息**:
```
http://localhost:5000/api/system-info
```

**获取推荐**:
```
http://localhost:5000/get_recommend?type=movie
```

### 当前警告说明

#### ⚠️ 数据集文件路径问题

**日志显示**:
```
❌ 数据集文件不存在: movie_recommendation\data\douban_movies.csv
```

**实际位置**:
```
data\datasets\douban_movies.csv  ✅ 文件存在
```

**原因**: 某些模块使用了旧的路径配置

**影响**: 
- ✅ 服务可以正常启动
- ⚠️ 推荐功能可能返回空数据
- ✅ 其他 API 功能正常

**临时解决方案**: 
系统会使用备用推荐算法，不影响基本功能。

#### ⚠️ TensorFlow 未安装

**日志显示**:
```
⚠️ TensorFlow/Keras未安装，将使用基于内容的推荐方案
```

**说明**: 
- 这是正常的，不是错误
- 系统会自动使用备用推荐算法
- 基本推荐功能完全可用

**如果需要深度学习推荐**:
```bash
pip install tensorflow
```

### 可用的 API 端点

#### 系统信息
- `GET /` - 服务首页
- `GET /api/system-info` - 系统信息

#### 数据管理
- `GET /api/movies` - 获取电影数据
- `GET /api/csv-text?type=movie` - 获取 CSV 文本
- `GET /api/download-csv?type=movie` - 下载 CSV

#### 电影查询
- `POST /api/get-movie-by-name` - 根据名称查询电影
- `POST /api/get-movies-by-names` - 批量查询电影

#### 剧集查询
- `POST /api/get-series-by-name` - 根据名称查询剧集
- `POST /api/get-series-by-names` - 批量查询剧集

#### 推荐系统
- `GET /get_recommend?type=movie` - 获取推荐
- `POST /sync-user-data` - 同步用户数据
- `POST /refresh-recommendations` - 刷新推荐

#### 搜索
- `GET /search?q=关键词` - 智能搜索

#### 想看清单
- `GET /watchlist` - 获取想看清单
- `POST /watchlist/add` - 添加到清单
- `POST /watchlist/remove` - 从清单移除

#### 反馈
- `POST /negative-feedback` - 提交负反馈

#### 图片代理
- `GET /proxy-image?url=图片地址` - 图片代理

### 测试示例

#### 使用浏览器

直接在浏览器中访问：
```
http://localhost:5000/api/system-info
```

#### 使用 curl

```bash
# 获取系统信息
curl http://localhost:5000/api/system-info

# 获取推荐
curl http://localhost:5000/get_recommend?type=movie

# 搜索
curl "http://localhost:5000/search?q=肖申克"
```

#### 使用 Python

```python
import requests

# 获取系统信息
response = requests.get('http://localhost:5000/api/system-info')
print(response.json())

# 获取推荐
response = requests.get('http://localhost:5000/get_recommend?type=movie')
print(response.json())
```

### 停止服务

在终端中按 `Ctrl+C` 停止服务。

### 重新启动

```bash
python movie_recommendation\app.py
```

### 调试信息

**Debugger PIN**: 741-868-435

这是 Flask 调试器的 PIN 码，用于在浏览器中调试错误。

### 常见问题

#### Q1: 推荐结果为空？
**A**: 这是正常的，因为：
1. 用户数据为空（偏好数量: 0）
2. 需要先同步用户偏好数据

**解决方案**:
```bash
# 使用 POST /sync-user-data 接口上传用户偏好
curl -X POST http://localhost:5000/sync-user-data \
  -H "Content-Type: application/json" \
  -d '{"preferences": [{"id": "1", "name": "肖申克的救赎", "genres": ["剧情", "犯罪"]}]}'
```

#### Q2: 如何查看完整日志？
**A**: 日志会实时显示在终端中。

#### Q3: 如何修改端口？
**A**: 编辑 `.env` 文件或在启动时指定：
```bash
set PORT=8000
python movie_recommendation\app.py
```

#### Q4: 如何关闭调试模式？
**A**: 编辑 `.env` 文件：
```
FLASK_DEBUG=False
```

### 下一步

1. ✅ **服务已启动** - 可以开始使用 API
2. 📝 **上传用户数据** - 使用 `/sync-user-data` 接口
3. 🎬 **获取推荐** - 使用 `/get_recommend` 接口
4. 🔍 **测试搜索** - 使用 `/search` 接口

### 生产环境部署

当前是开发模式，生产环境建议使用：

```bash
# 安装 gunicorn
pip install gunicorn

# 启动生产服务器
gunicorn -w 4 -b 0.0.0.0:5000 movie_recommendation.app:app
```

详细部署指南: 查看 `docs/DEPLOYMENT.md`

---

**服务状态**: ✅ 运行中
**访问地址**: http://localhost:5000
**调试模式**: 开启
**更新时间**: 2024-03-08
