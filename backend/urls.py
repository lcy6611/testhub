from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.csrf import csrf_exempt
from django.views.static import serve
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
import os

admin.site.site_title = 'TestHub 管理后台'
admin.site.site_header = 'TestHub 后台系统'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    path('api/auth/', include('apps.users.urls')),
    path('api/projects/', include('apps.projects.urls')),
    path('api/testcases/', include('apps.testcases.urls')),
    path('api/testsuites/', include('apps.testsuites.urls')),
    path('api/executions/', include('apps.executions.urls')),
    path('api/reports/', include('apps.reports.urls')),
    path('api/reviews/', include('apps.reviews.urls')),
    path('api/versions/', include('apps.versions.urls')),
    path('api/assistant/', include('apps.assistant.urls')),
    path('api/users/', include('apps.users.urls')),
    path('api/requirement-analysis/', include('apps.requirement_analysis.urls')),
    path('api/kg/', include('apps.knowledge_graph.urls')),
    path('api/ui-automation/', include('apps.ui_automation.urls')),
    path('api/data-factory/', include('apps.data_factory.urls')),
    path('api/app-automation/', include('apps.app_automation.urls')),
    path('api/', include('apps.api_testing.urls')),
    path('api/performance-testing/', include('apps.performance_testing.urls')),
    path('api/core/', include('apps.core.urls')),
    path('api/scheduler/', include('apps.scheduler.urls')),
    path('api/ops-tools/', include('apps.ops_tools.urls')),
    path('api/defects/', include('apps.defects.urls')),
    path('api/defects-oss/', include('apps.defects_oss.urls')),
    path('api/ai-eval/', include('apps.ai_eval.urls')),
    path('api/docs/', include('apps.docs.urls')),
    path('api/monitor/', include('apps.monitor.urls')),
    path('api/mcp/', include('apps.mcp.urls')),
]

# APP自动化 Template 目录静态访问
urlpatterns += [
    path(
        'app-automation-templates/<path:path>',
        serve,
        {'document_root': os.path.join(settings.BASE_DIR, 'apps', 'app_automation', 'Template')},
    ),
]

# APP自动化 Allure 报告访问
urlpatterns += [
    path(
        'app-automation-reports/<path:path>',
        serve,
        {'document_root': os.path.join(settings.MEDIA_ROOT, 'app-automation', 'allure-reports')},
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
