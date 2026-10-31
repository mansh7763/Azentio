import {BrainCircuit} from 'lucide-react';

type Shadow = {ml_score?:number|null; ml_band?:string|null; ml_factors?:{rule:string;effect:number}[]};

/** ML shadow score: the learned model's view of the same rule evidence. Shown for comparison only; the rule score
 * above stays the official result and drives the band and the case. */
export function MlScore({alert:source}:{alert:object}) {
  const alert = source as Shadow; // optional fields added by the engine; older runs lack them
  if (alert.ml_score == null) return <p className="muted">ML shadow score not available for this run (scored before the model was installed). Run detection to compute it.</p>;
  const factors = alert.ml_factors || [];
  return <section className="ml-shadow" aria-label="ML shadow score" style={{border:"1px dashed #c9d3c2",borderRadius:8,padding:"12px 14px",margin:"14px 0",background:"#fbfcf9"}}>
    <div className="ml-head" style={{display:"flex",alignItems:"center",gap:10,fontSize:13}}><BrainCircuit size={18}/><b>ML shadow score</b><span className="ml-value" style={{marginLeft:"auto",fontSize:22,fontWeight:700}}>{alert.ml_score}<small>/ 100</small></span><span className={`badge ${(alert.ml_band||'').toLowerCase()}`}>{alert.ml_band}</span></div>
    <p className="muted">A classifier trained on labelled synthetic scenarios re-weighs the same rule evidence. Shown for comparison only: it does not change the risk level, the case or any decision.</p>
    {factors.length>0&&<div className="tags">{factors.map(f=><span key={f.rule}>{f.rule} <b>{f.effect>0?'+':''}{f.effect.toFixed(2)}</b></span>)}</div>}
  </section>;
}
