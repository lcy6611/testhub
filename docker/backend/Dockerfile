FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 系统依赖（构建常见 Python 包 & mysqlclient 兼容；
# xvfb 提供虚拟显示，x11vnc 提供 VNC 访问，便于在容器内使用有头模式跑 UI/AI 自动化；
# fonts-wqy-zenhei 提供中文字体，保证 GIF 字幕中的中文不会变成方块）
RUN set -eux; \
  # python:* slim 可能是 bookworm，源文件可能是 sources.list 或 debian.sources；同时网络可能对某个镜像源不稳定
  # 这里按“多镜像源可降级”的方式处理，并在失败时输出完整日志，便于定位网络/DNS/证书问题。
  if [ -f /etc/apt/sources.list ]; then \
    cp /etc/apt/sources.list /etc/apt/sources.list.bak; \
    sed -i 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g' /etc/apt/sources.list; \
    sed -i 's|http://security.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list; \
  elif [ -f /etc/apt/sources.list.d/debian.sources ]; then \
    cp /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list.d/debian.sources.bak; \
    sed -i 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g' /etc/apt/sources.list.d/debian.sources; \
    sed -i 's|http://security.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
  fi; \
  echo "----- apt sources -----"; \
  (cat /etc/apt/sources.list 2>/dev/null || true); \
  (cat /etc/apt/sources.list.d/debian.sources 2>/dev/null || true); \
  apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update \
    || ( \
      echo "----- apt-get update failed; fallback to TUNA mirror -----"; \
      if [ -f /etc/apt/sources.list ]; then \
        cp /etc/apt/sources.list.bak /etc/apt/sources.list || true; \
        sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list; \
        sed -i 's|http://security.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list; \
      elif [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        cp /etc/apt/sources.list.d/debian.sources.bak /etc/apt/sources.list.d/debian.sources || true; \
        sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources; \
        sed -i 's|http://security.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
      fi; \
      apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update \
        || (echo "----- apt-get update still failed -----" && cat /var/log/apt/* 2>/dev/null || true && exit 1); \
    ); \
  apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    default-jre-headless \
    pkg-config \
    curl \
    xvfb \
    x11vnc \
    fonts-wqy-zenhei \
    fontconfig \
    fonts-noto-cjk \
  || (echo "----- apt-get install failed -----" && cat /var/log/apt/* 2>/dev/null || true && exit 1); \
  rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
# 允许通过构建参数切换 PyPI 源；避免某个镜像源偶发超时导致构建失败
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG INSTALL_PLAYWRIGHT=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=60 \
    PIP_RETRIES=5 \
    PIP_INDEX_URL=${PIP_INDEX_URL}
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    if [ "$INSTALL_PLAYWRIGHT" = "1" ]; then python -m playwright install --with-deps; else echo "Skip playwright install (INSTALL_PLAYWRIGHT=$INSTALL_PLAYWRIGHT)"; fi

# 生产镜像需要包含项目代码（否则 entrypoint/gunicorn 找不到 manage.py/backend 等）
COPY . /app

COPY docker/backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
