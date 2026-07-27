import logging

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated

from .kb_models import KbFunction
from .kb_serializers import KbFunctionSerializer

logger = logging.getLogger(__name__)


class KbFunctionViewSet(viewsets.ModelViewSet):
    """知识库功能模块与文档/功能关联配置。"""

    queryset = KbFunction.objects.all().prefetch_related("documents", "outgoing_relations__to_function")
    serializer_class = KbFunctionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        dataset_id = (self.request.query_params.get("dify_dataset_id") or "").strip()
        if dataset_id:
            qs = qs.filter(dify_dataset_id=dataset_id)
        active = self.request.query_params.get("is_active")
        if active in ("true", "1"):
            qs = qs.filter(is_active=True)
        return qs
