import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ConsultationResponses } from '../pages/ConsultationResponses';
afterEach(()=>vi.unstubAllGlobals());
it('stores a pasted response with selected prompt and renders model content as text',async()=>{
  const posts:Record<string,string>[]=[];
  const prompts=[{id:'old',content:'Original reviewed request',createdAt:'2026-09-25T10:00:00Z'},{id:'new',content:'Later request',createdAt:'2026-09-25T11:00:00Z'}];
  const fetch=vi.fn(async(_url:string,init?:RequestInit)=>{
    if(init?.method==='POST'){posts.push(JSON.parse(String(init.body)));return new Response('{}',{headers:{'Content-Type':'application/json'}});}
    return new Response(JSON.stringify({prompts,responses:posts.map(p=>({...p,createdAt:'2026-09-25T12:00:00Z'}))}),{headers:{'Content-Type':'application/json'}});
  });
  vi.stubGlobal('fetch',fetch);
  const onSaved=vi.fn();render(<ConsultationResponses id="consultation" revision="reviewed" onSaved={onSaved} onDirty={()=>{}}/>);
  await screen.findByRole('button',{name:'Сохранить ответ'});
  fireEvent.change(screen.getByLabelText('Версия запроса, переданная модели'),{target:{value:'old'}});
  fireEvent.change(screen.getByLabelText('Модель или сервис'),{target:{value:'Test model'}});
  fireEvent.change(screen.getByLabelText('Ответ модели'),{target:{value:'<script>fake()</script> Synthetic answer'}});
  fireEvent.click(screen.getByRole('button',{name:'Сохранить ответ'}));
  await waitFor(()=>expect(onSaved).toHaveBeenCalledOnce());
  expect(posts[0].promptId).toBe('old');expect(posts[0].model).toBe('Test model');
  expect(await screen.findByText('<script>fake()</script> Synthetic answer')).toBeVisible();
  expect(document.querySelector('script')).toBeNull();
  fireEvent.click(screen.getByText('Запрос, к которому относится ответ'));
  expect(screen.getAllByText('Original reviewed request').length).toBeGreaterThan(0);
});
it('does not offer response entry without a saved reviewed version',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({prompts:[],responses:[]}),{headers:{'Content-Type':'application/json'}})));
  render(<ConsultationResponses id="draft" revision="none" onSaved={()=>{}} onDirty={()=>{}}/>);
  expect(await screen.findByText(/Сначала проверьте и подтвердите/)).toBeVisible();
  expect(screen.queryByRole('button',{name:'Сохранить ответ'})).not.toBeInTheDocument();
});

it('keeps the selected request when a later reviewed version appears',async()=>{
  const prompts=[{id:'old',content:'First',createdAt:'2026-09-25T10:00:00Z'}];
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({prompts,responses:[]}),{headers:{'Content-Type':'application/json'}})));
  const dirty=vi.fn(),saved=vi.fn();
  const {rerender}=render(<ConsultationResponses id="same" revision="one" onSaved={saved} onDirty={dirty}/>);
  await waitFor(()=>expect(screen.getByLabelText('Версия запроса, переданная модели')).toHaveValue('old'));
  fireEvent.change(screen.getByLabelText('Ответ модели'),{target:{value:'Answer to first request'}});
  prompts.push({id:'new',content:'Second',createdAt:'2026-09-25T11:00:00Z'});
  rerender(<ConsultationResponses id="same" revision="two" onSaved={saved} onDirty={dirty}/>);
  await screen.findByRole('option',{name:/Версия 2/});
  expect(screen.getByLabelText('Версия запроса, переданная модели')).toHaveValue('old');
  expect(screen.getByLabelText('Ответ модели')).toHaveValue('Answer to first request');
});
