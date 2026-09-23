"""SQL Server metadata access for the local prototype; no model SQL execution."""
import json
import os
from contextlib import contextmanager
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[1]


def configuration():
    path = ROOT / 'config.json'
    if not path.exists():
        path = ROOT / 'config.example.json'
    return json.loads(path.read_text(encoding='utf-8'))


def secrets():
    values = {}
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                values[key.strip()] = value
    for key in ('DB_USERNAME', 'DB_PASSWORD', 'AI_API_KEY'):
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def odbc_value(value):
    return '{' + str(value).replace('}', '}}') + '}'


@contextmanager
def connection():
    cfg = configuration()['database']
    env = secrets()
    host = cfg['host']
    if cfg.get('port'):
        host += ',' + str(int(cfg['port']))
    fields = {
        'DRIVER': cfg['driver'], 'SERVER': host, 'DATABASE': cfg['database'],
        'APP': 'AI BI metadata prototype',
    }
    mode = (cfg.get('auth_mode') or 'sql').lower()
    if mode == 'windows':
        fields['Trusted_Connection'] = 'yes'
    elif mode == 'sql':
        fields['UID'] = env.get(cfg['username_env'], '')
        fields['PWD'] = env.get(cfg['password_env'], '')
    else:
        raise ValueError(f'Unsupported auth_mode: {mode}')
    conn = pyodbc.connect(
        ';'.join(k + '=' + odbc_value(v) for k, v in fields.items()),
        timeout=cfg['connection_timeout_seconds'], autocommit=False,
    )
    conn.timeout = cfg['query_timeout_seconds']
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


def list_views(search='', limit=50):
    limit = min(max(int(limit), 1), 100)
    with connection() as conn:
        rows = conn.cursor().execute('''
            SELECT TOP (?) s.name, v.name
            FROM sys.views v JOIN sys.schemas s ON s.schema_id=v.schema_id
            WHERE CHARINDEX(?, s.name + '.' + v.name) > 0
            ORDER BY s.name, v.name
        ''', limit, search).fetchall()
    return [{'schema': row[0], 'name': row[1]} for row in rows]


def describe_view(schema, name):
    with connection() as conn:
        rows = conn.cursor().execute('''
            SELECT c.name, t.name, c.is_nullable,
                   CONVERT(nvarchar(4000), ep.value)
            FROM sys.views v
            JOIN sys.schemas s ON s.schema_id=v.schema_id
            JOIN sys.columns c ON c.object_id=v.object_id
            JOIN sys.types t ON t.user_type_id=c.user_type_id
            LEFT JOIN sys.extended_properties ep
              ON ep.class=1 AND ep.major_id=c.object_id
              AND ep.minor_id=c.column_id AND ep.name=N'MS_Description'
            WHERE s.name=? AND v.name=? ORDER BY c.column_id
        ''', schema, name).fetchall()
    return [{'name': r[0], 'type': r[1], 'nullable': bool(r[2]),
             'description': r[3] or ''} for r in rows]
