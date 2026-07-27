# 部署 Dify

## 前置条件

- **Docker Desktop**：必须先安装并**保持运行**（托盘图标为运行中）。  
  下载：https://www.docker.com/products/docker-desktop/

---

## 方式一：在线安装（有网络）

在**项目根目录**下执行：

```cmd
deploy\dify\install-and-start.bat
```

脚本会：使用 dify-main 或克隆 → 生成 `.env` → 拉取镜像并启动。完成后访问 http://localhost/install 初始化。

---

## 方式二：离线安装（无网络 / 连不上外网）

### 步骤 A：在「能访问 Docker Hub」的机器上（只需做一次）

**重要**：导出脚本需要能访问 **registry-1.docker.io**（Docker Hub）。若本机拉取报错 `context deadline exceeded` 或 100% 丢包，说明当前环境连不上 Docker Hub，请用下面任一方式生成离线包：

- **换一台能上外网的电脑**（家里、另一间办公室、云服务器等）：在该机克隆/解压 Dify 到 **dify-main**，运行一次 `deploy\dify\export-images.bat`，再把生成的 **deploy\dify\offline** 拷到 U 盘或内网，拿到当前机器使用。
- **配置 Docker 镜像加速**（仅在国内网络时可能有效）：Docker Desktop → Settings → Docker Engine，增加 `"registry-mirrors": ["https://镜像地址"]`（如阿里云、腾讯云等提供的镜像），保存后重试 `export-images.bat`。

在上述「能成功拉取镜像」的机器上：

1. 确保已有 **dify-main**（或 deploy\dify-repo），且 Docker 已启动。
2. 在项目根目录执行：
   ```cmd
   deploy\dify\export-images.bat
   ```
3. 脚本会拉取全部 Dify 镜像并导出到 **deploy\dify\offline**，包括：
   - `dify-images.tar`（所有镜像打包）
   - `docker\`（compose 与 .env）
4. 将整个 **deploy\dify\offline** 文件夹拷贝到 U 盘或内网，再复制到**离线机**的同一路径（如 `E:\PycharmProjects\testhub_platform\deploy\dify\offline`）。

### 步骤 B：在离线机上（无外网）

1. 安装并启动 **Docker Desktop**（可用离线安装包提前装好）。
2. 在项目根目录执行：
   ```cmd
   deploy\dify\import-and-start.bat
   ```
   若离线包放在别的路径，可指定：
   ```cmd
   deploy\dify\import-and-start.bat D:\path\to\offline
   ```
3. 脚本会从 `dify-images.tar` 导入镜像（不联网），再启动容器。
4. 浏览器访问 **http://localhost/install** 完成初始化。

---

## 无法访问 Docker Hub 时的替代方案

若本机无法访问 Docker Hub（如 `registry-1.docker.io` 超时、丢包），可尝试以下方式，**不必直接连 Docker Hub**：

### 方案一：配置 Docker 镜像加速（推荐先试）

让 Docker 通过**国内或可访问的镜像站**拉取镜像，而不是直连 Docker Hub。

**Windows Docker Desktop 操作步骤**（简要）：

1. 打开 **Docker Desktop** → 右上角 **Settings** → 左侧 **Docker Engine**。
2. 在 JSON 里加上 `"registry-mirrors": ["https://dockerproxy.com", "https://docker.m.daocloud.io", "https://docker.1panel.live", "https://hub-mirror.c.163.com", "https://mirror.baidubce.com"]`（若已有其他键，保留并只在顶层增加该键，注意逗号）。
3. 点 **Apply & restart**，等 Docker 重启完成。
4. 再执行：`deploy\dify\install-and-start.bat`。

**详细说明与示例 JSON** 见：**[配置Docker镜像加速.md](配置Docker镜像加速.md)**。

### 方案二：用能访问外网的机器导出离线包

在**另一台能正常拉取 Docker 镜像的电脑**（家里、其他网络、云服务器等）上：

1. 放好 **dify-main** 和 **deploy\dify**，运行一次 `deploy\dify\export-images.bat`。
2. 将生成的 **deploy\dify\offline** 整份拷贝到本机，再执行 `deploy\dify\import-and-start.bat`。

详见上文「方式二：离线安装」。

### 方案三：本机有 HTTP 代理时

若本机通过代理才能访问外网：

1. Docker Desktop → **Settings** → **Resources** → **Proxies**。
2. 开启 **Manual proxy configuration**，填写代理地址与端口（及账号密码（若有））。
3. 保存并重启 Docker 后，再执行安装或导出脚本。

---

## 若 Git 克隆失败（在线机）

1. 打开 https://github.com/langgenius/dify/releases  
2. 下载 **Source code (zip)**，解压到项目根目录，文件夹改名为 **dify-main**  
3. 再运行 `deploy\dify\install-and-start.bat` 或 `export-images.bat`

## 把 Dify 部署到阿里云 ECS

在阿里云 ECS 上跑 Dify，通过公网访问。  
**步骤**（准备 ECS、安装 Docker、方式 A 直连 Docker Hub / 方式 B 用阿里云镜像仓库）见：**[Dify部署到阿里云ECS.md](Dify部署到阿里云ECS.md)**。

## 使用阿里云镜像仓库

若已在阿里云创建了镜像仓库（如 ACR），可用来推送/拉取镜像，在无法访问 Docker Hub 时从阿里云部署。  
**操作步骤**（登录、推送自己的镜像、把 Dify 整套迁到阿里云）见：**[阿里云镜像仓库使用说明.md](阿里云镜像仓库使用说明.md)**。

## 常用命令（在 docker 目录下）

| 操作 | 命令 |
|------|------|
| 停止 | `docker compose down` |
| 查看 | `docker compose ps` |
| 日志 | `docker compose logs -f` |
