from django.urls import path

from .views import DocContentView, DocTreeView

urlpatterns = [
    path("tree/", DocTreeView.as_view(), name="doc-tree"),
    path("content/", DocContentView.as_view(), name="doc-content"),
]
