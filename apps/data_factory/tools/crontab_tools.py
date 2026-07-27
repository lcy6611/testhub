"""Crontab 表达式工具"""
from datetime import datetime
from typing import Dict, Any

try:
    from croniter import croniter
    CRONITER_AVAILABLE = True
except ImportError:
    CRONITER_AVAILABLE = False


class CrontabTools:
    """Crontab 工具类"""

    @staticmethod
    def generate_expression(minute: str, hour: str, day: str, month: str, weekday: str) -> Dict[str, Any]:
        """生成 Crontab 表达式"""
        expression = f"{minute} {hour} {day} {month} {weekday}"
        return {
            'result': expression,
            'success': True,
        }

    @staticmethod
    def parse_expression(expression: str) -> Dict[str, Any]:
        """简单解析 Crontab 表达式"""
        parts = expression.strip().split()
        if len(parts) != 5:
            return {'error': 'Crontab 表达式必须包含 5 个字段'}
        minute, hour, day, month, weekday = parts
        return {
            'result': {
                'minute': minute,
                'hour': hour,
                'day': day,
                'month': month,
                'weekday': weekday,
            },
            'success': True,
        }

    @staticmethod
    def get_next_runs(expression: str, count: int = 10) -> Dict[str, Any]:
        """获取下 N 次执行时间"""
        if not CRONITER_AVAILABLE:
            return {'error': 'croniter 模块未安装，请先安装: pip install croniter'}
        base = datetime.now()
        cron = croniter(expression, base)
        runs = [cron.get_next(datetime).strftime('%Y-%m-%d %H:%M:%S') for _ in range(count)]
        return {
            'result': runs,
            'success': True,
            'expression': expression,
            'count': count,
        }

    @staticmethod
    def validate_expression(expression: str) -> Dict[str, Any]:
        """简单校验表达式格式"""
        parts = expression.strip().split()
        if len(parts) != 5:
            return {'result': False, 'valid': False, 'error': '必须包含 5 个字段'}
        return {'result': True, 'valid': True, 'message': '格式看起来是合法的'}

