// Kiểm tra logic hiển thị bằng dữ liệu thật, không cần tải thư viện CDN.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'webapp/index.html'), 'utf8');
const elements = {};
const context = {
    window: { addEventListener() {} },
    document: {
        addEventListener() {},
        getElementById(id) {
            assert.ok(html.includes(`id="${id}"`), `Không có phần tử ${id}`);
            return elements[id] ||= { value: 'all', textContent: '', innerHTML: '' };
        },
    },
    assert,
};
vm.createContext(context);
for (const file of ['data.js', 'app.js']) {
    vm.runInContext(fs.readFileSync(path.join(root, 'webapp', file), 'utf8'), context);
}
vm.runInContext(`
    initFindings();
    assert.equal(document.getElementById('finding-caar').textContent, '+0.570%');
    assert.match(document.getElementById('finding-event-desc').textContent, /6.009/);
    assert.equal(document.getElementById('finding-tone-p').textContent, 'p = 0.2130');
    assert.match(document.getElementById('reg-tone-inference').textContent, /không có ý nghĩa/);
    // Khi dữ liệu thay đổi, diễn giải phải đổi theo, không giữ kết luận cũ.
    const tone = D.regression.find(r => r.section === 'C1' && r.term === 'lm_net_prop');
    const saved = tone.p_hc3_two_sided;
    for (const [p, expected] of [[0.01, /có ý nghĩa thống kê ở mức 5%/], [0.08, /cận biên/], [null, /chưa có/]]) {
        tone.p_hc3_two_sided = p;
        initFindings();
        assert.match(document.getElementById('reg-tone-inference').textContent, expected);
    }
    tone.p_hc3_two_sided = saved;
    let rendered;
    renderTable = (id, columns, rows) => { rendered = rows; };
    for (const section of ['C1', 'C3', 'C4']) {
        document.getElementById('reg-model').value = section;
        for (const win of ['CAR_m1_p1', 'CAR_0_p3', 'CAR_m3_p3', 'CAR_m5_p5']) {
            document.getElementById('reg-window').value = win;
            filterRegression();
            assert.ok(rendered.length > 0);
            assert.ok(rendered.every(r => r.section === section && r.dependent_variable === win.toLowerCase()));
        }
    }
    document.getElementById('c2-full-window').value = 'car_m1_p1';
    renderC2Full();
    assert.equal(rendered.length, 6);
    const values = D.firmYear.map(r => r.CAR_m1_p1).filter(v => v != null);
    const bins = carHistogram(values);
    assert.equal(bins.reduce((sum, b) => sum + b.count, 0), 969);
    assert.equal(bins[0].count, 1);
    assert.equal(bins.at(-1).count, 8);
    assert.equal(bins[0].label, '< -15.00%');
    assert.equal(bins.at(-1).label, '> 15.00%');
    const edges = carHistogram([-0.16, -0.15, 0.15, 0.16, null, NaN]);
    assert.equal(edges[0].count, 1);
    assert.equal(edges[1].count, 1);
    assert.equal(edges.at(-2).count, 1);
    assert.equal(edges.at(-1).count, 1);
    let chart;
    Chart = function(canvas, config) { chart = config; this.destroy = () => {}; };
    renderRegressionCoefChart('all');
    assert.equal(chart.data.datasets.length, 1);
    assert.equal(chart.data.datasets[0].data.length, 5);
    assert.equal(document.getElementById('reg-coef-window').textContent, '[-1, +1]');
    renderRegressionCoefChart('CAR_0_p3');
    assert.equal(document.getElementById('reg-coef-window').textContent, '[0, +3]');
`, context);
assert.ok(!html.includes('0.0991') && !html.includes('0.519%') && !html.includes('6.467'));
assert.ok(!html.includes('Cùng dấu'));
console.log('Đạt: số liệu động, diễn giải, 12 bộ lọc hồi quy, C2, histogram và biểu đồ.');
