/* ==========================================================
   APP.JS — 10-K Textual Analysis Web App (Premium Edition)
   Reads embedded data from data.js (window.APP_DATA).
   No statistical recalculation — every displayed number
   comes directly from the analysis CSV tables.
   Adheres to UI/UX Pro Max & WCAG 2.1 AA Guidelines
   ========================================================== */

"use strict";

const D = window.APP_DATA;
const activeCharts = [];

/* ---- Chart.js Global Academic Defaults ---- */
if (window.Chart) {
    // Register Chart Zoom plugin if present
    const zoomPlugin = window.ChartZoom || window["ChartZoom"] || (window.Chart && window.Chart.Zoom);
    if (zoomPlugin && typeof Chart.register === "function") {
        try { Chart.register(zoomPlugin); } catch (e) {}
    }

    Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    Chart.defaults.color = "#475569";
    Chart.defaults.borderColor = "#f1f5f9";
    Chart.defaults.plugins.tooltip.backgroundColor = "rgba(15, 23, 42, 0.94)";
    Chart.defaults.plugins.tooltip.titleFont = { size: 12, weight: "700", family: "'Inter', sans-serif" };
    Chart.defaults.plugins.tooltip.bodyFont = { size: 12, family: "'Inter', sans-serif" };
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 6;
    Chart.defaults.plugins.tooltip.boxPadding = 5;
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.borderColor = "rgba(255, 255, 255, 0.1)";
    // Áp dụng màu chữ và lưới cho cả biểu đồ mới tạo trong chế độ tối.
    Chart.register({
        id: "researchTheme",
        beforeUpdate(chart) {
            const dark = document.documentElement.getAttribute("data-theme") === "dark";
            const text = dark ? "#a0afc4" : "#475569";
            Object.values(chart.options.scales || {}).forEach(scale => {
                if (scale.ticks) scale.ticks.color = text;
                if (scale.title) scale.title.color = text;
                if (scale.grid) scale.grid.color = dark ? "#28364b" : "#e2e8f0";
            });
            if (chart.options.plugins?.legend?.labels) chart.options.plugins.legend.labels.color = text;
            if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) chart.options.animation = false;
        },
    });
}

/* ---- Window label map ---- */
const WIN = {
    CAR_m1_p1: "[-1, +1]",
    CAR_0_p3:  "[0, +3]",
    CAR_m3_p3: "[-3, +3]",
    CAR_m5_p5: "[-5, +5]",
    car_m1_p1: "[-1, +1]",
    car_0_p3:  "[0, +3]",
    car_m3_p3: "[-3, +3]",
    car_m5_p5: "[-5, +5]",
};

/* ==========================================================
   TOAST NOTIFICATION HELPER (Micro-interactions)
   ========================================================== */

function showToast(message) {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = "toast";
    toast.innerHTML = `
        <svg class="icon-svg" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
        <span>${message}</span>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("toast-hide");
        setTimeout(() => {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 250);
    }, 2500);
}

/* ==========================================================
   THEME MANAGER (Light / Dark Mode)
   Swiss Modernism 2.0 Academic Navy & High Contrast
   ========================================================== */

function initTheme() {
    const toggleBtn = document.getElementById("theme-toggle");
    const savedTheme = localStorage.getItem("app_theme");
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initialTheme = savedTheme || (prefersDark ? "dark" : "light");

    applyTheme(initialTheme);

    if (toggleBtn) {
        toggleBtn.addEventListener("click", () => {
            const isDark = document.documentElement.getAttribute("data-theme") === "dark";
            const newTheme = isDark ? "light" : "dark";
            applyTheme(newTheme);
            localStorage.setItem("app_theme", newTheme);
            showToast(`Đã chuyển sang giao diện: ${newTheme === "dark" ? "Chế độ Tối" : "Chế độ Sáng"}`);
        });
    }
}

function applyTheme(theme) {
    const themeText = document.getElementById("theme-text");
    const isDark = theme === "dark";

    if (isDark) {
        document.documentElement.setAttribute("data-theme", "dark");
        if (themeText) themeText.textContent = "Sáng";
    } else {
        document.documentElement.removeAttribute("data-theme");
        if (themeText) themeText.textContent = "Tối";
    }

    // Dynamic Chart.js grid & ticks update
    const gridColor = isDark ? "#1e293b" : "#e2e8f0";
    const textColor = isDark ? "#94a3b8" : "#475569";

    activeCharts.forEach(chart => {
        if (!chart || !chart.options) return;
        if (chart.options.scales) {
            Object.values(chart.options.scales).forEach(scale => {
                if (scale.grid) scale.grid.color = gridColor;
                if (scale.ticks) scale.ticks.color = textColor;
                if (scale.title) scale.title.color = textColor;
            });
        }
        chart.update("none");
    });
}

/* ==========================================================
   CSV EXPORT UTILITY (RFC 4180 with UTF-8 BOM)
   ========================================================== */

function exportToCsv(filename, cols, rows) {
    if (!rows || rows.length === 0) {
        showToast("Không có dữ liệu phù hợp để xuất file CSV");
        return;
    }

    const header = cols.map(c => `"${c.label.replace(/"/g, '""')}"`).join(",");
    const lines = rows.map(r => {
        return cols.map(c => {
            let val = c.get ? c.get(r) : r[c.key];
            if (val == null) val = "";
            else if (typeof val === "number") val = String(val);
            else val = String(val).replace(/<[^>]*>/g, "").trim();
            return `"${val.replace(/"/g, '""')}"`;
        }).join(",");
    });

    const csvContent = "\uFEFF" + [header, ...lines].join("\r\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    showToast(`✓ Đã tải xuống ${rows.length.toLocaleString()} dòng (${filename})`);
}

/* ==========================================================
   FORMATTING UTILITIES
   Consistent decimal-dot format throughout (point 8)
   ========================================================== */

function fmt(v, d = 4) {
    if (v == null || !isFinite(v)) return "—";
    return Number(v).toFixed(d);
}

function pct(v, d = 3) {
    if (v == null || !isFinite(v)) return "—";
    return (Number(v) * 100).toFixed(d) + "%";
}

function pval(v) {
    if (v == null || !isFinite(v)) return "—";
    const n = Number(v);
    if (n < 0.0001) return "<0.0001";
    return n.toFixed(4);
}

function sigClass(p) {
    if (p == null || !isFinite(p)) return "";
    if (p < 0.05) return "sig-high";
    if (p < 0.10) return "sig-marginal";
    return "";
}

// Chuẩn hóa tên cửa sổ vì CSV và bộ lọc có thể khác chữ hoa/thường.
function sameWindow(a, b) {
    return String(a).toLowerCase() === String(b).toLowerCase();
}

function initFindings() {
    const event = D.eventSummary.find(r => sameWindow(r.window, "car_m1_p1"));
    const tone = D.regression.find(r => r.section === "C1" && r.term === "lm_net_prop"
        && sameWindow(r.dependent_variable, "car_m1_p1"));
    const setText = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    };
    if (event) {
        setText("finding-caar", (event.CAAR > 0 ? "+" : "") + pct(event.CAAR));
        setText("finding-event-desc", `CAAR tại cửa sổ [-1, +1] là ${pct(event.CAAR)}; ` +
            `p MacKinlay ${pval(event.MacKinlay_p).startsWith("<") ? "" : "= "}${pval(event.MacKinlay_p)}, Z MacKinlay = ${fmt(event.MacKinlay_Z, 3)}.`);
    }
    if (tone) {
        const p = tone.p_hc3_two_sided;
        const inference = p == null || !Number.isFinite(p) ? "chưa có p-value hợp lệ"
            : p < 0.05 ? "có ý nghĩa thống kê ở mức 5%"
            : p < 0.10 ? "chỉ có ý nghĩa cận biên ở mức 10%, không đạt 5%"
            : "không có ý nghĩa thống kê ở mức 10% hoặc 5%";
        const text = `C1 LM net_prop [-1, +1]: p HC3 ${pval(p).startsWith("<") ? "" : "= "}${pval(p)}; ${inference}.`;
        setText("finding-tone-p", `p ${pval(p).startsWith("<") ? "" : "= "}${pval(p)}`);
        setText("finding-tone-desc", text + " Không xem đây là tín hiệu giao dịch.");
        setText("reg-tone-inference", text);
    }
    const integrity = Object.values(D.sourceIntegrity || {});
    const exact = integrity.filter(r => r.status === "exact").length;
    const newline = integrity.filter(r => r.status === "line_endings_only").length;
    setText("finding-integrity", integrity.length
        ? `${exact}/${integrity.length} khớp byte; ${newline} khác xuống dòng`
        : "Chưa đối chiếu nguồn");
}

// Tách riêng hai đuôi phân phối để không gán ngoại lệ vào khoảng hữu hạn.
function carHistogram(values, nBins = 24, min = -0.15, max = 0.15) {
    const step = (max - min) / nBins;
    const bins = [
        { lo: -Infinity, hi: min, label: `< ${pct(min, 2)}`, count: 0 },
        ...Array.from({ length: nBins }, (_, i) => ({
            lo: min + i * step, hi: min + (i + 1) * step,
            label: `[${pct(min + i * step, 2)}; ${pct(min + (i + 1) * step, 2)}${i === nBins - 1 ? "]" : ")"}`,
            count: 0,
        })),
        { lo: max, hi: Infinity, label: `> ${pct(max, 2)}`, count: 0 },
    ];
    values.filter(v => v != null && Number.isFinite(v)).forEach(v => {
        const index = v < min ? 0 : v > max ? bins.length - 1
            : 1 + Math.min(nBins - 1, Math.floor((v - min) / step));
        bins[index].count++;
    });
    return bins;
}

/** Accessible sign symbol — not colour alone (WCAG 1.4.1 & point 10) */
function signSpan(v) {
    if (v == null || !isFinite(v)) return '<span>—</span>';
    const n = Number(v);
    if (n > 0) return `<span class="val-pos">${n.toFixed(4)}</span>`;
    if (n < 0) return `<span class="val-neg">${n.toFixed(4)}</span>`;
    return `<span>${n.toFixed(4)}</span>`;
}

/* ==========================================================
   GENERIC TABLE RENDERER (Sortable & Accessible)
   ========================================================== */

function renderTable(containerId, cols, rows, opts = {}) {
    const wrap = document.getElementById(containerId);
    if (!wrap) return;

    const { currentSort, onSort } = opts;

    let html = "<table><thead><tr>";
    cols.forEach(c => {
        const isSortable = !!c.sortable && !!onSort;
        const sortKey = c.sortKey || c.key;
        const isCurrent = currentSort && currentSort.key === sortKey;
        const clsList = [
            c.num ? "num" : "",
            c.center ? "center" : "",
            isSortable ? "sortable" : "",
            isCurrent ? (currentSort.dir === "asc" ? "sort-asc" : "sort-desc") : ""
        ].filter(Boolean);

        let ariaSort = "none";
        let sortIndicator = "";
        if (isSortable) {
            if (isCurrent) {
                ariaSort = currentSort.dir === "asc" ? "ascending" : "descending";
                sortIndicator = currentSort.dir === "asc" ? ' ▲' : ' ▼';
            } else {
                sortIndicator = ' ↕';
            }
        }

        const dataSortAttr = isSortable ? `data-sort-key="${sortKey}"` : "";
        const ariaAttr = isSortable ? `aria-sort="${ariaSort}" role="columnheader" tabindex="0" title="Bấm để sắp xếp theo ${c.label}"` : "";

        html += `<th class="${clsList.join(" ")}" ${dataSortAttr} ${ariaAttr}>${c.label}${sortIndicator}</th>`;
    });
    html += "</tr></thead><tbody>";

    if (rows.length === 0) {
        html += `<tr><td colspan="${cols.length}" style="text-align:center;color:var(--text-muted);padding:1.5rem">Không có dữ liệu phù hợp bộ lọc</td></tr>`;
    }

    rows.forEach(row => {
        html += "<tr>";
        cols.forEach(c => {
            const raw = c.get ? c.get(row) : row[c.key];
            const cls = [c.num ? "num" : "", c.center ? "center" : "", c.cls ? c.cls(row) : ""].filter(Boolean).join(" ");
            const val = c.fmt ? c.fmt(raw, row) : (raw ?? "—");
            html += `<td class="${cls}">${val}</td>`;
        });
        html += "</tr>";
    });

    html += "</tbody></table>";
    wrap.innerHTML = html;

    // Attach click and keyboard listeners for sortable headers
    if (onSort) {
        wrap.querySelectorAll("th.sortable").forEach(th => {
            const handler = () => {
                const sortKey = th.dataset.sortKey;
                if (sortKey) onSort(sortKey);
            };
            th.addEventListener("click", handler);
            th.addEventListener("keydown", (e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handler();
                }
            });
        });
    }
}

/* ==========================================================
   TAB NAVIGATION (Deep Linking & Keyboard Nav — Priority 1 & 9)
   ========================================================== */

/* ==========================================================
   TAB NAVIGATION (Sidebar, Deep Linking & Keyboard Nav)
   ========================================================== */

function renderMath(container) {
    if (window.renderMathInElement) {
        try {
            renderMathInElement(container || document.body, {
                delimiters: [
                    { left: "$$", right: "$$", display: true },
                    { left: "$", right: "$", display: false }
                ],
                throwOnError: false
            });
        } catch (e) {
            console.warn("KaTeX render notice:", e);
        }
    }
}
window.renderMath = renderMath;

function activateTab(tabId, updateHash = true) {
    const targetBtn = document.querySelector(`.nav-item[data-tab="${tabId}"], .tab-btn[data-tab="${tabId}"]`);
    const targetPanel = document.getElementById("tab-" + tabId);
    if (!targetBtn || !targetPanel) return;

    document.querySelectorAll(".nav-item, .tab-btn").forEach(b => { 
        b.classList.remove("active"); 
        b.setAttribute("aria-selected", "false"); 
    });
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));

    // Activate all matching tab buttons (both desktop sidebar and mobile if duplicate)
    document.querySelectorAll(`[data-tab="${tabId}"]`).forEach(b => {
        b.classList.add("active");
        b.setAttribute("aria-selected", "true");
    });
    targetPanel.classList.add("active");

    // Update topbar breadcrumb label
    const crumbEl = document.getElementById("topbar-crumb");
    if (crumbEl) {
        const labelEl = targetBtn.querySelector(".nav-label");
        crumbEl.textContent = labelEl ? labelEl.textContent.trim() : (targetBtn.textContent.trim() || tabId);
    }

    // Close mobile drawer if opened
    const sidebar = document.getElementById("app-sidebar");
    if (sidebar) sidebar.classList.remove("mobile-open");

    // Render KaTeX formulas if activating methodology
    if (tabId === "method") {
        setTimeout(() => renderMath(targetPanel), 50);
    }

    // Trigger chart resize & redraw smoothly after panel display change
    setTimeout(() => {
        activeCharts.forEach(c => {
            if (c) {
                try {
                    c.resize();
                    c.update();
                } catch (e) {}
            }
        });
        if (tabId === "regression" && typeof renderRegressionCoefChart === "function") {
            const win = document.getElementById("reg-window")?.value || "CAR_m1_p1";
            renderRegressionCoefChart(win === "all" ? "CAR_m1_p1" : win);
        }
    }, 100);

    if (updateHash && window.location.hash !== "#" + tabId) {
        history.replaceState(null, "", "#" + tabId);
    }
}
window.activateTab = activateTab;

function initNavigation() {
    const navItems = Array.from(document.querySelectorAll(".nav-item, .tab-btn"));
    navItems.forEach((btn, idx) => {
        btn.addEventListener("click", () => activateTab(btn.dataset.tab));
        
        // Arrow key keyboard navigation
        btn.addEventListener("keydown", (e) => {
            let targetIdx = null;
            if (e.key === "ArrowDown" || e.key === "ArrowRight") targetIdx = (idx + 1) % navItems.length;
            else if (e.key === "ArrowUp" || e.key === "ArrowLeft") targetIdx = (idx - 1 + navItems.length) % navItems.length;
            else if (e.key === "Home") targetIdx = 0;
            else if (e.key === "End") targetIdx = navItems.length - 1;

            if (targetIdx !== null) {
                e.preventDefault();
                const target = navItems[targetIdx];
                target.focus();
                activateTab(target.dataset.tab);
            }
        });
    });

    // Mobile Hamburger Menu Toggle
    const mobileToggle = document.getElementById("mobile-toggle");
    const sidebar = document.getElementById("app-sidebar");
    if (mobileToggle && sidebar) {
        mobileToggle.addEventListener("click", (e) => {
            e.stopPropagation();
            sidebar.classList.toggle("mobile-open");
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener("click", (e) => {
            if (sidebar.classList.contains("mobile-open") && !sidebar.contains(e.target) && e.target !== mobileToggle) {
                sidebar.classList.remove("mobile-open");
            }
        });
    }

    // Topbar quick CSV export button
    const topbarExportBtn = document.getElementById("btn-topbar-export");
    if (topbarExportBtn) {
        topbarExportBtn.addEventListener("click", () => {
            const cols = [
                { label: "Ticker", key: "ticker" },
                { label: "Company", key: "company_name" },
                { label: "Filing Year", key: "filing_year" },
                { label: "Report Year", key: "report_year" },
                { label: "Filing Date", key: "filing_date" },
                { label: "LM Net Prop", key: "lm_net_prop" },
                { label: "Harvard Net Prop", key: "harvard_net_prop" },
                { label: "CAR [-1, +1]", key: "CAR_m1_p1" },
            ];
            exportToCsv("10k_sample_all.csv", cols, D.firmYear);
        });
    }

    // Findings jump links in Overview
    document.querySelectorAll(".finding-link[href^='#tab-']").forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const tabId = link.getAttribute("href").replace("#tab-", "");
            activateTab(tabId);
            const targetSection = document.getElementById(tabId);
            if (targetSection) {
                targetSection.scrollIntoView({ behavior: "smooth" });
            }
        });
    });

    // Deep linking from URL hash
    const hash = window.location.hash.replace("#", "");
    if (hash && document.getElementById("tab-" + hash)) {
        activateTab(hash, false);
    }

    window.addEventListener("hashchange", () => {
        const currentHash = window.location.hash.replace("#", "");
        if (currentHash && document.getElementById("tab-" + currentHash)) {
            activateTab(currentHash, false);
        }
    });
}

/* ==========================================================
   PAGINATION HELPER
   ========================================================== */

function paginate(data, page, perPage = 25) {
    const total = Math.max(1, Math.ceil(data.length / perPage));
    const safePage = Math.min(Math.max(1, page), total);
    const start = (safePage - 1) * perPage;
    return { rows: data.slice(start, start + perPage), page: safePage, total, count: data.length };
}

function renderPagination(containerId, info, onChange) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `
        <span>Hiển thị ${info.count === 0 ? 0 : (info.page - 1) * 25 + 1}–${Math.min(info.page * 25, info.count)} trên tổng số ${info.count.toLocaleString()} hồ sơ</span>
        <span>
            <button ${info.page <= 1 ? "disabled" : ""} data-dir="-1" aria-label="Trang trước">← Trước</button>
            <span style="margin: 0 0.5rem; font-weight: 600;">Trang ${info.page} / ${info.total}</span>
            <button ${info.page >= info.total ? "disabled" : ""} data-dir="1" aria-label="Trang sau">Sau →</button>
        </span>`;
    el.querySelectorAll("button").forEach(b => {
        b.addEventListener("click", () => onChange(info.page + parseInt(b.dataset.dir)));
    });
}

/* ==========================================================
   TAB: OVERVIEW
   ========================================================== */

function initOverview() {
    const fy = D.firmYear;
    const nTone = fy.filter(r => r.has_item7_tone || r.has_method_score).length;
    const nCar = fy.filter(r => r.has_event_car).length;
    const nC2 = D.c2.length > 0 ? D.c2[0].n : 0;
    const nFirmsC2 = D.c2.length > 0 ? D.c2[0].n_firms : 0;

    // Metric cards with Phosphor vector icons
    document.getElementById("overview-cards").innerHTML = `
        <div class="card">
            <div class="card-top">
                <p class="card-label">Hồ sơ 10-K</p>
                <span class="card-icon" aria-hidden="true">
                    <svg class="icon-svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                </span>
            </div>
            <p class="card-value">${fy.length.toLocaleString()}</p>
            <p class="card-note">100 công ty × 10 năm nộp</p>
        </div>
        <div class="card">
            <div class="card-top">
                <p class="card-label">Có tone Item 7</p>
                <span class="card-icon" aria-hidden="true">
                    <svg class="icon-svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </span>
            </div>
            <p class="card-value">${nTone.toLocaleString()}</p>
            <p class="card-note">${fy.length - nTone} hồ sơ thiếu tone</p>
        </div>
        <div class="card">
            <div class="card-top">
                <p class="card-label">Có CAR</p>
                <span class="card-icon" aria-hidden="true">
                    <svg class="icon-svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
                </span>
            </div>
            <p class="card-value">${nCar.toLocaleString()}</p>
            <p class="card-note">${fy.length - nCar} hồ sơ thiếu CAR</p>
        </div>
        <div class="card">
            <div class="card-top">
                <p class="card-label">Mẫu C2 rút gọn</p>
                <span class="card-icon" aria-hidden="true">
                    <svg class="icon-svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                </span>
            </div>
            <p class="card-value">${nC2.toLocaleString()}</p>
            <p class="card-note">${nFirmsC2} công ty, 4 biến kiểm soát</p>
        </div>`;

    // CAAR bar chart
    const evs = D.eventSummary;
    const caarCanvas = document.getElementById("chart-caar");
    if (caarCanvas) {
        const c1 = new Chart(caarCanvas, {
            type: "bar",
            data: {
                labels: evs.map(r => WIN[r.window] || r.window),
                datasets: [{
                    label: "CAAR (%)",
                    data: evs.map(r => (r.CAAR * 100)),
                    backgroundColor: evs.map(r => r.CAAR >= 0 ? "rgba(37, 99, 235, 0.85)" : "rgba(194, 65, 12, 0.85)"),
                    borderColor: evs.map(r => r.CAAR >= 0 ? "#1d4ed8" : "#9a3412"),
                    borderWidth: 1,
                    borderRadius: 6,
                    barPercentage: 0.55,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: ctx => `Cửa sổ sự kiện: ${ctx[0].label}`,
                            label: ctx => {
                                const row = evs[ctx.dataIndex];
                                return [
                                    `CAAR: ${(row.CAAR * 100).toFixed(3)}%`,
                                    `SE CAAR: ${(row.SE_CAAR * 100).toFixed(4)}%`,
                                    `p MacKinlay: ${pval(row.MacKinlay_p)} (Z = ${fmt(row.MacKinlay_Z, 3)})`,
                                    `p Sign test: ${pval(row.Sign_p)} (+/${row.Sign_positive}, -/${row.Sign_negative})`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        title: { display: true, text: "CAAR (%)", font: { weight: "600" } },
                        grid: { color: "#e2e8f0" }
                    },
                    x: {
                        title: { display: true, text: "Cửa sổ giao dịch quanh ngày nộp", font: { weight: "600" } },
                        grid: { display: false }
                    },
                },
            },
        });
        activeCharts.push(c1);
    }

    // Coverage bar chart (Horizontal sample retention)
    const covCanvas = document.getElementById("chart-coverage");
    if (covCanvas) {
        const c2 = new Chart(covCanvas, {
            type: "bar",
            data: {
                labels: ["Hồ sơ gốc", "Tone Item 7", "CAR (event study)", "C2 rút gọn"],
                datasets: [{
                    label: "Số hồ sơ (N)",
                    data: [fy.length, nTone, nCar, nC2],
                    backgroundColor: [
                        "rgba(71, 85, 105, 0.85)",
                        "rgba(37, 99, 235, 0.85)",
                        "rgba(2, 132, 199, 0.85)",
                        "rgba(124, 58, 237, 0.85)"
                    ],
                    borderColor: [
                        "#334155",
                        "#1d4ed8",
                        "#0369a1",
                        "#6d28d9"
                    ],
                    borderWidth: 1,
                    borderRadius: 6,
                    barPercentage: 0.6,
                }],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => {
                                const v = ctx.parsed.x;
                                const pctVal = ((v / fy.length) * 100).toFixed(1);
                                return `Số hồ sơ: ${v.toLocaleString()} (${pctVal}% tổng mẫu)`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: { display: true, text: "Số lượng hồ sơ (N)", font: { weight: "600" } },
                        grid: { color: "#e2e8f0" },
                        max: 1050
                    },
                    y: { grid: { display: false } },
                },
            },
        });
        activeCharts.push(c2);
    }

    // CAAR table
    renderEventSummaryTable("overview-event-table");
}

/* ==========================================================
   TAB: EVENT STUDY
   ========================================================== */

function renderEventSummaryTable(containerId) {
    renderTable(containerId, [
        { label: "Cửa sổ", key: "window", fmt: v => WIN[v] || v },
        { label: "N", key: "N", num: true },
        { label: "CAAR (%)", get: r => r.CAAR, num: true, fmt: v => pct(v) },
        { label: "SE CAAR", get: r => r.SE_CAAR, num: true, fmt: v => fmt(v, 6) },
        { label: "Z MacKinlay", key: "MacKinlay_Z", num: true, fmt: v => fmt(v, 3) },
        { label: "p MacKinlay", key: "MacKinlay_p", num: true, fmt: v => pval(v), cls: r => sigClass(r.MacKinlay_p) },
        { label: "p Sign test", key: "Sign_p", num: true, fmt: v => pval(v), cls: r => sigClass(r.Sign_p) },
        { label: "N+ / N−", get: r => `${r.Sign_positive} / ${r.Sign_negative}`, center: true },
    ], D.eventSummary);
}

function initEventStudy() {
    const evs = D.eventSummary;
    const eventNEl = document.getElementById("event-n");
    if (eventNEl) eventNEl.textContent = evs.length > 0 ? evs[0].N.toLocaleString() : "—";

    renderEventSummaryTable("event-summary-table");

    // AAR line chart with Day 0 emphasis and gradient fill
    const daily = D.eventDaily.slice().sort((a, b) => a.event_time - b.event_time);
    const aarCanvas = document.getElementById("chart-aar");
    if (aarCanvas) {
        const c3 = new Chart(aarCanvas, {
            type: "line",
            data: {
                labels: daily.map(r => r.event_time),
                datasets: [{
                    label: "AAR (%)",
                    data: daily.map(r => r.AAR * 100),
                    borderColor: "#1d4ed8",
                    borderWidth: 2,
                    backgroundColor: "rgba(37, 99, 235, 0.08)",
                    fill: true,
                    tension: 0.2,
                    pointRadius: daily.map(r => r.event_time === 0 ? 6.5 : (r.BW_p < 0.05 ? 5 : 3.5)),
                    pointHoverRadius: 7.5,
                    pointBackgroundColor: daily.map(r => r.event_time === 0 ? "#0f172a" : (r.BW_p < 0.05 ? "#1d4ed8" : "#94a3b8")),
                    pointBorderColor: "#ffffff",
                    pointBorderWidth: 1.5,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    zoom: {
                        pan: { enabled: true, mode: 'x' },
                        zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' }
                    },
                    tooltip: {
                        callbacks: {
                            title: ctx => {
                                const t = daily[ctx[0].dataIndex].event_time;
                                return t === 0 ? `Ngày t = 0 (Phiên sự kiện)` : `Ngày tương đối: t = ${t > 0 ? "+" + t : t}`;
                            },
                            label: ctx => {
                                const r = daily[ctx.dataIndex];
                                return [
                                    `AAR: ${(r.AAR * 100).toFixed(4)}%`,
                                    `Brown-Warner Z: ${fmt(r.BW_Z, 3)}`,
                                    `BW p-value: ${pval(r.BW_p)} ${r.BW_p < 0.05 ? "(p < 0.05*)" : ""}`,
                                    `Số quan sát: ${r.N}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        title: { display: true, text: "AAR (%)", font: { weight: "600" } },
                        grid: { color: "#e2e8f0" },
                    },
                    x: {
                        title: { display: true, text: "Ngày giao dịch tương đối (t = 0 là phiên sự kiện)", font: { weight: "600" } },
                        grid: { color: "#f8fafc" },
                    },
                },
            },
        });
        activeCharts.push(c3);

        // Connect AAR Zoom Buttons
        document.getElementById("btn-aar-zoomin")?.addEventListener("click", () => c3.zoom(1.25));
        document.getElementById("btn-aar-zoomout")?.addEventListener("click", () => c3.zoom(0.8));
        document.getElementById("btn-aar-reset")?.addEventListener("click", () => c3.resetZoom());
    }

    // Individual CAR [-1, +1] cross-sectional distribution (969 filings)
    const carCanvas = document.getElementById("chart-car-dist");
    if (carCanvas) {
        const carValues = D.firmYear.map(r => r.CAR_m1_p1).filter(v => v != null && isFinite(v));
        const carBins = carHistogram(carValues);

        const cCar = new Chart(carCanvas, {
            type: "bar",
            data: {
                labels: carBins.map(b => b.label),
                datasets: [{
                    label: "Số hồ sơ 10-K",
                    data: carBins.map(b => b.count),
                    backgroundColor: carBins.map(b => ((b.lo + b.hi) / 2) >= 0 ? "rgba(37, 99, 235, 0.75)" : "rgba(234, 88, 12, 0.75)"),
                    borderColor: carBins.map(b => ((b.lo + b.hi) / 2) >= 0 ? "#1d4ed8" : "#c2410c"),
                    borderWidth: 1,
                    borderRadius: 2,
                    barPercentage: 0.98,
                    categoryPercentage: 0.98
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: ctx => {
                                const b = carBins[ctx[0].dataIndex];
                                return `Khoảng CAR: ${b.label}`;
                            },
                            label: ctx => `Số lượng: ${ctx.parsed.y} hồ sơ (${((ctx.parsed.y / carValues.length) * 100).toFixed(1)}%)`
                        }
                    }
                },
                scales: {
                    x: {
                        title: { display: true, text: "CAR [-1, +1] (%)", font: { weight: "600" } },
                        grid: { display: false },
                        ticks: { maxTicksLimit: 12, font: { size: 10 } }
                    },
                    y: {
                        title: { display: true, text: "Số lượng hồ sơ 10-K", font: { weight: "600" } },
                        grid: { color: "#e2e8f0" }
                    }
                }
            }
        });
        activeCharts.push(cCar);
    }

    // Daily table
    renderTable("event-daily-table", [
        { label: "Ngày t", key: "event_time", num: true, center: true, fmt: v => v === 0 ? "<strong>0 (sự kiện)</strong>" : (v > 0 ? `+${v}` : `${v}`) },
        { label: "AAR (%)", key: "AAR", num: true, fmt: v => pct(v) },
        { label: "N", key: "N", num: true },
        { label: "BW Z", key: "BW_Z", num: true, fmt: v => fmt(v, 3) },
        { label: "BW p", key: "BW_p", num: true, fmt: v => pval(v), cls: r => sigClass(r.BW_p) },
    ], daily);

    // Exclusions
    renderTable("event-exclusions-table", [
        { label: "Ticker", key: "ticker", fmt: v => `<strong>${v}</strong>` },
        { label: "Ngày nộp", key: "filing_date" },
        { label: "Accession", key: "accession_number", fmt: v => `<code>${v}</code>` },
        { label: "Lý do loại trừ", key: "event_exclusion_reason" },
    ], D.exclusions);
}

/* ==========================================================
   TAB: REGRESSION (points 5, 6)
   ========================================================== */

function filterRegression() {
    const section = document.getElementById("reg-model").value;
    const win = document.getElementById("reg-window").value;

    let rows = D.regression.filter(r => r.section === section && r.term !== "const");
    if (win !== "all") rows = rows.filter(r => sameWindow(r.dependent_variable, win));

    const titles = {
        C1: "C1 — CAR ~ Score (đơn biến, kiểm tra độ nhạy qua các định nghĩa tone)",
        C3: "C3 — CAR ~ LM positive + LM negative (tách riêng từ tích cực và tiêu cực)",
        C4: "C4 — CAR ~ LM net + Harvard net (đối chứng từ điển tổng quát)",
    };
    document.getElementById("reg-title").textContent = titles[section] || section;

    renderTable("reg-table", [
        { label: "Cửa sổ", key: "dependent_variable", fmt: v => WIN[v] || v },
        { label: "Biến", key: "term" },
        { label: "Score", key: "score_definition", fmt: v => v || "—" },
        { label: "N", key: "n", num: true },
        { label: "Hệ số", key: "coefficient", num: true, fmt: (v) => signSpan(v) },
        { label: "SE HC3", key: "se_hc3", num: true, fmt: v => fmt(v, 6) },
        { label: "p HC3", key: "p_hc3_two_sided", num: true, fmt: v => pval(v), cls: r => sigClass(r.p_hc3_two_sided) },
        { label: "SE cluster", key: "se_cluster", num: true, fmt: v => fmt(v, 6) },
        { label: "p cluster", key: "p_cluster_two_sided", num: true, fmt: v => pval(v), cls: r => sigClass(r.p_cluster_two_sided) },
        { label: "R²", key: "r_squared", num: true, fmt: v => fmt(v, 4) },
    ], rows);
}

let regCoefChart = null;

function renderRegressionCoefChart(windowKey = "CAR_m1_p1") {
    const canvas = document.getElementById("chart-reg-coef");
    if (!canvas) return;

    // Filter C2 rows for selected window, excluding intercept 'const'
    const selectedWindow = windowKey === "all" ? "CAR_m1_p1" : windowKey;
    const rows = D.c2.filter(r => sameWindow(r.dependent_variable, selectedWindow) && r.term !== "const");
    document.getElementById("reg-coef-window").textContent = WIN[selectedWindow] || selectedWindow;
    if (rows.length === 0) return;

    const termLabels = {
        lm_net_prop: "LM net_prop (Tone MD&A)",
        size: "Size (Quy mô ln(MV))",
        bm: "B/M (Book-to-Market)",
        volatility: "Volatility (Biến động giá)",
        turnover: "Turnover (Thanh khoản cổ phiếu)"
    };

    const labels = rows.map(r => termLabels[r.term] || r.term);
    const coefs = rows.map(r => r.coefficient);

    if (regCoefChart) {
        regCoefChart.destroy();
        const idx = activeCharts.indexOf(regCoefChart);
        if (idx > -1) activeCharts.splice(idx, 1);
    }

    regCoefChart = new Chart(canvas, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Hệ số OLS",
                    data: coefs,
                    backgroundColor: coefs.map((v, i) => {
                        const p = rows[i].p_hc3_two_sided;
                        return p < 0.05 ? "rgba(37, 99, 235, 0.85)" : (p < 0.10 ? "rgba(124, 58, 237, 0.75)" : "rgba(148, 163, 184, 0.65)");
                    }),
                    borderColor: coefs.map((v, i) => {
                        const p = rows[i].p_hc3_two_sided;
                        return p < 0.05 ? "#1d4ed8" : (p < 0.10 ? "#6d28d9" : "#64748b");
                    }),
                    borderWidth: 1,
                    borderRadius: 4,
                    barPercentage: 0.55
                }
            ]
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: ctx => labels[ctx[0].dataIndex],
                        label: ctx => {
                            const r = rows[ctx.dataIndex];
                            return [
                                `Hệ số: ${fmt(r.coefficient, 4)}`,
                                `SE HC3: ${fmt(r.se_hc3, 4)}`,
                                `p-value HC3: ${pval(r.p_hc3_two_sided)} ${r.p_hc3_two_sided < 0.05 ? '(p < 0.05*)' : (r.p_hc3_two_sided < 0.1 ? '(p < 0.10**)' : '')}`,
                                `CI 95% HC3: [${fmt(r.ci_hc3_low, 4)}; ${fmt(r.ci_hc3_high, 4)}]`,
                                `p-value cluster: ${pval(r.p_cluster_two_sided)}`
                            ];
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: "Hệ số ước lượng (Beta) — Kiểm định độ dốc", font: { weight: "600" } },
                    grid: { color: "#e2e8f0" }
                },
                y: {
                    grid: { display: false },
                    ticks: { font: { weight: "600", size: 11 } }
                }
            }
        },
        plugins: [{
            id: "zeroLine",
            afterDraw: (chart) => {
                const { ctx, chartArea: { top, bottom, left, right }, scales: { x } } = chart;
                const x0 = x.getPixelForValue(0);
                if (x0 >= left && x0 <= right) {
                    ctx.save();
                    ctx.strokeStyle = "rgba(15, 23, 42, 0.45)";
                    ctx.lineWidth = 1.5;
                    ctx.setLineDash([4, 3]);
                    ctx.beginPath();
                    ctx.moveTo(x0, top);
                    ctx.lineTo(x0, bottom);
                    ctx.stroke();
                    ctx.restore();
                }
            }
        }]
    });
    activeCharts.push(regCoefChart);
}

function initRegression() {
    document.getElementById("reg-model").addEventListener("change", filterRegression);
    document.getElementById("reg-window").addEventListener("change", () => {
        filterRegression();
        const win = document.getElementById("reg-window").value;
        renderRegressionCoefChart(win === "all" ? "CAR_m1_p1" : win);
    });
    filterRegression();
    renderRegressionCoefChart("CAR_m1_p1");

    // C2 summary (tone coef only)
    const c2tone = D.c2.filter(r => r.term === "lm_net_prop");
    if (c2tone.length > 0) {
        document.getElementById("c2-n").textContent = c2tone[0].n.toLocaleString();
        document.getElementById("c2-firms").textContent = c2tone[0].n_firms.toLocaleString();
    }

    renderTable("c2-table", [
        { label: "Cửa sổ", key: "dependent_variable", fmt: v => WIN[v] || v },
        { label: "N", key: "n", num: true },
        { label: "Hệ số tone", key: "coefficient", num: true, fmt: (v) => signSpan(v) },
        { label: "SE HC3", key: "se_hc3", num: true, fmt: v => fmt(v, 6) },
        { label: "p HC3", key: "p_hc3_two_sided", num: true, fmt: v => pval(v), cls: r => sigClass(r.p_hc3_two_sided) },
        { label: "CI 95% HC3", get: r => `[${fmt(r.ci_hc3_low, 4)}; ${fmt(r.ci_hc3_high, 4)}]`, num: true },
        { label: "SE cluster", key: "se_cluster", num: true, fmt: v => fmt(v, 6) },
        { label: "p cluster", key: "p_cluster_two_sided", num: true, fmt: v => pval(v), cls: r => sigClass(r.p_cluster_two_sided) },
        { label: "R²", key: "r_squared", num: true, fmt: v => fmt(v, 4) },
    ], c2tone);

    document.getElementById("extended-model").addEventListener("change", renderExtendedResults);
    renderExtendedResults();
}

function renderExtendedResults() {
    const key = document.getElementById("extended-model").value;
    let rows = D[key] || [];
    const notes = {
        wordPower: "H1/H2 chính, CAR [0,+3]. p một phía kiểm tra dấu kỳ vọng dương; trọng số từ tiêu cực dùng ridge. Các kết quả không đạt mức 5%.",
        c2Full6: "LM tone tỷ lệ; sáu biến kiểm soát, 481 hồ sơ / 71 công ty. Đây không phải Word Power.",
        c2Matched4: "Bốn biến kiểm soát ước lượng lại trên cùng 481 hồ sơ để so sánh công bằng với C2 sáu biến.",
        b6: "Kiểm định chuẩn hóa và phương sai cắt ngang cho CAAR ở bốn cửa sổ; không kiểm định hệ số tone.",
        brownWarner: "Brown–Warner và hiệu chỉnh tự tương quan B7 ở bốn cửa sổ; không kiểm định hệ số tone.",
        c5Full6: "Các yếu tố quyết định tone; mẫu có tone năm trước và đủ sáu biến kiểm soát.",
        c6: "Phản ứng chậm sau công bố, với các cửa sổ bắt đầu từ phiên +5.",
        c7: "Hồi quy cắt ngang AR ngày 0; bảng gồm các đặc tả được tính riêng.",
        c8: "Fama–MacBeth: trung bình hệ số qua 10 năm nộp; p hai phía."
    };
    document.getElementById("extended-note").textContent = notes[key] || "";

    if (key === "wordPower") {
        const primary = new Set(["C1_H1_WP_positive", "C1_H2_WP_negative",
            "C2_H1_WP_positive_six_controls", "C2_H2_WP_negative_six_controls"]);
        rows = rows.filter(r => primary.has(r.model) && r.dependent_variable === "car_0_p3" && r.term !== "const");
    }
    const columns = key === "b6" ? [
        { label: "Cửa sổ", key: "window", fmt: v => WIN[v] || v },
        { label: "N", key: "n", num: true },
        { label: "CAAR", key: "caar", num: true, fmt: v => fmt(v, 6) },
        { label: "z chuẩn hóa", key: "standardized_z", num: true, fmt: v => fmt(v, 4) },
        { label: "p chuẩn hóa", key: "standardized_p", num: true, fmt: pval },
        { label: "z phương sai cắt ngang", key: "cross_sectional_z", num: true, fmt: v => fmt(v, 4) },
        { label: "p phương sai cắt ngang", key: "cross_sectional_p", num: true, fmt: pval }
    ] : key === "brownWarner" ? [
        { label: "Cửa sổ", key: "window", fmt: v => WIN[v] || v },
        { label: "N ngày", key: "n_event_days", num: true },
        { label: "CAAR", key: "caar", num: true, fmt: v => fmt(v, 6) },
        { label: "Brown–Warner z", key: "brown_warner_z", num: true, fmt: v => fmt(v, 4) },
        { label: "p Brown–Warner", key: "brown_warner_p", num: true, fmt: pval },
        { label: "p tự tương quan", key: "autocorr_p", num: true, fmt: pval }
    ] : key === "c8" ? [
        { label: "Mô hình", key: "model" },
        { label: "Biến phụ thuộc", key: "dependent_variable", fmt: v => WIN[v] || v },
        { label: "Biến", key: "term" },
        { label: "Số năm", key: "n_years", num: true },
        { label: "Hệ số TB", key: "mean_coefficient", num: true, fmt: signSpan },
        { label: "p hai phía", key: "p_two_sided", num: true, fmt: pval }
    ] : [
        { label: "Mô hình", key: "model" },
        { label: "Cửa sổ / biến phụ thuộc", key: "dependent_variable", fmt: v => WIN[v] || v },
        { label: "Biến", key: "term" },
        { label: "N", key: "n", num: true },
        { label: "Công ty", key: "n_firms", num: true },
        { label: "Hệ số", key: "coefficient", num: true, fmt: signSpan },
        { label: "p HC3", key: "p_hc3_two_sided", num: true, fmt: pval },
        { label: "p cụm", key: "p_cluster_two_sided", num: true, fmt: pval },
        ...(key === "wordPower" ? [{ label: "p HC3 một phía", key: "p_hc3_one_sided", num: true, fmt: pval }] : [])
    ];
    renderTable("extended-table", columns, rows);
}

/* ==========================================================
   TAB: DICTIONARY (point 6 — LM primary, Harvard control)
   ========================================================== */

let dictPage = 1;
let dictFiltered = D.dictFilings;
let dictSort = { key: "ticker", dir: "asc" };

function filterDictFilings() {
    const ticker = document.getElementById("dict-ticker").value;
    const sign = document.getElementById("dict-sign").value;
    dictFiltered = D.dictFilings.filter(r => {
        if (ticker && r.ticker !== ticker) return false;
        if (sign === "true" && !r.opposite_sign) return false;
        if (sign === "false" && r.opposite_sign) return false;
        return true;
    });

    // Apply active sort
    if (dictSort.key) {
        dictFiltered.sort((a, b) => {
            let va = a[dictSort.key];
            let vb = b[dictSort.key];
            if (va == null && vb == null) return 0;
            if (va == null) return 1;
            if (vb == null) return -1;
            if (typeof va === "number" && typeof vb === "number") {
                return dictSort.dir === "asc" ? va - vb : vb - va;
            }
            if (typeof va === "boolean" && typeof vb === "boolean") {
                return dictSort.dir === "asc" ? (va === vb ? 0 : va ? 1 : -1) : (va === vb ? 0 : va ? -1 : 1);
            }
            return dictSort.dir === "asc"
                ? String(va).localeCompare(String(vb))
                : String(vb).localeCompare(String(va));
        });
    }

    dictPage = 1;

    const countEl = document.getElementById("dict-count");
    if (countEl) countEl.textContent = `Hiển thị ${dictFiltered.length.toLocaleString()} trên tổng số ${D.dictFilings.length.toLocaleString()} hồ sơ`;

    renderDictPage();
}

function renderDictPage() {
    const info = paginate(dictFiltered, dictPage);
    renderTable("dict-filings-table", [
        { label: "Ticker", key: "ticker", sortable: true, fmt: v => `<strong>${v}</strong>` },
        { label: "Công ty", key: "company_name", sortable: true },
        { label: "Ngày nộp", key: "filing_date", sortable: true },
        { label: "LM net_prop", key: "lm_net_prop", num: true, sortable: true, fmt: v => signSpan(v) },
        { label: "Harvard net_prop", key: "harvard_net_prop", num: true, sortable: true, fmt: v => signSpan(v) },
        { label: "Harvard − LM", key: "harvard_minus_lm", num: true, sortable: true, fmt: v => fmt(v, 4) },
        { label: "Trái dấu", key: "opposite_sign", center: true, sortable: true, fmt: v => v ? '<span class="badge badge-warn">Trái dấu</span>' : '<span class="badge badge-ok">Không trái dấu</span>' },
    ], info.rows, {
        currentSort: dictSort,
        onSort: (key) => {
            if (dictSort.key === key) {
                dictSort.dir = dictSort.dir === "asc" ? "desc" : "asc";
            } else {
                dictSort.key = key;
                dictSort.dir = "asc";
            }
            filterDictFilings();
        }
    });
    renderPagination("dict-pag", info, p => { dictPage = p; renderDictPage(); });
}

function initDictionary() {
    const ds = D.dictSummary;
    const sharePct = ds.share_opposite_sign != null ? (ds.share_opposite_sign * 100).toFixed(1) + "%" : "—";
    document.getElementById("dict-interpretation").textContent =
        `${sharePct} (${ds.n_opposite_sign} / ${ds.n_comparable_filings} hồ sơ) có điểm LM và Harvard trái dấu. ` +
        `Điểm trung bình LM là ${fmt(ds.mean_lm_net_prop, 4)}, Harvard là ${fmt(ds.mean_harvard_net_prop, 4)}. ` +
        "Đây là khác biệt giữa hai thước đo; chưa xác định từ điển nào đúng cho từng ngữ cảnh.";

    document.getElementById("dict-cards").innerHTML = `
        <div class="card">
            <div class="card-top">
                <p class="card-label">Hồ sơ so sánh</p>
                <span class="card-icon" aria-hidden="true">
                    <svg class="icon-svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                </span>
            </div>
            <p class="card-value">${ds.n_comparable_filings.toLocaleString()}</p>
            <p class="card-note">Có cả điểm LM và Harvard</p>
        </div>
        <div class="card">
            <div class="card-top">
                <p class="card-label">Trái dấu</p>
                <span class="card-icon" aria-hidden="true">
                    <svg class="icon-svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>
                </span>
            </div>
            <p class="card-value">${ds.n_opposite_sign.toLocaleString()}</p>
            <p class="card-note">${sharePct} hồ sơ</p>
        </div>
        <div class="card">
            <div class="card-top">
                <p class="card-label">Mean LM net_prop</p>
                <span class="card-icon" aria-hidden="true">
                    <svg class="icon-svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>
                </span>
            </div>
            <p class="card-value" style="font-size:1.35rem">${fmt(ds.mean_lm_net_prop, 4)}</p>
            <p class="card-note">Thiên về âm (thận trọng)</p>
        </div>
        <div class="card">
            <div class="card-top">
                <p class="card-label">Mean Harvard net_prop</p>
                <span class="card-icon" aria-hidden="true">
                    <svg class="icon-svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                </span>
            </div>
            <p class="card-value" style="font-size:1.35rem">${fmt(ds.mean_harvard_net_prop, 4)}</p>
            <p class="card-note">Thiên về dương</p>
        </div>`;

    document.getElementById("scatter-n").textContent = D.dictFilings.length.toLocaleString();

    // Populate ticker dropdown
    const tickers = [...new Set(D.dictFilings.map(r => r.ticker))].sort();
    const sel = document.getElementById("dict-ticker");
    tickers.forEach(t => { const o = document.createElement("option"); o.value = t; o.textContent = t; sel.appendChild(o); });

    document.getElementById("dict-ticker").addEventListener("change", filterDictFilings);
    document.getElementById("dict-sign").addEventListener("change", filterDictFilings);

    const dictResetBtn = document.getElementById("dict-reset");
    if (dictResetBtn) {
        dictResetBtn.addEventListener("click", () => {
            document.getElementById("dict-ticker").value = "";
            document.getElementById("dict-sign").value = "";
            dictSort = { key: "ticker", dir: "asc" };
            filterDictFilings();
        });
    }

    const dictExportBtn = document.getElementById("dict-export");
    if (dictExportBtn) {
        dictExportBtn.addEventListener("click", () => {
            const cols = [
                { label: "Ticker", key: "ticker" },
                { label: "Company", key: "company_name" },
                { label: "Filing Date", key: "filing_date" },
                { label: "LM Net Prop", key: "lm_net_prop" },
                { label: "Harvard Net Prop", key: "harvard_net_prop" },
                { label: "Harvard Minus LM", key: "harvard_minus_lm" },
                { label: "Opposite Sign", key: "opposite_sign" },
            ];
            exportToCsv("dictionary_comparison_filtered.csv", cols, dictFiltered);
        });
    }

    // Function to populate Scatter Point Inspector Card
    function showScatterInspector(f) {
        const card = document.getElementById("scatter-inspect-card");
        if (!card) return;
        card.style.display = "block";

        const signBadge = f.opposite_sign
            ? '<span class="badge badge-warn">Trái dấu (LM &lt; 0, Harvard &gt; 0)</span>'
            : '<span class="badge badge-ok">Không trái dấu</span>';

        const carVal = f.CAR_m1_p1 != null ? pct(f.CAR_m1_p1) : "—";

        card.innerHTML = `
            <div class="inspect-header">
                <div class="inspect-title-wrap">
                    <span class="inspect-ticker">${f.ticker}</span>
                    <span class="inspect-company">${f.company_name || ""}</span>
                </div>
                <div class="inspect-badges">
                    ${signBadge}
                    <span class="meta-chip"><span class="chip-label">Ngày nộp:</span> <span class="chip-val">${f.filing_date}</span></span>
                </div>
            </div>
            <div class="inspect-grid">
                <div class="inspect-item">
                    <div class="inspect-k">LM net_prop (Chuyên ngành tài chính)</div>
                    <div class="inspect-v">${signSpan(f.lm_net_prop)}</div>
                </div>
                <div class="inspect-item">
                    <div class="inspect-k">Harvard net_prop (Tổng quát)</div>
                    <div class="inspect-v">${signSpan(f.harvard_net_prop)}</div>
                </div>
                <div class="inspect-item">
                    <div class="inspect-k">Chênh lệch (Harvard − LM)</div>
                    <div class="inspect-v" style="color:var(--marginal)">${fmt(f.harvard_minus_lm, 4)}</div>
                </div>
                <div class="inspect-item">
                    <div class="inspect-k">Phản ứng giá CAR [-1, +1]</div>
                    <div class="inspect-v">${carVal}</div>
                </div>
            </div>
            <div class="inspect-footer">
                ${f.sec_url ? `
                    <a href="${f.sec_url}" target="_blank" rel="noopener noreferrer" class="inspect-sec-link">
                        <span>Mở hồ sơ 10-K gốc trên SEC EDGAR</span>
                        <svg class="icon-svg" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                    </a>` : '<span></span>'}
                <button type="button" class="btn-inspect-action" id="btn-inspect-filter-ticker" data-ticker="${f.ticker}">
                    <span>Lọc bảng theo mã ${f.ticker}</span>
                    <svg class="icon-svg" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                </button>
            </div>
        `;

        document.getElementById("btn-inspect-filter-ticker")?.addEventListener("click", () => {
            const tickerSel = document.getElementById("dict-ticker");
            if (tickerSel) {
                tickerSel.value = f.ticker;
                filterDictFilings();
                showToast(`Đã lọc bảng chi tiết theo ticker: ${f.ticker}`);
                const tableSection = document.getElementById("dict-filings-table");
                if (tableSection) tableSection.scrollIntoView({ behavior: "smooth" });
            }
        });
    }

    // Scatter chart with rich tooltip data, zoom & reference lines
    const same = D.dictFilings.filter(r => !r.opposite_sign).map(r => ({ x: r.lm_net_prop, y: r.harvard_net_prop, filing: r }));
    const opp = D.dictFilings.filter(r => r.opposite_sign).map(r => ({ x: r.lm_net_prop, y: r.harvard_net_prop, filing: r }));

    const scatterCanvas = document.getElementById("chart-scatter");
    if (scatterCanvas) {
        const c4 = new Chart(scatterCanvas, {
            type: "scatter",
            data: {
                datasets: [
                    {
                        label: "Không trái dấu (●, gồm điểm bằng 0)",
                        data: same,
                        backgroundColor: "rgba(37, 99, 235, 0.65)",
                        borderColor: "#1d4ed8",
                        borderWidth: 0.5,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        pointStyle: "circle"
                    },
                    {
                        label: "Trái dấu (◇)",
                        data: opp,
                        backgroundColor: "rgba(234, 88, 12, 0.6)",
                        borderColor: "#9a3412",
                        borderWidth: 0.5,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        pointStyle: "rectRot"
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (event, elements) => {
                    if (!elements || elements.length === 0) return;
                    const el = elements[0];
                    const dataset = c4.data.datasets[el.datasetIndex];
                    const point = dataset?.data[el.index];
                    if (point && point.filing) {
                        showScatterInspector(point.filing);
                    }
                },
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { font: { size: 11, weight: "600" }, padding: 15 }
                    },
                    zoom: {
                        pan: {
                            enabled: true,
                            mode: 'xy',
                        },
                        zoom: {
                            wheel: {
                                enabled: true,
                                speed: 0.1
                            },
                            pinch: {
                                enabled: true
                            },
                            mode: 'xy'
                        }
                    },
                    tooltip: {
                        callbacks: {
                            title: ctx => {
                                const f = ctx[0].raw.filing;
                                return f ? `${f.ticker} (${f.company_name}) · ${f.filing_date}` : "";
                            },
                            label: ctx => {
                                const f = ctx.raw.filing;
                                return [
                                    `LM net_prop: ${f.lm_net_prop > 0 ? "+" : ""}${fmt(f.lm_net_prop, 4)}`,
                                    `Harvard net_prop: ${f.harvard_net_prop > 0 ? "+" : ""}${fmt(f.harvard_net_prop, 4)}`,
                                    `Chênh lệch (H − LM): ${fmt(f.harvard_minus_lm, 4)}`,
                                    `Trạng thái: ${f.opposite_sign ? "Trái dấu" : "Không trái dấu"}`,
                                    `👉 Bấm điểm để xem thẻ chi tiết`
                                ];
                            }
                        }
                    },
                },
                scales: {
                    x: {
                        title: { display: true, text: "LM net_prop (từ điển tài chính chuyên ngành — chính)", font: { weight: "600" } },
                        grid: { color: "#e2e8f0" }
                    },
                    y: {
                        title: { display: true, text: "Harvard net_prop (từ điển tổng quát — đối chứng)", font: { weight: "600" } },
                        grid: { color: "#e2e8f0" }
                    },
                },
            },
            plugins: [{
                id: "scatterRefLines",
                afterDraw: (chart) => {
                    const { ctx, chartArea: { left, right, top, bottom }, scales: { x, y } } = chart;
                    ctx.save();

                    // Reference line x = 0 (vertical)
                    const x0 = x.getPixelForValue(0);
                    if (x0 >= left && x0 <= right) {
                        ctx.strokeStyle = "rgba(100, 116, 139, 0.4)";
                        ctx.lineWidth = 1.5;
                        ctx.setLineDash([4, 4]);
                        ctx.beginPath();
                        ctx.moveTo(x0, top);
                        ctx.lineTo(x0, bottom);
                        ctx.stroke();
                    }

                    // Reference line y = 0 (horizontal)
                    const y0 = y.getPixelForValue(0);
                    if (y0 >= top && y0 <= bottom) {
                        ctx.strokeStyle = "rgba(100, 116, 139, 0.4)";
                        ctx.lineWidth = 1.5;
                        ctx.setLineDash([4, 4]);
                        ctx.beginPath();
                        ctx.moveTo(left, y0);
                        ctx.lineTo(right, y0);
                        ctx.stroke();
                    }

                    // 45-degree diagonal line y = x (neutral line where LM = Harvard)
                    const minVal = Math.max(x.min, y.min);
                    const maxVal = Math.min(x.max, y.max);
                    const px1 = x.getPixelForValue(minVal);
                    const py1 = y.getPixelForValue(minVal);
                    const px2 = x.getPixelForValue(maxVal);
                    const py2 = y.getPixelForValue(maxVal);
                    if (isFinite(px1) && isFinite(py1) && isFinite(px2) && isFinite(py2)) {
                        ctx.strokeStyle = "rgba(139, 92, 246, 0.35)";
                        ctx.lineWidth = 1.2;
                        ctx.setLineDash([3, 4]);
                        ctx.beginPath();
                        ctx.moveTo(px1, py1);
                        ctx.lineTo(px2, py2);
                        ctx.stroke();
                    }

                    ctx.restore();
                }
            }]
        });
        activeCharts.push(c4);

        // Connect Scatter Zoom Controls
        document.getElementById("btn-scatter-zoomin")?.addEventListener("click", () => c4.zoom(1.25));
        document.getElementById("btn-scatter-zoomout")?.addEventListener("click", () => c4.zoom(0.8));
        document.getElementById("btn-scatter-reset")?.addEventListener("click", () => c4.resetZoom());
    }

    // Histogram
    const diffs = D.dictFilings.map(r => r.harvard_minus_lm).filter(v => v != null);
    const binCount = 30;
    const min = Math.min(...diffs), max = Math.max(...diffs);
    const binWidth = (max - min) / binCount;
    const bins = Array.from({ length: binCount }, (_, i) => ({ lo: min + i * binWidth, count: 0 }));
    diffs.forEach(v => {
        let idx = Math.floor((v - min) / binWidth);
        if (idx >= binCount) idx = binCount - 1;
        bins[idx].count++;
    });

    const histCanvas = document.getElementById("chart-hist");
    if (histCanvas) {
        const c5 = new Chart(histCanvas, {
            type: "bar",
            data: {
                labels: bins.map(b => (b.lo + binWidth / 2).toFixed(3)),
                datasets: [{
                    label: "Số hồ sơ",
                    data: bins.map(b => b.count),
                    backgroundColor: "rgba(124, 58, 237, 0.8)",
                    borderColor: "#6d28d9",
                    borderWidth: 1,
                    borderRadius: 3,
                    barPercentage: 1,
                    categoryPercentage: 1
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: ctx => {
                                const b = bins[ctx[0].dataIndex];
                                return `Khoảng: [${b.lo.toFixed(4)}; ${(b.lo + binWidth).toFixed(4)}]`;
                            },
                            label: ctx => `Số lượng: ${ctx.parsed.y} hồ sơ`
                        }
                    },
                },
                scales: {
                    x: {
                        title: { display: true, text: "Chênh lệch (Harvard net_prop − LM net_prop)", font: { weight: "600" } },
                        grid: { display: false },
                        ticks: { maxTicksLimit: 10, font: { size: 10 } }
                    },
                    y: {
                        title: { display: true, text: "Số lượng hồ sơ", font: { weight: "600" } },
                        grid: { color: "#e2e8f0" }
                    },
                },
            },
        });
        activeCharts.push(c5);
    }

    filterDictFilings();
}

/* ==========================================================
   TAB: FILINGS (points 2, 3, 4, 7)
   ========================================================== */

let filPage = 1;
let filFiltered = D.firmYear;
let filSort = { key: "ticker", dir: "asc" };

function getFilingSignal(r) {
    if (!r) return { code: "miss", label: "Thiếu tone", class: "badge-miss", icon: "—", rank: 4 };
    const hasTone = r.has_item7_tone || r.has_method_score || (r.lm_net_prop != null);
    if (!hasTone || r.lm_net_prop == null) {
        return { code: "miss", label: "Thiếu tone", class: "badge-miss", icon: "—", rank: 4 };
    }
    if (r.lm_net_prop > 0) {
        return { code: "pos", label: "Tích cực", class: "badge-signal badge-signal-pos", icon: "▲", rank: 1 };
    }
    if (r.lm_net_prop < 0) {
        return { code: "neg", label: "Tiêu cực", class: "badge-signal badge-signal-neg", icon: "▼", rank: 3 };
    }
    return { code: "zero", label: "Trung tính", class: "badge-signal badge-signal-neu", icon: "●", rank: 2 };
}
window.getFilingSignal = getFilingSignal;

function updateFilingsMicroStats(filtered) {
    const el = document.getElementById("fil-micro-stats");
    if (!el) return;

    const nTotal = filtered.length;
    if (nTotal === 0) {
        el.innerHTML = '<span class="micro-stat-label">Không có quan sát phù hợp</span>';
        return;
    }

    let nPos = 0, nNeg = 0, nZero = 0, nMiss = 0;
    filtered.forEach(r => {
        const s = getFilingSignal(r);
        if (s.code === "pos") nPos++;
        else if (s.code === "neg") nNeg++;
        else if (s.code === "zero") nZero++;
        else nMiss++;
    });

    const tones = filtered.map(r => r.lm_net_prop).filter(v => v != null);
    const meanTone = tones.length > 0 ? (tones.reduce((a, b) => a + b, 0) / tones.length) : null;

    const cars = filtered.map(r => r.CAR_m1_p1).filter(v => v != null);
    const meanCar = cars.length > 0 ? (cars.reduce((a, b) => a + b, 0) / cars.length) : null;

    el.innerHTML = `
        <div class="micro-stat-item">
            <span class="micro-stat-label">Đang xem:</span>
            <span class="micro-stat-val">${nTotal.toLocaleString()}</span>
            <span style="color:var(--text-muted);font-size:0.7rem">(${(nTotal / D.firmYear.length * 100).toFixed(1)}% mẫu)</span>
        </div>
        <div class="micro-stat-item" title="Hồ sơ có LM net_prop > 0 (Tích cực)">
            <span class="micro-stat-label">🟢 Tích cực:</span>
            <span class="micro-stat-val" style="color:#059669">${nPos.toLocaleString()}</span>
            <span style="color:var(--text-muted);font-size:0.7rem">(${(nPos / nTotal * 100).toFixed(1)}%)</span>
        </div>
        <div class="micro-stat-item" title="Hồ sơ có LM net_prop == 0 (Trung tính)">
            <span class="micro-stat-label">⚪ Trung tính:</span>
            <span class="micro-stat-val" style="color:var(--text-secondary)">${nZero.toLocaleString()}</span>
            <span style="color:var(--text-muted);font-size:0.7rem">(${(nZero / nTotal * 100).toFixed(1)}%)</span>
        </div>
        <div class="micro-stat-item" title="Hồ sơ có LM net_prop < 0 (Tiêu cực)">
            <span class="micro-stat-label">🔴 Tiêu cực:</span>
            <span class="micro-stat-val" style="color:#dc2626">${nNeg.toLocaleString()}</span>
            <span style="color:var(--text-muted);font-size:0.7rem">(${(nNeg / nTotal * 100).toFixed(1)}%)</span>
        </div>
        <div class="micro-stat-item" title="Hồ sơ thiếu Item 7 MD&A">
            <span class="micro-stat-label">⚠️ Thiếu:</span>
            <span class="micro-stat-val" style="color:var(--text-muted)">${nMiss.toLocaleString()}</span>
            <span style="color:var(--text-muted);font-size:0.7rem">(${(nMiss / nTotal * 100).toFixed(1)}%)</span>
        </div>
        <div class="micro-stat-item">
            <span class="micro-stat-label">Mean Tone:</span>
            <span class="micro-stat-val">${meanTone != null ? (meanTone > 0 ? "+" : "") + meanTone.toFixed(4) : "—"}</span>
        </div>
        <div class="micro-stat-item">
            <span class="micro-stat-label">Mean CAR [-1,+1]:</span>
            <span class="micro-stat-val">${meanCar != null ? (meanCar * 100).toFixed(3) + "%" : "—"}</span>
        </div>
    `;
}

function filterFilings() {
    const searchVal = (document.getElementById("fil-search")?.value || "").trim().toLowerCase();
    const ticker = document.getElementById("fil-ticker").value;
    const year = document.getElementById("fil-year").value;
    const status = document.getElementById("fil-status").value;
    const tone = document.getElementById("fil-tone").value;

    filFiltered = D.firmYear.filter(r => {
        if (searchVal) {
            const mTicker = r.ticker && r.ticker.toLowerCase().includes(searchVal);
            const mComp = r.company_name && r.company_name.toLowerCase().includes(searchVal);
            if (!mTicker && !mComp) return false;
        }
        if (ticker && r.ticker !== ticker) return false;
        if (year && r.filing_year !== parseInt(year)) return false;
        if (status === "has" && !(r.has_item7_tone || r.has_method_score)) return false;
        if (status === "miss" && (r.has_item7_tone || r.has_method_score)) return false;
        if (tone === "pos" && !(r.lm_net_prop != null && r.lm_net_prop > 0)) return false;
        if (tone === "neg" && !(r.lm_net_prop != null && r.lm_net_prop < 0)) return false;
        if (tone === "zero" && !(r.lm_net_prop != null && r.lm_net_prop === 0)) return false;
        if (tone === "miss" && (r.lm_net_prop != null)) return false;
        return true;
    });

    // Apply active sort
    if (filSort.key === "signal") {
        filFiltered.sort((a, b) => {
            const sa = getFilingSignal(a).rank;
            const sb = getFilingSignal(b).rank;
            return filSort.dir === "asc" ? sa - sb : sb - sa;
        });
    } else if (filSort.key) {
        filFiltered.sort((a, b) => {
            let va = a[filSort.key];
            let vb = b[filSort.key];
            if (va == null && vb == null) return 0;
            if (va == null) return 1;
            if (vb == null) return -1;
            if (typeof va === "number" && typeof vb === "number") {
                return filSort.dir === "asc" ? va - vb : vb - va;
            }
            if (typeof va === "boolean" && typeof vb === "boolean") {
                return filSort.dir === "asc" ? (va === vb ? 0 : va ? 1 : -1) : (va === vb ? 0 : va ? -1 : 1);
            }
            return filSort.dir === "asc"
                ? String(va).localeCompare(String(vb))
                : String(vb).localeCompare(String(va));
        });
    }

    // Show/hide tone grouping note (point 3)
    document.getElementById("fil-tone-note").style.display = tone ? "block" : "none";

    // Update counter with accessible phrase
    const countEl = document.getElementById("fil-count");
    if (countEl) countEl.textContent = `Hiển thị ${filFiltered.length.toLocaleString()} trên tổng số ${D.firmYear.length.toLocaleString()} hồ sơ`;

    updateFilingsMicroStats(filFiltered);

    filPage = 1;
    renderFilPage();
}

function renderFilPage() {
    const info = paginate(filFiltered, filPage);
    renderTable("filings-table", [
        { label: "Ticker", key: "ticker", sortable: true, fmt: v => `<strong>${v}</strong>` },
        { label: "Công ty", key: "company_name", sortable: true },
        { label: "Năm nộp", key: "filing_year", num: true, sortable: true },
        { label: "Năm TC", key: "report_year", num: true, sortable: true },
        { label: "Ngày nộp", key: "filing_date", sortable: true },
        { 
            label: "Tín hiệu Tone", 
            key: "signal", 
            sortable: true, 
            fmt: (v, r) => {
                const s = getFilingSignal(r);
                return `<span class="badge ${s.class}" title="Điểm LM net_prop: ${r.lm_net_prop != null ? (r.lm_net_prop > 0 ? "+" : "") + r.lm_net_prop.toFixed(5) : "Không có"}">${s.icon} ${s.label}</span>`;
            }
        },
        { label: "Status", key: "item_7_mda_lm_status", sortable: true, fmt: v => {
            if (v === "success") return '<span class="badge badge-ok">success</span>';
            if (v == null) return '<span class="badge badge-miss">—</span>';
            return `<span class="badge badge-warn">${v}</span>`;
        }},
        { label: "LM net_prop", key: "lm_net_prop", num: true, sortable: true, fmt: v => v != null ? signSpan(v) : "—" },
        { label: "Harvard net_prop", key: "harvard_net_prop", num: true, sortable: true, fmt: v => v != null ? signSpan(v) : "—" },
        { label: "CAR [-1,+1] (%)", key: "CAR_m1_p1", num: true, sortable: true, fmt: v => v != null ? pct(v) : "—" },
        { label: "CAR", key: "has_event_car", center: true, sortable: true, fmt: v => v ? "✓" : "—" },
        { label: "SEC", key: "sec_url", fmt: v => v ? `
            <a href="${v}" target="_blank" rel="noopener noreferrer" aria-label="Xem hồ sơ 10-K trên SEC EDGAR (mở tab mới)">
                10-K <svg class="icon-svg" viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </a>` : "—" 
        },
    ], info.rows, {
        currentSort: filSort,
        onSort: (key) => {
            if (filSort.key === key) {
                filSort.dir = filSort.dir === "asc" ? "desc" : "asc";
            } else {
                filSort.key = key;
                filSort.dir = "asc";
            }
            filterFilings();
        }
    });
    renderPagination("fil-pag", info, p => { filPage = p; renderFilPage(); });
}

function initFilings() {
    // Populate dropdowns
    const tickers = [...new Set(D.firmYear.map(r => r.ticker))].sort();
    const years = [...new Set(D.firmYear.map(r => r.filing_year))].sort();
    const ts = document.getElementById("fil-ticker");
    tickers.forEach(t => { const o = document.createElement("option"); o.value = t; o.textContent = t; ts.appendChild(o); });
    const ys = document.getElementById("fil-year");
    years.forEach(y => { const o = document.createElement("option"); o.value = y; o.textContent = y; ys.appendChild(o); });

    ["fil-ticker", "fil-year", "fil-status", "fil-tone"].forEach(id => {
        document.getElementById(id).addEventListener("change", filterFilings);
    });

    const searchInput = document.getElementById("fil-search");
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener("input", () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(filterFilings, 150);
        });
    }

    const resetBtn = document.getElementById("fil-reset");
    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            if (searchInput) searchInput.value = "";
            document.getElementById("fil-ticker").value = "";
            document.getElementById("fil-year").value = "";
            document.getElementById("fil-status").value = "";
            document.getElementById("fil-tone").value = "";
            filSort = { key: "ticker", dir: "asc" };
            filterFilings();
        });
    }

    const exportBtn = document.getElementById("fil-export");
    if (exportBtn) {
        exportBtn.addEventListener("click", () => {
            const cols = [
                { label: "Ticker", key: "ticker" },
                { label: "Company", key: "company_name" },
                { label: "Filing Year", key: "filing_year" },
                { label: "Report Year", key: "report_year" },
                { label: "Filing Date", key: "filing_date" },
                { label: "Item 7 Status", key: "item_7_mda_lm_status" },
                { label: "LM Net Prop", key: "lm_net_prop" },
                { label: "Harvard Net Prop", key: "harvard_net_prop" },
                { label: "CAR [-1, +1]", key: "CAR_m1_p1" },
                { label: "Has Tone", key: "has_method_score" },
                { label: "Has CAR", key: "has_event_car" },
                { label: "SEC URL", key: "sec_url" },
            ];
            exportToCsv("10k_filings_filtered.csv", cols, filFiltered);
        });
    }

    filterFilings();
}

/* ==========================================================
   TAB: AUDIT (point 7 — traceability)
   ========================================================== */

function initAudit() {
    const m = D.manifest;
    const v = D.verification;

    document.getElementById("audit-gen-date").textContent = D.generatedAt;

    // Manifest table
    const fileEntries = Object.entries(m.files || {}).map(([name, info]) => ({
        name, path: info.path, rows: info.rows, cols: info.columns ? info.columns.length : 0,
    }));
    renderTable("audit-manifest-table", [
        { label: "Bảng dữ liệu", key: "name", fmt: v => `<strong>${v}</strong>` },
        { label: "File nguồn", key: "path", fmt: v => `<code>${v}</code>` },
        { label: "Số hàng", key: "rows", num: true, fmt: v => v.toLocaleString() },
        { label: "Số cột", key: "cols", num: true },
    ], fileEntries);

    // SHA-256 with Phosphor copy SVG button
    const shaEntries = Object.entries(v.source_sha256 || {}).map(([path, hash]) => ({
        path, hash, current: D.sourceIntegrity?.[path]?.current_sha256,
        status: D.sourceIntegrity?.[path]?.status,
    }));
    renderTable("audit-sha-table", [
        { label: "Bảng đầu vào", key: "path", fmt: v => `<code>${v}</code>` },
        { label: "SHA-256 lần chạy phân tích", key: "hash", fmt: v => `
            <div class="hash-container">
                <span class="hash-display">${v}</span>
                <button type="button" class="copy-btn" data-hash="${v}" aria-label="Sao chép mã SHA-256">
                    <svg class="icon-svg" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                    <span>Copy</span>
                </button>
            </div>
        `},
        { label: "SHA-256 khi đóng gói", key: "current", fmt: value => value ? `<code>${value}</code>` : "—" },
        { label: "Đối chiếu khi đóng gói", key: "status", fmt: value => ({
            exact: "Khớp byte", line_endings_only: "Chỉ khác xuống dòng LF/CRLF",
            mismatch: "Không khớp nội dung", missing: "Thiếu tệp nguồn",
        }[value] || "Chưa đối chiếu") },
    ], shaEntries);

    // Add clipboard click handlers
    document.querySelectorAll(".copy-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const hash = btn.dataset.hash;
            navigator.clipboard.writeText(hash).then(() => {
                btn.innerHTML = `
                    <svg class="icon-svg" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                    <span>Đã chép</span>
                `;
                btn.classList.add("copied");
                showToast("✓ Đã sao chép SHA-256 vào clipboard");
                setTimeout(() => {
                    btn.innerHTML = `
                        <svg class="icon-svg" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                        <span>Copy</span>
                    `;
                    btn.classList.remove("copied");
                }, 2000);
            }).catch(() => {
                btn.querySelector("span").textContent = "Lỗi";
                showToast("Không thể sao chép vào clipboard");
            });
        });
    });

    // Arithmetic checks
    const checks = [];
    if (v.tone_arithmetic) {
        Object.entries(v.tone_arithmetic).forEach(([dict, info]) => {
            checks.push({ kiểm_tra: `Tone ${dict}: P/W − N/W = net_prop`, checked: info.checked, mismatches: info.mismatches });
        });
    }
    if (v.car_arithmetic) {
        Object.entries(v.car_arithmetic).forEach(([car, info]) => {
            checks.push({ kiểm_tra: `${car}: tổng AR = CAR`, checked: info.checked, mismatches: info.mismatches });
        });
    }
    if (v.event_calendar) {
        checks.push({ kiểm_tra: "Event day 0 = ngày sự kiện", checked: v.event_calendar.filings_checked, mismatches: v.event_calendar.day_zero_date_mismatches });
        checks.push({ kiểm_tra: "AR khớp lịch phiên ^GSPC", checked: v.event_calendar.rows_matching_market_calendar, mismatches: 0 });
        if (v.event_calendar.sec_timestamps_matched != null) {
            checks.push({ kiểm_tra: "SEC timestamps khớp event_date", checked: v.event_calendar.sec_timestamps_matched, mismatches: 0 });
        }
        if (v.event_calendar.sessions_shifted_after_filing_date != null) {
            checks.push({ kiểm_tra: "Phiên dời sang ngày T+1 (nộp sau 16:00 ET)", checked: v.event_calendar.sessions_shifted_after_filing_date, mismatches: 0 });
        }
    }
    renderTable("audit-arith-table", [
        { label: "Phép kiểm tra tính nhất quán", key: "kiểm_tra" },
        { label: "Đã kiểm", key: "checked", num: true, fmt: v => v.toLocaleString() },
        { label: "Sai lệch", key: "mismatches", num: true, fmt: v => v === 0 ? '<span class="badge badge-ok">0 sai lệch</span>' : `<span class="badge badge-miss">${v}</span>` },
    ], checks);

    // Missing filings
    renderTable("audit-missing-table", [
        { label: "Ticker", key: "ticker", fmt: v => `<strong>${v}</strong>` },
        { label: "Ngày nộp", key: "filing_date" },
        { label: "Accession", key: "accession_number", fmt: v => `<code>${v}</code>` },
        { label: "Status Item 7", key: "item_7_mda_status", fmt: v => `<span class="badge badge-warn">${v}</span>` },
        { label: "Có tone", key: "has_tone", center: true, fmt: v => v ? "✓" : "—" },
        { label: "Có event", key: "has_event", center: true, fmt: v => v ? "✓" : "—" },
        { label: "Lý do loại event", key: "event_exclusion_reason", fmt: v => v || "—" },
    ], D.missing);

    // C2 full coefficients
    document.getElementById("c2-full-window").addEventListener("change", renderC2Full);
    renderC2Full();
}

function renderC2Full() {
    const win = document.getElementById("c2-full-window").value;
    let rows = D.c2;
    if (win !== "all") rows = rows.filter(r => r.dependent_variable === win);

    renderTable("c2-full-table", [
        { label: "Cửa sổ", key: "dependent_variable", fmt: v => WIN[v] || v },
        { label: "Biến", key: "term" },
        { label: "Hệ số", key: "coefficient", num: true, fmt: v => signSpan(v) },
        { label: "SE HC3", key: "se_hc3", num: true, fmt: v => fmt(v, 6) },
        { label: "p HC3", key: "p_hc3_two_sided", num: true, fmt: v => pval(v), cls: r => sigClass(r.p_hc3_two_sided) },
        { label: "CI 95%", get: r => `[${fmt(r.ci_hc3_low, 4)}; ${fmt(r.ci_hc3_high, 4)}]`, num: true },
        { label: "SE cluster", key: "se_cluster", num: true, fmt: v => fmt(v, 6) },
        { label: "p cluster", key: "p_cluster_two_sided", num: true, fmt: v => pval(v), cls: r => sigClass(r.p_cluster_two_sided) },
        { label: "R²", key: "r_squared", num: true, fmt: v => fmt(v, 4) },
    ], rows);
}

/* ==========================================================
   INITIALIZATION
   ========================================================== */

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initFindings();
    initNavigation();
    initOverview();
    initEventStudy();
    initRegression();
    initDictionary();
    initFilings();
    initAudit();
    setTimeout(() => renderMath(), 200);
});

window.addEventListener("load", () => {
    renderMath();
});
