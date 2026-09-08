import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

type Field = {name:string; type:string; description:string};
type Dataset = {name:string; description:string; fields:Field[]};
type Catalog = {company_description:string; business_rules:string[]; datasets:Dataset[]};
type Status = {token:string; database:string; views:number; provider:string; model:string; ai_key_present:boolean};
type Column = {key:string; label:string; kind:string};
type Chart = {title:string; dataset:string; chart_type:string; columns:Column[]; rows:Record<string,unknown>[]; truncated:boolean; limit:number; sql:string; parameters:unknown[]; filters:{field:string; operator:string; value:unknown}[]};
type Report = {id:string; created_at:string; question:string; plan:{title:string; explanation:string; [key:string]:unknown}; charts:Chart[]; saved:boolean};
type History = {id:string; title:string; created_at:string; saved:boolean};
let token = '';

async function api<T>(path:string, method='GET', body?:unknown):Promise<T> {
  const response = await fetch('/api'+path, {method, headers:{'Content-Type':'application/json','X-Local-Token':token}, body:body===undefined?undefined:JSON.stringify(body)});
  let data;
  try {data = await response.json();} catch {throw new Error('Сервер вернул неожиданный ответ. Проверьте, запущен ли python run.py.');}
  if (!response.ok) throw new Error(typeof data.detail==='string'?data.detail:'Не удалось обработать запрос. Проверьте введённые данные.');
  return data;
}

const titleFor = (name:string) => name.split('.').pop()?.replaceAll('_',' ')||name;
const fmt = (v:unknown):string => v==null?'—':typeof v==='number'?v.toLocaleString('ru-RU',{maximumFractionDigits:2}):String(v);
const date = (s:string) => new Date(s).toLocaleString('ru-RU',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const money = (v:unknown) => v==null?'—':Number.isFinite(Number(v))?Number(v).toLocaleString('ru-RU',{maximumFractionDigits:2}):String(v);

function ChartCard({chart}:{chart:Chart}) {
  const dimensions = chart.columns.filter(c=>c.kind==='dimension');
  const measures = chart.columns.filter(c=>c.kind==='measure');
  const [mode,setMode] = useState(chart.chart_type);
  const [selected,setSelected] = useState(measures[0]?.key||'m0');
  const rows = chart.rows.slice(0,24);
  const numeric = rows.every(r=>r[selected]==null||Number.isFinite(Number(r[selected])));
  const vals = rows.map(r=>Number(r[selected]??0));
  const lo=Math.min(0,...vals), hi=Math.max(0,...vals), range=hi-lo||1;
  const label=(r:Record<string,unknown>)=>dimensions.map(d=>fmt(r[d.key])).join(' · ');
  const y=(v:number)=>190-(v-lo)/range*160;
  return <article className={'chart-card '+(mode==='kpi'?'kpi-card':'')}>
    <div className="chart-head"><div><span className="eyebrow">{titleFor(chart.dataset)}</span><h3>{chart.title}</h3></div>
      <select aria-label={'Вид: '+chart.title} value={mode} onChange={e=>setMode(e.target.value)}>
        <option value="table">Таблица</option>
        {dimensions.length>0&&<><option value="bar">Столбцы</option><option value="line">Линия</option></>}
        {!dimensions.length&&<option value="kpi">Показатели</option>}
      </select></div>
    {!chart.rows.length?<div className="empty-mini">По этим условиям данные не найдены.</div>:mode==='kpi'?<div className="kpis">{measures.map(m=><div key={m.key}><div className="big-value">{money(chart.rows[0][m.key])}</div><span>{m.label}</span></div>)}</div>:mode==='table'||!numeric?<div className="table-wrap"><table><thead><tr>{chart.columns.map(c=><th key={c.key}>{c.label}</th>)}</tr></thead><tbody>{chart.rows.map((r,i)=><tr key={i}>{chart.columns.map(c=><td key={c.key}>{c.kind==='measure'?money(r[c.key]):fmt(r[c.key])}</td>)}</tr>)}</tbody></table></div>:<>
      {measures.length>1&&<select className="measure-select" aria-label="Показатель графика" value={selected} onChange={e=>setSelected(e.target.value)}>{measures.map(m=><option key={m.key} value={m.key}>{m.label}</option>)}</select>}
      <div className="graph-area"><svg viewBox="0 0 650 255" role="img" aria-label={chart.title}>
        {[0,.5,1].map(t=><g key={t}><line x1="70" x2="635" y1={30+t*160} y2={30+t*160} stroke="#e5eaf2"/><text x="60" y={34+t*160} textAnchor="end" fill="#6b7890" fontSize="12">{new Intl.NumberFormat('ru',{notation:'compact',maximumFractionDigits:1}).format(hi-t*range)}</text></g>)}
        <line x1="70" x2="635" y1={y(0)} y2={y(0)} stroke="#aebcd2"/>
        {mode==='line'?<><polyline fill="none" stroke="#326cf9" strokeWidth="3" points={vals.map((v,i)=>`${85+i*(535/Math.max(vals.length-1,1))},${y(v)}`).join(' ')}/>{vals.map((v,i)=><circle key={i} cx={85+i*(535/Math.max(vals.length-1,1))} cy={y(v)} r="4" fill="#326cf9"><title>{label(rows[i])}: {money(rows[i][selected])}</title></circle>)}</>:vals.map((v,i)=><rect key={i} x={75+i*(560/vals.length)} y={Math.min(y(v),y(0))} width={Math.max(2,560/vals.length-9)} height={Math.max(1,Math.abs(y(v)-y(0)))} rx="3" fill={v<0?'#e28561':'#326cf9'}><title>{label(rows[i])}: {money(rows[i][selected])}</title></rect>)}
        {rows.map((r,i)=>i%Math.max(1,Math.ceil(rows.length/6))===0&&<text key={i} x={mode==='line'?85+i*(535/Math.max(vals.length-1,1)):80+i*(560/vals.length)} y="214" fill="#6b7890" fontSize="12">{label(r).slice(0,15)}<title>{label(r)}</title></text>)}
        <text x="70" y="245" fill="#6b7890" fontSize="12">{measures.find(m=>m.key===selected)?.label}</text>
      </svg></div>
      {chart.rows.length>24&&<p className="muted small">На графике первые 24 группы. Все полученные группы доступны в таблице.</p>}
    </>}
    <footer className="chart-footer"><span>{chart.dataset}</span><span>{chart.rows.length} {dimensions.length?'групп':'строк'}</span></footer>
    {chart.truncated&&<p className="warning small">Показаны первые {chart.limit} групп по заданной сортировке. Это не полный набор.</p>}
    <details className="query-details"><summary>Расчёт и фильтры</summary><pre>{chart.sql}</pre><div>Параметры: {JSON.stringify(chart.parameters)}</div><p>Фильтры: {chart.filters.length?chart.filters.map(f=>`${f.field} ${f.operator} ${JSON.stringify(f.value)}`).join('; '):'без фильтров'}</p></details>
  </article>;
}

function App(){
  const [status,setStatus]=useState<Status|null>(null);
  const [catalog,setCatalog]=useState<Catalog|null>(null);
  const [section,setSection]=useState<'analysis'|'catalog'|'reports'>('analysis');
  const [selectedDataset,setSelectedDataset]=useState('');
  const [history,setHistory]=useState<History[]>([]);
  const [report,setReport]=useState<Report|null>(null);
  const [question,setQuestion]=useState('');
  const [clarification,setClarification]=useState('');
  const [pendingQuestion,setPendingQuestion]=useState('');
  const [busy,setBusy]=useState(false);
  const [saving,setSaving]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [db,setDb]=useState('');
  const [fieldSearch,setFieldSearch]=useState('');
  const [dirty,setDirty]=useState(false);

  async function updateStatus(){const s=await api<Status>('/status');token=s.token;setStatus(s);}
  async function updateHistory(){setHistory(await api<History[]>('/reports'));}
  useEffect(()=>{Promise.all([updateStatus(),api<Catalog>('/catalog').then(c=>{setCatalog(c);setSelectedDataset(c.datasets[0]?.name||'');}),updateHistory()]).catch(e=>setError(e.message));},[]);
  useEffect(()=>{if(!dirty)return;const handler=(e:BeforeUnloadEvent)=>{e.preventDefault();};window.addEventListener('beforeunload',handler);return()=>window.removeEventListener('beforeunload',handler);},[dirty]);

  async function submit(e:React.FormEvent){
    e.preventDefault();if(busy||!question.trim())return;
    if(dirty){setError('Сохраните пояснения в разделе «Данные и правила» перед запросом.');return;}
    setBusy(true);setError('');setNotice('');
    const fullQuestion=pendingQuestion?pendingQuestion+'\nУточнение: '+question:question;
    try{
      const r=await api<Report & {clarification?:string}>('/ask','POST',{question:fullQuestion,previous_plan:report?.plan||null});
      if(r.clarification){setClarification(r.clarification);setPendingQuestion(fullQuestion);setQuestion('');}
      else{setReport(r);setClarification('');setPendingQuestion('');setQuestion('');await updateHistory();}
    }catch(e){setError((e as Error).message);}finally{setBusy(false);await updateStatus().catch(()=>{});}
  }
  async function saveContext(){
    if(!catalog)return;setSaving(true);setError('');setNotice('');
    try{const data={company_description:catalog.company_description,business_rules:catalog.business_rules.filter(r=>r.trim()),datasets:catalog.datasets.map(d=>({name:d.name,description:d.description,fields:d.fields.map(f=>({name:f.name,description:f.description}))}))};setCatalog(await api<Catalog>('/catalog','PUT',data));setDirty(false);setNotice('Пояснения сохранены. Следующий запрос учтёт их.');}catch(e){setError((e as Error).message);}finally{setSaving(false);}
  }
  function changeDataset(description:string){if(!catalog)return;setCatalog({...catalog,datasets:catalog.datasets.map(d=>d.name===selectedDataset?{...d,description}:d)});setDirty(true);}
  function changeField(name:string,description:string){if(!catalog)return;setCatalog({...catalog,datasets:catalog.datasets.map(d=>d.name===selectedDataset?{...d,fields:d.fields.map(f=>f.name===name?{...f,description}:f)}:d)});setDirty(true);}
  async function openReport(id:string){try{setReport(await api<Report>('/reports/'+id));setSection('analysis');setClarification('');setPendingQuestion('');setError('');}catch(e){setError((e as Error).message);}}
  async function saveReport(){if(!report)return;try{setReport(await api<Report>('/reports/'+report.id,'PATCH',{saved:!report.saved}));await updateHistory();}catch(e){setError((e as Error).message);}}
  async function refresh(){if(!report)return;setBusy(true);setError('');try{setReport(await api<Report>('/reports/'+report.id+'/refresh','POST'));await updateHistory();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  const dataset=catalog?.datasets.find(d=>d.name===selectedDataset);
  const described=catalog?.datasets.reduce((n,d)=>n+d.fields.filter(f=>f.description.trim()).length,0)||0;
  const total=catalog?.datasets.reduce((n,d)=>n+d.fields.length,0)||0;
  return <div className="shell">
    <aside className="sidebar"><div className="brand"><span className="brand-icon">▥</span><span>AI BI<span className="brand-sub">SQL ANALYTICS</span></span></div>
      <div className="workspace"><span className="workspace-icon">L</span><div><strong>{status?.database||'Источник данных'}</strong><span>Локальный прототип</span></div><span className="green-dot"/></div>
      <span className="nav-caption">РАБОЧЕЕ ПРОСТРАНСТВО</span>
      <nav><button className={section==='analysis'?'active':''} onClick={()=>setSection('analysis')}><span>✦</span>ИИ-аналитика</button><button className={section==='catalog'?'active':''} onClick={()=>setSection('catalog')}><span>▤</span>Данные и правила{dirty&&<i className="dirty-dot"/>}</button><button className={section==='reports'?'active':''} onClick={()=>setSection('reports')}><span>▧</span>Мои отчёты<span className="count">{history.filter(h=>h.saved).length}</span></button></nav>
      <div className="recent"><span className="nav-caption">ПОСЛЕДНИЕ ЗАПРОСЫ</span>{history.slice(0,5).map(h=><button key={h.id} onClick={()=>openReport(h.id)}>{h.title}<small>{date(h.created_at)}</small></button>)}{!history.length&&<p>Здесь появятся ваши отчёты</p>}</div>
      <div className="sidebar-bottom"><span className="avatar">M</span><div><strong>Рабочая сессия</strong><small>Доступ с этого компьютера</small></div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><span>Рабочее пространство <b>/</b> {section==='analysis'?'ИИ-аналитика':section==='catalog'?'Данные и правила':'Мои отчёты'}</span><span className="pill">SQL Server 2019</span></header>
    <main>
      {error&&<div role="alert" className="alert error">{error}<button aria-label="Закрыть ошибку" onClick={()=>setError('')}>×</button></div>}
      {notice&&<div role="status" className="alert success">{notice}</div>}
      {section==='analysis'&&<>
        <div className="page-heading"><div><span className="eyebrow">ОТ ВОПРОСА К ОТЧЁТУ</span><h1>Спросите ваши данные</h1><p>Опишите задачу — ИИ выберет поля и построит отчёт.</p></div><button className="secondary" disabled={busy} onClick={()=>{setReport(null);setQuestion('');setPendingQuestion('');setClarification('');setError('');}}>＋ Новый запрос</button></div>
        <div className="status-grid"><div><span className="status-icon">▦</span><div><strong>{status?.views??0} представлений</strong><span>{total} полей в каталоге</span></div></div><div><span className="status-icon purple">✦</span><div><strong>{status?.model||'Gemini'}</strong><span>{status?.ai_key_present?'Ключ настроен':'Ожидает API-ключ'}</span></div></div><div><span className="status-icon teal">≡</span><div><strong>{described} полей с пояснениями</strong><button className="text-link" onClick={()=>setSection('catalog')}>Дополнить бизнес-контекст →</button></div></div></div>
        <form className="ask-box" onSubmit={submit}><label htmlFor="question">{pendingQuestion?'Ваше уточнение':report?'Продолжить работу с отчётом':'Какую аналитику построить?'}</label><textarea id="question" value={question} onChange={e=>setQuestion(e.target.value)} maxLength={4000} disabled={busy} placeholder="Укажите показатель, период и нужную группировку" onKeyDown={e=>{if(e.ctrlKey&&e.key==='Enter'){e.preventDefault();e.currentTarget.form?.requestSubmit();}}}/><div className="ask-bottom"><span>В Gemini передаются вопрос и описания полей</span><button className="primary" disabled={busy||!question.trim()||!status} type="submit">{busy?<><span className="spinner"/> Строим отчёт…</>:<>Построить отчёт <span>↗</span></>}</button></div></form>
        {clarification&&<div className="clarification"><span>✦</span><div><strong>Нужно уточнение</strong><p>{clarification}</p></div></div>}
        {!status?.ai_key_present&&<div className="setup-note"><strong>Подключите Gemini</strong><p>Создайте ключ в <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">Google AI Studio</a> и заполните AI_API_KEY в файле .env. Используйте проект с бесплатной квотой.</p><button className="text-link" onClick={()=>updateStatus().catch(e=>setError(e.message))}>Я добавил ключ — проверить →</button></div>}
        {busy&&<div className="processing" role="status"><span className="spinner"/><div><strong>Подбираем расчёт и читаем данные</strong><p>Запрос к ИИ может занять до 90 секунд; каждый график ограничен таймаутом SQL.</p></div></div>}
        {report?<section className="report"><div className="report-heading"><div><span className="eyebrow">РЕЗУЛЬТАТ · {date(report.created_at)}</span><h2>{report.plan.title}</h2></div><div className="actions"><button className="secondary" disabled={busy} onClick={refresh}>↻ Обновить данные</button><button className="secondary" onClick={saveReport}>{report.saved?'★ Сохранён':'☆ Сохранить'}</button></div></div><p className="explanation">{report.plan.explanation}</p><div className="charts">{report.charts.map((c,i)=><ChartCard chart={c} key={report.id+'-'+i}/>)}</div></section>:!busy&&<section className="starter"><div className="section-heading"><h2>Начните с конкретного показателя</h2><span>Примеры запросов</span></div><div className="examples">{[
          ['Динамика показателя','Покажи динамику основного показателя по месяцам. Если его определение не задано, уточни его.'],
          ['Состав данных','Какие показатели можно рассчитать по подключённым данным? Предложи один отчёт и уточни период.'],
          ['Сравнение категорий','Сравни категории по выбранному показателю. Уточни, какие поля использовать.']
        ].map(([title,q])=><button key={title} onClick={()=>setQuestion(q)}><span className="example-symbol">↗</span><strong>{title}</strong><p>{q}</p></button>)}</div><div className="source-strip"><span>Доступные данные</span>{catalog?.datasets.map(d=><button key={d.name} onClick={()=>{setSelectedDataset(d.name);setSection('catalog');}}>{titleFor(d.name)}</button>)}</div></section>}
      </>}
      {section==='catalog'&&catalog&&<>
        <div className="page-heading"><div><span className="eyebrow">КОНТЕКСТ ДЛЯ ИИ</span><h1>Данные и бизнес-правила</h1><p>Названия полей загружены из SQL Server. Добавьте их смысл и правила расчёта.</p></div><button className="primary" disabled={saving||!dirty} onClick={saveContext}>{saving?'Сохраняем…':dirty?'Сохранить пояснения':'Всё сохранено'}</button></div>
        <div className="context-box"><label>О компании<textarea value={catalog.company_description} maxLength={2000} placeholder="Чем занимается компания, какие валюты и направления учитываются" onChange={e=>{setCatalog({...catalog,company_description:e.target.value});setDirty(true);}}/></label><label>Бизнес-правила — по одному на строку<textarea value={catalog.business_rules.join('\n')} placeholder="Например: какой показатель считаем выручкой; как учитываем возвраты; какая дата определяет период" onChange={e=>{setCatalog({...catalog,business_rules:e.target.value.split('\n')});setDirty(true);}}/></label></div>
        <div className="catalog-layout"><div className="dataset-list">{catalog.datasets.map(d=><button className={d.name===selectedDataset?'selected':''} key={d.name} onClick={()=>{setSelectedDataset(d.name);setFieldSearch('');}}><strong>{titleFor(d.name)}</strong><small>{d.name} · {d.fields.length} полей</small></button>)}<button className="check-connection" onClick={async()=>{try{await api('/database/check');setDb('Подключение работает');}catch(e){setDb((e as Error).message);}}}>Проверить подключение</button>{db&&<p className="small">{db}</p>}</div>
          {dataset&&<div className="fields-panel"><div className="section-heading"><div><h2>{titleFor(dataset.name)}</h2><span>{dataset.name}</span></div><span className="pill">{dataset.fields.length} полей</span></div><label className="dataset-description">Назначение и детализация представления<textarea maxLength={2000} value={dataset.description} onChange={e=>changeDataset(e.target.value)} placeholder="Что означает одна строка, какие документы включены, есть ли дубли или исключения"/></label><input className="field-search" placeholder="Найти поле…" aria-label="Найти поле" value={fieldSearch} onChange={e=>setFieldSearch(e.target.value)}/><div className="field-headers"><span>Поле в базе</span><span>Пояснение для ИИ</span></div>{dataset.fields.filter(f=>f.name.toLowerCase().includes(fieldSearch.toLowerCase())).map(f=><div className="field-row" key={f.name}><div><strong>{f.name}</strong><small>{f.type}</small></div><textarea aria-label={'Описание '+f.name} maxLength={1000} value={f.description} onChange={e=>changeField(f.name,e.target.value)} placeholder="Смысл, единицы, правила использования"/></div>)}</div>}
        </div>
      </>}
      {section==='reports'&&<><div className="page-heading"><div><span className="eyebrow">ПОВТОРНОЕ ИСПОЛЬЗОВАНИЕ</span><h1>Мои отчёты</h1><p>Сохранённые расчёты и история успешных запросов.</p></div></div>{!history.length?<div className="empty-state"><h2>Пока нет отчётов</h2><p>Постройте первый отчёт в ИИ-аналитике.</p><button className="primary" onClick={()=>setSection('analysis')}>Задать вопрос →</button></div>:<div className="history-list">{history.map(h=><button key={h.id} onClick={()=>openReport(h.id)}><span className="report-symbol">{h.saved?'★':'▧'}</span><div><strong>{h.title}</strong><small>{h.saved?'Сохранённый отчёт':'История'} · {date(h.created_at)}</small></div><span>→</span></button>)}</div>}</>}
      <footer className="main-footer">AI BI · Прототип <span>Расчёты выполняются в SQL Server · Результаты хранятся локально</span></footer>
    </main></div>
  </div>;
}
class RenderBoundary extends React.Component<{children:React.ReactNode},{failed:boolean}> {
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  render(){return this.state.failed?<main><h1>Не удалось отобразить интерфейс</h1><p>Обновите страницу. Если ошибка повторится, сообщите об этом разработчику.</p><button onClick={()=>location.reload()}>Перезагрузить</button></main>:this.props.children;}
}
createRoot(document.getElementById('root')!).render(<RenderBoundary><App/></RenderBoundary>);
