# 将 Dify 部署到阿里云 ECS

以下步骤把 Dify 跑在阿里云 ECS 上，通过公网访问。

---

## 一、准备 ECS

1. **购买/准备一台 ECS**
   - 地域：建议与你的阿里云镜像仓库一致（如青岛 cn-qingdao），便于用内网拉镜像。
   - 配置：至少 **2 核 4GB**，推荐 4 核 8GB。
   - 系统盘：**Alibaba Cloud Linux 3** 或 **Ubuntu 22.04**。
   - 网络：分配公网 IP，或后面绑定弹性公网 IP。

2. **安全组**
   - 入方向放行：**80**（HTTP）、**443**（HTTPS，若用 SSL）。若暂时只测 HTTP，只开 80 即可。

3. **登录 ECS**
   - 使用 SSH（或阿里云控制台「远程连接」）登录，例如：
     ```bash
     ssh root@你的ECS公网IP
     ```

---

## 二、在 ECS 上安装 Docker 与 Docker Compose

**Alibaba Cloud Linux 3 / CentOS 系：**

```bash
# 安装 Docker
yum install -y docker-ce docker-ce-cli containerd.io
systemctl enable docker && systemctl start docker

# 安装 Docker Compose 插件（或独立命令 docker-compose）
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

**Ubuntu：**

```bash
apt update && apt install -y docker.io docker-compose-plugin
systemctl enable docker && systemctl start docker
```

验证：`docker --version`、`docker compose version`（或 `docker-compose --version`）有输出即可。

---

## 三、在 ECS 上部署 Dify

分两种方式：**能访问外网** 与 **不能访问 Docker Hub、走阿里云镜像仓库**。

### 方式 A：ECS 能访问外网（可直接拉 Docker Hub）

1. 在 ECS 上拉取 Dify 代码并启动：
   ```bash
   cd /opt
   git clone --depth 1 https://github.com/langgenius/dify.git
   cd dify/docker
   cp .env.example .env
   # 可选：编辑 .env 修改端口、域名等
   docker compose pull
   docker compose up -d
   ```
2. 浏览器访问：`http://你的ECS公网IP/install`，按提示创建管理员账号。

若 GitHub 较慢，可先在本地下载 Dify 的 ZIP，用 scp 或 SFTP 上传到 ECS 的 `/opt` 后解压，再执行上面 `cd dify/docker` 及之后的命令。

---

### 方式 B：ECS 不能访问 Docker Hub（用阿里云镜像仓库）

**思路**：在**能访问 Docker Hub 的机器**（如你本机）把 Dify 所需镜像推到你的阿里云 ACR；在 **ECS** 上登录 ACR，用这些镜像启动 Dify。

**步骤 1：在本机（或能上外网的机器）推送 Dify 镜像到阿里云**

- 你已能 `docker login` 阿里云且 Login Succeeded。
- 在项目里已有 **dify-main** 时，在本机执行：
  ```bash
  cd E:\PycharmProjects\testhub_platform\dify-main\docker
  docker compose pull
  ```
- 在阿里云 ACR 为每个 Dify 镜像创建一个「镜像仓库」（命名空间用你已有的，如 testhub-lcy；仓库名可设为 dify-api、dify-web、dify-nginx 等，与下面 tag 一致即可）。
- 对每个镜像做 tag 并 push（把 `REGISTRY` 换成你的公网地址，如 `crpi-hr6f2vrzv7uqdl2t.cn-qingdao.personal.cr.aliyuncs.com/testhub-lcy`）：
  ```bash
  set REGISTRY=crpi-hr6f2vrzv7uqdl2t.cn-qingdao.personal.cr.aliyuncs.com/testhub-lcy
  docker tag langgenius/dify-api:1.12.1 %REGISTRY%/dify-api:1.12.1
  docker push %REGISTRY%/dify-api:1.12.1
  docker tag langgenius/dify-web:1.12.1 %REGISTRY%/dify-web:1.12.1
  docker push %REGISTRY%/dify-web:1.12.1
  ```
  其余镜像（nginx、worker、worker_beat、db_postgres、redis、weaviate、plugin_daemon、ssrf_proxy、sandbox 等）同理：先 `docker compose config --images` 查看列表，再逐个 tag 并 push 到 ACR。

**步骤 2：在 ECS 上用阿里云镜像启动 Dify**

- 把 **dify-main** 的 `docker` 目录（含 `docker-compose.yaml`、`.env`）上传到 ECS，例如 `/opt/dify/docker`。
- 在 ECS 上登录阿里云镜像仓库（**用公网地址**，若 ECS 与 ACR 同地域可用 VPC 地址加速）：
  ```bash
  docker login --username=lcy2020026128 crpi-hr6f2vrzv7uqdl2t.cn-qingdao.personal.cr.aliyuncs.com
  ```
- 编辑 `docker-compose.yaml`（或通过 .env 覆盖）：把所有 `image: xxx` 改为你在 ACR 的地址，例如：
  - `image: crpi-hr6f2vrzv7uqdl2t.cn-qingdao.personal.cr.aliyuncs.com/testhub-lcy/dify-api:1.12.1`
  - 其他服务同理。
- 启动：
  ```bash
  cd /opt/dify/docker
  docker compose up -d
  ```
- 浏览器访问：`http://你的ECS公网IP/install`，完成初始化。

---

## 四、可选：绑定域名与 HTTPS

- 在阿里云**域名解析**里把域名 A 记录指向 ECS 公网 IP。
- 在 Dify 的 `.env` 中设置 `APP_WEB_URL=https://你的域名` 等（参考 Dify 官方文档）。
- 在 ECS 上可用 **Nginx 反向代理 + Let's Encrypt** 或阿里云 **SSL 证书 + SLB** 做 HTTPS。

---

## 五、小结

| 场景           | 做法 |
|----------------|------|
| ECS 能访问外网 | 在 ECS 上 clone Dify → `docker compose up -d`，访问 `http://ECS公网IP/install` |
| ECS 不能访问 Docker Hub | 本机把 Dify 镜像 push 到阿里云 ACR → ECS 上 login ACR，修改 compose 使用 ACR 镜像后 `docker compose up -d` |
| 已登录阿里云 ACR | 使用「方式 B」即可在 ECS 上从阿里云拉取镜像部署 Dify |

按你 ECS 是否能访问外网，选择 **方式 A** 或 **方式 B** 即可把 Dify 部署到阿里云上。
