# -*- coding: utf-8 -*-
"""
JSON 相关工具（格式化 / 校验 / 转换 / 对比 / Mock）
"""
import json
import yaml
import xml.etree.ElementTree as ET
from typing import Dict, Any, List
from difflib import SequenceMatcher, unified_diff
import logging

try:
    from jsonpath_ng import parse as jsonpath_parse
    JSONPATH_AVAILABLE = True
except ImportError:
    JSONPATH_AVAILABLE = False

logger = logging.getLogger(__name__)


class JsonTools:
    """JSON 工具类（精简但接口兼容）"""

    @staticmethod
    def format_json(json_str: str, indent: int = 2, sort_keys: bool = False, compress: bool = False) -> Dict[str, Any]:
        try:
            data = json.loads(json_str)
            original_chars = len(json_str)
            original_lines = json_str.count('\n') + 1

            if compress:
                result = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
                compressed_chars = len(result)
                compressed_lines = result.count('\n') + 1
                return {
                    'result': result,
                    'success': True,
                    'mode': 'compress',
                    'original_length': original_chars,
                    'compressed_length': compressed_chars,
                    'original_lines': original_lines,
                    'compressed_lines': compressed_lines,
                }
            else:
                result = json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=sort_keys)
                formatted_chars = len(result)
                formatted_lines = result.count('\n') + 1
                return {
                    'result': result,
                    'success': True,
                    'mode': 'format',
                    'indent': indent,
                    'sort_keys': sort_keys,
                    'original_length': original_chars,
                    'formatted_length': formatted_chars,
                    'original_lines': original_lines,
                    'formatted_lines': formatted_lines,
                }
        except json.JSONDecodeError as e:
            return {'success': False, 'error': f'JSON格式错误: {str(e)}', 'line': e.lineno, 'column': e.colno}
        except Exception as e:
            logger.error(f'JSON格式化失败: {str(e)}')
            return {'error': 'JSON格式化失败，请检查输入或联系管理员！'}

    @staticmethod
    def validate_json(json_str: str) -> Dict[str, Any]:
        try:
            data = json.loads(json_str)
            return {
                'result': True,
                'success': True,
                'valid': True,
                'message': 'JSON格式正确',
                'data_type': type(data).__name__,
                'size': len(json_str),
            }
        except json.JSONDecodeError as e:
            return {
                'result': False,
                'success': False,
                'valid': False,
                'error': f'JSON格式错误: {str(e)}',
                'line': e.lineno,
                'column': e.colno,
                'position': e.pos,
            }
        except Exception as e:
            logger.error(f'JSON校验失败: {str(e)}')
            return {'error': 'JSON校验失败，请检查输入数据！'}

    @staticmethod
    def json_to_yaml(json_str: str) -> Dict[str, Any]:
        try:
            data = json.loads(json_str)
            yaml_str = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
            return {'result': yaml_str, 'success': True}
        except json.JSONDecodeError as e:
            return {'error': f'JSON格式错误: {str(e)}'}
        except Exception as e:
            return {'error': f'JSON转YAML失败: {str(e)}'}

    @staticmethod
    def yaml_to_json(yaml_str: str) -> Dict[str, Any]:
        try:
            data = yaml.safe_load(yaml_str)
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            return {'result': json_str, 'success': True}
        except yaml.YAMLError as e:
            return {'error': f'YAML格式错误: {str(e)}'}
        except Exception as e:
            return {'error': f'YAML转JSON失败: {str(e)}'}

    @staticmethod
    def json_diff_enhanced(json_str1: str, json_str2: str, ignore_whitespace: bool = True,
                           show_only_diff: bool = False) -> Dict[str, Any]:
        try:
            data1 = json.loads(json_str1)
            data2 = json.loads(json_str2)
            str1 = json.dumps(data1, ensure_ascii=False, sort_keys=True, indent=2)
            str2 = json.dumps(data2, ensure_ascii=False, sort_keys=True, indent=2)
            if ignore_whitespace:
                str1 = ''.join(str1.split())
                str2 = ''.join(str2.split())

            similarity = SequenceMatcher(None, str1, str2).ratio()
            diff_lines = list(unified_diff(
                str1.splitlines(keepends=True),
                str2.splitlines(keepends=True),
                fromfile='JSON 1',
                tofile='JSON 2',
                lineterm='',
            ))
            diff_result = ''.join(diff_lines) if diff_lines else '无差异'
            return {
                'success': True,
                'result': {
                    'similarity': f"{similarity * 100:.2f}%",
                    'identical': similarity == 1.0,
                },
                'diff': diff_result,
                'size1': len(json_str1),
                'size2': len(json_str2),
                'show_only_diff': show_only_diff,
            }
        except json.JSONDecodeError as e:
            return {'error': f'JSON格式错误: {str(e)}'}
        except Exception as e:
            return {'error': f'JSON对比失败: {str(e)}'}

    @staticmethod
    def json_to_xml(json_str: str, root_tag: str = 'root') -> Dict[str, Any]:
        """JSON 转 XML"""
        try:
            data = json.loads(json_str)
            def dict_to_xml(d, parent):
                for key, value in d.items():
                    if isinstance(value, dict):
                        elem = ET.SubElement(parent, key)
                        dict_to_xml(value, elem)
                    elif isinstance(value, list):
                        for item in value:
                            elem = ET.SubElement(parent, key)
                            if isinstance(item, dict):
                                dict_to_xml(item, elem)
                            else:
                                elem.text = str(item) if item is not None else ''
                    else:
                        elem = ET.SubElement(parent, key)
                        elem.text = str(value) if value is not None else ''
            root = ET.Element(root_tag)
            dict_to_xml(data, root)
            xml_str = ET.tostring(root, encoding='unicode', method='xml')
            return {'result': xml_str, 'success': True, 'root_tag': root_tag}
        except json.JSONDecodeError as e:
            return {'error': f'JSON格式错误: {str(e)}'}
        except Exception as e:
            return {'error': f'JSON转XML失败: {str(e)}'}

    @staticmethod
    def xml_to_json(xml_str: str) -> Dict[str, Any]:
        """XML 转 JSON"""
        try:
            def xml_to_dict(element):
                result = {}
                for child in element:
                    if len(child) == 0:
                        result[child.tag] = child.text
                    else:
                        result[child.tag] = xml_to_dict(child)
                return result
            root = ET.fromstring(xml_str)
            data = xml_to_dict(root)
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            return {'result': json_str, 'success': True}
        except ET.ParseError as e:
            return {'error': f'XML格式错误: {str(e)}'}
        except Exception as e:
            return {'error': f'XML转JSON失败: {str(e)}'}

    @staticmethod
    def jsonpath_query(json_str: str, jsonpath_expr: str) -> Dict[str, Any]:
        """JSONPath 查询"""
        if not JSONPATH_AVAILABLE:
            return {'error': 'jsonpath_ng 未安装，请先安装 jsonpath-ng'}
        try:
            data = json.loads(json_str)
            parse_expr = jsonpath_parse(jsonpath_expr)
            matches = [match.value for match in parse_expr.find(data)]
            return {'result': matches, 'success': True, 'expression': jsonpath_expr, 'count': len(matches)}
        except json.JSONDecodeError as e:
            return {'error': f'JSON格式错误: {str(e)}'}
        except Exception as e:
            return {'error': f'JSONPath查询失败: {str(e)}'}

    @staticmethod
    def json_path_list(json_str: str) -> Dict[str, Any]:
        """列出 JSON 所有路径"""
        try:
            data = json.loads(json_str)
            paths = []
            def get_paths(obj, current_path=''):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        new_path = f"{current_path}.{key}" if current_path else key
                        paths.append(new_path)
                        get_paths(value, new_path)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        new_path = f"{current_path}[{i}]"
                        paths.append(new_path)
                        get_paths(item, new_path)
            get_paths(data)
            return {'success': True, 'result': paths, 'count': len(paths)}
        except json.JSONDecodeError as e:
            return {'error': f'JSON格式错误: {str(e)}'}
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def json_flatten(json_str: str, separator: str = '.') -> Dict[str, Any]:
        """扁平化 JSON"""
        try:
            data = json.loads(json_str)
            result = {}
            def flatten(obj, parent_key=''):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        new_key = f"{parent_key}{separator}{key}" if parent_key else key
                        flatten(value, new_key)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        new_key = f"{parent_key}[{i}]"
                        flatten(item, new_key)
                else:
                    result[parent_key] = obj
            flatten(data)
            return {'success': True, 'result': result}
        except json.JSONDecodeError as e:
            return {'error': f'JSON格式错误: {str(e)}'}
        except Exception as e:
            return {'error': str(e)}

