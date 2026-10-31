import {useEffect, useMemo, useState} from 'react';
import {Bot, Check, Download, Lightbulb, Network, Scissors, Send, X} from 'lucide-react';
import {api, apiText} from './api';
import type {Alert, Case, CaseEvent} from './contracts';

const label = (s:string)=>s.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
const post = (body:unknown):RequestInit=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
function Rows({rows}:{rows:Record<string,unknown>[]}) {
  const keys=[...new Set(rows.flatMap(Object.keys))];
  if(!rows.length) return <p className="muted">No records.</p>;
  return <div className="table-scroll"><table><thead><tr>{keys.map(k=><th key={k}>{label(k)}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{keys.map(k=><td key={k}>{r[k]==null?'—':typeof r[k]==='object'?JSON.stringify(r[k]):String(r[k])}</td>)}</tr>)}</tbody></table></div>;
}

/* ---------- Relationship network (L2-2) ---------- */
type GNode = {id:string;type:string;label:string;risk:string|null};
type GEdge = {source:string;target:string;via:string;evidence_ids:string[]};
type Graph = {nodes:GNode[];edges:GEdge[];hubs_hidden?:string[]};
type Group = {group_id:string;members:string[];alert_ids:string[];highest_band:string|null;reason:string;links:{via:string;value:string;members:string[];evidence_ids:string[]}[]};
const TYPE_COLOR:Record<string,string> = {customer:'#1f6f5f',account:'#4a6fa5',device:'#8a5a9e',ip:'#7a7f86',phone:'#b07a2a',email:'#b07a2a',application:'#c0603a',claim:'#9e4a6a',policy:'#9e4a6a'};
const RISK_COLOR:Record<string,string> = {High:'#bd6059',Medium:'#cb9a3e',Low:'#399987'};

function layout(g:Graph, center:string) {
  const adj=new Map<string,string[]>(); g.nodes.forEach(n=>adj.set(n.id,[]));
  g.edges.forEach(e=>{adj.get(e.source)?.push(e.target);adj.get(e.target)?.push(e.source)});
  const depth=new Map([[center,0]]); const queue=[center];
  while(queue.length){const n=queue.shift()!;for(const m of adj.get(n)||[])if(!depth.has(m)){depth.set(m,depth.get(n)!+1);queue.push(m)}}
  const rings=new Map<number,string[]>(); g.nodes.forEach(n=>{const d=depth.get(n.id)??3;rings.set(d,[...(rings.get(d)||[]),n.id])});
  const pos=new Map<string,{x:number;y:number}>();
  rings.forEach((ids,d)=>ids.forEach((id,i)=>{const a=2*Math.PI*i/ids.length+d*0.6;const r=d*150;pos.set(id,{x:420+r*Math.cos(a),y:330+r*Math.sin(a)})}));
  return pos;
}

export function NetworkView({initial}:{initial?:string}) {
  const [entity,setEntity]=useState(initial||''); const [graph,setGraph]=useState<Graph|null>(null); const [center,setCenter]=useState('');
  const [records,setRecords]=useState<{id:string;records:Record<string,Record<string,unknown>[]>}|null>(null);
  const [edge,setEdge]=useState<GEdge|null>(null); const [groups,setGroups]=useState<Group[]>([]); const [error,setError]=useState('');
  async function open(id:string){setError('');setEdge(null);try{const g=await api<Graph>(`/graph?entity_id=${encodeURIComponent(id)}&depth=2`);if(!g.nodes.length)throw new Error(`No stored records link to ${id}.`);setGraph(g);setCenter(id);setEntity(id);await inspect(id)}catch(e){setError(e instanceof Error?e.message:String(e))}}
  async function inspect(id:string){try{const r=await api<{records:Record<string,Record<string,unknown>[]>}>(`/graph/entity/${encodeURIComponent(id)}`);setRecords({id,records:r.records})}catch(e){setError(e instanceof Error?e.message:String(e))}}
  useEffect(()=>{api<{groups:Group[]}>('/graph/groups').then(r=>setGroups(r.groups)).catch(e=>setError(String(e.message||e)));if(initial)void open(initial)},[]);
  const pos=useMemo(()=>graph?layout(graph,center):new Map(),[graph,center]);
  return <>
    <section className="panel"><div className="section-heading"><div><h2>Relationship network</h2><p>Every link is a shared identifier found in the source records. Hover a link for its evidence; select an entity for its records.</p></div><Network size={19}/></div>
      <form className="filters" onSubmit={e=>{e.preventDefault();if(entity.trim())void open(entity.trim())}}><label>Entity<input aria-label="Network entity" value={entity} onChange={e=>setEntity(e.target.value)} placeholder="Customer, account, device, IP…"/></label><button className="primary">Show network</button></form>
      {error&&<p className="warning">{error}</p>}
      {graph&&<div className="graph-wrap"><svg viewBox="0 0 840 660" role="img" aria-label={`Network around ${center}`}>
        {graph.edges.map((e,i)=>{const a=pos.get(e.source),b=pos.get(e.target);if(!a||!b)return null;return <g key={i} className={`edge ${edge===e?'on':''}`} onMouseEnter={()=>setEdge(e)} onClick={()=>setEdge(e)}><line x1={a.x} y1={a.y} x2={b.x} y2={b.y}/><line className="hit" x1={a.x} y1={a.y} x2={b.x} y2={b.y}/><title>{`${e.source} — ${e.via} — ${e.target}\nEvidence: ${e.evidence_ids.join(', ')}`}</title></g>})}
        {graph.nodes.map(n=>{const p=pos.get(n.id);if(!p)return null;return <g key={n.id} className={`node ${records?.id===n.id?'on':''}`} transform={`translate(${p.x},${p.y})`} onClick={()=>void inspect(n.id)} onDoubleClick={()=>void open(n.id)} tabIndex={0} onKeyDown={e=>{if(e.key==='Enter')void inspect(n.id)}}><circle r={n.id===center?16:11} fill={TYPE_COLOR[n.type]||'#888'} stroke={n.risk?RISK_COLOR[n.risk]:'#fff'} strokeWidth={n.risk?4:2}/><text y={n.id===center?30:25}>{n.label.length>16?n.label.slice(0,15)+'…':n.label}</text><title>{`${label(n.type)} ${n.id}${n.risk?` · ${n.risk} risk alert`:''}`}</title></g>})}
      </svg>
      <div className="graph-legend">{Object.entries(TYPE_COLOR).filter(([t])=>graph.nodes.some(n=>n.type===t)).map(([t,c])=><span key={t}><i style={{background:c}}/>{label(t)}</span>)}<span><i className="ring"/>Outline = alert risk</span><span>Double-click an entity to re-centre</span></div>
      {edge&&<p className="edge-detail"><b>{edge.source}</b> ↔ <b>{edge.target}</b> via <b>{label(edge.via)}</b> · evidence {edge.evidence_ids.join(', ')||'none'}</p>}
      {!!graph.hubs_hidden?.length&&<p className="muted">Hidden hubs (too common to be meaningful): {graph.hubs_hidden.join(', ')}</p>}</div>}
      {records&&<section className="evidence-focus"><div className="section-heading"><h3>Records for {records.id}</h3><button onClick={()=>setRecords(null)}>Close</button></div>{Object.entries(records.records).map(([name,rows])=><details key={name} open><summary>{label(name)} <small>{rows.length} records</small></summary><Rows rows={rows}/></details>)}{!Object.keys(records.records).length&&<p className="muted">No source rows reference this ID.</p>}</section>}
    </section>
    <section className="panel"><div className="section-heading"><div><h2>Linked customer groups</h2><p>Customers sharing a device, phone, email or payout account (never just an IP or a common payee).</p></div></div>
      <div className="table-scroll"><table><thead><tr><th>Group</th><th>Why linked</th><th>Alerts</th><th>Highest risk</th><th/></tr></thead><tbody>{groups.map(g=><tr key={g.group_id}><td>{g.members.join(', ')}</td><td>{g.reason}</td><td>{g.alert_ids.length}</td><td>{g.highest_band||'—'}</td><td><button onClick={()=>void open(g.members[0])}>View network</button></td></tr>)}</tbody></table></div>{!groups.length&&<div className="empty">No linked groups in the stored records.</div>}
    </section>
  </>;
}

/* ---------- Pattern Scout suggestions ---------- */
type Suggestion = {id:string;title:string;hypothesis:string;suggested_rule:string;entities:string[];evidence_ids:string[];source:string;status:string;decided_by?:string;note?:string;decision_note?:string};
export function PatternsPanel({actor}:{actor:string}) {
  const [items,setItems]=useState<Suggestion[]|null>(null); const [usedLlm,setUsedLlm]=useState(false); const [busy,setBusy]=useState(false); const [msg,setMsg]=useState('');
  async function scout(){setBusy(true);setMsg('');try{const r=await api<{suggestions:Suggestion[];used_llm:boolean}>('/agents/pattern-scout',{method:'POST'});setItems(r.suggestions);setUsedLlm(r.used_llm);const n=(st:string)=>r.suggestions.filter(x=>x.status===st).length;setMsg(`Scan finished: ${n('suggested')} new (awaiting review), ${n('approved')} already approved, ${n('dismissed')} dismissed.`)}catch(e){setMsg(e instanceof Error?e.message:String(e))}finally{setBusy(false)}}
  const [notes,setNotes]=useState<Record<string,string>>({});
  useEffect(()=>{api<{items:Suggestion[]}>('/agents/suggestions').then(r=>{if(r.items.length)setItems(r.items)}).catch(()=>{})},[]);
  async function decide(s:Suggestion, verdict:'approved'|'dismissed'){
    const note=(notes[s.id]||'').trim();
    if(!actor.trim()||!note){setMsg('Give a reviewer name (case workspace) and a note before approving or dismissing.');return}
    // Plan rev 2 #7: B stores suggestions with stable IDs; approving never changes the rules.
    try{await api(`/agents/suggestions/${encodeURIComponent(s.id)}/decision`,post({decision:verdict==='approved'?'approve':'dismiss',actor:actor.trim(),note}));
      setItems(old=>old?.map(x=>x.id===s.id?{...x,status:verdict,decided_by:actor.trim(),note}:x)||null);setMsg(`${s.id} ${verdict} and saved. Rules are unchanged.`)}
    catch(e){setMsg(`${s.id} was not saved: ${e instanceof Error?e.message:String(e)}`)}
  }
  return <section className="panel"><div className="section-heading"><div><h2>Suggested patterns <span className="number-pill">{items?.length??'—'}</span></h2><p>Linked behaviour no rule alerted on. Suggestions only: they need analyst approval and never change a score.</p></div><button className="primary" disabled={busy} onClick={()=>void scout()}><Lightbulb size={16}/>Run Pattern Scout</button></div>
    {msg&&<p className="muted" role="status">{msg}</p>}
    {items&&<p className="muted">{usedLlm?'Hypotheses worded by AI from deterministic findings · IDs checked.':'AI off: hypotheses are templates over deterministic findings.'}</p>}
    {items?.map(s=><article className={`suggestion ${s.status}`} key={s.id}><div><b>{s.title}</b><small>{s.id} · {s.source==='ai'?'AI-worded':'rules'} · {s.status}</small><p>{s.hypothesis}</p><p><b>Suggested rule:</b> {s.suggested_rule}</p><small>Entities: {s.entities.join(', ')} · Evidence: {s.evidence_ids.join(', ')}</small></div>{s.status==='suggested'?<div className="suggestion-buttons"><input aria-label={`Note for ${s.id}`} placeholder="Note (required)" value={notes[s.id]||''} onChange={e=>setNotes(n=>({...n,[s.id]:e.target.value}))}/><button onClick={()=>void decide(s,'approved')}><Check size={15}/>Approve</button><button onClick={()=>void decide(s,'dismissed')}><X size={15}/>Dismiss</button></div>:s.decided_by&&<small>{label(s.status)} by {s.decided_by}{(s.note||s.decision_note)?`: ${s.note||s.decision_note}`:''}</small>}</article>)}
    {items&&!items.length&&<div className="empty">No unalerted patterns found in the latest run.</div>}
  </section>;
}

/* ---------- Ask FinShield (AI Assistant) ---------- */
type Answer = {answer:string;citations:string[];dropped_citations:string[];used_llm:boolean;label:string};
export function Assistant({route,ids={},onSaved}:{route:string;ids?:Record<string,string|undefined|null>;onSaved?:(c:Case)=>void}) {
  const [open,setOpen]=useState(false); const [q,setQ]=useState(''); const [busy,setBusy]=useState(false);
  const [log,setLog]=useState<{q:string;a?:Answer;error?:string;saved?:string}[]>([]);
  // Plan rev 2 #9: only output tied to a case is saved, marked AI-generated, so the analyst can reject it.
  async function save(i:number){const m=log[i];if(!ids.case_id||!m.a)return;let saved='Saved to the case audit trail as an AI assessment.';
    try{const updated=await api<Case>(`/cases/${encodeURIComponent(ids.case_id)}/events`,post({type:'ai_assessment',actor:'Ask FinShield (AI-generated)',note:`Q: ${m.q}\nA: ${m.a.answer}\nCites: ${m.a.citations.join(', ')||'none'} · ${m.a.label}`,detail:{citations:m.a.citations,used_llm:m.a.used_llm,question:m.q}}));onSaved?.(updated)}
    catch(e){saved=`Not saved: ${e instanceof Error?e.message:String(e)}`}
    setLog(l=>l.map((x,j)=>j===i?{...x,saved}:x))}
  async function ask(){const question=q.trim();if(!question)return;setBusy(true);setQ('');
    try{const a=await api<Answer>('/assistant',post({question,screen:{route,ids}}));setLog(l=>[...l,{q:question,a}])}catch(e){setLog(l=>[...l,{q:question,error:e instanceof Error?e.message:String(e)}])}finally{setBusy(false)}}
  return <>
    <button className="ask-button" onClick={()=>setOpen(o=>!o)} aria-expanded={open}><Bot size={17}/>Ask FinShield</button>
    {open&&<aside className="assistant" aria-label="Ask FinShield"><header><div><b>Ask FinShield</b><small>Answers from what is on this screen ({route}). Explains only; never acts.</small></div><button onClick={()=>setOpen(false)} aria-label="Close assistant"><X size={18}/></button></header>
      <div className="assistant-log">{!log.length&&<p className="muted">Try: “Why is this case high risk?”, “What links these customers?”, or ask about an ID you can see.</p>}
        {log.map((m,i)=><div key={i}><p className="q">{m.q}</p>{m.error?<p className="error">{m.error}</p>:m.a&&<div className="a"><p>{m.a.answer}</p>{!!m.a.citations.length&&<small>Cites: {m.a.citations.join(', ')}</small>}{!!m.a.dropped_citations.length&&<small className="bad">Dropped unverifiable IDs: {m.a.dropped_citations.join(', ')}</small>}<small className="ai-label">{m.a.label}</small>{ids.case_id&&(m.saved?<small>{m.saved}</small>:<button className="link-button" onClick={()=>void save(i)}>Save to case as AI assessment</button>)}</div>}</div>)}
        {busy&&<p className="muted">Thinking…</p>}</div>
      <form onSubmit={e=>{e.preventDefault();void ask()}}><input aria-label="Question" value={q} onChange={e=>setQ(e.target.value)} placeholder="Ask about this screen"/><button className="primary" disabled={busy||!q.trim()} aria-label="Send"><Send size={15}/></button></form>
    </aside>}
  </>;
}

/* ---------- Case workspace additions (L2-3, L2-4, L2-5, L2-6) ---------- */
type Priority = {alert_id:string;priority:number;exposure:number;related_events:number;confidence:string;evidence_strength?:string;needs_review:boolean;factors:string[]};
const STRENGTH:Record<string,string> = {high:'strong',medium:'moderate',low:'weak'};
const strength = (p:Priority)=>p.evidence_strength || STRENGTH[p.confidence] || p.confidence;
type Memory = {case_id:string;at:string;actor:string;from?:string;to:string;note?:string;type?:string};

/* Consolidated investigations and per-case priority come from B's GET /incidents (plan rev 2 #1, #10). */
export type CasePriority = {priority:number;score:number;band:string|null;alert_count:number;related_events:number;exposure_by_currency:Record<string,number>;evidence_strength:string;needs_review:boolean;factors:string[]};
export type Incident = {incident_id:string;alert_ids:string[];entities:string[];customers:string[];reason:string;priority:CasePriority};
export const incidentFor = (c:{alert_ids:string[]}, list:Incident[])=>list.find(i=>i.alert_ids.some(a=>c.alert_ids.includes(a)));
export const casePriority = (c:Case, list:Incident[]):CasePriority|undefined=>c.priority?{priority:c.priority,score:c.score,band:c.band,alert_count:c.alert_ids.length,related_events:0,exposure_by_currency:c.exposure_by_currency||{},evidence_strength:c.evidence_strength||'weak',needs_review:!!c.needs_review,factors:c.priority_factors||[]}:incidentFor(c,list)?.priority;
export async function loadIncidents() {try{return (await api<{items:Incident[]}>('/incidents')).items}catch{return []}}
export function PriorityCell({p}:{p?:CasePriority}) {
  if(!p) return <span className="muted">—</span>;
  return <div className={`priority-cell ${p.needs_review?'review':''}`} title={p.factors.join('\n')}><b>{p.priority}</b><small>evidence {p.evidence_strength}{p.needs_review?' · needs review':''}</small></div>;
}
export function IncidentsPanel({incidents, cases, onOpen}:{incidents:Incident[];cases:Case[];onOpen:(c:Case)=>void}) {
  const grouped=incidents.filter(i=>i.alert_ids.length>1);
  return <section className="panel"><div className="section-heading"><div><h2>Consolidated investigations <span className="number-pill">{grouped.length}</span></h2><p>Related alerts grouped by a linked customer group or the same customer within 72 hours, highest priority first. The original alerts are kept.</p></div></div>
    <div className="table-scroll"><table className="incidents"><thead><tr><th>Investigation</th><th>Why grouped</th><th>Alerts</th><th>Customers</th><th>Priority</th><th/></tr></thead><tbody>{grouped.map(i=>{const c=cases.find(x=>x.alert_ids.some(a=>i.alert_ids.includes(a)));return <tr key={i.incident_id}><td><b>{i.incident_id}</b><small>{i.alert_ids.join(' · ')}</small></td><td>{i.reason}</td><td>{i.alert_ids.length}</td><td>{i.customers.join(', ')||'—'}</td><td><PriorityCell p={i.priority}/><small>{i.priority.factors.join(' · ')}</small></td><td>{c?<button onClick={()=>onOpen(c)}>Open case</button>:<small>No case (Low only)</small>}</td></tr>})}</tbody></table></div>
    {!grouped.length&&<div className="empty">No multi-alert investigations in the latest run.</div>}
  </section>;
}

/* Audit-trail extras: AI assessments can be rejected (rev 2 #9); reclassifications show both levels (rev 2 #4). */
export function EventExtras({event, events, caseId, actor, note, onSaved}:{event:CaseEvent;events:CaseEvent[];caseId:string;actor:string;note:string;onSaved:(c:Case,msg:string)=>void}) {
  const [msg,setMsg]=useState('');
  const d=event.detail||{}; const from=d.from_band as string|undefined, to=d.to_band as string|undefined;
  const rejection=events.find(e=>e.type==='correction'&&e.detail?.rejects_event_id!=null&&e.detail.rejects_event_id===event.id);
  async function reject(){setMsg('');
    if(!actor.trim()||!note.trim()){setMsg('Enter a reviewer and, in the rationale, why the AI assessment is wrong.');return}
    try{const id=encodeURIComponent(caseId);await api(`/cases/${id}/events`,post({type:'correction',actor:actor.trim(),note:`Rejected AI assessment: ${note.trim()}`,detail:{rejects_event_id:event.id,rejected_at:event.at}}));onSaved(await api<Case>(`/cases/${id}`),'AI assessment rejected; the original stays in the audit trail.')}
    catch(e){setMsg(`Rejection not recorded: ${e instanceof Error?e.message:String(e)}`)}}
  return <>
    {from&&to&&<p className="reclass">Risk reclassified <span className={`badge ${from.toLowerCase()}`}>{from}</span> → <span className={`badge ${to.toLowerCase()}`}>{to}</span> (original kept)</p>}
    {event.type==='ai_assessment'&&<p className="ai-event"><span className="ai-tag">AI-generated</span>{rejection?<small className="bad">Rejected by {rejection.actor}: {(rejection.note||'').replace(/^Rejected AI assessment: /,'')}</small>:<button className="link-button" onClick={()=>void reject()}>Reject this assessment</button>}</p>}
    {typeof d.action==='string'&&<small>Action: {label(d.action)}{d.recommendation?' (recommendation only)':''}{d.new_case_id?` · moved to ${d.new_case_id}`:''}{d.from_case_id?` · split from ${d.from_case_id}`:''}</small>}
    {msg&&<small className="bad">{msg}</small>}
  </>;
}
const ACTIONS:{id:string;name:string;recommendation?:boolean;needsReason?:boolean}[] = [
  {id:'confirm',name:'Confirm needs investigation'},{id:'false_positive',name:'False positive',needsReason:true},
  {id:'request_info',name:'Request information'},{id:'escalate',name:'Escalate to specialist'},
  {id:'recommend_hold',name:'Recommend temporary hold',recommendation:true},{id:'recommend_verification',name:'Recommend enhanced verification',recommendation:true},
  {id:'conclude',name:'Record conclusion'},{id:'reclassify',name:'Reclassify risk'},
];

function download(name:string, text:string, type:string) {
  const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);
}
function localReport(c:Case, priority:Priority[], memory:Memory[], incident?:Incident) {
  return {generated_at:new Date().toISOString(),generated_by:'FinShield workspace (browser)',case:{...c,alerts:undefined,events:undefined},
    alerts:(c.alerts||[]).map(a=>({alert_id:a.alert_id,run:a.detection_run_id,score:a.score,band:a.band,category:a.category,narrative:a.narrative,indicators:a.contributions,evidence:a.evidence})),
    investigation:incident?{incident_id:incident.incident_id,grouping_reason:incident.reason,alert_ids:incident.alert_ids,entities:incident.entities}:null,
    case_priority:incident?.priority||null,alert_priority:priority.filter(p=>c.alert_ids.includes(p.alert_id)),audit_trail:c.events||[],earlier_reviewers:memory};
}

export function CaseLevel2({detail, actor, note, onSaved}:{detail:Case;actor:string;note:string;onSaved:(c:Case,msg:string)=>void}) {
  const [priority,setPriority]=useState<Priority[]>([]); const [memory,setMemory]=useState<Memory[]>([]); const [incidents,setIncidents]=useState<Incident[]>([]);
  const [split,setSplit]=useState<string[]>([]); const [band,setBand]=useState(''); const [outcome,setOutcome]=useState('Closed'); const [busy,setBusy]=useState(false); const [msg,setMsg]=useState('');
  const id=encodeURIComponent(detail.case_id);
  useEffect(()=>{api<{items:Priority[]}>('/priority').then(r=>setPriority(r.items)).catch(()=>setPriority([]));void loadIncidents().then(setIncidents);
    api<{items:Memory[]}>(`/assistant/memory?case_id=${id}${detail.customer_id?`&entity_id=${encodeURIComponent(detail.customer_id)}`:''}`).then(r=>setMemory(r.items)).catch(()=>setMemory([]))},[detail.case_id]);
  const mine=priority.filter(p=>detail.alert_ids.includes(p.alert_id));
  const incident=incidentFor(detail,incidents); const cp=casePriority(detail,incidents); const outside=incident?incident.alert_ids.filter(a=>!detail.alert_ids.includes(a)):[];
  const reason=detail.grouping_reason||incident?.reason;
  const latest=new Map<string,Alert>(); (detail.alerts||[]).forEach(a=>latest.set(a.alert_id,a));
  async function act(action:typeof ACTIONS[number]){setMsg('');
    if(!actor.trim()||!note.trim()){setMsg('Enter a reviewer and a note (the reason) before recording an action.');return}
    if(action.id==='reclassify'&&!band){setMsg('Choose the new risk level to reclassify to.');return}
    setBusy(true);try{await api(`/cases/${id}/actions`,post({action:action.id,note:note.trim(),actor:actor.trim(),...(action.id==='reclassify'?{band}:{}),...(action.id==='conclude'?{outcome}:{})}));const saved=await api<Case>(`/cases/${id}`);onSaved(saved,`${action.name} recorded${action.recommendation?' as a recommendation (no account action executed)':''}.`)}
    catch(e){setMsg(`${action.name} was not recorded: ${e instanceof Error?e.message:String(e)}`)}finally{setBusy(false)}}
  async function doSplit(){setMsg('');if(!split.length||!note.trim()){setMsg('Select the alerts to separate and give a reason in the note.');return}
    setBusy(true);try{const r=await api<Case>(`/cases/${id}/split`,post({alert_ids:split,reason:note.trim(),actor:actor.trim()}));const saved=await api<Case>(`/cases/${id}`);setSplit([]);onSaved(saved,`Split into ${r.case_id||'a new case'}. Original alerts kept on both.`)}
    catch(e){setMsg(`Split not recorded: ${e instanceof Error?e.message:String(e)}`)}finally{setBusy(false)}}
  async function report(format:'json'|'markdown'='json'){setMsg('');
    try{if(format==='markdown'){download(`${detail.case_id}-report.md`,await apiText(`/cases/${id}/report?format=markdown`),'text/markdown');return}
      const r=await api<unknown>(`/cases/${id}/report`);download(`${detail.case_id}-report.json`,JSON.stringify(r,null,2),'application/json')}
    catch{download(`${detail.case_id}-report.json`,JSON.stringify(localReport(detail,priority,memory,incident),null,2),'application/json');setMsg('Report API unavailable: downloaded a report built from the case data on screen.')}}
  return <section className="level2">
    <h3>Priority</h3><p className="muted">Evidence strength is how many independent facts agree, not a probability of fraud.</p>{cp?<div className={`priority ${cp.needs_review?'review':''}`}><b>{cp.priority}</b><div><span>{detail.alert_ids.length} alert{detail.alert_ids.length===1?'':'s'} · evidence {cp.evidence_strength}{cp.needs_review&&' · needs further review, not top priority'}</span><small>{cp.factors.join(' · ')}</small></div></div>:mine.length?mine.map(p=><div className={`priority ${p.needs_review?'review':''}`} key={p.alert_id}><b>{p.priority}</b><div><span>{p.alert_id} · evidence {strength(p)}{p.needs_review&&' · needs further review'}</span><small>{p.factors.map(f=>f.replace(/^confidence (\w+)/,(_,c:string)=>`evidence ${STRENGTH[c]||c}`)).join(' · ')}</small></div></div>):<p className="muted">No priority computed for this case's alerts in the latest run.</p>}
    {detail.system_band&&detail.system_band!==detail.band&&<p className="reclass">Risk: detector said <span className={`badge ${detail.system_band.toLowerCase()}`}>{detail.system_band}</span>, analyst set <span className={`badge ${detail.band.toLowerCase()}`}>{detail.band}</span>. The original is kept.</p>}
    {reason&&<><h3>Why these alerts are grouped</h3><p className="grouping">{reason}</p></>}
    {outside.length>0&&<p className="muted">Also in this investigation (other cases until the case store consolidates them): {outside.join(', ')}</p>}
    {(detail.alert_ids.length>1)&&<><h3>Grouped alerts</h3><p className="muted">Select any alert that does not belong, add a reason in the note, then split. The original alerts are kept.</p>
      {detail.alert_ids.map(a=><label className="check" key={a}><input type="checkbox" checked={split.includes(a)} onChange={e=>setSplit(s=>e.target.checked?[...s,a]:s.filter(x=>x!==a))}/>{a}{latest.get(a)&&<small> · {label(latest.get(a)!.category)} · {latest.get(a)!.band}</small>}</label>)}
      <button disabled={busy||!split.length} onClick={()=>void doSplit()}><Scissors size={15}/>Split selected into a new case</button></>}
    <h3>Analyst actions</h3><p className="muted">Uses the reviewer and note above. Holds and verification are recorded as recommendations only; nothing changes an account or payment without an authorised workflow.</p>
    <label className="reclassify">Reclassify to<select aria-label="New risk level" value={band} onChange={e=>setBand(e.target.value)}><option value="">Choose…</option>{['Low','Medium','High'].filter(b=>b!==detail.band).map(b=><option key={b}>{b}</option>)}</select><small>Original {detail.system_band||detail.band} is kept with your reason.</small></label><label className="reclassify">Conclusion outcome<select aria-label="Conclusion outcome" value={outcome} onChange={e=>setOutcome(e.target.value)}><option>Closed</option><option>Confirmed Fraud</option></select></label><div className="decision-buttons actions">{ACTIONS.map(a=><button key={a.id} disabled={busy} onClick={()=>void act(a)}>{a.name}{a.recommendation&&<small> (recommendation)</small>}</button>)}</div>
    <div className="report-buttons"><button onClick={()=>void report()}><Download size={15}/>Download case report (JSON)</button><button onClick={()=>void report('markdown')}><Download size={15}/>Markdown</button></div>
    {msg&&<p className="warning" role="status">{msg}</p>}
    <h3>What earlier reviewers found</h3>{memory.length?memory.map((m,i)=><article className="history" key={i}><b>{m.case_id} · {m.from||'Created'} → {m.to}{m.type&&m.type!=='decision'?` · ${label(m.type)}`:''}</b><small>{new Date(m.at.endsWith('Z')?m.at:m.at+'Z').toLocaleString()} · {m.actor}</small><p>{m.note}</p></article>):<p className="muted">No earlier reviewer notes on this case or on cases sharing its customer.</p>}
  </section>;
}
