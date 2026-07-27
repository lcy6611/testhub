## 使用 Docker 启动本地开发环境（MySQL + Django + Vue）

> 开发环境用，容器里跑 MySQL / Redis / Django dev / 前端 dev，代码仍在宿主机编辑。

### 1. 准备环境文件

在项目根目录执行（只需一次）：

```bash
cd E:\PycharmProjects\testhub_platform
copy docker\env.docker.example docker\.env.docker
```

然后按需修改 `docker\.env.docker`。**与本地共用同一个 MySQL 时**：`DB_NAME`、`DB_USER`、`DB_PASSWORD` 必须与本地一致（例如本地用 `root`/`141008` 则这里也填相同），compose 已通过 `host.docker.internal` 连宿主机 MySQL。

### 2. 启动所有服务

在项目根目录执行：

```bash
docker compose -f docker-compose.dev.yml up -d
```

首次会拉取镜像并初始化数据库，时间会较长。

### 3. 访问

- 后端 API：`http://localhost:8000/api/`
- 前端开发站点（Vite）：`http://localhost:5173/`

### 4. 登录与 API 代理

- 前端（localhost:5173）通过 Vite 代理将 `/api` 请求转发到容器内 `backend:8000`（由 `VITE_PROXY_TARGET` 配置）。
- 若曾出现登录 400 或 “Session data corrupted”，多为浏览器携带了过期的 session cookie；后端已对 `/api/` 请求忽略该 cookie，避免因此报错。

### 5. 停止 / 查看日志

```bash
# 停止并移除容器
docker compose -f docker-compose.dev.yml down

# 查看某个服务日志（示例：backend）
docker compose -f docker-compose.dev.yml logs -f backend
```

