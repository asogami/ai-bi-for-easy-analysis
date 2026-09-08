"""Initialize local settings without overwriting existing credentials or catalog."""
from pathlib import Path

root = Path(__file__).resolve().parent
for source, target in [('config.example.json', 'config.json'),
                       ('business_context.example.json', 'business_context.json'),
                       ('.env.example', '.env')]:
    try:
        with (root / target).open('x', encoding='utf-8') as output:
            output.write((root / source).read_text(encoding='utf-8'))
        print('Created:', target)
    except FileExistsError:
        print('Kept existing:', target)
