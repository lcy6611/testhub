# -*- coding: utf-8 -*-
"""
随机数据生成工具
"""
import logging
import random
import string
import uuid
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class RandomTools:
    """随机工具类（与数据工厂视图兼容的接口）"""

    @staticmethod
    def random_int(min_val: int, max_val: int, count: int = 1) -> Dict[str, Any]:
        try:
            if count == 1:
                result = random.randint(min_val, max_val)
                return {'success': True, 'result': result}
            else:
                result = [random.randint(min_val, max_val) for _ in range(count)]
                return {'success': True, 'result': result, 'count': len(result)}
        except Exception as e:
            logger.error(f'随机数生成失败: {str(e)}')
            return {'result': False, 'error': f'随机数生成失败: {str(e)}'}

    @staticmethod
    def random_float(min_val: float, max_val: float, precision: int = 2, count: int = 1) -> Dict[str, Any]:
        try:
            if count == 1:
                result = round(random.uniform(min_val, max_val), precision)
                return {'success': True, 'result': result}
            else:
                result = [round(random.uniform(min_val, max_val), precision) for _ in range(count)]
                return {'success': True, 'result': result, 'count': len(result)}
        except Exception as e:
            logger.error(f'随机浮点数生成失败: {str(e)}')
            return {'result': False, 'error': f'随机浮点数生成失败: {str(e)}'}

    @staticmethod
    def random_string(length: int = 10, char_type: str = 'all', count: int = 1) -> Dict[str, Any]:
        try:
            char_sets = {
                'all': string.ascii_letters + string.digits + string.punctuation,
                'letters': string.ascii_letters,
                'lowercase': string.ascii_lowercase,
                'uppercase': string.ascii_uppercase,
                'digits': string.digits,
                'alphanumeric': string.ascii_letters + string.digits,
                'hex': string.hexdigits.lower(),
            }
            if char_type not in char_sets:
                return {'result': False, 'error': f'不支持的字符类型: {char_type}'}
            chars = char_sets[char_type]
            if count == 1:
                result = ''.join(random.choice(chars) for _ in range(length))
                return {'success': True, 'result': result, 'length': len(result)}
            else:
                result = [''.join(random.choice(chars) for _ in range(length)) for _ in range(count)]
                return {'success': True, 'result': result, 'count': len(result), 'string_length': length}
        except Exception as e:
            logger.error(f'随机字符串生成失败: {str(e)}')
            return {'result': False, 'error': f'随机字符串生成失败: {str(e)}'}

    @staticmethod
    def random_uuid(version: int = 4, count: int = 1) -> Dict[str, Any]:
        try:
            if version == 1:
                gen = uuid.uuid1
            else:
                gen = uuid.uuid4
            if count == 1:
                result = str(gen())
                return {'success': True, 'result': result, 'version': version, 'format': 'string'}
            else:
                result = [str(gen()) for _ in range(count)]
                return {'success': True, 'result': result, 'version': version, 'count': len(result)}
        except Exception as e:
            logger.error(f'UUID生成失败: {str(e)}')
            return {'result': False, 'error': f'UUID生成失败: {str(e)}'}

    @staticmethod
    def random_mac_address(separator: str = ':', count: int = 1) -> Dict[str, Any]:
        try:
            def generate():
                parts = [f'{random.randint(0x00, 0xff):02x}' for _ in range(6)]
                parts[0] = f'{int(parts[0], 16) & 0xfe:02x}'
                return separator.join(parts)

            if count == 1:
                result = generate()
                return {'success': True, 'result': result}
            else:
                result = [generate() for _ in range(count)]
                return {'success': True, 'result': result, 'count': len(result)}
        except Exception as e:
            logger.error(f'MAC地址生成失败: {str(e)}')
            return {'result': False, 'error': f'MAC地址生成失败: {str(e)}'}

    @staticmethod
    def random_ip_address(ip_version: int = 4, count: int = 1) -> Dict[str, Any]:
        try:
            def ipv4():
                return '.'.join(str(random.randint(0, 255)) for _ in range(4))

            if ip_version == 4:
                if count == 1:
                    result = ipv4()
                    return {'success': True, 'result': result, 'version': 4}
                else:
                    result = [ipv4() for _ in range(count)]
                    return {'success': True, 'result': result, 'version': 4, 'count': len(result)}
            else:
                return {'result': False, 'error': f'不支持的IP版本: {ip_version}'}
        except Exception as e:
            logger.error(f'IP地址生成失败: {str(e)}')
            return {'result': False, 'error': f'IP地址生成失败: {str(e)}'}

    @staticmethod
    def random_date(start_date: str, end_date: str, count: int = 1, date_format: str = '%Y-%m-%d') -> Dict[str, Any]:
        """生成随机日期"""
        try:
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            delta = end_dt - start_dt
            if count == 1:
                random_seconds = random.randint(0, max(0, int(delta.total_seconds())))
                result = (start_dt + timedelta(seconds=random_seconds)).strftime(date_format)
                return {'success': True, 'result': result, 'format': date_format}
            result = []
            for _ in range(count):
                random_seconds = random.randint(0, max(0, int(delta.total_seconds())))
                result.append((start_dt + timedelta(seconds=random_seconds)).strftime(date_format))
            return {'success': True, 'result': result, 'count': len(result), 'format': date_format}
        except Exception as e:
            logger.error(f'随机日期生成失败: {str(e)}')
            return {'result': False, 'error': str(e)}

    @staticmethod
    def random_boolean(count: int = 1) -> Dict[str, Any]:
        """生成随机布尔值"""
        try:
            if count == 1:
                return {'success': True, 'result': random.choice([True, False])}
            return {'success': True, 'result': [random.choice([True, False]) for _ in range(count)], 'count': count}
        except Exception as e:
            logger.error(f'随机布尔值生成失败: {str(e)}')
            return {'result': False, 'error': str(e)}

    @staticmethod
    def random_color(format: str = 'hex', count: int = 1) -> Dict[str, Any]:
        """生成随机颜色"""
        try:
            def gen():
                r, g, b = random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
                if format == 'hex':
                    return f'#{r:02x}{g:02x}{b:02x}'
                if format == 'rgb':
                    return f'rgb({r}, {g}, {b})'
                if format == 'rgba':
                    return f'rgba({r}, {g}, {b}, {round(random.random(), 2)})'
                return f'#{r:02x}{g:02x}{b:02x}'
            if count == 1:
                return {'success': True, 'result': gen(), 'format': format}
            return {'success': True, 'result': [gen() for _ in range(count)], 'count': count, 'format': format}
        except Exception as e:
            logger.error(f'随机颜色生成失败: {str(e)}')
            return {'result': False, 'error': str(e)}

    @staticmethod
    def random_password(length: int = 12, include_uppercase: bool = True, include_lowercase: bool = True,
                       include_digits: bool = True, include_special: bool = True, count: int = 1) -> Dict[str, Any]:
        """生成随机密码"""
        try:
            chars = ''
            if include_uppercase:
                chars += string.ascii_uppercase
            if include_lowercase:
                chars += string.ascii_lowercase
            if include_digits:
                chars += string.digits
            if include_special:
                chars += '!@#$%^&*()_+-=[]{}|;:,.<>?'
            if not chars:
                return {'result': False, 'error': '至少选择一种字符类型'}
            def gen():
                return ''.join(random.choice(chars) for _ in range(length))
            if count == 1:
                return {'success': True, 'result': gen(), 'length': length}
            return {'success': True, 'result': [gen() for _ in range(count)], 'count': count, 'length': length}
        except Exception as e:
            logger.error(f'随机密码生成失败: {str(e)}')
            return {'result': False, 'error': str(e)}

    @staticmethod
    def random_sequence(sequence: List, count: int = 1, unique: bool = False) -> Dict[str, Any]:
        """从序列中随机选择"""
        try:
            if unique:
                if count > len(sequence):
                    return {'result': False, 'error': f'请求数量({count})大于序列长度'}
                result = random.sample(sequence, count)
            else:
                result = [random.choice(sequence) for _ in range(count)]
            return {'success': True, 'result': result[0] if count == 1 else result, 'count': len(result) if count > 1 else 1}
        except Exception as e:
            logger.error(f'随机序列选择失败: {str(e)}')
            return {'result': False, 'error': str(e)}

