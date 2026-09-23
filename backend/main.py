import json
import mimetypes
import secrets as token_secrets
import threading
import uuid
from datetime import datetime, timezone

import pyodbc
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.ai import AIError, request_plan
from backend.catalog import load_catalog, save_context
from backend.database import ROOT, configuration, connection, secrets
from backend.models import AskRequest, ContextUpdate, ReportPlan, StrictModel
from backend.query import compile_chart, execute_chart

# Windows registry can associate .js with text/plain. ES modules require a JS MIME type.
mimetypes.init()
mimetypes.add_type('text/javascript', '.js')
mimetypes.add_type('text/javascript', '.mjs')
mimetypes.add_type('text/css', '.css')

app = FastAPI(title='AI BI local prototype', docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
session_token = token_secrets.token_urlsafe(32)
generation_lock = threading.Lock()
history_lock = threading.Lock()
REPORTS = ROOT / 'data' / 'reports'


@app.middleware('http')
async def local_guard(request: Request, call_next):
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        if not token_secrets.compare_digest(request.headers.get('x-local-token', ''), session_token):
            return JSONResponse({'detail': 'Откройте приложение заново для обновления сессии.'}, status_code=403)
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail': 'Запрос с другого сайта запрещён.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    # Local demo must also render in the Codex embedded preview.
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(AIError)
async def ai_error(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=exc.status)


@app.exception_handler(ValueError)
async def plan_error(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=422)


@app.exception_handler(pyodbc.Error)
async def db_error(request, exc):
    code = str(exc.args[0]) if exc.args else ''
    message = ('Запрос к SQL Server превысил время ожидания. Сузьте период или упростите отчёт.'
               if code.startswith('HYT') else
               'SQL Server не выполнил запрос. Проверьте подключение и актуальность каталога полей.')
    return JSONResponse({'detail': message}, status_code=502)


@app.get('/api/status')
def status():
    cfg = configuration()
    return {'token': session_token, 'database': cfg['database']['database'],
            'views': len(cfg['database']['allowed_views']), 'provider': cfg['ai']['provider'],
            'model': cfg['ai']['model'], 'ai_key_present': bool(secrets().get('AI_API_KEY', '').strip())}


@app.get('/api/database/check')
def check_database():
    with connection() as conn:
        name = conn.cursor().execute('SELECT DB_NAME()').fetchval()
    return {'connected': True, 'database': name}


@app.get('/api/catalog')
def catalog():
    return load_catalog()


@app.put('/api/catalog')
def update_catalog(update: ContextUpdate):
    return save_context(update)


def persist_report(report):
    with history_lock:
        REPORTS.mkdir(parents=True, exist_ok=True)
        path = REPORTS / (report['id'] + '.json')
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(report, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        temp.replace(path)


def read_report(report_id):
    try:
        report_id = str(uuid.UUID(report_id))
        return json.loads((REPORTS / (report_id + '.json')).read_text(encoding='utf-8'))
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, 'Отчёт не найден.') from None


def execute_report(plan, question, catalog):
    for chart in plan.charts:
        compile_chart(chart, catalog)
    results = [execute_chart(chart, catalog) for chart in plan.charts]
    report = {'id': str(uuid.uuid4()), 'created_at': datetime.now(timezone.utc).isoformat(),
              'question': question, 'plan': plan.model_dump(), 'charts': results, 'saved': False}
    persist_report(report)
    return report


@app.post('/api/ask')
def ask(request: AskRequest):
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(409, 'Другой отчёт уже строится. Дождитесь завершения.')
    try:
        data = load_catalog()
        plan = request_plan(request.question, data, request.previous_plan)
        if plan.clarification:
            return {'clarification': plan.clarification, 'plan': plan.model_dump()}
        return execute_report(plan, request.question, data)
    finally:
        generation_lock.release()


@app.get('/api/reports')
def list_reports():
    with history_lock:
        paths = sorted(REPORTS.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:100]
        output = []
        for path in paths:
            data = json.loads(path.read_text(encoding='utf-8'))
            output.append({'id': data['id'], 'title': data['plan']['title'],
                           'created_at': data['created_at'], 'saved': data['saved']})
        return output


@app.get('/api/reports/{report_id}')
def get_report(report_id: str):
    return read_report(report_id)


class SaveRequest(StrictModel):
    saved: bool


@app.patch('/api/reports/{report_id}')
def save_report(report_id: str, request: SaveRequest):
    with history_lock:
        report = read_report(report_id)
        report['saved'] = request.saved
        # Write directly under the same lock to avoid nested acquisition.
        path = REPORTS / (report['id'] + '.json')
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(report, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        temp.replace(path)
    return report


@app.post('/api/reports/{report_id}/refresh')
def refresh_report(report_id: str):
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(409, 'Другой отчёт уже строится.')
    try:
        previous = read_report(report_id)
        return execute_report(ReportPlan.model_validate(previous['plan']), previous['question'], load_catalog())
    finally:
        generation_lock.release()


# Always mount so a rebuild after server start still serves new hashed assets.
# Directory is created empty if the first build has not run yet.
_assets = ROOT / 'dist' / 'assets'
_assets.mkdir(parents=True, exist_ok=True)
app.mount('/assets', StaticFiles(directory=_assets), name='assets')


@app.get('/')
def index():
    path = ROOT / 'dist' / 'index.html'
    if not path.exists():
        raise HTTPException(503, 'Сначала выполните npm run build.')
    return FileResponse(path)
