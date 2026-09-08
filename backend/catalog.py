import json
import os
import threading
import uuid
from backend.database import ROOT, configuration
from backend.models import ContextUpdate

lock = threading.RLock()


def load_catalog():
    with lock:
        path = ROOT / configuration()['business_context_file']
        if not path.exists():
            path = ROOT / 'business_context.example.json'
        data = json.loads(path.read_text(encoding='utf-8'))
    allowed = set(configuration()['database']['allowed_views'])
    data['datasets'] = [d for d in data['datasets'] if d['name'] in allowed]
    return data


def save_context(update: ContextUpdate):
    with lock:
        data = load_catalog()
        datasets = {d['name']: d for d in data['datasets']}
        for change in update.datasets:
            if change.name not in datasets:
                raise ValueError('Неизвестное представление в описаниях.')
            target = datasets[change.name]
            fields = {f['name']: f for f in target['fields']}
            for field in change.fields:
                if field.name not in fields:
                    raise ValueError('Неизвестное поле в описаниях.')
                fields[field.name]['description'] = field.description
            target['description'] = change.description
        if any(len(rule) > 2000 for rule in update.business_rules):
            raise ValueError('Одно бизнес-правило должно быть короче 2000 символов.')
        data['company_description'] = update.company_description
        data['business_rules'] = update.business_rules
        path = ROOT / configuration()['business_context_file']
        temp = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, path)
        return data
