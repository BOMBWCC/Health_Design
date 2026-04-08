const state = {
    user: null,
    token: localStorage.getItem('access_token'),
    metrics: [],
    sleepRecords: [],
    loading: false,
    error: null,
    rangeDays: 7, // 默认 7 天
    charts: {} // 存储 chart 实例以便销毁
};

// --- API Helpers ---
const api = {
    async login(username, password) {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch('/api/v1/auth/login', {
            method: 'POST',
            body: formData,
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Login failed');
        }

        return response.json();
    },

    async fetchMetrics(days = 7) {
        const endDate = new Date().toISOString().split('T')[0];
        const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
        
        const response = await fetch(`/api/v1/query/metrics?start_date=${startDate}&end_date=${endDate}`, {
            headers: { 'Authorization': `Bearer ${state.token}` }
        });

        if (response.status === 401) {
            logout();
            throw new Error('Session expired');
        }

        if (!response.ok) throw new Error('Failed to fetch metrics');
        return response.json();
    },

    async fetchSleepRecords(days = 7) {
        const endTime = new Date();
        const startTime = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
        const params = new URLSearchParams({
            start_time: startTime.toISOString(),
            end_time: endTime.toISOString(),
            order: 'desc'
        });

        const response = await fetch(`/api/v1/query/sleep-records?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${state.token}` }
        });

        if (response.status === 401) {
            logout();
            throw new Error('Session expired');
        }

        if (!response.ok) throw new Error('Failed to fetch sleep records');
        return response.json();
    },

    async triggerAggregation() {
        const response = await fetch('/api/v1/tasks/trigger', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${state.token}` }
        });
        return response.json();
    }
};

// --- State Actions ---
async function handleLogin(e) {
    e.preventDefault();
    const username = e.target.username.value;
    const password = e.target.password.value;
    state.loading = true;
    state.error = null;
    render();
    try {
        const data = await api.login(username, password);
        state.token = data.access_token;
        localStorage.setItem('access_token', state.token);
        await initDashboard();
    } catch (err) {
        state.error = err.message;
        state.loading = false;
        render();
    }
}

function logout() {
    state.token = null;
    state.user = null;
    state.metrics = [];
    state.sleepRecords = [];
    localStorage.removeItem('access_token');
    render();
}

async function setRange(days) {
    state.rangeDays = days;
    await initDashboard();
}

async function initDashboard() {
    state.loading = true;
    render();
    try {
        const [metricsData, sleepData] = await Promise.all([
            api.fetchMetrics(state.rangeDays),
            api.fetchSleepRecords(state.rangeDays)
        ]);
        state.metrics = metricsData.data;
        state.sleepRecords = sleepData.data;
        state.user = metricsData.user;
    } catch (err) {
        state.error = err.message;
    } finally {
        state.loading = false;
        render();
        initCharts();
    }
}

async function refreshData() {
    state.loading = true;
    render();
    try {
        await api.triggerAggregation();
        setTimeout(() => initDashboard(), 2000);
    } catch (err) {
        state.error = err.message;
        state.loading = false;
        render();
    }
}

// --- Chart Logic ---
function initCharts() {
    const chartMetrics = state.metrics.filter(m => m.category !== 'sleep_analysis');

    // 1. 按 category 归组数据
    const grouped = {};
    chartMetrics.forEach(m => {
        if (!grouped[m.category]) grouped[m.category] = { label: m.metadata?.display_name || m.category, unit: m.metadata?.unit || '', points: [] };
        grouped[m.category].points.push({ x: m.record_date, y: m.value });
    });

    // 2. 遍历 7 个维度绘制图表
    Object.keys(grouped).forEach(cat => {
        const ctx = document.getElementById(`chart-${cat}`);
        if (!ctx) return;

        // 销毁旧图表
        if (state.charts[cat]) state.charts[cat].destroy();

        // 排序数据点（按时间升序）
        const sortedPoints = grouped[cat].points.sort((a, b) => new Date(a.x) - new Date(b.x));

        state.charts[cat] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: sortedPoints.map(p => p.x),
                datasets: [{
                    label: grouped[cat].label,
                    data: sortedPoints.map(p => p.y),
                    borderColor: '#7170ff',
                    backgroundColor: 'rgba(113, 112, 255, 0.1)',
                    borderWidth: 2,
                    pointRadius: 3,
                    pointBackgroundColor: '#7170ff',
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#8a8f98', font: { size: 10 } }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#8a8f98', font: { size: 10 } }
                    }
                }
            }
        });
    });
}

function formatDateTime(value) {
    const date = new Date(value);
    return new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
}

function formatTime(value) {
    const date = new Date(value);
    return new Intl.DateTimeFormat(undefined, {
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
}

function formatDuration(hours) {
    const wholeHours = Math.floor(hours);
    const minutes = Math.round((hours - wholeHours) * 60);

    if (wholeHours === 0) return `${minutes}m`;
    if (minutes === 0) return `${wholeHours}h`;
    return `${wholeHours}h ${minutes}m`;
}

function buildSleepSummary(records) {
    if (records.length === 0) {
        return {
            totalObservedHours: 0,
            latestWindow: null
        };
    }

    return {
        totalObservedHours: records.reduce((sum, item) => sum + item.duration_hours, 0),
        latestWindow: records[0]
    };
}

function SleepSection() {
    const summary = buildSleepSummary(state.sleepRecords);
    const recordsHtml = state.sleepRecords.length > 0
        ? state.sleepRecords.slice(0, 12).map(record => `
            <div class="sleep-record">
                <div class="sleep-record-main">
                    <div class="sleep-record-date">${formatDateTime(record.start_time)}</div>
                    <div class="sleep-record-range">${formatTime(record.start_time)} - ${formatTime(record.end_time)}</div>
                </div>
                <div class="sleep-record-side">
                    <div class="sleep-record-duration">${formatDuration(record.duration_hours)}</div>
                    <div class="sleep-record-source">${record.source || 'unknown source'}</div>
                </div>
            </div>
        `).join('')
        : '<div class="sleep-empty">No observed sleep intervals found in this range.</div>';

    return `
        <section class="card sleep-card fade-in">
            <div class="sleep-card-header">
                <div>
                    <div class="sleep-eyebrow">Sleep Intervals</div>
                    <h3>Observed sleep records</h3>
                    <p class="sleep-description">This view shows recorded sleep segments directly from raw data instead of daily sleep totals.</p>
                </div>
                <div class="sleep-summary">
                    <div class="sleep-summary-item">
                        <span class="sleep-summary-label">Observed total</span>
                        <strong>${formatDuration(summary.totalObservedHours)}</strong>
                    </div>
                    <div class="sleep-summary-item">
                        <span class="sleep-summary-label">Latest window</span>
                        <strong>${summary.latestWindow ? `${formatTime(summary.latestWindow.start_time)} - ${formatTime(summary.latestWindow.end_time)}` : 'None'}</strong>
                    </div>
                </div>
            </div>
            <div class="sleep-list">${recordsHtml}</div>
        </section>
    `;
}

// --- View Components ---
function LoginView() {
    return `
        <div class="login-container">
            <div class="card login-card fade-in">
                <div style="text-align: center; margin-bottom: 2rem;">
                    <div style="width: 48px; height: 48px; background: var(--accent); border-radius: 12px; margin: 0 auto 1rem; display: flex; align-items: center; justify-content: center;">
                        <i data-lucide="activity" style="color: white;"></i>
                    </div>
                    <h1>Health Hub</h1>
                    <p style="font-size: 14px; color: var(--text-tertiary);">Sign in to your trend dashboard</p>
                </div>
                <form onsubmit="handleLogin(event)">
                    <div class="form-group"><label class="form-label">Username</label><input type="text" name="username" class="input" placeholder="admin" required autofocus></div>
                    <div class="form-group"><label class="form-label">Password</label><input type="password" name="password" class="input" placeholder="••••••••" required></div>
                    ${state.error ? `<p style="color: var(--error); font-size: 13px; margin-bottom: 1rem;">${state.error}</p>` : ''}
                    <button type="submit" class="btn btn-primary" style="width: 100%;" ${state.loading ? 'disabled' : ''}>Continue</button>
                </form>
            </div>
        </div>
    `;
}

function DashboardView() {
    const visibleMetrics = state.metrics.filter(m => m.category !== 'sleep_analysis');
    const categories = [...new Set(visibleMetrics.map(m => m.category))];
    const metricsHtml = categories.length > 0 
        ? categories.map(cat => {
            const latest = visibleMetrics.filter(m => m.category === cat).sort((a,b) => new Date(b.record_date) - new Date(a.record_date))[0];
            return `
                <div class="card">
                    <div class="metric-header">
                        <div>
                            <span class="metric-title">${latest.metadata?.display_name || cat}</span>
                            <div class="metric-value" style="font-size: 1.5rem; margin-top: 0.5rem;">
                                ${latest.value.toLocaleString()} <span class="metric-unit">${latest.metadata?.unit || ''}</span>
                            </div>
                        </div>
                        <div class="range-btn active" style="font-size: 10px; padding: 2px 6px;">TREND</div>
                    </div>
                    <div class="chart-container">
                        <canvas id="chart-${cat}"></canvas>
                    </div>
                </div>
            `;
        }).join('')
        : '<div class="card" style="grid-column: 1/-1; text-align: center;"><p>No trend metrics found for this range.</p></div>';

    return `
        <nav class="nav">
            <div class="nav-brand"><i data-lucide="activity" style="color: var(--accent);"></i> Health Hub</div>
            <div style="display: flex; gap: 1.5rem; align-items: center;">
                <div class="range-selector">
                    <button class="range-btn ${state.rangeDays === 3 ? 'active' : ''}" onclick="setRange(3)">3D</button>
                    <button class="range-btn ${state.rangeDays === 7 ? 'active' : ''}" onclick="setRange(7)">1W</button>
                    <button class="range-btn ${state.rangeDays === 30 ? 'active' : ''}" onclick="setRange(30)">1M</button>
                </div>
                <button class="btn btn-ghost" onclick="refreshData()" title="Trigger Sync"><i data-lucide="refresh-cw" style="width: 14px;"></i></button>
                <button class="btn btn-ghost" onclick="logout()">Logout</button>
            </div>
        </nav>
        <main class="container">
            <header style="margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: flex-end;">
                <div>
                    <h2 style="font-size: 28px;">Health Trends</h2>
                    <p style="font-size: 14px; color: var(--text-tertiary);">Showing data for last ${state.rangeDays} days</p>
                </div>
                <div style="font-size: 13px; color: var(--text-quaternary);">Identity: ${state.user}</div>
            </header>
            <div class="metric-grid fade-in">${metricsHtml}</div>
            <div class="sleep-section-wrap">${SleepSection()}</div>
        </main>
    `;
}

function render() {
    const app = document.getElementById('app');
    app.innerHTML = !state.token ? LoginView() : DashboardView();
    lucide.createIcons();
}

document.addEventListener('DOMContentLoaded', () => state.token ? initDashboard() : render());
window.handleLogin = handleLogin; window.logout = logout; window.setRange = setRange; window.refreshData = refreshData;
