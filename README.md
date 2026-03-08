# 电影推荐系统后端 API

基于 Flask 的智能电影/剧集推荐系统后端服务，使用神经协同过滤（NCF）和文本卷积神经网络（TextCNN）算法。

## 功能特性

- 🎬 **智能推荐**：基于用户偏好的个性化推荐
- 🔍 **智能搜索**：支持模糊搜索和相似度匹配
- 📋 **想看清单**：用户可以管理自己的观影清单
- 👎 **负反馈**：支持用户反馈不喜欢的内容
- 🖼️ **图片代理**：解决跨域图片访问问题
- 📊 **数据管理**：CSV 数据导入导出

## 技术栈

- **Web 框架**：Flask 3.1.3
- **数据处理**：Pandas, NumPy
- **机器学习**：PyTorch, Scikit-learn
- **文本处理**：Jieba
- **图像处理**：Pillow

## 项目结构

```
diploma-project-backend/
├── movie_recommendation/     # 主应用目录
│   ├── api/                 # API 路由模块
│   ├── data/                # 数据管理模块
│   ├── recommendation/      # 推荐引擎模块
│   ├── search/              # 搜索模块
│   ├── utils/               # 工具模块
│   ├── watchlist/           # 想看清单模块
│   ├── app.py              # Flask 应用入口
│   └── config.py           # 配置管理
├── data/                    # 数据目录
│   ├── datasets/           # CSV 数据集
│   ├── user/               # 用户数据
│   └── recommendations/    # 推荐结果
├── cache/                   # 缓存目录
├── logs/                    # 日志目录
├── tests/                   # 测试目录
└── docs/                    # 文档目录
```

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd diploma-project-backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
copy .env.example .env

# 编辑 .env 文件，配置必要的参数
```

### 3. 准备数据

将电影和剧集的 CSV 数据文件放置到 `data/datasets/` 目录：
- `douban_movies.csv`
- `douban_series.csv`

### 4. 启动服务

```bash
# 开发模式
python movie_recommendation/app.py

# 或使用 Flask 命令
flask run
```

服务将在 `http://localhost:5000` 启动。

## API 文档

### 系统信息

- `GET /` - 服务首页
- `GET /api/system-info` - 获取系统信息

### 数据管理

- `GET /api/movies` - 获取电影数据（JSON 格式）
- `GET /api/csv-text?type=movie` - 获取 CSV 原始文本
- `GET /api/download-csv?type=movie` - 下载 CSV 文件

### 电影查询

- `POST /api/get-movie-by-name` - 根据电影名查询
- `POST /api/get-movies-by-names` - 批量查询电影

### 剧集查询

- `POST /api/get-series-by-name` - 根据剧集名查询
- `POST /api/get-series-by-names` - 批量查询剧集

### 推荐系统

- `GET /get_recommend?type=movie&refresh=true` - 获取推荐
- `POST /refresh-recommendations` - 刷新推荐
- `POST /sync-user-data` - 同步用户偏好数据

### 搜索

- `GET /search?q=关键词&type=movie` - 智能搜索

### 想看清单

- `GET /watchlist?type=movie` - 获取想看清单
- `POST /watchlist/add` - 添加到想看清单
- `POST /watchlist/remove` - 从想看清单移除

### 反馈

- `POST /negative-feedback` - 提交负反馈

### 图片代理

- `GET /proxy-image?url=图片地址` - 图片代理服务

详细 API 文档请查看 [docs/API.md](docs/API.md)

## 开发指南

### 代码规范

- 遵循 PEP 8 代码风格
- 使用类型注解（Type Hints）
- 编写完整的文档字符串（Docstrings）
- 单元测试覆盖率 > 80%

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_api.py

# 查看测试覆盖率
pytest --cov=movie_recommendation
```

### 贡献指南

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 部署

详细部署指南请查看 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## 许可证

本项目采用 MIT 许可证。

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。

---

**注意**：本项目为毕业设计项目，仅供学习和研究使用。
