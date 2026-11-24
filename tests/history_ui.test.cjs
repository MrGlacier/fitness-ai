// Deterministic browser-logic checks; synthetic data and a small DOM double.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Node {
    constructor(tag='div') { this.tag=tag;this.children=[];this.listeners={};this.value='';this.textContent='';this.hidden=false;this.attributes={}; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children=nodes; }
    addEventListener(name,fn) {this.listeners[name]=fn;}
    setAttribute(key,value) {this.attributes[key]=value;}
    get options() {return this.children;}
    set innerHTML(_) {throw new Error('Unsafe HTML insertion');}
}
const keys='sessions duration_sec distance_m tss avg_watts np_watts avg_hr ftp rpe lthr threshold_speed_mps w_per_kg ctl atl tsb hrv resting_hr weight vo2max run_pace swim_pace active_days sessions_per_week lit_hit'.split(' ');
function fixture() {
    const metrics=Object.fromEntries(keys.map(k=>[k,{value:null,unit:'',status:'unavailable'}]));
    metrics.sessions={value:0,unit:'Einheiten'};metrics.duration_sec={value:0,unit:'s'};
    const period={start:'2024-02-01',end:'2024-02-07',metrics,activities:[],planned:[],phases:[],weekly:[],wellness:[],sources:[],activity_source_complete:true};
    return {a:structuredClone(period),b:structuredClone(period),pairs:[],differences:Object.fromEntries(keys.map(k=>[k,{absolute:null,percent:null}])),limitations:['Synthetic limitation'],unequal_days:false};
}
function app(compareResult=fixture(), fail=false) {
    const nodes={},requests=[];
    for(const match of fs.readFileSync('dashboard/templates/comparison.html','utf8').matchAll(/id="([^"]+)"/g)) nodes[match[1]]=new Node();
    const document={getElementById(id){return nodes[id] ||= new Node();},createElement(tag){return new Node(tag);},createElementNS(ns,tag){return new Node(tag);},createTextNode(text){return {textContent:text};}};
    const context={document,Date,URLSearchParams,console,fetch:async(path,options)=>{
        requests.push({path,options});return {ok:!fail,json:async()=> fail?{detail:'Offline'}:path.endsWith('catalog')?{preparations:[],races:[]}:compareResult};
    }};
    vm.runInNewContext(fs.readFileSync('dashboard/static/comparison.js','utf8'),context);
    nodes['sport'].value='all';nodes['chart-metric'].value='duration_sec';
    return {nodes,requests};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('empty comparison renders explicit missing data and restores submit button',async()=>{
    const ui=app();await settle();const button=new Node('button');
    await ui.nodes['compare-form'].listeners.submit({preventDefault(){},submitter:button});
    assert.equal(ui.nodes.results.hidden,false);assert.equal(ui.nodes['metric-rows'].children.length,24);
    assert.equal(button.disabled,false);assert.match(ui.nodes['chart-readout'].textContent,/Keine Verlaufswerte/);
    const payload=JSON.parse(ui.requests.find(r=>r.path.endsWith('compare')).options.body);
    assert.equal(payload.a.start,'2023-12-18');assert.equal(payload.sport,'all');
});
test('API failure stays visible and leaves results hidden',async()=>{
    const ui=app(fixture(),true);await settle();ui.nodes.results=new Node();ui.nodes.results.hidden=true;
    const button=new Node();await ui.nodes['compare-form'].listeners.submit({preventDefault(){},submitter:button});
    assert.equal(ui.nodes['compare-status'].textContent,'Offline');assert.equal(button.disabled,false);assert.equal(ui.nodes.results.hidden,true);
});
test('race dates align exactly and require confirmed dates',()=>{
    const ui=app();ui.nodes['weeks-before'].value='20';ui.nodes['week-count'].value='1';
    ui.nodes['align-race'].listeners.click();assert.match(ui.nodes['compare-status'].textContent,/bestätigten/);
    ui.nodes['race-a'].value='2024-06-01';ui.nodes['race-b'].value='2026-06-01';ui.nodes['align-race'].listeners.click();
    assert.equal(ui.nodes['start-a'].value,'2024-01-13');assert.equal(ui.nodes['end-a'].value,'2024-01-19');
});
test('names are rendered as text and chart points support keyboard focus',async()=>{
    const f=fixture();f.a.activities=[{id:'synthetic',name:'<img onerror=alert(1)>',date:'2024-02-01',sport:'Run',source:'activity',reference:'activity:synthetic',assignment:{phase:null,reason:'Unknown'}}];
    f.a.weekly=[{start:'2024-02-01',duration_sec:3600}];const ui=app(f);await settle();
    await ui.nodes['compare-form'].listeners.submit({preventDefault(){},submitter:new Node()});
    const svg=ui.nodes['history-chart'].children[0];const point=svg.children.find(n=>n.tag==='circle');
    assert.equal(point.attributes.tabindex,0);point.listeners.focus();assert.match(ui.nodes['chart-readout'].textContent,/2024-02-01/);
    const activity=ui.nodes['activity-lists'].children[0].children[1];assert.equal(activity.children[0].textContent,'2024-02-01 · <img onerror=alert(1)>');
});
