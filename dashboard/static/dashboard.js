(() => {
    const node = document.getElementById('analyst-data');
    if (!node) return;
    const data = JSON.parse(node.textContent);
    const canvas = document.getElementById('fitness-chart');
    // Absolute TSB bands, inspired by Intervals.icu. These describe model values.
    const formBands = [
        { min: -Infinity, max: -30, color: '#fa7182', fill: '#fa71821c' },
        { min: -30, max: -10, color: '#64dcb1', fill: '#64dcb11c' },
        { min: -10, max: 5, color: '#aab6c8', fill: '#aab6c812' },
        { min: 5, max: 20, color: '#73bfff', fill: '#73bfff16' },
        { min: 20, max: Infinity, color: '#e5ca58', fill: '#e5ca581a' },
    ];
    const formColor = value => formBands.find(b => value < b.max).color;
    function draw() {
        if (!canvas) return;
        const history = data.fitness_history || [];
        const future = (data.fitness_forecast || {}).points || [];
        const dated = [...history, ...future].filter(p => Number.isFinite(Date.parse(p.date)));
        const usable = dated.filter(p => ['ctl', 'atl', 'tsb'].some(key => Number.isFinite(p[key])));
        const ctx = canvas.getContext('2d');
        const width = canvas.clientWidth || 600, height = canvas.clientHeight || 360;
        canvas.width = width * devicePixelRatio; canvas.height = height * devicePixelRatio;
        ctx.scale(devicePixelRatio, devicePixelRatio);
        ctx.font = '12px sans-serif'; ctx.fillStyle = '#a2b1c8';
        if (!usable.length) { ctx.fillText('Keine Verlaufsdaten verfügbar.', 20, 40); return; }

        // Empty forecast tails must not squeeze the actual history into a corner.
        const begin = Math.min(...usable.map(p => Date.parse(p.date)));
        const end = Math.max(...usable.map(p => Date.parse(p.date)));
        const left = 45, right = width - 12, top = 24;
        const loadBottom = Math.round(height * .55), formTop = loadBottom + 34, bottom = height - 30;
        const x = p => left + (Date.parse(p.date) - begin) / (end - begin || 1) * (right - left);
        const loadValues = usable.flatMap(p => [p.ctl, p.atl]).filter(Number.isFinite);
        const loadMin = Math.max(0, Math.floor(((loadValues.length ? Math.min(...loadValues) : 0) - 5) / 10) * 10);
        const loadMax = Math.max(loadMin + 10, Math.ceil(((loadValues.length ? Math.max(...loadValues) : 10) + 5) / 10) * 10);
        const formValues = usable.map(p => p.tsb).filter(Number.isFinite);
        const formMin = Math.min(-40, Math.floor(((formValues.length ? Math.min(...formValues) : -30) - 3) / 10) * 10);
        const formMax = Math.max(25, Math.ceil(((formValues.length ? Math.max(...formValues) : 20) + 3) / 10) * 10);
        const loadY = v => loadBottom - (v - loadMin) / (loadMax - loadMin) * (loadBottom - top);
        const formY = v => bottom - (v - formMin) / (formMax - formMin) * (bottom - formTop);

        for (const band of formBands) {
            const upper = formY(Math.min(formMax, band.max)), lower = formY(Math.max(formMin, band.min));
            ctx.fillStyle = band.fill; ctx.fillRect(left, upper, right - left, lower - upper);
        }
        function horizontal(value, y) {
            ctx.fillStyle = '#a2b1c8'; ctx.textAlign = 'right'; ctx.fillText(String(Math.round(value)), left - 9, y + 4);
            ctx.strokeStyle = '#293951'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
        }
        for (let i = 0; i <= 4; i++) {
            const value = loadMin + (loadMax - loadMin) * i / 4;
            horizontal(value, loadY(value));
        }
        for (const value of [-30, -10, 5, 20]) horizontal(value, formY(value));
        ctx.fillStyle = '#a2b1c8'; ctx.textAlign = 'left';
        ctx.fillText('Fitness / Ermüdung', left, 13); ctx.fillText('Form · TSB absolut', left, formTop - 10);

        function groups(points, key) {
            const result = []; let group = [], previous = null;
            for (const p of points) {
                const time = Date.parse(p.date);
                if (!Number.isFinite(p[key]) || !Number.isFinite(time)) {
                    if (group.length) result.push(group); group = []; previous = null; continue;
                }
                if (previous !== null && (time <= previous || time - previous > 129600000)) {
                    if (group.length) result.push(group); group = [];
                }
                group.push(p); previous = time;
            }
            if (group.length) result.push(group);
            return result;
        }
        function loadSeries(points, key, color, dash, fill) {
            ctx.setLineDash(dash); ctx.lineDashOffset = 0;
            for (const group of groups(points, key)) {
                if (fill && group.length > 1) {
                    ctx.beginPath(); ctx.moveTo(x(group[0]), loadBottom);
                    for (const p of group) ctx.lineTo(x(p), loadY(p[key]));
                    ctx.lineTo(x(group.at(-1)), loadBottom); ctx.closePath(); ctx.fillStyle = fill; ctx.fill();
                }
                ctx.beginPath(); group.forEach((p, i) => i ? ctx.lineTo(x(p), loadY(p[key])) : ctx.moveTo(x(p), loadY(p[key])));
                ctx.strokeStyle = color; ctx.lineWidth = key === 'ctl' ? 2 : 1.5; ctx.stroke();
                if (group.length === 1) { ctx.beginPath(); ctx.arc(x(group[0]), loadY(group[0][key]), 2, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill(); }
            }
        }
        function formSeries(points, dash) {
            ctx.setLineDash(dash); ctx.lineWidth = 2;
            for (const group of groups(points, 'tsb')) {
                let length = 0;
                if (group.length === 1) { ctx.beginPath(); ctx.arc(x(group[0]), formY(group[0].tsb), 2, 0, Math.PI * 2); ctx.fillStyle = formColor(group[0].tsb); ctx.fill(); }
                for (let i = 1; i < group.length; i++) {
                    const a = group[i - 1], b = group[i], delta = b.tsb - a.tsb;
                    const cuts = [0, 1];
                    if (delta) for (const edge of [-30, -10, 5, 20]) {
                        const t = (edge - a.tsb) / delta; if (t > 0 && t < 1) cuts.push(t);
                    }
                    cuts.sort((a, b) => a - b);
                    for (let j = 1; j < cuts.length; j++) {
                        const t0 = cuts[j - 1], t1 = cuts[j];
                        const x0 = x(a) + (x(b) - x(a)) * t0, x1 = x(a) + (x(b) - x(a)) * t1;
                        const y0 = formY(a.tsb + delta * t0), y1 = formY(a.tsb + delta * t1);
                        ctx.lineDashOffset = -length; ctx.strokeStyle = formColor(a.tsb + delta * (t0 + t1) / 2);
                        ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
                        length += Math.hypot(x1 - x0, y1 - y0);
                    }
                }
            }
        }
        const actual = history.filter(p => Number.isFinite(Date.parse(p.date))).sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
        const planned = [...(actual.length ? [actual.at(-1)] : []), ...future];
        loadSeries(actual, 'ctl', '#73bfff', [], '#73bfff18');
        loadSeries(planned, 'ctl', '#73bfff', [6, 4], '#73bfff09');
        loadSeries(actual, 'atl', '#aa8bff', []);
        loadSeries(planned, 'atl', '#aa8bff', [6, 4]);
        formSeries(actual, []); formSeries(planned, [6, 4]);
        ctx.setLineDash([]); ctx.lineDashOffset = 0;
        const today = Date.parse(data.date);
        if (Number.isFinite(today) && today >= begin && today <= end) {
            const px = x({ date: data.date }); ctx.setLineDash([3, 4]); ctx.strokeStyle = '#a2b1c866'; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(px, top); ctx.lineTo(px, bottom); ctx.stroke(); ctx.setLineDash([]);
        }
        const ticks = width < 450 ? 2 : 4;
        ctx.fillStyle = '#a2b1c8';
        for (let i = 0; i < ticks; i++) {
            const time = begin + (end - begin) * i / (ticks - 1);
            ctx.textAlign = i === 0 ? 'left' : i === ticks - 1 ? 'right' : 'center';
            const iso = new Date(time).toISOString().slice(0, 10);
            const label = (i === 0 || i === ticks - 1 ? iso : iso.slice(5)).split('-').reverse().join('.');
            ctx.fillText(label, left + (right - left) * i / (ticks - 1), height - 7);
        }
        ctx.textAlign = 'left';
    }
    draw(); window.addEventListener('resize',draw);
    function drawPreparation() {
        document.querySelectorAll('.preparation-chart').forEach(chart => {
            const history = ((data.race_preparation || {})[chart.dataset.raceId] || {}).history || [];
            const ctx=chart.getContext('2d'), width=chart.clientWidth || 600, height=180;
            chart.width=width*devicePixelRatio; chart.height=height*devicePixelRatio;
            ctx.scale(devicePixelRatio,devicePixelRatio); ctx.font='14px sans-serif'; ctx.fillStyle='#a2b1c8';
            for (const v of [0,50,100]) {
                const y=150-v*1.2; ctx.fillText(String(v),0,y);
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
        payload.elevation_gain_m=fields.elevation_gain_m ? Number(fields.elevation_gain_m) : null;
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
