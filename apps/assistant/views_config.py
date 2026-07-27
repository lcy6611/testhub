from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import DifyConfig
from .serializers import DifyConfigSerializer
import requests

TEST_CONNECTION_TIMEOUT = 8


def _normalize_dify_api_base_url(raw: str) -> str:
    """自动补全 /v1，避免用户填错或 Dify 返回 404"""
    api_url = (raw or "").strip().rstrip("/")
    if api_url.endswith("/v1"):
        return api_url
    return f"{api_url}/v1"


def _strip_bearer_prefix(key: str) -> str:
    api_key = (key or "").strip()
    for prefix in ("Bearer ", "bearer ", "Token ", "token "):
        if api_key.startswith(prefix):
            return api_key[len(prefix) :].strip()
    return api_key


def _auth_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _test_app_api_key(api_url: str, api_key: str) -> tuple[bool, str]:
    """测试 Dify 应用 API Key（app-），用于 AI 评测师 / chat 应用。"""
    headers = _auth_headers(api_key)
    chat_url = f"{api_url}/chat-messages"
    chat_data = {
        "inputs": {},
        "query": "ping",
        "response_mode": "blocking",
        "user": "test_user",
    }
    resp = requests.post(chat_url, headers=headers, json=chat_data, timeout=TEST_CONNECTION_TIMEOUT)

    if resp.status_code in (401, 403):
        detail = (resp.text or "")[:500]
        return False, f"应用 API Key 无效 ({resp.status_code}): {detail}"

    if resp.status_code == 200:
        return True, "应用 API Key 有效（Chat 应用）"

    if resp.status_code == 400:
        try:
            err = resp.json() if resp.content else {}
        except Exception:
            err = {}
        if isinstance(err, dict) and err.get("code") == "not_chat_app":
            return True, "应用 API Key 有效（Workflow/Completion 应用，非 Chat 端点）"

    detail = (resp.text or "")[:500]
    return False, f"应用 API 测试失败 ({resp.status_code}): {detail}"


def _test_dataset_api_key(api_url: str, dataset_api_key: str) -> tuple[bool, str]:
    """测试 Dify 知识库 API Key（dataset-），用于 AI 用例生成检索知识库。"""
    headers = _auth_headers(dataset_api_key)
    resp = requests.get(
        f"{api_url}/datasets",
        headers=headers,
        params={"page": 1, "limit": 1},
        timeout=TEST_CONNECTION_TIMEOUT,
    )
    if resp.status_code in (401, 403):
        detail = (resp.text or "")[:500]
        return False, f"知识库 API Key 无效 ({resp.status_code}): {detail}"
    if resp.ok:
        return True, "知识库 API Key 有效"
    detail = (resp.text or "")[:500]
    return False, f"知识库 API 测试失败 ({resp.status_code}): {detail}"


class DifyConfigViewSet(viewsets.ModelViewSet):
    """Dify配置管理ViewSet"""
    queryset = DifyConfig.objects.all()
    serializer_class = DifyConfigSerializer
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """获取激活的配置；无配置时返回 200 空数据，避免前端当 404 报错"""
        try:
            active_config = DifyConfig.get_active_config()
            if active_config:
                serializer = self.get_serializer(active_config)
                data = serializer.data
                if 'api_key' in data and data['api_key']:
                    data['api_key_masked'] = data['api_key'][:8] + '****'
                    del data['api_key']
                return Response(data)
            return Response({})
        except Exception as e:
            return Response(
                {'error': '加载配置异常', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=["get"], url_path="all")
    def list_all(self, request):
        """返回所有 Dify 配置（用于前端在对话时选择连接哪个应用）。"""
        try:
            configs = DifyConfig.objects.all().order_by("-created_at")
            data = []
            for c in configs:
                api_key_masked = (c.api_key or "")
                if len(api_key_masked) > 8:
                    api_key_masked = api_key_masked[:8] + "****"
                dataset_key_masked = (c.dataset_api_key or "")
                if len(dataset_key_masked) > 8:
                    dataset_key_masked = dataset_key_masked[:8] + "****"
                data.append(
                    {
                        "id": c.id,
                        "api_url": c.api_url,
                        "app_type": getattr(c, "app_type", "workflow"),
                        "invoke_mode": getattr(c, "invoke_mode", "workflow") or "workflow",
                        "is_active": bool(c.is_active),
                        "api_key_masked": api_key_masked,
                        "dataset_api_key_masked": dataset_key_masked,
                        "has_api_key": bool((c.api_key or "").strip()),
                        "has_dataset_api_key": bool((c.dataset_api_key or "").strip()),
                    }
                )
            return Response(data)
        except Exception as e:
            return Response({"error": "加载配置失败", "detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request):
        """创建新配置"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, pk=None, partial=False):
        """更新配置"""
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """部分更新配置"""
        return self.update(request, pk=pk, partial=True)
    
    @action(detail=False, methods=['post'])
    def test_connection(self, request):
        """
        测试 Dify 连通性。

        - 应用 API Key（app-）：AI 评测师 / Dify 应用对话
        - 知识库 API Key（dataset-）：AI 用例生成检索知识库

        二者可只填其一；至少测试已提供的 Key。请求体中的值优先于数据库已保存值。
        """
        config_id = request.data.get('config_id')
        api_url = request.data.get('api_url')

        saved_cfg = None
        if config_id:
            try:
                saved_cfg = DifyConfig.objects.get(pk=config_id)
            except Exception as e:
                return Response({'error': '加载Dify配置失败', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        has_app_in_body = 'api_key' in request.data
        has_dataset_in_body = 'dataset_api_key' in request.data
        config_only = bool(config_id) and not has_app_in_body and not has_dataset_in_body

        if not (api_url or "").strip() and saved_cfg:
            api_url = saved_cfg.api_url

        api_key = ""
        dataset_api_key = ""

        if config_only and saved_cfg:
            # 列表卡片「测试连接」：测试已保存的全部 Key
            api_key = _strip_bearer_prefix(saved_cfg.api_key or "")
            dataset_api_key = _strip_bearer_prefix(saved_cfg.dataset_api_key or "")
        else:
            # 弹窗测试：仅测试用户本次填写的 Key；应用 Key 留空表示不测、不沿用旧值
            if has_app_in_body:
                api_key = _strip_bearer_prefix(request.data.get('api_key') or "")
            if has_dataset_in_body:
                dataset_api_key = _strip_bearer_prefix(request.data.get('dataset_api_key') or "")
            elif saved_cfg:
                # 知识库 Key 留空时沿用已保存值（编辑时常见）
                dataset_api_key = _strip_bearer_prefix(saved_cfg.dataset_api_key or "")

        api_url = (api_url or "").strip()
        if not api_url:
            return Response(
                {'error': 'API URL 为必填项'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not api_key and not dataset_api_key:
            return Response(
                {'error': '请至少填写「应用 API Key」或「知识库 API Key」之一'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            api_url = _normalize_dify_api_base_url(api_url)
            results: list[str] = []
            errors: list[str] = []

            if dataset_api_key:
                ok, msg = _test_dataset_api_key(api_url, dataset_api_key)
                (results if ok else errors).append(msg)

            if api_key:
                ok, msg = _test_app_api_key(api_url, api_key)
                (results if ok else errors).append(msg)
            elif config_only and saved_cfg and not (saved_cfg.api_key or "").strip():
                results.append("未配置应用 API Key，已跳过应用连接测试（AI 评测师不可用）")

            if results and not errors:
                message = '连接成功！' + '；'.join(results)
                if (has_dataset_in_body and not has_app_in_body and not api_key) or (
                    config_only and saved_cfg and not (saved_cfg.api_key or "").strip()
                ):
                    message += '（未填写应用 API Key，已跳过应用连接测试）'
                return Response({
                    'message': message,
                    'success': True,
                    'details': results,
                })

            if results and errors:
                detail = '成功：' + '；'.join(results) + '。失败：' + '；'.join(errors)
                if any('应用 API Key 无效' in e for e in errors):
                    detail += '。应用 Key 无效时 AI 评测师无法对话；若仅用于用例生成知识库，可只保留知识库 Key。'
                return Response({
                    'error': '部分连接失败',
                    'detail': detail,
                    'success': False,
                }, status=status.HTTP_400_BAD_REQUEST)

            hint = (
                "若 TestHub 后端在本机运行，API URL 请用 http://localhost:8081，"
                "不要用 host.docker.internal（那是容器访问宿主机用的）。"
            )
            return Response({
                'error': '连接失败',
                'detail': '；'.join(errors) + ('。' + hint if errors else ''),
                'success': False,
            }, status=status.HTTP_400_BAD_REQUEST)

        except requests.exceptions.Timeout:
            return Response({
                'error': '连接超时，请检查 API URL 是否正确（本机建议 http://localhost:8081）',
                'success': False,
            }, status=status.HTTP_408_REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as e:
            return Response({
                'error': f'连接错误: {str(e)}',
                'success': False,
            }, status=status.HTTP_400_BAD_REQUEST)
