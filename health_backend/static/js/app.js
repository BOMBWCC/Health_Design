const state = {
    user: null,
    token: localStorage.getItem('access_token'),
    metrics: [],
    loading: false,
    error: null
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

    async fetchMetrics() {
        const response = await fetch('/api/v1/query/metrics', {
            headers: { 'Authorization': `Bearer ${state.token}` }
        });

        if (response.status === 401) {
            logout();
            throw new Error('Session expired');
        }

        if (!response.ok) throw new Error('Failed to fetch metrics');
        return response.json();
    },

    async triggerAggregation() {
        const response = await fetch('/api/v1/tasks/trigger', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${state.token}` }
        });
        if (!response.ok) throw new Error('Failed to trigger aggregation');
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
    localStorage.removeItem('access_token');
    render();
}

async function initDashboard() {
    state.loading = true;
    render();
    try {
        const data = await api.fetchMetrics();
        state.metrics = data.data;
        state.user = data.user;
    } catch (err) {
        state.error = err.message;
    } finally {
        state.loading = false;
        render();
    }
}

async function refreshData() {
    state.loading = true;
    render();
    try {
        await api.triggerAggregation();
        // Wait a bit for background task to start
        setTimeout(async () => {
            const data = await api.fetchMetrics();
            state.metrics = data.data;
            state.loading = false;
            render();
        }, 2000);
    } catch (err) {
        state.error = err.message;
        state.loading = false;
        render();
    }
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
                    <h1>Health Data Hub</h1>
                    <p style="font-size: 14px; color: var(--text-tertiary);">Sign in to your health dashboard</p>
                </div>

                <form onsubmit="handleLogin(event)">
                    <div class="form-group">
                        <label class="form-label">Username</label>
                        <input type="text" name="username" class="input" placeholder="admin" required autofocus>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Password</label>
                        <input type="password" name="password" class="input" placeholder="••••••••" required>
                    </div>
                    
                    ${state.error ? `<p style="color: var(--error); font-size: 13px; margin-bottom: 1rem;">${state.error}</p>` : ''}
                    
                    <button type="submit" class="btn btn-primary" style="width: 100%;" ${state.loading ? 'disabled' : ''}>
                        ${state.loading ? '<div class="loading-spinner" style="width: 16px; height: 16px;"></div>' : 'Continue'}
                    </button>
                </form>
            </div>
        </div>
    `;
}

function DashboardView() {
    const metricsHtml = state.metrics.length > 0 
        ? state.metrics.map(m => MetricCard(m)).join('')
        : '<div class="card" style="grid-column: 1/-1; text-align: center;"><p>No data available. Use Shortcuts to upload data.</p></div>';

    return `
        <nav class="nav">
            <div class="nav-brand">
                <i data-lucide="activity" style="color: var(--accent);"></i>
                Health Data Hub
            </div>
            <div style="display: flex; gap: 1rem; align-items: center;">
                <span style="font-size: 14px; color: var(--text-tertiary);">User: <strong>${state.user}</strong></span>
                <button class="btn btn-ghost" onclick="refreshData()" title="Trigger Aggregation">
                    <i data-lucide="refresh-cw" style="width: 16px;"></i>
                </button>
                <button class="btn btn-ghost" onclick="logout()">Logout</button>
            </div>
        </nav>
        <main class="container">
            <header style="margin-bottom: 3rem;">
                <h2 style="font-size: 32px; letter-spacing: -0.03em;">Insights</h2>
                <p>Overview of your synchronized health metrics</p>
            </header>

            ${state.loading ? '<div style="display: flex; justify-content: center; padding: 4rem;"><div class="loading-spinner"></div></div>' : ''}

            <div class="metric-grid fade-in">
                ${metricsHtml}
            </div>
        </main>
    `;
}

function MetricCard(m) {
    const iconMap = {
        'step_count': 'footprints',
        'sleep_analysis': 'moon',
        'resting_heart_rate': 'heart',
        'walking_heart_rate': 'person-standing',
        'active_energy': 'flame',
        'stand_hours': 'clock',
        'hrv': 'zap'
    };
    const icon = iconMap[m.category] || 'activity';
    const displayName = m.metadata ? m.metadata.display_name : m.category;
    const unit = m.metadata ? m.metadata.unit : '';

    return `
        <div class="card">
            <div class="metric-header">
                <span class="metric-title">${displayName}</span>
                <i data-lucide="${icon}" style="color: var(--accent); width: 20px; opacity: 0.8;"></i>
            </div>
            <div class="metric-value">
                ${m.value.toLocaleString()}
                <span class="metric-unit">${unit}</span>
            </div>
            <div class="metric-footer">
                <i data-lucide="calendar" style="width: 12px;"></i>
                <span>${m.record_date} (UTC)</span>
                <span style="margin-left: auto;">${m.sample_count} samples</span>
            </div>
        </div>
    `;
}

// --- Main Render ---
function render() {
    const app = document.getElementById('app');
    if (!state.token) {
        app.innerHTML = LoginView();
    } else {
        app.innerHTML = DashboardView();
    }
    lucide.createIcons();
}

// --- Boot ---
document.addEventListener('DOMContentLoaded', () => {
    if (state.token) {
        initDashboard();
    } else {
        render();
    }
});

// Expose handlers to global scope for HTML onsubmit/onclick
window.handleLogin = handleLogin;
window.logout = logout;
window.refreshData = refreshData;
window.initDashboard = initDashboard;
