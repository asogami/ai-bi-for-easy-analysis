"""List a bounded set of view names, or inspect columns; never print credentials."""
import argparse
import json

from backend.database import ROOT, configuration, connection, describe_view, list_views

parser = argparse.ArgumentParser()
parser.add_argument('--search', default='')
parser.add_argument('--schema')
parser.add_argument('--view')
parser.add_argument('--check', action='store_true')
parser.add_argument('--sync-catalog', action='store_true')
args = parser.parse_args()
try:
    if args.sync_catalog:
        path = ROOT / configuration()['business_context_file']
        context = json.loads(path.read_text(encoding='utf-8'))
        existing = {d['name']: d for d in context.get('datasets', [])}
        datasets = []
        for full_name in configuration()['database']['allowed_views']:
            schema, name = full_name.split('.', 1)
            fields = describe_view(schema, name)
            if not fields:
                raise ValueError('Configured view was not found')
            old = existing.get(full_name, {})
            descriptions = {f['name']: f.get('description', '') for f in old.get('fields', [])}
            for field in fields:
                if descriptions.get(field['name']):
                    field['description'] = descriptions[field['name']]
            datasets.append({**old, 'name': full_name,
                             'description': old.get('description', ''), 'fields': fields})
        context['datasets'] = datasets
        path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding='utf-8')
        output = [{'view': d['name'], 'fields': len(d['fields']),
                   'described_fields': sum(bool(f['description']) for f in d['fields'])}
                  for d in datasets]
    elif args.check:
        with connection() as conn:
            row = conn.cursor().execute(
                'SELECT DB_NAME(), (SELECT COUNT(*) FROM sys.views)'
            ).fetchone()
        output = {'connected': True, 'database': row[0], 'views_count': row[1]}
    elif args.view:
        output = describe_view(args.schema or 'dbo', args.view)
    else:
        output = list_views(args.search)
    print(json.dumps(output, ensure_ascii=False, indent=2))
except Exception:
    print('Database operation failed. Check local configuration, credentials and SQL Server availability.')
    raise SystemExit(1)
