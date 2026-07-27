import logging
import re
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

# 从 SQL 里提取候选表名的简单正则（覆盖 SELECT/FROM/JOIN/INTO/UPDATE/DELETE FROM 等）
_TABLE_NAME_RE = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+`?([a-zA-Z_][a-zA-Z0-9_]*)`?",
    re.IGNORECASE,
)
# CTE / subquery 里也可能有表名，但这里只校验最外层真实表名，避免过度拦截

# 只读语句前缀（白名单）。命中即真实执行并返回结果集。
_READONLY_PREFIXES = (
    'select', 'show', 'desc', 'describe', 'explain',
    'with', 'use', 'pragma', 'analyze', 'call',
)


def _build_url(env):
    """根据环境配置拼 SQLAlchemy URL。

    对于非 sqlite 数据库，db_host 不能为空——因为从 Docker 容器内
    127.0.0.1 是不通的（连的是容器自己），会让用户踩到 111 Connection refused。
    """
    db_type = (env.db_type or 'mysql').lower()
    user = env.db_username or 'root'
    pw = env.db_password or ''
    host = (env.db_host or '').strip()
    port = env.db_port or 3306
    name = (env.db_name or '').strip()

    if db_type == 'sqlite':
        return f'sqlite:///{name}'

    if not host:
        raise ValueError(
            '该环境未配置数据库主机（db_host）。'
            '如使用本地环境，请新建「数据库直连」类型的环境并填写 host.docker.internal 或宿主 IP。'
        )
    if not name:
        raise ValueError('该环境未配置数据库名（db_name）。')

    if db_type == 'postgresql':
        driver = 'postgresql+psycopg2'
    else:
        driver = 'mysql+pymysql'
    return f"{driver}://{user}:{pw}@{host}:{port}/{name}?charset=utf8mb4"


def _is_readonly(sql: str) -> bool:
    s = sql.strip().lower()
    first = s.split(None, 1)[0] if s else ''
    return first in _READONLY_PREFIXES


def _jsonable(v):
    """把数据库返回的非常规类型转成可 JSON 序列化的值。"""
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, bytes):
        return v.decode('utf-8', 'replace')
    return v


def get_schema(env, max_tables: int = 200, max_columns_per_table: int = 100):
    """
    用 SQLAlchemy Inspector 读取目标数据库的表结构。
    返回 {'tables': [{'name': str, 'columns': [{'name': str, 'type': str}]}]}。
    失败时返回 {'error': str}。
    """
    try:
        engine = sqlalchemy.create_engine(
            _build_url(env), pool_pre_ping=True, connect_args={'connect_timeout': 10}
        )
        inspector = inspect(engine)
        schema = {'tables': []}
        for table_name in inspector.get_table_names()[:max_tables]:
            try:
                cols = inspector.get_columns(table_name)[:max_columns_per_table]
                schema['tables'].append({
                    'name': table_name,
                    'columns': [
                        {'name': c['name'], 'type': str(c['type'])}
                        for c in cols
                    ],
                })
            except Exception as exc:
                logger.warning('读取表 %s 结构失败: %s', table_name, exc)
        return schema
    except Exception as exc:
        logger.exception('读取数据库 schema 失败')
        return {'error': str(exc)}


def format_schema_for_prompt(schema: dict) -> str:
    """把 get_schema 的结果转成适合放进 LLM prompt 的文本。"""
    if not schema or schema.get('error'):
        return ''
    lines = ['可用数据表（仅允许使用下列表名和字段）：']
    for table in schema.get('tables', []):
        col_str = ', '.join(f"{c['name']}({c['type']})" for c in table.get('columns', []))
        lines.append(f"- {table['name']}: {col_str}")
    return '\n'.join(lines)


def extract_tables(sql: str):
    """从 SQL 中提取候选真实表名（去重，忽略 schema/database 前缀）。"""
    return list({name for name in _TABLE_NAME_RE.findall(sql or '')})


def validate_tables(env, sql: str):
    """
    检查 SQL 中的表名是否都存在于数据库 schema 中。
    返回 (ok: bool, missing: list[str], available: list[str])。
    """
    sql_tables = extract_tables(sql)
    if not sql_tables:
        return True, [], []
    try:
        engine = sqlalchemy.create_engine(
            _build_url(env), pool_pre_ping=True, connect_args={'connect_timeout': 10}
        )
        inspector = inspect(engine)
        available = set()
        for t in sql_tables:
            try:
                if inspector.has_table(t):
                    available.add(t)
            except Exception:
                pass
        missing = [t for t in sql_tables if t not in available]
        return len(missing) == 0, missing, sorted(available)
    except Exception as exc:
        logger.exception('校验表名失败')
        # 校验失败时不阻塞执行，让真实数据库报错更直观
        return True, [], []


def run_sql(env, sql: str, max_rows: int = 200, mode: str = 'query') -> dict:
    """
    连接环境数据库执行 SQL。

    - 查询模式（mode='query'）：
        - 只读语句：真实执行，返回列名 + 数据行。
        - 写操作（INSERT/UPDATE/DELETE 等）：在事务中执行后立刻回滚，
          返回影响行数但不实际落库，避免误改数据。
    - 数据变更模式（mode='dml'）：
        - 写操作真实提交落库，请谨慎使用。
    """
    url = _build_url(env)
    engine = sqlalchemy.create_engine(
        url, pool_pre_ping=True, connect_args={'connect_timeout': 10}
    )

    # 数据变更模式：真实提交
    if mode == 'dml' and not _is_readonly(sql):
        with engine.begin() as conn:
            result = conn.execute(text(sql))
            affected = result.rowcount
            return {
                'sql': sql,
                'affected_rows': affected,
                'readonly': False,
                'message': f'数据变更已真实执行（影响 {affected} 行）',
            }

    with engine.connect() as conn:
        if _is_readonly(sql):
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [[_jsonable(c) for c in row] for row in result.fetchall()][:max_rows]
            return {
                'sql': sql,
                'columns': columns,
                'rows': rows,
                'row_count': len(rows),
                'readonly': True,
                'message': f'真实执行成功（只读查询，返回 {len(rows)} 行）',
            }
        # 查询模式下的写操作：执行后回滚，安全演示
        trans = conn.begin()
        try:
            result = conn.execute(text(sql))
            affected = result.rowcount
            trans.rollback()
            return {
                'sql': sql,
                'affected_rows': affected,
                'readonly': False,
                'message': f'写操作已在事务中执行并回滚，未实际落库（影响 {affected} 行，安全演示）',
            }
        except Exception:
            trans.rollback()
            raise
