"""Compile a constrained report plan. Never execute SQL supplied by the model."""
import datetime
import decimal
import math
from backend.database import configuration, connection
from backend.models import ChartPlan

NUMERIC = {'float', 'real', 'decimal', 'numeric', 'money', 'smallmoney',
           'tinyint', 'smallint', 'int', 'bigint'}
DATES = {'date', 'datetime', 'datetime2', 'smalldatetime', 'datetimeoffset'}


def quote(identifier):
    return '[' + identifier.replace(']', ']]') + ']'


def compile_chart(chart: ChartPlan, catalog):
    allowed = set(configuration()['database']['allowed_views'])
    datasets = {d['name']: d for d in catalog['datasets'] if d['name'] in allowed}
    if chart.dataset not in datasets:
        raise ValueError('ИИ выбрал представление вне разрешённого списка.')
    fields = {f['name']: f for f in datasets[chart.dataset]['fields']}

    def field_sql(name):
        if name not in fields:
            raise ValueError(f'В представлении нет поля «{name}». Уточните запрос.')
        return quote(name)

    projections, groups, columns = [], [], []
    for i, dimension in enumerate(chart.dimensions):
        expr = field_sql(dimension.field)
        if dimension.grain != 'value':
            if fields[dimension.field]['type'] not in DATES:
                raise ValueError('Группировка по времени требует поле даты.')
            if dimension.grain == 'year':
                expr = f'YEAR({expr})'
            elif dimension.grain == 'month':
                expr = f'CONVERT(char(7), {expr}, 126)'
            else:
                expr = f'CONVERT(date, {expr})'
        groups.append(expr)
        projections.append(f'{expr} AS [d{i}]')
        columns.append({'key': f'd{i}', 'label': dimension.field, 'kind': 'dimension'})
    for i, measure in enumerate(chart.measures):
        if measure.field == '*' and measure.aggregate == 'count':
            expr = 'COUNT_BIG(*)'
        else:
            expr = field_sql(measure.field)
            if measure.aggregate in {'sum', 'avg'}:
                if fields[measure.field]['type'] not in NUMERIC:
                    raise ValueError('Сумма и среднее требуют числовое поле.')
                expr = f'{measure.aggregate.upper()}(CAST({expr} AS decimal(38, 6)))'
            elif measure.aggregate == 'count_distinct':
                expr = f'COUNT_BIG(DISTINCT {expr})'
            elif measure.aggregate == 'count':
                expr = f'COUNT_BIG({expr})'
            else:
                expr = f'{measure.aggregate.upper()}({expr})'
        projections.append(f'{expr} AS [m{i}]')
        columns.append({'key': f'm{i}', 'label': measure.label, 'kind': 'measure'})
    if chart.chart_type == 'kpi' and chart.dimensions:
        raise ValueError('Карточка показателя не должна содержать группировку.')
    if chart.chart_type in {'bar', 'line'} and not chart.dimensions:
        raise ValueError('Для графика нужна группировка.')
    where, parameters = [], []
    for item in chart.filters:
        expr = field_sql(item.field)
        if item.operator in {'is_null', 'not_null'}:
            where.append(expr + (' IS NULL' if item.operator == 'is_null' else ' IS NOT NULL'))
        elif item.operator == 'in':
            if not isinstance(item.value, list) or not 1 <= len(item.value) <= 50:
                raise ValueError('Фильтр IN требует от 1 до 50 значений.')
            where.append(expr + ' IN (' + ','.join('?' for _ in item.value) + ')')
            parameters.extend(item.value)
        else:
            if item.value is None or isinstance(item.value, list):
                raise ValueError('Фильтр требует одно значение.')
            if item.operator == 'contains':
                if fields[item.field]['type'] not in {'varchar', 'nvarchar', 'char', 'nchar'}:
                    raise ValueError('Поиск подстроки требует текстовое поле.')
                value = str(item.value).replace('~', '~~').replace('%', '~%').replace('_', '~_').replace('[', '~[')
                where.append(expr + " LIKE ? ESCAPE '~'")
                parameters.append('%' + value + '%')
            else:
                operators = {'eq': '=', 'ne': '<>', 'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<='}
                where.append(expr + ' ' + operators[item.operator] + ' ?')
                parameters.append(item.value)
    keys = {c['key'] for c in columns}
    if chart.sort_by not in keys:
        raise ValueError('Неверное поле сортировки в плане отчёта.')
    schema, name = chart.dataset.split('.', 1)
    limit = min(chart.limit, configuration()['database']['max_result_rows'])
    # One extra group detects truncation. Only controlled tokens become SQL syntax.
    sql = f'SELECT TOP ({limit + 1}) ' + ', '.join(projections)
    sql += ' FROM ' + quote(schema) + '.' + quote(name)
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    if groups:
        sql += ' GROUP BY ' + ', '.join(groups)
    sql += ' ORDER BY ' + quote(chart.sort_by) + ' ' + chart.sort_direction.upper()
    return sql, parameters, columns, limit


def json_value(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        # Preserve SQL precision in transport; chart rendering converts explicitly.
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, bytes):
        return value.hex()
    return value


def execute_chart(chart, catalog):
    sql, params, columns, limit = compile_chart(chart, catalog)
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SET LOCK_TIMEOUT 10000')
        rows = cursor.execute(sql, *params).fetchmany(limit + 1)
    return {'title': chart.title, 'dataset': chart.dataset, 'chart_type': chart.chart_type,
            'columns': columns, 'rows': [dict(zip([c['key'] for c in columns],
                       [json_value(v) for v in row])) for row in rows[:limit]],
            'truncated': len(rows) > limit, 'limit': limit,
            'sql': sql, 'parameters': params, 'filters': [f.model_dump() for f in chart.filters]}
