'use strict';
const $ = id => document.getElementById(id);
const colors = {fixed:'#6d768b', po:'#b36b00', inc:'#087f78'};
const names = {fixed:'Fixed voltage', po:'Perturb & Observe', inc:'Incremental Conductance'};
const state = {manifest:null,summary:[],run:null,curves:null,frame:128,signal:'p',curve:'pv',visible:new Set(['fixed','po','inc']),playing:false,timer:null,request:0};
const fmt = (v,d=2) => v == null ? 'N/A' : Number(v).toFixed(d);
const escapeText = text => String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function getJSON(path){const response=await fetch(path);if(!response.ok)throw new Error(`Could not load ${path} (${response.status})`);return response.json();}
function stop(){state.playing=false;clearInterval(state.timer);$('play').textContent='▶';$('play').setAttribute('aria-label','Play recorded experiment');}
function currentConfig(){return `step${$('step').value}-sample${$('sample').value}`;}
async function loadRun(){
  stop();const request=++state.request;const scenario=$('scenario').value;
  $('status').textContent='Loading recorded configuration…';$('play').disabled=$('reset').disabled=$('download').disabled=$('timeline').disabled=true;
  try{
    const [run,curves]=await Promise.all([getJSON(`data/runs/${scenario}-${currentConfig()}.json`),getJSON(`data/curves/${scenario}.json`)]);
    if(request!==state.request)return;
    state.run=run;state.curves=curves;
    $('scenario-description').textContent=run.scenario.description;
    $('seed').textContent=`SEED ${run.scenario.seed} · ${run.config.slew_v_per_s} V/s ACTUATOR`;
    $('download-json').href=`data/runs/${scenario}-${currentConfig()}.json`;
    $('status').textContent='';$('play').disabled=$('reset').disabled=$('download').disabled=$('timeline').disabled=false;
    renderMetrics();renderSweep();render();
  }catch(error){if(request!==state.request)return;$('status').textContent=`${error.message}. Serve the built dist folder over HTTP; see README.`;console.error(error);}
}
function renderMetrics(){
  const r=state.run;
  $('metrics').innerHTML=Object.entries(r.controllers).map(([key,c])=>{
    const m=c.metrics;let result=key==='fixed'?'BASELINE':'TRACKING';
    return `<article class="metric-card" style="--controller-color:${colors[key]}"><div class="metric-name"><span class="dot"></span>${names[key]}<span class="tag">${result}</span></div><div class="metric-main">${fmt(m.tracking_pct)}<small> %</small></div><div class="metric-description">energy tracking efficiency · full run</div><div class="metric-bottom"><span>Harvested <b>${fmt(m.harvested_wh,3)} Wh</b></span><span>Available <b>${fmt(m.available_wh,3)} Wh</b></span></div></article>`;
  }).join('');
}
function plotSVG({x,lines,maxX,maxY,labelX,labelY,cursor=null,points=[],title,id}){
  const W=id==='curve-plot'?420:660,H=300,L=53,R=16,T=29,B=39,pw=W-L-R,ph=H-T-B;
  maxY=Math.max(maxY,1e-5);
  const sx=v=>L+v/maxX*pw, sy=v=>T+ph-v/maxY*ph;
  let grid='';
  for(let k=0;k<=4;k++){let y=maxY*k/4;grid+=`<line x1="${L}" x2="${W-R}" y1="${sy(y)}" y2="${sy(y)}" stroke="#e9edf1"/><text x="${L-9}" y="${sy(y)+4}" text-anchor="end">${fmt(y,maxY<5?1:0)}</text>`;}
  for(let k=0;k<=4;k++){let v=maxX*k/4;grid+=`<text x="${sx(v)}" y="${H-19}" text-anchor="middle">${fmt(v,maxX<10?1:0)}</text>`;}
  const paths=lines.map(line=>`<path d="${line.y.map((v,k)=>`${k?'L':'M'}${sx(x[k]).toFixed(2)},${sy(v).toFixed(2)}`).join(' ')}" fill="none" stroke="${line.color}" stroke-width="${line.width||1.8}" ${line.dash?'stroke-dasharray="5 4"':''} vector-effect="non-scaling-stroke"/>`).join('');
  const marks=points.map(p=>`<circle cx="${sx(p.x)}" cy="${sy(p.y)}" r="${p.oracle?5:5.5}" fill="${p.oracle?'#fff':p.color}" stroke="${p.color}" stroke-width="2"><title>${escapeText(p.name)}: ${fmt(p.x)} V, ${fmt(p.y)} ${state.curve==='iv'?'A':'W'}</title></circle>`).join('');
  const marker=cursor==null?'':`<line x1="${sx(cursor)}" x2="${sx(cursor)}" y1="${T-3}" y2="${H-B+1}" stroke="#8e98a4" stroke-width="1" stroke-dasharray="3 4"/><circle cx="${sx(cursor)}" cy="${H-B}" r="3" fill="#3a4c5b"/>`;
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="${id}-title ${id}-desc"><title id="${id}-title">${escapeText(title)}</title><desc id="${id}-desc">${escapeText(labelY)} plotted against ${escapeText(labelX)}. Exact values are available in the electrical values table and CSV download.</desc><g fill="#657383" font-size="10" font-family="ui-monospace,monospace">${grid}<text x="${L}" y="13" font-size="10">${escapeText(labelY)}</text><text x="${W-R}" y="${H-3}" text-anchor="end" font-size="9">${escapeText(labelX)}</text></g>${paths}${marker}${marks}</svg>`;
}
function renderTimeline(k){
  const r=state.run,signal=state.signal;
  const titles={p:['Power (W)','True panel power'],v:['Voltage (V)','True panel voltage'],g:['Irradiance (W/m²)','Effective irradiance'],tc:['Cell temperature (°C)','Cell temperature'],energy_wh:['Energy (Wh)','Cumulative harvested energy']};
  let lines=[];
  if(signal==='g'||signal==='tc'){lines=[{y:signal==='g'?r.irradiance_w_m2:r.cell_temperature_c,color:'#4d748b'}];}
  else{
    const oracleKey={p:'oracle_w',v:'oracle_v',energy_wh:'oracle_energy_wh'}[signal];
    lines.push({y:r[oracleKey],color:'#a7b0ba',dash:true,width:1.3});
    for(const key of state.visible)lines.push({y:r.controllers[key].series[signal],color:colors[key]});
  }
  const maxY=Math.max(...lines.flatMap(line=>line.y))*1.12;
  $('timeline-chart').innerHTML=plotSVG({x:r.time_s,lines,maxX:60,maxY,labelX:'Time (s)',labelY:titles[signal][0],cursor:r.time_s[k],title:titles[signal][1]+' over the recorded experiment',id:'timeline-plot'});
}
function renderCurve(k){
  const r=state.run,frame=state.curves.frames[state.frame],x=state.curves.voltage_v;
  const isPower=state.curve==='pv',y=isPower?frame.i_a.map((i,j)=>i*x[j]):frame.i_a;
  const points=[{x:r.oracle_v[k],y:isPower?r.oracle_w[k]:r.oracle_w[k]/Math.max(r.oracle_v[k],1e-20),color:'#8895a1',oracle:true,name:'Oracle MPP'}];
  for(const name of state.visible){const s=r.controllers[name].series;points.push({x:s.v[k],y:isPower?s.p[k]:s.i[k],color:colors[name],name:names[name]});}
  $('curve-chart').innerHTML=plotSVG({x,lines:[{y,color:'#bcc9cc',width:2}],maxX:50,maxY:Math.max(...y)*1.15,labelX:'Voltage (V)',labelY:isPower?'Power (W)':'Current (A)',points,title:isPower?'Panel power versus voltage at selected time':'Panel current versus voltage at selected time',id:'curve-plot'});
  $('current-g').innerHTML=`${fmt(r.irradiance_w_m2[k],0)} <small>W/m²</small>`;
  $('current-t').innerHTML=`${fmt(r.cell_temperature_c[k],1)} <small>°C</small>`;
  $('curve-time').textContent=`${fmt(r.time_s[k])} s`;
}
function renderDecisions(k){
  const r=state.run;
  $('decisions').innerHTML=Object.entries(r.controllers).map(([name,c])=>{
    const s=c.series,d=c.decisions[s.decision_index[k]];
    return `<article class="decision" style="--controller-color:${colors[name]}"><h3><span class="dot"></span>${names[name]}</h3><p>${escapeText(d.reason)}.</p><span class="mono">SAMPLE ${fmt(d.time_s)} s → TARGET ${fmt(d.target_v)} V</span></article>`;
  }).join('');
  $('snapshot').innerHTML=Object.entries(r.controllers).map(([name,c])=>{const s=c.series;return `<tr><th scope="row">${names[name]}</th>${['v','i','p','sensor_v','sensor_i'].map(key=>`<td>${fmt(s[key][k],4)}</td>`).join('')}</tr>`;}).join('');
  $('snapshot-caption').textContent=`True electrical values at ${fmt(r.time_s[k])} s. Sensor values held from each controller's latest sample shown above.`;
}
function render(){if(!state.run)return;const k=Math.round(state.frame*.25/state.run.config.dt_s);$('timeline').value=state.frame;$('timeline').setAttribute('aria-valuetext',`${fmt(state.frame*.25)} seconds`);$('clock').innerHTML=`${fmt(state.frame*.25)} <span>/ 60.00 s</span>`;renderTimeline(k);renderCurve(k);renderDecisions(k);}
function renderSweep(){
  if(!state.run)return;
  const ctrl=$('sweep-controller').value,scenario=state.run.scenario.id;
  const rows=state.summary.filter(r=>r.scenario===scenario&&r.controller===ctrl);
  const get=(step,sample)=>rows.find(r=>r.step_v===step&&r.sample_s===sample);
  $('sweep-table').innerHTML=`<table><caption>Energy tracking efficiency (%) · ${names[ctrl]} · ${escapeText(state.run.scenario.name)}</caption><thead><tr><th scope="col">Step / sample</th>${[.1,.25,.5].map(s=>`<th scope="col">${fmt(s)} s</th>`).join('')}</tr></thead><tbody>${[.2,.6,1.2].map(step=>`<tr><th scope="row">${fmt(step,1)} V</th>${[.1,.25,.5].map(sample=>{const m=get(step,sample);return `<td><button class="sweep-cell" data-step="${step}" data-sample="${sample}" aria-pressed="${m.config_id===currentConfig()}" aria-label="Load ${step} V step, ${sample} s sampling, ${fmt(m.tracking_pct)} percent efficiency">${fmt(m.tracking_pct)}%</button></td>`;}).join('')}</tr>`).join('')}</tbody></table>`;
  const best=rows.reduce((a,b)=>a.tracking_pct>b.tracking_pct?a:b),worst=rows.reduce((a,b)=>a.tracking_pct<b.tracking_pct?a:b);
  const selected=rows.find(r=>r.config_id===currentConfig());
  let metric=selected.steady_ripple_pp_w==null?'A steady-state ripple metric is undefined for this continuously changing profile.':`Selected steady-window power ripple: ${fmt(selected.steady_ripple_pp_w)} W peak-to-peak (including any residual drift).`;
  const changes=selected.settling.filter(e=>e.event_s>0);
  if(changes.length)metric+=` Recovery after ${changes.map(e=>`${fmt(e.event_s,0)} s: ${e.settling_s==null?'not settled':fmt(e.settling_s)+' s'}`).join('; ')}. Criterion: ≥98% of oracle for 2 s.`;
  $('sweep-finding').textContent=`${names[ctrl]} ranges from ${fmt(worst.tracking_pct)}% to ${fmt(best.tracking_pct)}% here. Best recorded setting: ${best.step_v} V every ${best.sample_s} s. ${metric}`;
  $('sweep-table').querySelectorAll('button').forEach(button=>button.addEventListener('click',()=>{$('step').value=button.dataset.step;$('sample').value=button.dataset.sample;loadRun();}));
}
function downloadCSV(){
  const r=state.run;const header=['controller','time_s','irradiance_w_m2','cell_temperature_c','oracle_v','oracle_w','oracle_energy_wh','voltage_v','current_a','power_w','energy_wh','target_v','sensor_v','sensor_i','sampled','decision'];
  const csv=[header.join(',')];
  const quote=v=>'"'+String(v).replaceAll('"','""')+'"';
  for(const [key,c] of Object.entries(r.controllers)){const s=c.series;for(let k=0;k<r.time_s.length;k++)csv.push([key,r.time_s[k],r.irradiance_w_m2[k],r.cell_temperature_c[k],r.oracle_v[k],r.oracle_w[k],r.oracle_energy_wh[k],s.v[k],s.i[k],s.p[k],s.energy_wh[k],s.target_v[k],s.sensor_v[k],s.sensor_i[k],s.sampled[k],quote(c.decisions[s.decision_index[k]].reason)].join(','));}
  const url=URL.createObjectURL(new Blob([csv.join('\n')+'\n'],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download=`${r.scenario.id}-${currentConfig()}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function init(){
  try{
    [state.manifest,state.summary]=await Promise.all([getJSON('data/manifest.json'),getJSON('data/summary.json')]);
    $('scenario').innerHTML=state.manifest.scenarios.map(s=>`<option value="${s.id}">${escapeText(s.name)}</option>`).join('');$('scenario').value='drop';
    $('verification-error').textContent=state.manifest.verification.max_current_abs_error_a.toExponential(2);
    $('legend').innerHTML=Object.keys(names).map(key=>`<label style="--controller-color:${colors[key]}"><input type="checkbox" data-controller="${key}" checked><span class="dot"></span>${names[key]}</label>`).join('')+'<span class="oracle-legend">Oracle</span>';
    $('legend').querySelectorAll('input').forEach(input=>input.addEventListener('change',()=>{if(input.checked)state.visible.add(input.dataset.controller);else state.visible.delete(input.dataset.controller);render();}));
    for(const id of ['scenario','step','sample'])$(id).addEventListener('change',loadRun);
    $('sweep-controller').addEventListener('change',renderSweep);
    document.querySelectorAll('[data-signal]').forEach(button=>button.addEventListener('click',()=>{state.signal=button.dataset.signal;document.querySelectorAll('[data-signal]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();}));
    document.querySelectorAll('[data-curve]').forEach(button=>button.addEventListener('click',()=>{state.curve=button.dataset.curve;document.querySelectorAll('[data-curve]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();}));
    $('timeline').addEventListener('input',()=>{stop();state.frame=Number($('timeline').value);render();});
    $('play').addEventListener('click',()=>{if(state.playing){stop();return;}if(state.frame===240)state.frame=0;state.playing=true;$('play').textContent='Ⅱ';$('play').setAttribute('aria-label','Pause recorded experiment');let last=performance.now(),fraction=state.frame;state.timer=setInterval(()=>{const now=performance.now();fraction+=(now-last)/1000*Number($('speed').value)/.25;last=now;state.frame=Math.min(240,Math.floor(fraction));render();if(state.frame===240)stop();},100);});
    $('reset').addEventListener('click',()=>{stop();state.frame=0;render();});
    $('download').addEventListener('click',downloadCSV);
    await loadRun();
  }catch(error){$('status').textContent='Experiment data could not be loaded. Run the generation and build commands in the README, then serve dist over HTTP.';console.error(error);}
}
init();
