# -*- coding: utf-8 -*-
"""
字符串处理工具
"""
import re
import json
import difflib
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class StringTools:
    """字符串工具类"""

    @staticmethod
    def remove_whitespace(text: str) -> Dict[str, Any]:
        """去除空格和换行"""
        new_text = re.sub(r'\s+', '', text)
        return {'result': new_text, 'original_length': len(text), 'new_length': len(new_text)}

    @staticmethod
    def replace_string(text: str, old_str: str, new_str: str, is_regex: bool = False) -> Dict[str, Any]:
        """字符串替换"""
        if is_regex:
            try:
                result = re.sub(old_str, new_str, text)
                return {'result': result}
            except re.error as e:
                logger.error(f'正则表达式错误: {str(e)}')
                return {'error': f'正则表达式错误: {str(e)}'}
        else:
            result = text.replace(old_str, new_str)
            return {'result': result}

    @staticmethod
    def escape_string(text: str, escape_type: str = 'json') -> Dict[str, Any]:
        escape_mapping = {
            'json': json.dumps,
            'html': lambda x: x.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'),
        }
        if escape_type not in escape_mapping:
            return {'error': f'不支持的转义类型: {escape_type}'}
        return {'result': escape_mapping[escape_type](text)}

    @staticmethod
    def unescape_string(text: str, unescape_type: str = 'json') -> Dict[str, Any]:
        if unescape_type == 'json':
            try:
                return {'result': json.loads(text)}
            except json.JSONDecodeError as e:
                return {'error': f'JSON解析错误: {str(e)}'}
        return {'error': f'不支持的反转义类型: {unescape_type}'}

    @staticmethod
    def word_count(text: str) -> Dict[str, Any]:
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        numbers = len(re.findall(r'\d+', text))
        punctuation = len(re.findall(r'[^\w\s\u4e00-\u9fff]', text))
        result = {
            'total_length': len(text),
            'chinese_chars': chinese_chars,
            'english_words': english_words,
            'numbers': numbers,
            'punctuation': punctuation,
            'lines': len(text.split('\n')),
        }
        return {'result': len(text), **result}

    @staticmethod
    def text_diff(text1: str, text2: str) -> Dict[str, Any]:
        text1 = text1 or ""
        text2 = text2 or ""
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()
        differ = difflib.Differ()
        diff = list(differ.compare(lines1, lines2))
        added = sum(1 for l in diff if l.startswith('+ '))
        removed = sum(1 for l in diff if l.startswith('- '))
        unchanged = sum(1 for l in diff if l.startswith('  '))
        res = {'diff': diff, 'added': added, 'removed': removed, 'unchanged': unchanged, 'total_changes': added + removed}
        return {'result': added + removed + unchanged, **res}

    @staticmethod
    def regex_test(pattern: str, text: str, flags: str = '') -> Dict[str, Any]:
        try:
            flag_mapping = {'i': re.IGNORECASE, 'm': re.MULTILINE, 's': re.DOTALL}
            regex_flags = 0
            for f in flags:
                if f in flag_mapping:
                    regex_flags |= flag_mapping[f]
            regex = re.compile(pattern, regex_flags)
            matches = regex.findall(text)
            match = regex.search(text)
            groups = match.groups() if match else ()
            return {'result': True, 'matches': matches, 'match_count': len(matches), 'groups': groups, 'is_valid': True}
        except re.error as e:
            return {'error': f'正则表达式错误: {str(e)}', 'is_valid': False}

    @staticmethod
    def case_convert(text: str, convert_type: str) -> Dict[str, Any]:
        funcs = {
            'upper': str.upper,
            'lower': str.lower,
            'capitalize': str.capitalize,
            'title': str.title,
            'swapcase': str.swapcase,
        }
        if convert_type not in funcs:
            return {'error': f'不支持的转换类型: {convert_type}'}
        return {'result': funcs[convert_type](text), 'original': text}

    @staticmethod
    def string_format(text: str, format_type: str) -> Dict[str, Any]:
        """字符串格式化：trim / reverse / split / join"""
        if format_type == 'trim':
            return {'result': text.strip()}
        if format_type == 'reverse':
            return {'result': text[::-1]}
        if format_type == 'split':
            return {'result': text.split()}
        if format_type == 'join':
            return {'result': ''.join(text.split())}
        return {'error': f'不支持的格式化类型: {format_type}'}

