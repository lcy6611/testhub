"""
数据工厂 API 视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.core.cache import cache
from django.db.models import Count
from pathlib import Path
import logging

from .models import DataFactoryRecord
from .serializers import DataFactoryRecordSerializer, ToolExecuteSerializer
from .tool_list import get_categories, get_tool_list
from .tools.string_tools import StringTools
from .tools.encoding_tools import EncodingTools
from .tools.random_tools import RandomTools
from .tools.encryption_tools import EncryptionTools
from .tools.test_data_tools import TestDataTools
from .tools.json_tools import JsonTools
from .tools.crontab_tools import CrontabTools
from .tools.image_tools import ImageTools

logger = logging.getLogger(__name__)


class DataFactoryPagination(PageNumberPagination):
    """数据工厂自定义分页"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class DataFactoryViewSet(viewsets.ModelViewSet):
    """数据工厂视图集"""
    queryset = DataFactoryRecord.objects.all()
    serializer_class = DataFactoryRecordSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = DataFactoryPagination

    def get_queryset(self):
        # 取消用户隔离：所有登录用户可见所有记录
        return DataFactoryRecord.objects.all().only(
            'id', 'user', 'tool_name', 'tool_category', 'tool_scenario',
            'input_data', 'output_data', 'is_saved', 'tags', 'created_at', 'updated_at'
        ).order_by('-created_at')

    def filter_queryset(self, queryset):
        tags_contains = self.request.query_params.get('tags__contains')
        if tags_contains:
            queryset = queryset.filter(tags__contains=tags_contains)
        tool_name_icontains = self.request.query_params.get('tool_name__icontains')
        if tool_name_icontains:
            queryset = queryset.filter(tool_name__icontains=tool_name_icontains)
        tool_category = self.request.query_params.get('tool_category')
        if tool_category:
            queryset = queryset.filter(tool_category=tool_category)
        return queryset

    def list(self, request, *args, **kwargs):
        try:
            query_params = request.query_params.copy()
            query_params.pop('_t', None)
            cache_key = (
                f"data_factory_history_"
                f"{query_params.get('page', 1)}_"
                f"{query_params.get('page_size', 10)}_"
                f"{query_params.get('tool_category', '')}_"
                f"{query_params.get('tool_name__icontains', '')}_"
                f"{query_params.get('tags__contains', '')}"
            )
            if '_t' not in request.query_params:
                cached_data = cache.get(cache_key)
                if cached_data:
                    return Response(cached_data)
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                paginated = self.get_paginated_response(serializer.data)
                if '_t' not in request.query_params:
                    cache.set(cache_key, paginated.data, 180)
                return paginated
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f'列表方法错误: {str(e)}', exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        """执行工具并保存结果"""
        serializer = ToolExecuteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        result = self.execute_tool(
            data['tool_name'],
            data['tool_category'],
            data['input_data'],
        )
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        if data.get('is_saved', True):
            record = DataFactoryRecord.objects.create(
                user=request.user,
                tool_name=data['tool_name'],
                tool_category=data['tool_category'],
                tool_scenario=data['tool_scenario'],
                input_data=data['input_data'],
                output_data=result,
                is_saved=data.get('is_saved', True),
                tags=data.get('tags', None),
            )
            result['record_id'] = str(record.id)
            result['created_at'] = record.created_at.isoformat()
            self.clear_user_cache(request.user.id)
        return Response(result, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.delete()
            self.clear_user_cache(request.user.id)
            return Response({'message': '删除成功'}, status=status.HTTP_200_OK)
        except DataFactoryRecord.DoesNotExist:
            return Response({'error': '记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f'删除记录失败: {str(e)}', exc_info=True)
            return Response({'error': f'删除失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def clear_user_cache(self, user_id=None):
        # 取消用户隔离后：不再按 user 维度缓存
        cache.delete('data_factory_statistics')
        cache.delete('data_factory_tags')
        try:
            if hasattr(cache, '_cache'):
                keys_to_delete = [
                    key for key in cache._cache if 'data_factory_history' in key
                ]
                for key in keys_to_delete:
                    cache.delete(key)
        except Exception as e:
            logger.error(f'清除历史记录缓存失败: {str(e)}')

    # 工具分发
    def execute_tool(self, tool_name: str, tool_category: str, input_data: dict):
        try:
            if tool_category == 'string':
                return self.execute_string_tool(tool_name, input_data)
            if tool_category == 'encoding':
                return self.execute_encoding_tool(tool_name, input_data)
            if tool_category == 'random':
                return self.execute_random_tool(tool_name, input_data)
            if tool_category == 'encryption':
                return self.execute_encryption_tool(tool_name, input_data)
            if tool_category == 'test_data':
                if tool_name.startswith('mock_'):
                    return self.execute_mock_tool(tool_name, input_data)
                return self.execute_test_data_tool(tool_name, input_data)
            if tool_category == 'json':
                return self.execute_json_tool(tool_name, input_data)
            if tool_category == 'crontab':
                return self.execute_crontab_tool(tool_name, input_data)
            return {'error': f'不支持的工具分类: {tool_category}'}
        except Exception as e:
            logger.error(f'工具执行失败: {str(e)}', exc_info=True)
            return {'error': f'工具执行失败: {str(e)}'}

    def execute_string_tool(self, tool_name: str, input_data: dict | str):
        mapping = {
            'remove_whitespace': StringTools.remove_whitespace,
            'replace_string': StringTools.replace_string,
            'escape_string': StringTools.escape_string,
            'unescape_string': StringTools.unescape_string,
            'word_count': StringTools.word_count,
            'text_diff': StringTools.text_diff,
            'regex_test': StringTools.regex_test,
            'case_convert': StringTools.case_convert,
            'string_format': StringTools.string_format,
        }
        if tool_name not in mapping:
            return {'error': f'不支持的字符工具: {tool_name}'}
        if isinstance(input_data, str):
            input_data = {'text': input_data}
        return mapping[tool_name](**input_data)

    def execute_encoding_tool(self, tool_name: str, input_data: dict | str):
        mapping = {
            'timestamp_convert': EncodingTools.timestamp_convert,
            'base64_encode': EncodingTools.base64_encode,
            'base64_decode': EncodingTools.base64_decode,
            'image_to_base64': ImageTools.image_to_base64,
            'base64_to_image': ImageTools.base64_to_image,
            'generate_barcode': EncodingTools.generate_barcode,
            'generate_qrcode': EncodingTools.generate_qrcode,
            'decode_qrcode': EncodingTools.decode_qrcode,
            'base_convert': EncodingTools.base_convert,
            'unicode_convert': EncodingTools.unicode_convert,
            'ascii_convert': EncodingTools.ascii_convert,
            'color_convert': EncodingTools.color_convert,
            'url_encode': EncodingTools.url_encode,
            'url_decode': EncodingTools.url_decode,
            'jwt_decode': EncodingTools.jwt_decode,
        }
        if tool_name not in mapping:
            return {'error': f'不支持的编码工具: {tool_name}'}
        if isinstance(input_data, str):
            input_data = {'text': input_data}
        return mapping[tool_name](**input_data)

    def execute_random_tool(self, tool_name: str, input_data: dict | str):
        mapping = {
            'random_int': RandomTools.random_int,
            'random_float': RandomTools.random_float,
            'random_string': RandomTools.random_string,
            'random_uuid': RandomTools.random_uuid,
            'random_mac_address': RandomTools.random_mac_address,
            'random_ip_address': RandomTools.random_ip_address,
            'random_boolean': RandomTools.random_boolean,
            'random_date': RandomTools.random_date,
            'random_password': RandomTools.random_password,
            'random_color': RandomTools.random_color,
            'random_sequence': RandomTools.random_sequence,
        }
        if tool_name not in mapping:
            return {'error': f'不支持的随机工具: {tool_name}'}
        if isinstance(input_data, str):
            input_data = {'text': input_data}
        return mapping[tool_name](**input_data)

    def execute_encryption_tool(self, tool_name: str, input_data: dict | str):
        mapping = {
            'md5_hash': EncryptionTools.md5_hash,
            'sha1_hash': EncryptionTools.sha1_hash,
            'sha256_hash': EncryptionTools.sha256_hash,
            'sha512_hash': EncryptionTools.sha512_hash,
            'hash_comparison': EncryptionTools.hash_comparison,
            'password_strength': EncryptionTools.password_strength,
            'generate_salt': EncryptionTools.generate_salt,
            'aes_encrypt': EncryptionTools.aes_encrypt,
            'aes_decrypt': EncryptionTools.aes_decrypt,
        }
        if tool_name not in mapping:
            return {'error': f'不支持的加密工具: {tool_name}'}
        if isinstance(input_data, str):
            input_data = {'text': input_data}
        # aes_decrypt 前端传 text 表示密文，后端参数为 encrypted_text
        if tool_name == 'aes_decrypt' and 'text' in input_data and 'encrypted_text' not in input_data:
            input_data = {**input_data, 'encrypted_text': input_data.pop('text', '')}
        return mapping[tool_name](**input_data)

    def execute_test_data_tool(self, tool_name: str, input_data: dict | str):
        mapping = {
            'generate_chinese_name': TestDataTools.generate_chinese_name,
            'generate_chinese_phone': TestDataTools.generate_chinese_phone,
            'generate_chinese_email': TestDataTools.generate_chinese_email,
            'generate_chinese_address': TestDataTools.generate_chinese_address,
            'generate_id_card': TestDataTools.generate_id_card,
            'generate_company_name': TestDataTools.generate_company_name,
            'generate_bank_card': TestDataTools.generate_bank_card,
            'generate_user_profile': TestDataTools.generate_user_profile,
            'generate_hk_id_card': TestDataTools.generate_hk_id_card,
            'generate_business_license': TestDataTools.generate_business_license,
            'generate_coordinates': TestDataTools.generate_coordinates,
        }
        if tool_name not in mapping:
            return {'error': f'不支持的测试数据工具: {tool_name}'}
        if isinstance(input_data, str):
            input_data = {'count': 1}
        return mapping[tool_name](**input_data)

    def execute_json_tool(self, tool_name: str, input_data: dict | str):
        mapping = {
            'format_json': JsonTools.format_json,
            'validate_json': JsonTools.validate_json,
            'json_to_yaml': JsonTools.json_to_yaml,
            'yaml_to_json': JsonTools.yaml_to_json,
            'json_diff_enhanced': JsonTools.json_diff_enhanced,
            'jsonpath_query': JsonTools.jsonpath_query,
            'json_path_list': JsonTools.json_path_list,
            'json_flatten': JsonTools.json_flatten,
            'json_to_xml': JsonTools.json_to_xml,
            'xml_to_json': JsonTools.xml_to_json,
        }
        if tool_name not in mapping:
            return {'error': f'不支持的JSON工具: {tool_name}'}
        if isinstance(input_data, str):
            input_data = {'json_str': input_data}
        return mapping[tool_name](**input_data)

    def execute_mock_tool(self, tool_name: str, input_data: dict | str):
        """简单 Mock 数据，这里直接复用 JsonTools.mock_data"""
        data_type = tool_name.replace('mock_', '')
        if isinstance(input_data, str):
            input_data = {}
        input_data['data_type'] = data_type
        return JsonTools.mock_data(data_type, input_data.get('count', 1), **input_data)

    def execute_crontab_tool(self, tool_name: str, input_data: dict | str):
        mapping = {
            'generate_expression': CrontabTools.generate_expression,
            'parse_expression': CrontabTools.parse_expression,
            'get_next_runs': CrontabTools.get_next_runs,
            'validate_expression': CrontabTools.validate_expression,
        }
        if tool_name not in mapping:
            return {'error': f'不支持的Crontab工具: {tool_name}'}
        if isinstance(input_data, str):
            input_data = {'expression': input_data}
        return mapping[tool_name](**input_data)

    @action(detail=False, methods=['get'])
    def categories(self, request):
        cache_key = 'data_factory_categories'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)
        categories = get_categories()
        tool_list = get_tool_list()
        for cat in categories:
            cat['tools'] = [t for t in tool_list if t['scenario'] == cat['scenario']]
        data = {'categories': categories, 'total_tools': sum(len(c['tools']) for c in categories)}
        cache.set(cache_key, data, 1800)
        return Response(data)

    @action(detail=False, methods=['get'])
    def tags(self, request):
        cache_key = 'data_factory_tags'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)
        queryset = DataFactoryRecord.objects.all()
        tag_set = set()
        for record in queryset:
            if record.tags and isinstance(record.tags, list):
                tag_set.update(record.tags)
        tags = sorted(list(tag_set))
        data = {'tags': tags, 'count': len(tags)}
        cache.set(cache_key, data, 300)
        return Response(data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取使用统计"""
        cache_key = 'data_factory_statistics'
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)
        category_map = dict(DataFactoryRecord.TOOL_CATEGORIES)
        scenario_map = dict(DataFactoryRecord.TOOL_SCENARIOS)
        total_records = DataFactoryRecord.objects.count()
        category_stats = {}
        for item in DataFactoryRecord.objects.values('tool_category').annotate(count=Count('id')):
            cat_display = category_map.get(item['tool_category'], item['tool_category'])
            category_stats[cat_display] = item['count']
        for _cat, cat_display in DataFactoryRecord.TOOL_CATEGORIES:
            if cat_display not in category_stats:
                category_stats[cat_display] = 0
        scenario_stats = {}
        for item in DataFactoryRecord.objects.values('tool_scenario').annotate(count=Count('id')):
            sce_display = scenario_map.get(item['tool_scenario'], item['tool_scenario'])
            scenario_stats[sce_display] = item['count']
        for _sce, sce_display in DataFactoryRecord.TOOL_SCENARIOS:
            if sce_display not in scenario_stats:
                scenario_stats[sce_display] = 0
        recent_tools = []
        for record in DataFactoryRecord.objects.only(
            'tool_name', 'tool_category', 'tool_scenario', 'created_at'
        ).order_by('-created_at')[:10]:
            recent_tools.append({
                'tool_name': record.tool_name,
                'tool_category_display': record.get_tool_category_display(),
                'tool_scenario_display': record.get_tool_scenario_display(),
                'created_at': record.created_at,
            })
        stats_data = {
            'total_records': total_records,
            'category_stats': category_stats,
            'scenario_stats': scenario_stats,
            'recent_tools': recent_tools,
        }
        cache.set(cache_key, stats_data, 300)
        return Response(stats_data)

    @action(detail=False, methods=['get'])
    def variable_functions(self, request):
        """变量助手：返回可在请求体/脚本中引用的变量示例列表"""
        variables = [
            {'name': '时间戳(秒)', 'example': '{{$timestamp}}', 'category': '常用'},
            {'name': '时间戳(毫秒)', 'example': '{{$timestamp_ms}}', 'category': '常用'},
            {'name': '随机整数', 'example': '{{$randomInt}}', 'category': '常用'},
            {'name': '随机UUID', 'example': '{{$randomUuid}}', 'category': '常用'},
            {'name': '随机字符串', 'example': '{{$randomString}}', 'category': '常用'},
            {'name': '当前日期', 'example': '{{$date}}', 'category': '常用'},
            {'name': '当前时间', 'example': '{{$datetime}}', 'category': '常用'},
            {'name': '环境base_url', 'example': '{{base_url}}', 'category': '环境'},
            {'name': '环境host', 'example': '{{host}}', 'category': '环境'},
        ]
        return Response(variables)