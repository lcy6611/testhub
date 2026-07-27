"""
DRF 分页：允许客户端通过 ?page_size= 指定每页条数（与前端一致），避免前后端默认 page size 不一致导致「无效页」。
"""
from rest_framework.pagination import PageNumberPagination


class StandardPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 500
