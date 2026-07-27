## 生产环境部署（HTTP + 现有 MySQL）

这套生产部署与开发 `docker-compose.dev.yml` 完全隔离：
- **生产**：`docker-compose.prod.yml`（Nginx + 静态前端 + Gunicorn 后端）
- **开发**：`docker-compose.dev.yml`（Vite dev server + Django runserver）

### 前置条件

- 服务器已安装 Docker / Docker Compose
- 服务器能访问你的 MySQL（`DB_HOST/DB_PORT` 网络可达）
- 开放端口：`80`（或你改成的 `HTTP_PORT`）

### 1）准备环境变量

复制模板生成生产环境变量文件（注意：文件名必须是 `.env.prod`）：

- Windows：

```bash
copy env.prod.example.txt .env.prod
```

- Linux/macOS：

```bash
cp env.prod.example.txt .env.prod
```

然后编辑 `.env.prod`，至少填：
- `SECRET_KEY`
- `ALLOWED_HOSTS`（你的服务器 IP，例如 `192.168.56.1`）
- `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`
- `REDIS_PASSWORD`

### 2）启动生产环境

在项目根目录执行：

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

首次启动会在容器内自动执行：
- `python manage.py migrate --noinput`（由后端 entrypoint 执行）
- `python manage.py collectstatic --noinput`（由后端 command 执行）

### 3）初始化管理员账号（只需一次）

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

### 4）访问

浏览器访问：
- `http://192.168.56.1/`

API（用于自测）：
- `http://192.168.56.1/api/`

---

## 更新流程（开发 → 生产）

生产更新建议流程：

1. 在开发环境完成改动并自测
2. 将代码更新到生产服务器（例如 git pull 或同步代码）
3. 在生产服务器执行：

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate --noinput
```

如果只更新后端代码，`--build` 会重建镜像并滚动更新；前端改动也会在 Nginx 镜像构建时自动重新 `vite build`。

