from django.urls import path
from . import views

urlpatterns = [
    # 测试用例相关
    path('', views.TestCaseListCreateView.as_view(), name='testcase-list'),
    path('<int:pk>/', views.TestCaseDetailView.as_view(), name='testcase-detail'),
    # AI 深入分析
    path('analyze/', views.analyze_case, name='testcase-analyze'),
    path('analyses/', views.list_case_analyses, name='testcase-analyses'),
]