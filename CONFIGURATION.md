# Конфигурация

Подробная инструкция: [README.md](README.md).

1. `python setup_local.py` создаёт рабочие файлы без перезаписи.
2. В `config.json` задайте БД и разрешённые представления.
3. В `.env` заполните SQL-логин, пароль и ключ Gemini.
4. Выполните `python inspect_database.py --check` и `python inspect_database.py --sync-catalog`.
5. Для передачи вопроса и каталога включите `ai.external_data_policy: question_and_schema`; исходный шаблон запрещает вызовы.
6. Соберите frontend и запустите `python run.py`.

Локальные конфиги, каталог, секреты и результаты исключены из Git. Не копируйте их в публичные шаблоны.
