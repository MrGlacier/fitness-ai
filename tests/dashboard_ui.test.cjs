// Regressionstests für Formularlogik ohne Browser, Netzwerk oder Abhängigkeiten.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync('dashboard/static/dashboard.js', 'utf8');

function app(response, blockedStorage = false, analysis = {}) {
    const requests = [], state = { reloads: 0 };
    const paint = { strokes: [], fills: [], labels: [] };
    let path = [], dash = [];
    const drawing = {
        scale() {},
        fillText(text) { paint.labels.push(text); },
        fillRect(...rect) { paint.fills.push({ color: this.fillStyle, rect }); },
        setLineDash(value) { dash = [...value]; },
        beginPath() { path = []; },
        moveTo(x, y) { path.push(['M', x, y]); },
        lineTo(x, y) { path.push(['L', x, y]); },
        closePath() {}, arc() {}, fill() {},
        stroke() { paint.strokes.push({ color: this.strokeStyle, dash: [...dash], path: [...path] }); },
    };
    const input = value => ({ value, listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; } });
    const fields = { plan_id: input('example'), current_week: input('6'), start_date: input('2026-10-12'), end_date: input('2027-01-03') };
    const output = { textContent: '' }, button = { disabled: false };
    const form = {
        fields, listeners: {}, elements: { namedItem: name => fields[name] },
        addEventListener(name, fn) { this.listeners[name] = fn; },
        querySelector: selector => selector === 'output' ? output : button,
    };
    const race = { addEventListener() {} }, settings = { open: false };
    const nodes = {
        'analyst-data': { textContent: JSON.stringify({ date: '2026-11-20', available_plans: [{ id: 'example', total_weeks: 12 }], ...analysis }) },
        'fitness-chart': { clientWidth: 600, getContext: () => drawing },
        'assignment-form': form, 'race-form': race, 'plan-settings': settings,
    };
    const context = {
        document: { getElementById: id => nodes[id], querySelectorAll: () => [] },
        window: { addEventListener() {} }, devicePixelRatio: 1,
        FormData: class { constructor(value) { return new Map(Object.entries(value.fields).map(([key, item]) => [key, item.value])); } },
        sessionStorage: {
            getItem() { if (blockedStorage) throw new Error('blocked'); return null; },
            setItem() { if (blockedStorage) throw new Error('blocked'); }, removeItem() {},
        },
        location: { reload() { state.reloads++; } },
        fetch: async (path, options) => { requests.push({ path, payload: JSON.parse(options.body) }); return response; },
    };
    vm.runInNewContext(script, context);
    return { form, fields, output, requests, state, button, paint };
}
const settle = () => new Promise(resolve => setImmediate(resolve));

test('Planzuordnung wird auch mit gesperrtem Webspeicher gespeichert', async () => {
    const ui = app({ ok: true, json: async () => ({ plan: { message: 'Manuell aktiv' } }) }, true);
    ui.form.listeners.submit({ preventDefault() {} });
    await settle();
    assert.equal(ui.requests.length, 1);
    assert.equal(ui.requests[0].path, '/dashboard/assignment');
    assert.equal(ui.requests[0].payload.plan_id, 'example');
    assert.equal(ui.requests[0].payload.current_week, undefined);
    assert.equal(ui.state.reloads, 1);
    assert.match(ui.output.textContent, /gespeichert/);
    assert.equal(ui.button.disabled, false);
});

test('Validierungsfehler wird angezeigt und löst keinen Reload aus', async () => {
    const ui = app({ ok: false, json: async () => ({ detail: 'Der Planstart muss ein Montag sein.' }) });
    ui.form.listeners.submit({ preventDefault() {} });
    await settle();
    assert.match(ui.output.textContent, /Nicht gespeichert:.*Montag/);
    assert.equal(ui.state.reloads, 0);
});

test('Planwoche berechnet Start und Gültigkeitsende deterministisch', () => {
    const ui = app({});
    ui.fields.current_week.listeners.change();
    assert.equal(ui.fields.start_date.value, '2026-10-12');
    assert.equal(ui.fields.end_date.value, '2027-01-03');
});

test('Ohne Planwoche oder Startdatum wird kein Beginn geraten', () => {
    const ui = app({});
    ui.fields.current_week.value = '';
    ui.fields.start_date.value = '';
    ui.fields.plan_id.listeners.change();
    assert.equal(ui.fields.start_date.value, '');
});

test('Form erhält fünf Hintergrundbereiche und wechselt an allen Grenzen die Linienfarbe', () => {
    const { paint } = app({}, false, { fitness_history: [
        { date: '2026-11-19', ctl: 40, atl: 80, tsb: -40 },
        { date: '2026-11-20', ctl: 42, atl: 12, tsb: 30 },
    ] });
    assert.equal(paint.fills.length, 5);
    assert.ok(paint.fills.every(fill => fill.rect.every(Number.isFinite) && fill.rect[3] > 0));
    // All five portions of the crossing must remain inside the lower form panel.
    const form = paint.strokes.filter(stroke => stroke.path.length === 2 && stroke.path.every(point => point[2] >= 232));
    for (const color of ['#fa7182', '#64dcb1', '#aab6c8', '#73bfff', '#e5ca58']) {
        assert.ok(form.some(stroke => stroke.color === color), `Formbereich ${color} fehlt`);
    }
});

test('Fehlende Werte werden nicht zu einer durchgehenden Fitnesslinie verbunden', () => {
    const { paint } = app({}, false, { fitness_history: [
        { date: '2026-11-18', ctl: 40, atl: 50, tsb: -10 },
        { date: '2026-11-19', ctl: null, atl: null, tsb: null },
        { date: '2026-11-20', ctl: 42, atl: 48, tsb: -6 },
    ] });
    const fitness = paint.strokes.filter(stroke => stroke.color === '#73bfff');
    assert.ok(fitness.length);
    assert.ok(fitness.every(stroke => !stroke.path.some(point => point[0] === 'L')));
});

test('Eine leere Prognose bis April verkleinert nicht den tatsächlichen Novemberverlauf', () => {
    const { paint } = app({}, false, { fitness_history: [
        { date: '2026-11-19', ctl: 40, atl: 50, tsb: -10 },
        { date: '2026-11-20', ctl: 42, atl: 48, tsb: -6 },
    ], fitness_forecast: { points: [{ date: '2027-04-24', ctl: null, atl: null, tsb: null }] } });
    const line = paint.strokes.find(stroke => stroke.color === '#73bfff' && stroke.path.some(point => point[0] === 'L'));
    assert.equal(line.path.at(-1)[1], 588);
    assert.equal(paint.labels.at(-1), '20.11.2026');
});

test('Kalenderszenario bleibt gestrichelt und wird bei unbekannten Tagen unterbrochen', () => {
    const { paint } = app({}, false, { fitness_history: [
        { date: '2026-11-20', ctl: 40, atl: 50, tsb: -10 },
    ], fitness_forecast: { points: [
        { date: '2026-11-21', ctl: 41, atl: 52, tsb: -11 },
        { date: '2026-11-22', ctl: null, atl: null, tsb: null },
        { date: '2026-11-23', ctl: 42, atl: 48, tsb: -6 },
    ] } });
    const planned = paint.strokes.filter(stroke => stroke.color === '#73bfff' && stroke.dash.length);
    assert.ok(planned.some(stroke => stroke.path.length === 2));
    assert.ok(planned.every(stroke => stroke.path.length <= 2));
    assert.ok(planned.every(stroke => stroke.dash.join(',') === '6,4'));
});
