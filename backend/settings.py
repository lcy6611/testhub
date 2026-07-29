# https://newpanjing.github.io/simpleui_docs/

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None, cast=None):
    """
    Simplified environment variable helper to avoid external decouple dependency.
    """
    value = os.environ.get(name, default)
    if cast is not None and value is not None:
        try:
            return cast(value)
        except (TypeError, ValueError):
            return default
    return value


SECRET_KEY = env('SECRET_KEY', default='django-insecure-your-secret-key-here')

DEBUG = env('DEBUG', default=True, cast=lambda v: str(v).lower() in ('1', 'true', 'yes'))

# 知识图谱：设为 false 可关闭建边/查询（不删表，便于回退）
KNOWLEDGE_GRAPH_ENABLED = env('KNOWLEDGE_GRAPH_ENABLED', default=True, cast=lambda v: str(v).lower() in ('1', 'true', 'yes'))

# 根据DEBUG模式设置ALLOWED_HOSTS，生产环境不应使用通配符
if DEBUG:
    ALLOWED_HOSTS = ['*']
else:
    _allowed_hosts_raw = env('ALLOWED_HOSTS', default='localhost,127.0.0.1')
    ALLOWED_HOSTS = [s.strip() for s in _allowed_hosts_raw.split(',') if s.strip()]

DJANGO_APPS = [
    'simpleui',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',  # 添加JWT支持
    'rest_framework_simplejwt.token_blacklist',  # JWT token黑名单
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'channels',  # WebSocket/实时推送（APP自动化执行状态）
    'django_q',  # 统一调度中心（Django-Q2，Redis 队列 + 独立 scheduler）
]

LOCAL_APPS = [
    'apps.users',
    'apps.projects',
    'apps.testcases',
    'apps.testsuites',
    'apps.executions',
    'apps.reports',
    'apps.reviews',
    'apps.versions',
    'apps.assistant',
    'apps.requirement_analysis',
    'apps.knowledge_graph',
    'apps.api_testing',
    'apps.core',
    'apps.execution_common.apps.ExecutionCommonConfig',  # 统一执行诊断基础层（证据/重试/失败诊断）
    'apps.ui_automation.apps.UiAutomationConfig',
    'apps.data_factory',
    'apps.app_automation.apps.AppAutomationConfig',
    'apps.performance_testing',
    'apps.scheduler.apps.SchedulerConfig',  # 统一调度中心
    'apps.ops_tools.apps.OpsToolsConfig',  # 运维工具
    'apps.defects.apps.DefectsConfig',  # 缺陷实体与发布门禁（#260）
    'apps.ai_eval.apps.AiEvalConfig',  # AI 评测与反馈闭环（#261）
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'backend.middleware.StripSessionCookieForAPIMiddleware',  # before SessionMiddleware to avoid SuspiciousSession on stale cookie
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'backend.middleware.DisableCSRFMiddleware',  # 添加CSRF禁用中间件
    'backend.middleware.ServerMarkMiddleware',  # Debug: identify which server handled request
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'
ASGI_APPLICATION = 'backend.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DB_NAME', default='testhub'),
        'USER': env('DB_USER', default='root'),
        'PASSWORD': env('DB_PASSWORD', default='141008'),  # 移除硬编码默认密码
        'HOST': env('DB_HOST', default='127.0.0.1'),
        'PORT': env('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True  # 移除重复定义

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Channels / WebSocket 配置（APP自动化执行状态推送）
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [env('REDIS_URL', default='redis://:1234@127.0.0.1:6379/0')],
        },
    },
}

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# DRF Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',  # JWT认证（优先）
        'rest_framework.authentication.TokenAuthentication',  # 保留Token认证（兼容）
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'backend.pagination.StandardPageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# JWT Settings
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),  # access_token 30分钟
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),  # refresh_token 7天
    # 为避免 /auth/token/refresh/ 因黑名单写入或 last_login 更新依赖数据库而触发 500，
    # 默认关闭 refresh 轮换/黑名单/last_login 更新；如需启用请通过环境变量显式打开。
    'ROTATE_REFRESH_TOKENS': env('JWT_ROTATE_REFRESH_TOKENS', default=False, cast=lambda v: str(v).lower() in ('1', 'true', 'yes')),
    'BLACKLIST_AFTER_ROTATION': env('JWT_BLACKLIST_AFTER_ROTATION', default=False, cast=lambda v: str(v).lower() in ('1', 'true', 'yes')),
    'UPDATE_LAST_LOGIN': env('JWT_UPDATE_LAST_LOGIN', default=False, cast=lambda v: str(v).lower() in ('1', 'true', 'yes')),

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',

    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# 兼容旧逻辑：DEBUG 下强制关闭黑名单相关写入（即便环境变量误配开启）
if DEBUG:
    SIMPLE_JWT.update(
        {
            "ROTATE_REFRESH_TOKENS": False,
            "BLACKLIST_AFTER_ROTATION": False,
            "UPDATE_LAST_LOGIN": False,
        }
    )

# CSRF Settings - 根据DEBUG模式设置
if DEBUG:
    CSRF_COOKIE_SECURE = False
    CSRF_USE_SESSIONS = False
    CSRF_COOKIE_HTTPONLY = False
    CSRF_COOKIE_SAMESITE = 'Lax'
else:
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SAMESITE = 'Strict'

# CORS Settings
if DEBUG:
    # 开发环境：允许 localhost、127.0.0.1 和任意 IP 地址的前端端口
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    # 允许任意 IP 地址的 3000 端口（用于局域网访问）
    CORS_ALLOW_ALL_ORIGINS = False  # 不使用通配符，而是通过正则匹配
    CORS_ALLOW_CREDENTIALS = True
    # 允许的请求头
    CORS_ALLOW_HEADERS = [
        'accept',
        'accept-encoding',
        'authorization',
        'content-type',
        'dnt',
        'origin',
        'user-agent',
        'x-csrftoken',
        'x-requested-with',
    ]
else:
    _cors_allowed_raw = env('CORS_ALLOWED_ORIGINS', default='http://localhost:3000')
    CORS_ALLOWED_ORIGINS = [s.strip() for s in _cors_allowed_raw.split(',') if s.strip()]

# 媒体文件 / 静态文件直接给响应加上 CORS 头，方便不同端口/IP 间访问
CORS_ALLOW_HEADERS = (CORS_ALLOW_HEADERS + [
    'range',
])
CORS_EXPOSE_HEADERS = [
    'accept-ranges',
    'content-length',
    'content-range',
    'content-type',
]

# 即便不在 CORS_ALLOWED_ORIGINS 白名单的来源（如局域网 IP 直连）也能拿到附件
# 仅在 DEBUG 模式下启用，避免生产环境被打
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

# CSRF Settings
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Spectacular Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'TestHub API',
    'DESCRIPTION': 'Test Case Management Platform API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Celery Configuration
CELERY_BROKER_URL = env('REDIS_URL', default='redis://:123456@127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://:123456@127.0.0.1:6379/0')

# ================ Django-Q2 统一调度中心 ================
# 复用同一套 Redis（独立 db=1，避免与 Celery 冲突）。
# retry 必须大于 timeout，否则任务会在完成前被重新触发。
_Q_REDIS_PW = env('REDIS_PASSWORD', default='123456')
Q_CLUSTER = {
    'name': 'testhub',
    'workers': 4,
    'timeout': 300,        # 单任务执行超时（秒）
    'retry': 360,          # 失败重试间隔（秒），须 > timeout
    'queue_limit': 50,
    'bulk': 10,
    'orm': 'default',      # 调度/任务结果存 Django 默认数据库
    'redis': 'redis://:{}@redis:6379/1'.format(_Q_REDIS_PW),
    'djq_loglevel': 'INFO',
}

# Email Configuration
# 使用自定义 EmailBackend 以更好地处理 SSL/TLS 连接问题（特别是 "Connection unexpectedly closed" 错误）
EMAIL_BACKEND = 'apps.api_testing.custom_email_backend.CustomEmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = env('EMAIL_USE_TLS', default=True, cast=lambda v: str(v).lower() in ('1', 'true', 'yes'))
EMAIL_USE_SSL = env('EMAIL_USE_SSL', default=False, cast=lambda v: str(v).lower() in ('1', 'true', 'yes'))
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='webmaster@localhost')

# 增加超时时间，避免连接过早断开
EMAIL_TIMEOUT = 60

# 确保日志目录存在
log_dir = os.path.join(BASE_DIR, 'logs')
os.makedirs(log_dir, exist_ok=True)
# 每个服务用独立日志文件名（通过环境变量 LOG_FILE 区分），避免多进程并发写同一文件
LOG_FILE = os.getenv('LOG_FILE', 'django.log')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(log_dir, LOG_FILE),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        # UI automation module logs (suite run / scheduled task run)
        'apps.ui_automation': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps.ui_automation.views': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps.api_testing.views': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        # 需求分析 / Skill / AI 用例生成日志
        'apps.requirement_analysis': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps.requirement_analysis.views': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        # 运维工具日志
        'apps.ops_tools': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Debug marker: verify correct settings loaded by server
print("RUNSERVER_MARK_A backend.settings loaded")

# 指定simpleui默认的主题,指定一个文件名，相对路径就从simpleui的theme目录读取
SIMPLEUI_DEFAULT_THEME = 'admin.lte.css'
# 是否显示图标
SIMPLEUI_DEFAULT_ICON = True
# 是否关闭登录页粒子效果
SIMPLEUI_LOGIN_PARTICLES = True
# 后台管理首页，可以是url或者html文件
SIMPLEUI_HOME_PAGE = 'https://www.baidu.com/'  # 后面可以扩展为大屏显示做统计
# 自定义首页标题
SIMPLEUI_HOME_TITLE = 'Dashboard'
# 自定义首页图标 首页图标,支持element-ui和fontawesome的图标，参考https://fontawesome.com/icons图标
SIMPLEUI_HOME_ICON = 'fa fa-gauge'
# 设置simpleui 点击首页图标跳转的地址
SIMPLEUI_INDEX = 'http://localhost:3000'
# 自定义后台的Logo
SIMPLEUI_LOGO = 'https://static.djangoproject.com/img/favicon.6dbf28c0650e.ico'
# 是否显示首页信息
SIMPLEUI_HOME_INFO = False
# 是否显示快捷入口
SIMPLEUI_HOME_QUICK = True
# 是否显示最近动作
SIMPLEUI_HOME_ACTION = True
# 使用分析
SIMPLEUI_ANALYSIS = False
# 离线模式
SIMPLEUI_STATIC_OFFLINE = True
# True或None 默认显示加载遮罩层，指定为False 不显示遮罩层。默认显示
SIMPLEUI_LOADING = True

# ============================================================
# 性能测试模块配置
# ============================================================
# JMeter 可执行路径（留空则用 JMETER_PATH 环境变量或 PATH 中的 jmeter）
PERFORMANCE_JMETER_PATH = os.environ.get("JMETER_PATH", "")
# 实时报告开关（InfluxDB 2.x）
PERFORMANCE_REALTIME_REPORT_ENABLED = False
PERFORMANCE_INFLUXDB_URL = os.environ.get("PERFORMANCE_INFLUXDB_URL", "")
PERFORMANCE_INFLUXDB_ORG = os.environ.get("PERFORMANCE_INFLUXDB_ORG", "testhub")
PERFORMANCE_INFLUXDB_BUCKET = os.environ.get("PERFORMANCE_INFLUXDB_BUCKET", "jmeter")
PERFORMANCE_INFLUXDB_TOKEN = os.environ.get("PERFORMANCE_INFLUXDB_TOKEN", "")
PERFORMANCE_INFLUXDB_MEASUREMENT = "jmeter"
PERFORMANCE_INFLUXDB_APPLICATION = "testhub"
