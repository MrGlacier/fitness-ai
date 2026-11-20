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
        ctx.font = '14px sans-serif'; ctx.fillStyle = '#64748b';
        for (let i = 0; i <= 4; i++) {
            const v = min + (max-min)*i/4;
            ctx.fillText(String(Math.round(v)), 2, y(v));
            ctx.strokeStyle = '#cbd5e1'; ctx.beginPath(); ctx.moveTo(40,y(v)); ctx.lineTo(width-15,y(v)); ctx.stroke();
        }
        for (const [key,color] of [['ctl','#2563eb'],['atl','#ea580c'],['tsb','#16a34a']]) {
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
            ctx.scale(devicePixelRatio,devicePixelRatio); ctx.font='14px sans-serif'; ctx.fillStyle='#64748b';
            for (const v of [0,50,100]) {
                const y=150-v*1.2; ctx.fillText(String(v)+'%',0,y);
                ctx.strokeStyle='#cbd5e1'; ctx.beginPath(); ctx.moveTo(45,y); ctx.lineTo(width-15,y); ctx.stroke();
            }
            if (!history.length) { ctx.fillText('Noch kein Indexverlauf vorhanden.',50,85); return; }
            const start=Date.parse(history[0].day), end=Date.parse(history.at(-1).day);
            const x=p=>50+(Date.parse(p.day)-start)/(end-start || 1)*(width-75);
            ctx.strokeStyle='#2563eb'; ctx.beginPath(); let previous=null;
            for (const p of history) {
                if (!Number.isFinite(p.score)) {previous=null;continue;}
                if (!previous || previous.model_version !== p.model_version) ctx.moveTo(x(p),150-p.score*1.2);
                else ctx.lineTo(x(p),150-p.score*1.2);
                previous=p;
            }
            ctx.stroke(); ctx.fillStyle='#2563eb';
            for (const p of history) if (Number.isFinite(p.score)) { ctx.beginPath(); ctx.arc(x(p),150-p.score*1.2,3,0,Math.PI*2);ctx.fill(); }
            ctx.fillStyle='#64748b'; ctx.fillText(history[0].day,45,175); ctx.fillText(history.at(-1).day,Math.max(45,width-110),175);
        });
    }
    drawPreparation(); window.addEventListener('resize',drawPreparation);
    async function save(form,path,payload) {
        const output=form.querySelector('output'); output.textContent='Speichert…';
        try { const response=await fetch(path,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
            if (!response.ok) throw new Error(); output.textContent='Gespeichert'; location.reload();
        } catch { output.textContent='Speichern fehlgeschlagen. Eingaben und API prüfen.'; }
    }
    const raceForm=document.getElementById('race-form');
    raceForm.addEventListener('submit',event=>{
        event.preventDefault(); const fields=Object.fromEntries(new FormData(raceForm));
        const distances={}; for (const [field,sport] of [['swim','Swim'],['ride','Ride'],['run','Run']]) if(fields[field]) distances[sport]=Number(fields[field]);
        const payload={}; for(const key of ['id','source_id','name','date','sport','performance_goal','priority','status']) payload[key]=fields[key] || null;
        for(const key of ['target_seconds','transition_seconds']) payload[key]=fields[key] === '' ? null : Number(fields[key]);
        const splits={}; for (const [field,sport] of [['split_swim','Swim'],['split_ride','Ride'],['split_run','Run']]) if(fields[field]) splits[sport]=Number(fields[field]);
        payload.goal_splits_seconds=splits;
        payload.distances_km=distances; save(raceForm,'/dashboard/races',payload);
    });
    document.querySelectorAll('.edit-race').forEach(button=>button.addEventListener('click',()=>{
        const race=JSON.parse(button.dataset.race); raceForm.reset();
        for(const [key,value] of Object.entries(race)) if(raceForm.elements.namedItem(key)) raceForm.elements.namedItem(key).value=value ?? '';
        for(const [key,sport] of [['swim','Swim'],['ride','Ride'],['run','Run']]) raceForm.elements.namedItem(key).value=race.distances_km[sport] ?? '';
        for(const [key,sport] of [['split_swim','Swim'],['split_ride','Ride'],['split_run','Run']]) raceForm.elements.namedItem(key).value=(race.goal_splits_seconds || {})[sport] ?? '';
        raceForm.scrollIntoView({behavior:'smooth'});
    }));
    const assignment=document.getElementById('assignment-form');
    assignment.addEventListener('submit',event=>{event.preventDefault(); save(assignment,'/dashboard/assignment',Object.fromEntries(new FormData(assignment)));});
})();
