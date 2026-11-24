(() => {
    const node = document.getElementById('analyst-data');
    if (!node) return;
    const data = JSON.parse(node.textContent);
    const canvas = document.getElementById('fitness-chart');
    function draw() {
        const history = data.fitness_history || [];
        const future = (data.fitness_forecast || {}).points || [];
        const all = [...history, ...future];
        const ctx = canvas.getContext('2d');
        const width = canvas.clientWidth || 600, height = 280;
        canvas.width = width * devicePixelRatio; canvas.height = height * devicePixelRatio;
        ctx.scale(devicePixelRatio, devicePixelRatio);
        if (!all.length) { ctx.fillText('Keine Verlaufsdaten verfügbar.', 20, 40); return; }
        const values = all.flatMap(p => [p.ctl, p.atl, p.tsb]).filter(Number.isFinite);
        if (!values.length) return;
        const min = Math.min(0, ...values) - 5, max = Math.max(...values) + 5;
        const begin = Date.parse(all[0].date), end = Date.parse(all.at(-1).date);
        const x = p => 45 + (Date.parse(p.date) - begin) / (end - begin || 1) * (width - 65);
        const y = v => 240 - (v - min) / (max - min) * 215;
        ctx.font = '14px sans-serif'; ctx.fillStyle = '#a2b1c8';
        for (let i = 0; i <= 4; i++) {
            const v = min + (max-min)*i/4;
            ctx.fillText(String(Math.round(v)), 2, y(v));
            ctx.strokeStyle = '#293951'; ctx.beginPath(); ctx.moveTo(40,y(v)); ctx.lineTo(width-15,y(v)); ctx.stroke();
        }
        for (const [key,color] of [['ctl','#73a8ff'],['atl','#ffb777'],['tsb','#64dcb1']]) {
            for (const [points,dash] of [[history,[]],[[...(history.length ? [history.at(-1)] : []),...future],[6,5]]]) {
                ctx.strokeStyle=color; ctx.setLineDash(dash); ctx.beginPath(); let started=false;
                for (const p of points) { if (!Number.isFinite(p[key])) { started=false; continue; }
                    if (!started) ctx.moveTo(x(p),y(p[key])); else ctx.lineTo(x(p),y(p[key])); started=true; }
                ctx.stroke();
            }
        }
        ctx.setLineDash([]); ctx.fillText(all[0].date, 40,270); ctx.fillText(all.at(-1).date,Math.max(40,width-110),270);
    }
    draw(); window.addEventListener('resize',draw);
    function drawPreparation() {
        document.querySelectorAll('.preparation-chart').forEach(chart => {
            const history = ((data.race_preparation || {})[chart.dataset.raceId] || {}).history || [];
            const ctx=chart.getContext('2d'), width=chart.clientWidth || 600, height=180;
            chart.width=width*devicePixelRatio; chart.height=height*devicePixelRatio;
            ctx.scale(devicePixelRatio,devicePixelRatio); ctx.font='14px sans-serif'; ctx.fillStyle='#a2b1c8';
            for (const v of [0,50,100]) {
                const y=150-v*1.2; ctx.fillText(String(v)+'%',0,y);
                ctx.strokeStyle='#293951'; ctx.beginPath(); ctx.moveTo(45,y); ctx.lineTo(width-15,y); ctx.stroke();
            }
            if (!history.length) { ctx.fillText('Noch kein Indexverlauf vorhanden.',50,85); return; }
            const start=Date.parse(history[0].day), end=Date.parse(history.at(-1).day);
            const x=p=>50+(Date.parse(p.day)-start)/(end-start || 1)*(width-75);
            ctx.strokeStyle='#73a8ff'; ctx.beginPath(); let previous=null;
            for (const p of history) {
                if (!Number.isFinite(p.score)) {previous=null;continue;}
                if (!previous || previous.model_version !== p.model_version) ctx.moveTo(x(p),150-p.score*1.2);
                else ctx.lineTo(x(p),150-p.score*1.2);
                previous=p;
            }
            ctx.stroke(); ctx.fillStyle='#73a8ff';
            for (const p of history) if (Number.isFinite(p.score)) { ctx.beginPath(); ctx.arc(x(p),150-p.score*1.2,3,0,Math.PI*2);ctx.fill(); }
            ctx.fillStyle='#a2b1c8'; ctx.fillText(history[0].day,45,175); ctx.fillText(history.at(-1).day,Math.max(45,width-110),175);
        });
    }
    drawPreparation(); window.addEventListener('resize',drawPreparation);
    document.querySelectorAll('details').forEach(details=>details.addEventListener('toggle',()=>{if(details.open) drawPreparation();}));
    function durationSeconds(text) {
        if (!text) return null;
        const [h,m,s]=text.split(':').map(Number);
        return h*3600+m*60+s;
    }
    function durationText(seconds) {
        if(seconds === null || seconds === undefined) return '';
        const value=Math.round(seconds);
        return `${Math.floor(value/3600)}:${String(Math.floor(value%3600/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`;
    }
    async function save(form,path,payload) {
        const output=form.querySelector('output'), button=form.querySelector('[type="submit"]');
        output.className=''; output.textContent='Wird gespeichert…'; button.disabled=true;
        try {
            const response=await fetch(path,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
            const result=await response.json();
            if (!response.ok) {
                const detail=result.detail;
                const reason=Array.isArray(detail) ? detail.map(e=>`${e.loc.at(-1)}: ${e.msg}`).join(' · ') : typeof detail==='string' ? detail : 'Bitte Eingaben prüfen.';
                throw new Error(reason);
            }
            output.className='success';
            if(path==='/dashboard/assignment') {
                const plan=result.plan || {};
                output.textContent='Planzuordnung gespeichert. '+(plan.message || 'Die Übersicht wird aktualisiert.');
                // Bestätigung bleibt beim Neuladen sichtbar und ist an die konkrete Speicherung gebunden.
                try {sessionStorage.setItem('fitness-assignment-feedback',output.textContent);} catch { /* Speicherung auf dem Server war trotzdem erfolgreich. */ }
            }
            location.reload();
        } catch (error) {
            output.className='error';
            output.textContent=`Nicht gespeichert: ${error.message || 'API nicht erreichbar.'}`;
        } finally {button.disabled=false;}
    }
    const raceForm=document.getElementById('race-form');
    raceForm.addEventListener('submit',event=>{
        event.preventDefault(); const fields=Object.fromEntries(new FormData(raceForm));
        const distances={}; for (const [field,sport] of [['swim','Swim'],['ride','Ride'],['run','Run']]) if(fields[field]) distances[sport]=Number(fields[field]);
        const payload={}; for(const key of ['id','source_id','name','date','sport','performance_goal','priority','status']) payload[key]=fields[key] || null;
        payload.target_seconds=durationSeconds(fields.target_time);
        payload.transition_seconds=fields.transition_minutes === '' ? null : Number(fields.transition_minutes)*60;
        const splits={}; for (const [field,sport] of [['split_swim_time','Swim'],['split_ride_time','Ride'],['split_run_time','Run']]) if(fields[field]) splits[sport]=durationSeconds(fields[field]);
        payload.goal_splits_seconds=splits;
        payload.distances_km=distances; save(raceForm,'/dashboard/races',payload);
    });
    document.querySelectorAll('.edit-race').forEach(button=>button.addEventListener('click',()=>{
        const race=JSON.parse(button.dataset.race); raceForm.reset();
        for(const [key,value] of Object.entries(race)) if(raceForm.elements.namedItem(key)) raceForm.elements.namedItem(key).value=value ?? '';
        for(const [key,sport] of [['swim','Swim'],['ride','Ride'],['run','Run']]) raceForm.elements.namedItem(key).value=race.distances_km[sport] ?? '';
        for(const [key,sport] of [['split_swim_time','Swim'],['split_ride_time','Ride'],['split_run_time','Run']]) raceForm.elements.namedItem(key).value=durationText((race.goal_splits_seconds || {})[sport]);
        raceForm.elements.namedItem('target_time').value=durationText(race.target_seconds);
        raceForm.elements.namedItem('transition_minutes').value=race.transition_seconds === null ? '' : race.transition_seconds/60;
        document.getElementById('race-settings').open=true;
        raceForm.scrollIntoView({behavior:'smooth'});
    }));
    const assignment=document.getElementById('assignment-form');
    let feedback=null;
    try {feedback=sessionStorage.getItem('fitness-assignment-feedback');} catch { /* Formular bleibt bei gesperrtem Webspeicher nutzbar. */ }
    if(feedback) {
        const output=assignment.querySelector('output'); output.className='success'; output.textContent=feedback;
        document.getElementById('plan-settings').open=true;
        try {sessionStorage.removeItem('fitness-assignment-feedback');} catch { /* Bestätigung ist bereits sichtbar. */ }
    }
    assignment.addEventListener('submit',event=>{
        event.preventDefault(); const payload=Object.fromEntries(new FormData(assignment));
        const output=assignment.querySelector('output');
        if(payload.end_date < payload.start_date) {output.className='error';output.textContent='Nicht gespeichert: Das Gültigkeitsende liegt vor dem Planstart.';return;}
        delete payload.current_week;
        save(assignment,'/dashboard/assignment',payload);
    });
    function suggestedDates(fromWeek) {
        const fields=assignment.elements;
        const selected=(data.available_plans || []).find(plan=>plan.id===fields.namedItem('plan_id').value);
        if(!selected) return;
        const total=selected.total_weeks || 1, current=fields.namedItem('current_week');
        current.max=String(total);
        if(fromWeek || !fields.namedItem('start_date').value) {
            if(!current.value) return;
            const week=Number(current.value);
            if(week < 1 || week > total) return;
            const today=new Date(`${data.date}T12:00:00Z`);
            if(!Number.isFinite(today.getTime())) return;
            const day=(today.getUTCDay()+6)%7;
            today.setUTCDate(today.getUTCDate()-day-(week-1)*7);
            fields.namedItem('start_date').value=today.toISOString().slice(0,10);
        }
        const end=new Date(`${fields.namedItem('start_date').value}T12:00:00Z`);
        if(Number.isFinite(end.getTime())) {
            end.setUTCDate(end.getUTCDate()+total*7-1);
            fields.namedItem('end_date').value=end.toISOString().slice(0,10);
        }
    }
    assignment.elements.namedItem('plan_id').addEventListener('change',()=>suggestedDates(false));
    assignment.elements.namedItem('current_week').addEventListener('change',()=>suggestedDates(true));
    assignment.elements.namedItem('start_date').addEventListener('change',()=>suggestedDates(false));
    document.querySelectorAll('a[href="#race-settings"]').forEach(link=>link.addEventListener('click',()=>document.getElementById('race-settings').open=true));
})();
