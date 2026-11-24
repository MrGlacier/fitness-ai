/* No external chart library or third-party data transfer. */
(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    let data, catalog = {preparations: []};
    const labels = {sessions:'Einheiten', duration_sec:'Trainingsdauer', distance_m:'Distanz', tss:'Trainingsbelastung', avg_watts:'Ø Leistung je Einheit', np_watts:'Ø Normalized Power je Einheit', avg_hr:'Ø Herzfrequenz je Einheit', ftp:'Gespeicherte Aktivitäts-FTP', rpe:'Ø subjektive Belastung', lthr:'Gespeicherte Schwellen-HF', threshold_speed_mps:'Gespeicherte Schwellengeschwindigkeit', w_per_kg:'Gespeicherte FTP / Gewicht', ctl:'Ø Fitness', atl:'Ø Fatigue', tsb:'Ø Form (CTL − ATL)', hrv:'Ø HRV', resting_hr:'Ø Ruhepuls', weight:'Ø Gewicht', vo2max:'Ø VO₂max', run_pace:'Ø Laufpace je Einheit', swim_pace:'Ø Schwimmpace je Einheit', active_days:'Trainingstage', sessions_per_week:'Häufigkeit', lit_hit:'LIT-/HIT-Verteilung'};
    const el = (tag, text, className) => {const n = document.createElement(tag); if(text !== undefined) n.textContent = text; if(className) n.className = className; return n;};
    const iso = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    const shift = (s, days) => {const d = new Date(`${s}T12:00:00`); d.setDate(d.getDate()+days); return iso(d);};
    const num = n => Number.isFinite(n) ? n.toLocaleString('de-DE',{maximumFractionDigits:2}) : '—';
    function format(key, value, unit='') {
        if(!Number.isFinite(value)) return 'Nicht verfügbar';
        if(key==='duration_sec') return `${num(value/3600)} h`;
        if(key==='distance_m') return `${num(value/1000)} km`;
        return `${num(value)} ${unit}`.trim();
    }
    async function api(path, method='GET', body) {
        const r = await fetch(`/dashboard/history/${path}`, {method, headers:{'Content-Type':'application/json'}, ...(body ? {body:JSON.stringify(body)} : {})});
        const result = await r.json();
        if(!r.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Eingaben prüfen oder später erneut versuchen.');
        return result;
    }
    function options(select, rows, first) {
        const prior = select.value; select.replaceChildren();
        if(first) {const o=el('option',first);o.value='';select.append(o);}
        rows.forEach(([value,text])=>{const o=el('option',text);o.value=value;select.append(o);});
        if([...select.options].some(o=>o.value===prior)) select.value=prior;
    }
    async function loadCatalog() {
        catalog = await api('catalog');
        for(const k of ['a','b']) {options($(`prep-${k}`), catalog.preparations.map(p=>[p.id,p.name]), 'Zeitraum frei wählen');options($(`race-choice-${k}`),(catalog.races||[]).map(r=>[r.date,`${r.date} · ${r.name}`]),'Datum manuell eingeben');}
    }
    const today = new Date(), monday = shift(iso(today), -(today.getDay()+6)%7);
    $('start-a').value='2023-12-18'; $('end-a').value='2023-12-24';
    $('start-b').value=monday; $('end-b').value=iso(today);
    for(const k of ['a','b']) {
        $(`race-choice-${k}`).addEventListener('change',()=>{if($(`race-choice-${k}`).value)$(`race-${k}`).value=$(`race-choice-${k}`).value;});
        $(`prep-${k}`).addEventListener('change',()=>{
            const p=catalog.preparations.find(p=>p.id===$(`prep-${k}`).value); if(!p)return;
            $(`start-${k}`).value=p.start;$(`end-${k}`).value=p.end;$(`race-${k}`).value=p.race_date || '';
        });
        $(`phase-${k}`).addEventListener('change',()=>{
            const [start,end] = $(`phase-${k}`).value.split('|'); if(!start || !end)return;
            $(`start-${k}`).value=start;$(`end-${k}`).value=end;
        });
    }
    $('last-six').addEventListener('click',()=>{$('start-b').value=shift(monday,-42);$('end-b').value=shift(monday,-1);});
    $('align-race').addEventListener('click',()=>{
        const weeks=Number($('weeks-before').value), count=Number($('week-count').value);
        if(!Number.isInteger(weeks)||weeks<1||weeks>80||!Number.isInteger(count)||count<1||count>52 || !['a','b'].every(k=>$(`race-${k}`).value)) { $('compare-status').textContent='Bitte beide bestätigten Wettkampftermine und gültige Wochenangaben eintragen.';return; }
        for(const k of ['a','b']) {const start=shift($(`race-${k}`).value,-7*weeks);$(`start-${k}`).value=start;$(`end-${k}`).value=shift(start,7*count-1);}
        $('compare-status').textContent='Zeiträume ausgerichtet. Jetzt Vergleich laden.';
    });
    $('compare-form').addEventListener('submit',async event=>{
        event.preventDefault();const button=event.submitter;button.disabled=true;$('compare-status').textContent='Historische Daten werden geladen …';
        try {
            const payload={sport:$('sport').value};for(const k of ['a','b'])payload[k]={start:$(`start-${k}`).value,end:$(`end-${k}`).value,race_date:$(`race-${k}`).value||null};
            data=await api('compare','POST',payload);render();$('compare-status').textContent='Vergleich geladen. Fehlende Werte und Quellenfehler sind gekennzeichnet.';
        } catch(error) {$('compare-status').textContent=error.message;} finally {button.disabled=false;}
    });
    function render() {
        $('results').hidden=false;$('pair-result').replaceChildren();$('pair-status').textContent='';
        const errors=['a','b'].flatMap(k=>data[k].sources.filter(s=>['unavailable','stale'].includes(s.status)).map(s=>`${k.toUpperCase()}: ${s.source} ${s.month.slice(0,7)} ${s.http_status===429?'(Rate-Limit)':''}`));
        $('quality').textContent=[data.unequal_days?'Die Zeiträume sind unterschiedlich lang. Gesamtsummen sind dadurch eingeschränkt vergleichbar.':'', errors.length?`Quellen unvollständig: ${errors.join(' · ')}. Betroffene Kennzahlen bleiben nicht verfügbar.`:''].filter(Boolean).join(' ');
        $('headline-metrics').replaceChildren();$('metric-rows').replaceChildren();
        for(const [key,label] of Object.entries(labels)) {
            const a=data.a.metrics[key],b=data.b.metrics[key],d=data.differences[key];
            const row=el('tr');row.append(el('th',label));
            for(const m of [a,b]) {const cell=el('td',format(key,m.value,m.unit));if(m.expected!==undefined)cell.append(el('small',`${m.known ?? m.value ?? 0} / ${m.expected} ${['ctl','atl','tsb','hrv','resting_hr','weight','vo2max'].includes(key)?'Tage':'Beobachtungen'}`));row.append(cell);}
            row.append(el('td',format(key,d.absolute,a.unit)),el('td',d.percent===null?'—':`${d.percent>0?'+':''}${num(d.percent)} %`));$('metric-rows').append(row);
            if(['duration_sec','sessions','tss','active_days'].includes(key)) {const card=el('article',undefined,'history-kpi');card.append(el('span',label,'muted'),el('strong',format(key,b.value,b.unit)),el('small',`A: ${format(key,a.value,a.unit)} · Δ ${d.percent===null?'—':num(d.percent)+' %'}`));$('headline-metrics').append(card);}
        }
        for(const k of ['a','b']) {
            const knownRaces=[...(catalog.races||[]),...data[k].planned.filter(r=>r.category?.startsWith('RACE_'))];
            options($(`race-choice-${k}`),knownRaces.map(r=>[r.date,`${r.date} · ${r.name}`]),'Datum manuell eingeben');
            const phases=[];
            for(const p of data[k].phases) {
                phases.push([`${p.start}|${p.end}`,`${p.phase} · beobachtet ${p.start} – ${p.end} (Vorschlag)`]);
                for(const w of p.weeks) {const start=shift(p.anchor,7*(w-1));phases.push([`${start}|${shift(start,6)}`,`${p.phase} Woche ${w} (Titelhinweis)`]);}
            }
            options($(`phase-${k}`),phases,'Phase / Woche auswählen');
            options($(`session-${k}`),data[k].activities.map(r=>[r.id,`${r.date} · ${r.name}`]));
        }
        $('pair-suggestions').replaceChildren();
        const suggestions=data.pairs.slice(0,6);
        if(!suggestions.length)$('pair-suggestions').append(el('p','Keine ausreichend ähnlichen Einheiten erkannt. Eine manuelle Auswahl bleibt möglich.','helper'));
        for(const pair of suggestions) {const a=data.a.activities.find(r=>r.reference===pair.a),b=data.b.activities.find(r=>r.reference===pair.b);const button=el('button',`${a.date} ↔ ${b.date} · ${a.sport}`,'secondary');button.type='button';button.title=pair.evidence;button.addEventListener('click',()=>{$('session-a').value=a.id;$('session-b').value=b.id;$('load-pair').click();});$('pair-suggestions').append(button,document.createTextNode(' '));}
        renderActivities();draw();
        $('source-details').replaceChildren();for(const text of data.limitations)$('source-details').append(el('p',text,'helper'));
        for(const k of ['a','b']) for(const s of data[k].sources)$('source-details').append(el('p',`${k.toUpperCase()} · ${s.source} · ${s.month} · ${s.status} · abgerufen ${s.fetched_at||'nicht verfügbar'}`,'helper'));
    }
    function renderActivities() {
        const target=$('activity-lists');target.replaceChildren();
        for(const k of ['a','b']) {
            const details=el('details');details.append(el('summary',`Zeitraum ${k.toUpperCase()} · ${data[k].activity_source_complete?data[k].activities.length+' absolviert':'Ist-Quelle unvollständig'} · ${data[k].sources.some(s=>s.source==='calendar'&&['unavailable','stale'].includes(s.status))?'Planquelle unvollständig':data[k].planned.length+' geplant'}`));
            for(const row of [...data[k].activities,...data[k].planned]) {
                const item=el('article',undefined,'history-activity');item.append(el('strong',`${row.date} · ${row.name}`),el('p',`${row.source==='activity'?'Absolviert':'Geplant'} · ${row.sport} · ${row.reference}`,'helper'));
                const h=row.assignment;item.append(el('p',`${h.phase||'Phase unbekannt'}${h.week?' · Woche '+h.week:''} · ${h.reason}`,'helper'));
                if(row.description) {const description=el('details');description.append(el('summary','Beschreibung (Urheberschaft nicht bestätigt)'),el('p',row.description));item.append(description);}
                const editor=el('details');editor.append(el('summary','Zuordnung korrigieren'));
                const form=el('form',undefined,'comparison-actions');
                function field(text,node) {const label=el('label',text);label.append(node);form.append(label);return node;}
                const prep=field('Vorbereitung',el('select'));options(prep,catalog.preparations.map(p=>[p.id,p.name]),'Keine bestätigte Vorbereitung');prep.value=h.preparation_id||'';
                const phase=field('Phase',el('input'));phase.maxLength=80;phase.value=h.phase||'';
                const week=field('Woche',el('input'));week.type='number';week.min=1;week.max=80;week.value=h.week||'';
                const button=el('button','Zuordnung speichern');button.type='submit';form.append(button);const output=el('output');
                form.addEventListener('submit',async e=>{e.preventDefault();button.disabled=true;try {await api('assignment','PUT',{reference:row.reference,preparation_id:prep.value||null,phase:phase.value||null,week:week.value?Number(week.value):null});row.assignment={preparation_id:prep.value||null,phase:phase.value||null,week:week.value?Number(week.value):null,confidence:'manual',reason:'Manuell bestätigt/korrigiert.'};output.textContent='Manuelle Zuordnung gespeichert. Beim nächsten Vergleich wird sie berücksichtigt.';}catch(e){output.textContent=e.message;}finally{button.disabled=false;}});
                editor.append(form,output);item.append(editor);details.append(item);
            }
            target.append(details);
        }
    }
    function draw() {
        if(!data)return;
        const key=$('chart-metric').value,weekly=['duration_sec','tss'].includes(key),ns='http://www.w3.org/2000/svg';
        const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 900 280');svg.setAttribute('role','img');svg.setAttribute('aria-label',labels[key]+' beider Zeiträume');
        const pointSets=['a','b'].map(k=>{
            const p=data[k],points=weekly?p.weekly:p.wellness;
            return points.map(r=>{const day=r.start||r.date,origin=data.a.race_date&&data.b.race_date?p.race_date:p.start;return {day,value:r[key]===null?null:key==='duration_sec'?r[key]/3600:r[key],offset:(Date.parse(day)-Date.parse(origin))/86400000/(weekly?7:1)};});
        });
        const points=pointSets.flat(),valid=points.filter(p=>Number.isFinite(p.value));
        $('history-chart').replaceChildren(svg);if(!valid.length){$('chart-readout').textContent='Keine Verlaufswerte für diese Kennzahl verfügbar.';return;}
        const min=Math.min(0,...valid.map(p=>p.value)),max=Math.max(1,...valid.map(p=>p.value));const xmin=Math.min(...points.map(p=>p.offset)),xmax=Math.max(...points.map(p=>p.offset));
        const x=p=>55+(p.offset-xmin)/(xmax-xmin||1)*810,y=v=>230-(v-min)/(max-min||1)*200;
        function shape(tag,attrs,text) {const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;svg.append(n);return n;}
        for(let i=0;i<=4;i++){const v=min+(max-min)*i/4;shape('line',{x1:50,x2:875,y1:y(v),y2:y(v),stroke:'#293951'});shape('text',{x:3,y:y(v)+4,fill:'#a2b1c8','font-size':12},num(v));}
        pointSets.forEach((set,index)=>{let previous=null;const color=index?'#64dcb1':'#73a8ff';for(const p of set){if(!Number.isFinite(p.value)){previous=null;continue;}if(previous && p.offset-previous.offset<=(weekly?1.01:1.01))shape('line',{x1:x(previous),x2:x(p),y1:y(previous.value),y2:y(p.value),stroke:color,'stroke-width':2});
                const text=`Zeitraum ${index?'B':'A'} · ${p.day} · ${num(p.value)} ${key==='duration_sec'?'h':key}`;
                const circle=shape('circle',{cx:x(p),cy:y(p.value),r:4,fill:color,tabindex:0,'aria-label':text});circle.addEventListener('focus',()=>{$('chart-readout').textContent=text;});circle.addEventListener('pointerenter',()=>{$('chart-readout').textContent=text;});previous=p;}});
        shape('text',{x:55,y:270,fill:'#a2b1c8','font-size':12},`${num(xmin)} → ${num(xmax)} ${weekly?'Wochen':'Tage'} ${data.a.race_date&&data.b.race_date?'zum Wettkampf':'ab Zeitraumstart (je Reihe)'}`);
    }
    $('chart-metric').addEventListener('change',draw);
    $('load-pair').addEventListener('click',async()=>{
        if(!$('session-a').value||!$('session-b').value)return;
        $('load-pair').disabled=true;$('pair-status').textContent='Messwerte und Originalkommentare werden geladen …';
        try {
            const p=await api(`pair?${new URLSearchParams({a_id:$('session-a').value,b_id:$('session-b').value})}`);const target=$('pair-result');target.replaceChildren();
            target.append(el('p',p.comparability?p.comparability.evidence:'Keine ausreichende automatische Vergleichbarkeit belegt.','notice warning'));
            const grid=el('div',undefined,'history-pair-grid');
            for(const k of ['a','b']) {const col=el('div'),row=p[k],comments=p[`comments_${k}`];col.append(el('h3',`${k.toUpperCase()} · ${row.date} · ${row.name}`));
                col.append(el('p',`Dauer ${format('duration_sec',row.duration_sec)} · Leistung ${format('avg_watts',row.avg_watts,'W')} · Puls ${format('avg_hr',row.avg_hr,'bpm')} · RPE ${num(row.rpe)}`));
                const details=row.details||{};
                col.append(el('p',`Sensor / Gerät: ${details.device||row.device||'nicht verfügbar'} · Temperatur: ${num(details.average_temp)} °C · Indoor: ${details.trainer===true?'ja':details.trainer===false?'nein':'unbekannt'}`,'helper'));
                if(details.description) {const description=el('details');description.append(el('summary','Originalbeschreibung · Urheberschaft nicht bestätigt'),el('p',details.description));col.append(description);}
                if(details.intervals?.length) {const laps=el('details');laps.append(el('summary',`${details.intervals.length} Intervalle / Abschnitte`));for(const lap of details.intervals)laps.append(el('p',`${lap.index}. ${lap.label||lap.split_type||'Abschnitt'} · ${format('duration_sec',lap.duration_sec)} · ${num(lap.avg_watts)} W · ${num(lap.avg_hr)} bpm · ${num(lap.pace_sec_per_km)} s/km`,'helper'));col.append(laps);}
                for(const c of comments.comments) {const quote=el('blockquote',c.text);quote.append(el('small',`${c.personal?'Persönlicher Kommentar':'Andere / unbekannte Urheberschaft'} · ${c.created||'Datum fehlt'} · activity:${row.id} · ${c.topics.join(', ')}`));col.append(quote);}
                if(!comments.comments.length)col.append(el('p',comments.source.status==='unavailable'?'Kommentare nicht abrufbar.':'Keine Kommentare vorhanden.','helper'));
                if(comments.possibly_truncated)col.append(el('p','Kommentarabruf auf 100 Nachrichten begrenzt.','helper'));
                grid.append(col);
            }target.append(grid);
            for(const o of p.observations)target.append(el('p',`${labels[o.metric]||o.metric}: ${num(o.a)} → ${num(o.b)} · Δ ${num(o.absolute)}${o.percent===null?'':` (${num(o.percent)} %)`}`,'helper'));
            target.append(el('p',p.interpretation,'helper'));for(const limitation of p.insufficient_evidence)target.append(el('p',limitation,'helper'));
            const ask=el('button','Kommentare und Messwerte von KI einordnen');ask.type='button';const output=el('output');
            ask.addEventListener('click',async()=>{ask.disabled=true;output.textContent='Analyse läuft …';try{const answer=await api('explain','POST',{a_id:p.a.id,b_id:p.b.id});output.textContent=answer.answer;}catch(e){output.textContent=e.message;}finally{ask.disabled=false;}});target.append(ask,output);
            $('pair-status').textContent='Originaldaten geladen. Themenhinweise ersetzen keine semantische Interpretation.';
        }catch(e){$('pair-status').textContent=e.message;}finally{$('load-pair').disabled=false;}
    });
    $('preparation-form').addEventListener('submit',async e=>{
        e.preventDefault();const form=e.target,output=form.querySelector('output'),payload=Object.fromEntries(new FormData(form));payload.race_date ||= null;
        try{await api('preparation','PUT',payload);await loadCatalog();if(data)renderActivities();output.textContent='Vorbereitung gespeichert.';}catch(e){output.textContent=e.message;}
    });
    loadCatalog().catch(e=>{$('compare-status').textContent=e.message;});
})();
