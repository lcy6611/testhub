FROM node:20-bullseye-slim AS frontend-build

WORKDIR /app/frontend
RUN set -eux; \
  # 在部分网络环境下 deb.debian.org 可能超时，切换到更稳定的镜像源并增加重试
  sed -i 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g' /etc/apt/sources.list; \
  sed -i 's|http://security.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list; \
  apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update; \
  apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 install -y --no-install-recommends \
      python3 \
      make \
      g++ \
  ; \
  rm -rf /var/lib/apt/lists/*
COPY frontend/package.json frontend/package-lock.json ./
RUN node -v && npm -v && npm config get registry && \
  npm ci --no-audit --fund=false --verbose --foreground-scripts || ( \
    echo "----- npm ci failed: dumping npm logs -----" && \
    (ls -la /root/.npm/_logs 2>/dev/null || true) && \
    (cat /root/.npm/_logs/* 2>/dev/null || true) && \
    exit 1 \
  )
COPY frontend/ ./
ENV NODE_OPTIONS=--max_old_space_size=4096
RUN /bin/sh -lc 'set -eux; npm run build --verbose 2>&1 | tee /tmp/vite-build.log' || ( \
    echo "----- npm run build failed: dumping vite build log -----" && \
    (tail -n 400 /tmp/vite-build.log 2>/dev/null || true) && \
    echo "----- npm run build failed: dumping npm logs -----" && \
    (ls -la /root/.npm/_logs 2>/dev/null || true) && \
    (tail -n 400 /root/.npm/_logs/* 2>/dev/null || true) && \
    exit 1 \
  )


FROM nginx:1.27-alpine

# Nginx 配置
COPY docker/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# 前端静态文件
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html

# 运行时挂载：/static /media（由 docker-compose.prod.yml 提供 volume）
RUN mkdir -p /static /media

