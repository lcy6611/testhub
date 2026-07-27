import json
import logging
import re
import time
from django.utils import timezone
from .models import RequestHistory

logger = logging.getLogger(__name__)


def execute_assertions(response, assertions):
    """执行断言验证"""
    results = []
    
    for assertion in assertions:
        result = {
            'name': assertion.get('name', '未命名断言'),
            'type': assertion.get('type'),
            'passed': False,
            'expected': assertion.get('expected'),
            'actual': None,
            'error': None
        }
        
        try:
            assertion_type = assertion.get('type')
            expected = assertion.get('expected')
            operator = assertion.get('operator', 'eq')  # eq, ne, gt, ge, lt, le, contains
            actual = None
            passed = False
            
            if assertion_type == 'status_code':
                actual = response.status_code
                passed = _compare(actual, expected, operator)
                
            elif assertion_type == 'response_time':
                # 响应时间断言在调用方处理
                actual = assertion.get('actual_time')
                passed = _compare(actual, expected, operator) if actual else False
                
            elif assertion_type == 'contains':
                text = response.text or ''
                pattern = str(expected)
                actual = text[:200] + '...' if len(text) > 200 else text
                passed = pattern in str(text)
                
            elif assertion_type == 'json_path':
                json_path = assertion.get('json_path', '')
                expected_value = assertion.get('expected')
                actual = None
                passed = False
                
                try:
                    # 检查响应是否为JSON格式
                    content_type = response.headers.get('content-type', '').lower()
                    if 'application/json' not in content_type:
                        raise ValueError(f"响应不是JSON格式，Content-Type: {content_type}")
                    
                    response_json = json.loads(response.text)
                    
                    # 检查JSONPath表达式是否为空
                    if not json_path:
                        raise ValueError("JSON路径表达式不能为空")
                    
                    from jsonpath_ng import parse
                    matches = parse(json_path).find(response_json)
                    actual = matches[0].value if matches else None
                    passed = _compare(actual, expected_value, operator)
                    
                    # 确保actual值被正确设置到result中
                    result['actual'] = actual
                except json.JSONDecodeError as e:
                    actual = None
                    passed = False
                    result['error'] = f"JSON解析失败: {str(e)}"
                    result['actual'] = actual
                except ImportError as e:
                    actual = None
                    passed = False
                    result['error'] = f"缺少依赖库: {str(e)}，请安装jsonpath-ng"
                    result['actual'] = actual
                except Exception as e:
                    actual = None
                    passed = False
                    result['error'] = f"执行错误: {str(e)}"
                    result['actual'] = actual
                    
            elif assertion_type == 'header':
                header_name = assertion.get('header_name', '')
                expected_value = assertion.get('expected_value')
                actual = response.headers.get(header_name)
                passed = _compare(actual, expected_value, operator)
                
            elif assertion_type == 'equals':
                actual = response.text.strip()
                passed = _compare(actual, str(expected).strip(), operator)
            
            # 确保在所有情况下都设置actual值
            if 'actual' not in result or result['actual'] is None:
                result['actual'] = actual
            result['passed'] = passed
            
        except Exception as e:
            result['error'] = str(e)
            result['passed'] = False
        
        results.append(result)
    
    return results


def execute_test_suite(test_suite, environment, executed_by):
    """执行测试套件并返回结果"""
    from .models import TestExecution, RequestHistory
    import requests
    import time
    
    try:
        # 创建执行记录
        execution = TestExecution.objects.create(
            test_suite=test_suite,
            status='RUNNING',
            start_time=timezone.now(),
            executed_by=executed_by
        )
        
        # 获取套件中的请求
        suite_requests = test_suite.testsuiterequest_set.filter(enabled=True).order_by('order')
        
        execution.total_requests = suite_requests.count()
        execution.save()
        
        results = []
        passed_count = 0
        failed_count = 0
        
        # 执行每个请求
        for suite_request in suite_requests:
            api_request = suite_request.request
            
            try:
                # 解析环境变量
                variables = {}
                if environment:
                    variables.update(environment.variables)
                
                # 替换URL中的变量
                url = _replace_variables(api_request.url, variables)
                
                # 准备请求头
                headers = {}
                if isinstance(api_request.headers, list):
                    for header_item in api_request.headers:
                        if header_item.get('enabled', True) and header_item.get('key'):
                            key = header_item['key']
                            value = _replace_variables(str(header_item.get('value', '')), variables)
                            headers[key] = value
                else:
                    headers = api_request.headers.copy()
                    for key, value in headers.items():
                        headers[key] = _replace_variables(str(value), variables)
                
                # 准备请求参数
                params = api_request.params.copy() if api_request.params else {}
                for key, value in params.items():
                    params[key] = _replace_variables(str(value), variables)
                
                # 准备请求体
                body_data = None
                if api_request.body and api_request.method in ['POST', 'PUT', 'PATCH']:
                    if api_request.body.get('type') == 'json':
                        body_data = api_request.body.get('data', {})
                        body_data = _replace_variables_in_dict(body_data, variables)
                
                # 执行请求
                start_time = time.time()
                response = requests.request(
                    method=api_request.method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=body_data,
                    timeout=30
                )
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                # 执行断言验证
                assertions = api_request.assertions or []
                for assertion in assertions:
                    if assertion.get('type') == 'response_time':
                        assertion['actual_time'] = response_time
                
                assertions_results = execute_assertions(response, assertions)
                
                # 检查所有断言是否通过
                passed = True
                error_message = ''
                
                # 检查套件请求的断言
                for assertion in suite_request.assertions:
                    if assertion.get('type') == 'status_code':
                        expected = assertion.get('value')
                        if response.status_code != expected:
                            passed = False
                            error_message = f'状态码断言失败: 期望 {expected}, 实际 {response.status_code}'
                            break
                
                # 检查接口自身的断言
                if passed and assertions_results:
                    for assertion_result in assertions_results:
                        if not assertion_result.get('passed', True):
                            passed = False
                            error_message = f"断言失败: {assertion_result.get('name', '未命名断言')} - {assertion_result.get('error', '断言不通过')}"
                            break
                
                if passed:
                    passed_count += 1
                else:
                    failed_count += 1
                
                results.append({
                    'name': api_request.name,
                    'method': api_request.method,
                    'url': url,
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'passed': passed,
                    'error': error_message,
                    'assertions_results': assertions_results
                })
                
                # 保存请求历史
                history = RequestHistory.objects.create(
                    request=api_request,
                    environment=environment,
                    request_data={
                        'url': url,
                        'method': api_request.method,
                        'headers': headers,
                        'params': params,
                        'body': body_data
                    },
                    response_data={
                        'headers': dict(response.headers),
                        'body': response.text,
                        'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
                    },
                    status_code=response.status_code,
                    response_time=response_time,
                    assertions_results=assertions_results,
                    executed_by=executed_by
                )
                try:
                    from apps.knowledge_graph.writeback import safe_writeback_api_request_execution
                    safe_writeback_api_request_execution(history)
                except Exception:
                    logger.warning("知识图谱回写 API 执行结果失败", exc_info=True)
                
            except Exception as e:
                failed_count += 1
                results.append({
                    'name': api_request.name,
                    'method': api_request.method,
                    'url': api_request.url,
                    'passed': False,
                    'error': str(e)
                })
                history = RequestHistory.objects.create(
                    request=api_request,
                    environment=environment,
                    request_data={
                        'url': api_request.url,
                        'method': api_request.method,
                        'headers': api_request.headers,
                        'params': api_request.params,
                        'body': api_request.body
                    },
                    error_message=str(e),
                    executed_by=executed_by
                )
                try:
                    from apps.knowledge_graph.writeback import safe_writeback_api_request_execution
                    safe_writeback_api_request_execution(history)
                except Exception:
                    logger.warning("知识图谱回写 API 执行结果失败", exc_info=True)
        
        # 更新执行结果
        execution.end_time = timezone.now()
        execution.passed_requests = passed_count
        execution.failed_requests = failed_count
        execution.status = 'COMPLETED' if failed_count == 0 else 'FAILED'
        execution.results = results
        execution.save()
        
        return {
            'success': True,
            'execution_id': execution.id,
            'passed_count': passed_count,
            'failed_count': failed_count,
            'total_count': execution.total_requests,
            'results': results
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def execute_api_request(api_request, environment, executed_by):
    """执行单个API请求并返回结果"""
    import requests
    import time
    
    try:
        # 解析环境变量
        variables = {}
        if environment:
            variables.update(environment.variables)
        
        # 替换URL中的变量
        url = _replace_variables(api_request.url, variables)
        
        # 准备请求头
        headers = {}
        if isinstance(api_request.headers, list):
            for header_item in api_request.headers:
                if header_item.get('enabled', True) and header_item.get('key'):
                    key = header_item['key']
                    value = _replace_variables(str(header_item.get('value', '')), variables)
                    headers[key] = value
        else:
            headers = api_request.headers.copy()
            for key, value in headers.items():
                headers[key] = _replace_variables(str(value), variables)
        
        # 准备请求参数
        params = api_request.params.copy() if api_request.params else {}
        for key, value in params.items():
            params[key] = _replace_variables(str(value), variables)
        
        # 准备请求体
        body_data = None
        if api_request.body and api_request.method in ['POST', 'PUT', 'PATCH']:
            if api_request.body.get('type') == 'json':
                body_data = api_request.body.get('data', {})
                body_data = _replace_variables_in_dict(body_data, variables)
        
        # 执行请求
        start_time = time.time()
        response = requests.request(
            method=api_request.method,
            url=url,
            headers=headers,
            params=params,
            json=body_data,
            timeout=30
        )
        end_time = time.time()
        response_time = (end_time - start_time) * 1000
        
        # 执行断言验证
        assertions = api_request.assertions or []
        for assertion in assertions:
            if assertion.get('type') == 'response_time':
                assertion['actual_time'] = response_time
        
        assertions_results = execute_assertions(response, assertions)
        
        # 保存请求历史
        history = RequestHistory.objects.create(
            request=api_request,
            environment=environment,
            request_data={
                'url': url,
                'method': api_request.method,
                'headers': headers,
                'params': params,
                'body': body_data
            },
            response_data={
                'headers': dict(response.headers),
                'body': response.text,
                'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
            },
            status_code=response.status_code,
            response_time=response_time,
            assertions_results=assertions_results,
            executed_by=executed_by
        )
        try:
            from apps.knowledge_graph.writeback import safe_writeback_api_request_execution
            safe_writeback_api_request_execution(history)
        except Exception:
            logger.warning("知识图谱回写 API 执行结果失败", exc_info=True)
        
        return {
            'success': True,
            'history_id': history.id,
            'status_code': response.status_code,
            'response_time': response_time,
            'assertions_results': assertions_results,
            'response_data': {
                'headers': dict(response.headers),
                'body': response.text,
                'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
            }
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def _replace_variables(text, variables):
    """替换文本中的变量"""
    if not isinstance(text, str):
        return text
    
    result = text
    for key, value in (variables or {}).items():
        if isinstance(value, dict):
            replacement = str(value.get('currentValue', '') or value.get('initialValue', ''))
        else:
            replacement = str(value) if value is not None else ''
        result = result.replace(f'{{{{{key}}}}}', replacement)
    return result


def _replace_variables_in_dict(data, variables):
    """递归替换字典中的变量"""
    if isinstance(data, dict):
        return {k: _replace_variables_in_dict(v, variables) for k, v in data.items()}
    elif isinstance(data, list):
        return [_replace_variables_in_dict(item, variables) for item in data]
    elif isinstance(data, str):
        return _replace_variables(data, variables)
    else:
        return data


# ==================== 断言比较运算符 ====================

def _compare(actual, expected, operator='eq'):
    """
    通用比较函数，支持以下运算符：
      eq  = 等于
      ne  = 不等于
      gt  = 大于
      ge  = 大于等于
      lt  = 小于
      le  = 小于等于
      contains = 包含
    """
    if operator == 'contains':
        return str(expected) in str(actual) if actual is not None else False

    # 尝试数值比较
    try:
        a = float(actual) if actual is not None else None
        e = float(expected) if expected is not None else None
    except (TypeError, ValueError):
        a = actual
        e = expected

    if operator == 'eq':
        return a == e
    elif operator == 'ne':
        return a != e
    elif operator == 'gt':
        return a is not None and e is not None and a > e
    elif operator == 'ge':
        return a is not None and e is not None and a >= e
    elif operator == 'lt':
        return a is not None and e is not None and a < e
    elif operator == 'le':
        return a is not None and e is not None and a <= e
    return a == e


# ==================== 响应变量提取器 ====================

def execute_extractors(response, extractors):
    """
    从响应中提取变量，返回 {变量名: 值} 字典。

    每个 extractor 结构：
      {
        "type": "json_path" | "regex" | "header",
        "variable": "变量名",
        "expression": "JSONPath 或正则表达式或响应头名",
        "group": 1,            # regex 专用，捕获组序号，默认 1
        "default": "",         # 提取失败时的默认值
      }
    """
    extracted = {}
    if not extractors:
        return extracted

    for ext in extractors:
        var_name = ext.get('variable', '').strip()
        if not var_name:
            continue
        ext_type = ext.get('type', 'json_path')
        expression = ext.get('expression', '')
        default = ext.get('default', '')
        value = default

        try:
            if ext_type == 'json_path':
                content_type = response.headers.get('content-type', '').lower()
                if 'json' in content_type:
                    resp_json = json.loads(response.text)
                    from jsonpath_ng import parse as jp_parse
                    matches = jp_parse(expression).find(resp_json)
                    if matches:
                        value = matches[0].value
                else:
                    logger.warning("JSONPath 提取器: 响应不是 JSON 格式")

            elif ext_type == 'regex':
                group = int(ext.get('group', 1))
                match = re.search(expression, response.text or '')
                if match:
                    value = match.group(group) if match.lastindex and group <= match.lastindex else match.group(0)

            elif ext_type == 'header':
                value = response.headers.get(expression, default)

        except Exception as e:
            logger.warning("提取变量 %s 失败: %s", var_name, e)
            value = default

        extracted[var_name] = value

    return extracted


# ==================== SAZ 导入 ====================

def parse_saz_file(saz_file):
    """
    解析 Fiddler SAZ 文件（ZIP 格式），返回请求列表。

    SAZ 结构：
      - raw/00001_c.txt  → 客户端请求（原始 HTTP 报文）
      - raw/00001_s.txt  → 服务端响应
      - raw/00001_m.xml  → 元数据

    返回: list[dict]，每个 dict 包含 name, method, url, headers, body, status_code
    """
    import zipfile
    from io import BytesIO

    if hasattr(saz_file, 'read'):
        zip_data = saz_file.read()
    else:
        zip_data = saz_file

    requests_list = []
    try:
        with zipfile.ZipFile(BytesIO(zip_data), 'r') as zf:
            # 收集所有 _c.txt 文件（客户端请求）
            c_files = sorted(
                [n for n in zf.namelist() if n.startswith('raw/') and n.endswith('_c.txt')],
                key=lambda x: x,
            )
            for cf in c_files:
                try:
                    raw_request = zf.read(cf).decode('utf-8', errors='replace')
                    parsed = _parse_raw_http_request(raw_request)
                    if parsed:
                        # 尝试读取对应的响应文件
                        s_file = cf.replace('_c.txt', '_s.txt')
                        if s_file in zf.namelist():
                            raw_response = zf.read(s_file).decode('utf-8', errors='replace')
                            # 提取状态码
                            first_line = raw_response.split('\r\n')[0] if raw_response else ''
                            parts = first_line.split(' ', 2)
                            if len(parts) >= 2:
                                try:
                                    parsed['status_code'] = int(parts[1])
                                except ValueError:
                                    pass
                        requests_list.append(parsed)
                except Exception as e:
                    logger.warning("解析 SAZ 条目 %s 失败: %s", cf, e)
    except zipfile.BadZipFile:
        raise ValueError("不是有效的 SAZ/ZIP 文件")

    return requests_list


def _parse_raw_http_request(raw_text):
    """解析原始 HTTP 请求报文为结构化字典。"""
    lines = raw_text.split('\r\n')
    if not lines or not lines[0]:
        return None

    # 解析请求行: METHOD URL HTTP/1.1
    request_line = lines[0]
    parts = request_line.split(' ', 2)
    if len(parts) < 2:
        return None

    method = parts[0].upper()
    url = parts[1]

    # 解析请求头
    headers = []
    body = ''
    body_start = False
    for line in lines[1:]:
        if body_start:
            body += line + '\r\n'
            continue
        if line == '':
            body_start = True
            continue
        if ':' in line:
            k, v = line.split(':', 1)
            headers.append({
                'key': k.strip(),
                'value': v.strip(),
                'enabled': True,
            })

    # 从 URL 中提取查询参数
    params = []
    if '?' in url:
        path, query_string = url.split('?', 1)
        for pair in query_string.split('&'):
            if '=' in pair:
                k, v = pair.split('=', 1)
                params.append({'key': k, 'value': v, 'enabled': True})
            elif pair:
                params.append({'key': pair, 'value': '', 'enabled': True})

    # 判断 body 类型
    body_data = None
    if body.strip():
        body_data = {
            'type': 'raw',
            'data': body.strip(),
        }
        # 检查是否为 JSON
        try:
            json.loads(body.strip())
            body_data['type'] = 'json'
            body_data['data'] = json.loads(body.strip())
        except (json.JSONDecodeError, ValueError):
            pass

    # 从 URL 中提取名称
    name = url.split('/')[-1].split('?')[0] or url[:50]

    return {
        'name': name,
        'method': method,
        'url': url,
        'headers': headers,
        'params': params,
        'body': body_data,
    }
