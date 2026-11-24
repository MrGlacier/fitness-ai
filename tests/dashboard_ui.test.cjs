// Regressionstests für Formularlogik ohne Browser, Netzwerk oder Abhängigkeiten.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync('dashboard/static/dashboard.js', 'utf8');

function app(response, blockedStorage = false) {
    const requests = [], state = { reloads: 0 };
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
        'analyst-data': { textContent: JSON.stringify({ date: '2026-11-20', available_plans: [{ id: 'example', total_weeks: 12 }] }) },
        'fitness-chart': { clientWidth: 600, getContext: () => ({ scale() {}, fillText() {} }) },
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
    return { form, fields, output, requests, state, button };
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
