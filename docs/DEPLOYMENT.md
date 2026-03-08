# 部署指南

本文档介绍如何在不同环境中部署电影推荐系统后端服务。

## 1. 开发环境部署

### 1.1 前置要求

- Python 3.7+
- pip
- 虚拟环境工具（venv 或 virtualenv）

### 1.2 部署步骤

```bash
# 1. 克隆项目
git clone <repository-url>
cd diploma-project-backend

# 2. 创建虚拟环境
python -m venv venv

# 3. 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 配置环境变量
copy .env.example .env
# 编辑 .env 文件

# 6. 准备数据
# 将 CSV 数据文件放到 data/datasets/ 目录

# 7. 启动服务
python movie_recommendation/app.py
```

服务将在 `http://localhost:5000` 启动。

## 2. 生产环境部署

### 2.1 使用 Gunicorn (推荐)

#### 安装 Gunicorn

```bash
pip install gunicorn
```

#### 启动服务

```bash
# 基本启动
gunicorn -w 4 -b 0.0.0.0:5000 movie_recommendation.app:app

# 使用配置文件
gunicorn -c gunicorn_config.py movie_recommendation.app:app
```

#### Gunicorn 配置文件 (gunicorn_config.py)

```python
import multiprocessing

# 服务器配置
bind = "0.0.0.0:5000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# 日志配置
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"

# 进程命名
proc_name = "movie_recommendation"

# 后台运行
daemon = False

# 优雅重启
graceful_timeout = 30
```

### 2.2 使用 uWSGI

#### 安装 uWSGI

```bash
pip install uwsgi
```

#### 配置文件 (uwsgi.ini)

```ini
[uwsgi]
# 应用配置
module = movie_recommendation.app:app
callable = app

# 服务器配置
http = 0.0.0.0:5000
processes = 4
threads = 2
master = true

# 日志配置
logto = logs/uwsgi.log
log-maxsize = 50000000

# 性能优化
enable-threads = true
lazy-apps = true
vacuum = true
die-on-term = true
```

#### 启动服务

```bash
uwsgi --ini uwsgi.ini
```

### 2.3 使用 Nginx 反向代理

#### Nginx 配置

```nginx
upstream movie_recommendation {
    server 127.0.0.1:5000;
    # 如果有多个实例
    # server 127.0.0.1:5001;
    # server 127.0.0.1:5002;
}

server {
    listen 80;
    server_name your-domain.com;

    # 日志配置
    access_log /var/log/nginx/movie_recommendation_access.log;
    error_log /var/log/nginx/movie_recommendation_error.log;

    # 静态文件（如果有）
    location /static {
        alias /path/to/project/static;
        expires 30d;
    }

    # API 代理
    location / {
        proxy_pass http://movie_recommendation;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # 文件上传大小限制
    client_max_body_size 10M;
}
```

#### HTTPS 配置（使用 Let's Encrypt）

```bash
# 安装 Certbot
sudo apt-get install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

## 3. Docker 部署

### 3.1 Dockerfile

```dockerfile
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建必要的目录
RUN mkdir -p data/datasets data/user data/recommendations cache/images logs

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "movie_recommendation.app:app"]
```

### 3.2 docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./cache:/app/cache
      - ./logs:/app/logs
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=${SECRET_KEY}
    restart: unless-stopped
    networks:
      - app-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - web
    restart: unless-stopped
    networks:
      - app-network

networks:
  app-network:
    driver: bridge
```

### 3.3 构建和运行

```bash
# 构建镜像
docker build -t movie-recommendation .

# 运行容器
docker run -d -p 5000:5000 --name movie-rec movie-recommendation

# 使用 docker-compose
docker-compose up -d

# 查看日志
docker-compose logs -f web

# 停止服务
docker-compose down
```

## 4. 云平台部署

### 4.1 AWS EC2

```bash
# 1. 启动 EC2 实例（Ubuntu 20.04）

# 2. 连接到实例
ssh -i your-key.pem ubuntu@your-ec2-ip

# 3. 安装依赖
sudo apt-get update
sudo apt-get install python3-pip python3-venv nginx

# 4. 克隆项目
git clone <repository-url>
cd diploma-project-backend

# 5. 设置虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 6. 配置 Nginx
sudo cp nginx.conf /etc/nginx/sites-available/movie-recommendation
sudo ln -s /etc/nginx/sites-available/movie-recommendation /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 7. 使用 systemd 管理服务
sudo cp movie-recommendation.service /etc/systemd/system/
sudo systemctl enable movie-recommendation
sudo systemctl start movie-recommendation
```

#### systemd 服务文件 (movie-recommendation.service)

```ini
[Unit]
Description=Movie Recommendation API
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/diploma-project-backend
Environment="PATH=/home/ubuntu/diploma-project-backend/venv/bin"
ExecStart=/home/ubuntu/diploma-project-backend/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 movie_recommendation.app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4.2 Heroku

```bash
# 1. 安装 Heroku CLI
# https://devcenter.heroku.com/articles/heroku-cli

# 2. 登录
heroku login

# 3. 创建应用
heroku create your-app-name

# 4. 添加 Procfile
echo "web: gunicorn movie_recommendation.app:app" > Procfile

# 5. 部署
git add .
git commit -m "Deploy to Heroku"
git push heroku main

# 6. 查看日志
heroku logs --tail
```

### 4.3 阿里云 ECS

部署步骤类似 AWS EC2，主要区别：
- 使用阿里云控制台创建 ECS 实例
- 配置安全组规则开放端口
- 可以使用阿里云 SLB 做负载均衡

## 5. 性能优化

### 5.1 应用层优化

```python
# 使用连接池
from flask_sqlalchemy import SQLAlchemy
app.config['SQLALCHEMY_POOL_SIZE'] = 10
app.config['SQLALCHEMY_MAX_OVERFLOW'] = 20

# 启用 gzip 压缩
from flask_compress import Compress
Compress(app)

# 使用缓存
from flask_caching import Cache
cache = Cache(app, config={'CACHE_TYPE': 'redis'})
```

### 5.2 数据库优化

- 使用索引加速查询
- 使用连接池
- 读写分离
- 数据分片

### 5.3 缓存策略

- Redis 缓存热点数据
- CDN 加速静态资源
- 浏览器缓存

## 6. 监控与维护

### 6.1 日志管理

```bash
# 使用 logrotate 管理日志
sudo vim /etc/logrotate.d/movie-recommendation

/path/to/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload movie-recommendation
    endscript
}
```

### 6.2 健康检查

```python
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })
```

### 6.3 监控工具

- **Prometheus + Grafana**: 指标监控
- **ELK Stack**: 日志分析
- **Sentry**: 错误追踪
- **New Relic**: APM 监控

## 7. 备份与恢复

### 7.1 数据备份

```bash
# 备份脚本
#!/bin/bash
BACKUP_DIR="/backup/movie-recommendation"
DATE=$(date +%Y%m%d_%H%M%S)

# 备份数据
tar -czf $BACKUP_DIR/data_$DATE.tar.gz data/

# 备份配置
tar -czf $BACKUP_DIR/config_$DATE.tar.gz .env movie_recommendation/config.py

# 删除 7 天前的备份
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

### 7.2 自动备份

```bash
# 添加到 crontab
crontab -e

# 每天凌晨 2 点备份
0 2 * * * /path/to/backup.sh
```

## 8. 故障排查

### 8.1 常见问题

**问题 1**: 服务无法启动
```bash
# 检查端口占用
netstat -tulpn | grep 5000

# 检查日志
tail -f logs/error.log
```

**问题 2**: 性能问题
```bash
# 检查进程资源使用
top -p $(pgrep -f gunicorn)

# 检查数据库连接
# 查看慢查询日志
```

**问题 3**: 内存泄漏
```bash
# 使用 memory_profiler
pip install memory_profiler
python -m memory_profiler movie_recommendation/app.py
```

### 8.2 紧急恢复

```bash
# 回滚到上一个版本
git checkout <previous-commit>
sudo systemctl restart movie-recommendation

# 从备份恢复
tar -xzf backup/data_20240308.tar.gz
```

## 9. 安全加固

### 9.1 防火墙配置

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 9.2 SSL/TLS 配置

- 使用强加密套件
- 启用 HSTS
- 配置 OCSP Stapling

### 9.3 应用安全

- 定期更新依赖
- 使用环境变量存储敏感信息
- 实施 API 限流
- 添加 CSRF 保护

## 10. 扩展阅读

- [Flask 部署选项](https://flask.palletsprojects.com/en/2.3.x/deploying/)
- [Gunicorn 文档](https://docs.gunicorn.org/)
- [Nginx 配置指南](https://nginx.org/en/docs/)
- [Docker 最佳实践](https://docs.docker.com/develop/dev-best-practices/)
