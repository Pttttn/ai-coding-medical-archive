import { useEffect, useRef, useState } from 'react';
import { api, json, message } from '../api';
import { ErrorNotice, Loading, Notice } from '../components';
import { useApi } from '../hooks';
import type { Consultation } from '../types';

export function ConsultationResponses({ id, revision, onSaved, onDirty }: { id:string; revision:string; onSaved:()=>void; onDirty:(dirty:boolean)=>void }) {
  const data=useApi<Consultation>(`/consultations/${id}`);
  const [promptId,setPromptId]=useState('');
  const [model,setModel]=useState('');
  const [content,setContent]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const submission=useRef<{key:string;id:string}|null>(null);
  useEffect(()=>{data.reload();},[revision,data.reload]);
  useEffect(()=>{onDirty(Boolean(content.trim()));return()=>onDirty(false);},[content,onDirty]);
  const prompts=data.data?.prompts??[];
  const latestPrompt=prompts.at(-1)?.id||'';
  useEffect(()=>{if(!promptId&&latestPrompt)setPromptId(current=>current||latestPrompt);},[promptId,latestPrompt]);
  const selected=promptId||latestPrompt;
  useEffect(()=>{
    const prevent=(event:BeforeUnloadEvent)=>{if(content.trim()){event.preventDefault();event.returnValue='';}};
    window.addEventListener('beforeunload',prevent);return()=>window.removeEventListener('beforeunload',prevent);
  },[content]);
  async function save(){
    if(!selected||!model.trim()||!content.trim())return;
    setBusy(true);setError('');
    const key=JSON.stringify([id,selected,model,content]);
    if(submission.current?.key!==key)submission.current={key,id:crypto.randomUUID()};
    try{
      await api(`/consultations/${id}/responses`,{method:'POST',body:json({id:submission.current.id,promptId:selected,model:model.trim(),content})});
      setContent('');submission.current=null;data.reload();onSaved();
    }catch(cause){setError(message(cause));}finally{setBusy(false);}
  }
  return <section className="panel"><div className="panel-body"><h2>Ответы frontier-моделей</h2>
    <Notice>Вставьте ответ вручную. Он хранится отдельно от медицинских фактов и не подтверждает диагнозы или назначения.</Notice>
    <ErrorNotice error={data.error||error} retry={data.reload}/>
    {data.loading?<Loading/>:<>
      {(data.data?.responses??[]).map(response=><article key={response.id} className="consultation-answer">
        <h3>{response.model} · {new Date(response.createdAt).toLocaleString('ru-RU')}</h3>
        <p className="muted">Ответ внешней модели · добавлен вручную</p>
        <pre className="consultation-text">{response.content}</pre>
        <details><summary>Запрос, к которому относится ответ</summary><pre className="consultation-text">{prompts.find(p=>p.id===response.promptId)?.content??'Версия недоступна'}</pre></details>
      </article>)}
      {!data.data?.responses?.length&&<p>Сохранённых ответов пока нет.</p>}
      {!prompts.length?<p>Сначала проверьте и подтвердите текст запроса. Его точная версия сохранится для прикрепления ответа.</p>:<>
        <h3>Добавить ответ</h3>
        <label>Версия запроса, переданная модели<select value={selected} disabled={busy} onChange={e=>setPromptId(e.target.value)}>{prompts.map((p,i)=><option key={p.id} value={p.id}>Версия {i+1} · {new Date(p.createdAt).toLocaleString('ru-RU')}</option>)}</select></label>
        <details><summary>Просмотреть выбранный запрос</summary><pre className="consultation-text">{prompts.find(p=>p.id===selected)?.content}</pre></details>
        <p className="muted">Укажите именно отправленную версию. Сохранение здесь не означает автоматическую отправку.</p>
        <label>Модель или сервис<input maxLength={200} value={model} disabled={busy} onChange={e=>setModel(e.target.value)} placeholder="Название модели из вашего чата"/></label>
        <label>Ответ модели<textarea rows={10} maxLength={100000} value={content} disabled={busy} onChange={e=>setContent(e.target.value)} placeholder="Вставьте полный ответ…"/></label>
        <button className="button primary" disabled={busy||!model.trim()||!content.trim()} onClick={()=>void save()}>{busy?'Сохраняем…':'Сохранить ответ'}</button>
        <p className="small-text muted">После сохранения ответ и версия запроса остаются в истории. Новый ответ можно добавить отдельно.</p>
      </>}
    </>}
  </div></section>;
}
