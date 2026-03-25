/**
 * WA/D - Wisdom Assistor/Distributor
 * Main frontend application
 */

const API_BASE = '';

// ──────────────────────────────────────────────
// State
// ──────────────────────────────────────────────
const state = {
    ws: null,
    connected: false,
    processing: false,
    activeTab: 'agents',
    automationState: 'inactive',
    lastResult: null,
    messages: [],
    agents: {},
    memory: [],
    memoryStats: {},
    monitors: [],
    selectedMonitor: 0,
};

// ──────────────────────────────────────────────
// DOM helpers
// ──────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function el(tag, attrs = {}, children = []) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
        if (k === 'className') e.className = v;
        else if (k === 'innerHTML') e.innerHTML = v;
        else if (k === 'textContent') e.textContent = v;
        else if (k.startsWith('on')) e.addEventListener(k.slice(2).toLowerCase(), v);
        else e.setAttribute(k, v);
    }
    for (const c of children) {
        if (typeof c === 'string') e.appendChild(document.createTextNode(c));
        else if (c) e.appendChild(c);
    }
    return e;
}

// ──────────────────────────────────────────────
// WebSocket
// ──────────────────────────────────────────────
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws`;

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        state.connected = true;
        updateConnectionStatus();
        console.log('WebSocket connected');
    };

    state.ws.onclose = () => {
        state.connected = false;
        updateConnectionStatus();
        console.log('WebSocket disconnected, reconnecting in 3s...');
        setTimeout(connectWebSocket, 3000);
    };

    state.ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };

    state.ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleWSMessage(msg);
        } catch (e) {
            console.error('Failed to parse WS message:', e);
        }
    };
}

function handleWSMessage(msg) {
    const { event, data } = msg;

    switch (event) {
        case 'pong':
            break;
        case 'processing':
            state.processing = true;
            showProcessing();
            break;
        case 'result':
            state.processing = false;
            state.lastResult = data;
            hideProcessing();
            addSystemMessage(data);
            renderAgentPanel(data);
            break;
        case 'status':
            state.automationState = data.state;
            updateAutomationStatus();
            break;
        case 'action':
            addActionMessage(data);
            break;
        case 'error':
            state.processing = false;
            hideProcessing();
            addErrorMessage(data.message);
            break;
        case 'screen_state':
            break;
    }
}

function updateConnectionStatus() {
    const el = $('#connection-status');
    if (!el) return;
    if (state.connected) {
        el.className = 'connection-status connected';
        el.innerHTML = '<span class="status-dot"></span> Connected';
    } else {
        el.className = 'connection-status disconnected';
        el.innerHTML = '<span class="status-dot"></span> Disconnected';
    }
}

// ──────────────────────────────────────────────
// API calls
// ──────────────────────────────────────────────
async function apiCall(method, path, body = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API_BASE}${path}`, opts);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'API error');
    }
    return res.json();
}

async function loadMonitors() {
    try {
        const data = await apiCall('GET', '/api/screen/monitors');
        state.monitors = data.monitors || [];
        updateMonitorSelect();
    } catch (err) {
        console.error('Failed to load monitors:', err);
        state.monitors = [{ index: 0, label: 'Default (All)', width: 0, height: 0 }];
        updateMonitorSelect();
    }
}

function updateMonitorSelect() {
    const select = $('#monitor-select');
    if (!select) return;
    select.innerHTML = '';
    for (const mon of state.monitors) {
        const opt = document.createElement('option');
        opt.value = mon.index;
        opt.textContent = `${mon.label} (${mon.width}x${mon.height})`;
        if (mon.index === state.selectedMonitor) opt.selected = true;
        select.appendChild(opt);
    }
}

async function sendQuery(instruction, includeScreen = false) {
    state.processing = true;
    showProcessing();
    addUserMessage(instruction);

    try {
        const result = await apiCall('POST', '/api/query', {
            instruction,
            include_screen: includeScreen,
            monitor_index: state.selectedMonitor,
            use_memory_context: true,
        });

        state.processing = false;
        state.lastResult = result;
        hideProcessing();
        addSystemMessage(result);
        renderAgentPanel(result);
    } catch (err) {
        state.processing = false;
        hideProcessing();
        addErrorMessage(err.message);
    }
}

async function loadAgents() {
    try {
        const data = await apiCall('GET', '/api/agents');
        state.agents = data.agents;
        renderAgentStatusCards();
    } catch (err) {
        console.error('Failed to load agents:', err);
    }
}

async function loadMemory() {
    try {
        const [recent, stats] = await Promise.all([
            apiCall('GET', '/api/memory/recent?limit=20'),
            apiCall('GET', '/api/memory/stats'),
        ]);
        state.memory = recent.entries;
        state.memoryStats = stats;
        renderMemoryPanel();
    } catch (err) {
        console.error('Failed to load memory:', err);
    }
}

async function updateApiKey(agentKey, apiKey) {
    try {
        const data = await apiCall('POST', '/api/agents/key', {
            agent_key: agentKey,
            api_key: apiKey,
        });
        state.agents = data.agents;
        renderAgentStatusCards();
    } catch (err) {
        addErrorMessage(`Failed to update API key: ${err.message}`);
    }
}

async function saveSettings() {
    const fields = {
        openai_api_key: $('#setting-openai-key')?.value || undefined,
        anthropic_api_key: $('#setting-anthropic-key')?.value || undefined,
        google_api_key: $('#setting-google-key')?.value || undefined,
        microsoft_api_key: $('#setting-microsoft-key')?.value || undefined,
        openai_model: $('#setting-openai-model')?.value || undefined,
        anthropic_model: $('#setting-anthropic-model')?.value || undefined,
        gemini_model: $('#setting-gemini-model')?.value || undefined,
    };

    // Filter out empty/undefined
    const body = {};
    for (const [k, v] of Object.entries(fields)) {
        if (v !== undefined && v !== '') body[k] = v;
    }

    try {
        await apiCall('POST', '/api/settings', body);
        await loadAgents();
        addInfoMessage('Settings saved successfully.');
    } catch (err) {
        addErrorMessage(`Failed to save settings: ${err.message}`);
    }
}

async function grantScreenPermission() {
    try {
        await apiCall('POST', '/api/screen/permission?grant=true');
        addInfoMessage('Screen capture permission granted.');
        await loadMonitors();
    } catch (err) {
        addErrorMessage(err.message);
    }
}

async function grantActionPermission() {
    try {
        await apiCall('POST', '/api/action/permission?grant=true');
        state.automationState = 'active';
        updateAutomationStatus();
        addInfoMessage('Automation permission granted. Desktop control is now active.');
    } catch (err) {
        addErrorMessage(err.message);
    }
}

async function pauseAutomation() {
    try {
        await apiCall('POST', '/api/action/pause');
        state.automationState = 'paused';
        updateAutomationStatus();
    } catch (err) {
        addErrorMessage(err.message);
    }
}

async function resumeAutomation() {
    try {
        await apiCall('POST', '/api/action/resume');
        state.automationState = 'active';
        updateAutomationStatus();
    } catch (err) {
        addErrorMessage(err.message);
    }
}

async function emergencyStop() {
    try {
        await apiCall('POST', '/api/action/stop');
        state.automationState = 'emergency_stopped';
        updateAutomationStatus();
        addErrorMessage('EMERGENCY STOP activated. All automation halted.');
    } catch (err) {
        addErrorMessage(err.message);
    }
}

async function clearMemory() {
    if (!confirm('Clear all memory? This cannot be undone.')) return;
    try {
        await apiCall('POST', '/api/memory/clear');
        await loadMemory();
        addInfoMessage('Memory cleared.');
    } catch (err) {
        addErrorMessage(err.message);
    }
}

// ──────────────────────────────────────────────
// Chat Messages
// ──────────────────────────────────────────────
function addUserMessage(text) {
    const msg = { type: 'user', text, time: new Date() };
    state.messages.push(msg);
    renderMessage(msg);
}

function addSystemMessage(result) {
    const text = result.selected_answer || 'No answer available.';
    const meta = `${result.selected_agent} | Confidence: ${(result.confidence * 100).toFixed(0)}% | Agreement: ${(result.agreement_score * 100).toFixed(0)}%`;
    const msg = { type: 'system', text, meta, time: new Date() };
    state.messages.push(msg);
    renderMessage(msg);
}

function addErrorMessage(text) {
    const msg = { type: 'system', text: `Error: ${text}`, meta: 'System', time: new Date(), isError: true };
    state.messages.push(msg);
    renderMessage(msg);
}

function addInfoMessage(text) {
    const msg = { type: 'system', text, meta: 'System', time: new Date() };
    state.messages.push(msg);
    renderMessage(msg);
}

function addActionMessage(action) {
    const msg = {
        type: 'system',
        text: `Action: ${action.description}${action.error ? ' - ' + action.error : ''}`,
        meta: action.success ? 'Action Completed' : 'Action Failed',
        time: new Date(),
        isError: !action.success,
    };
    state.messages.push(msg);
    renderMessage(msg);
}

function renderMessage(msg) {
    const container = $('#chat-messages');
    if (!container) return;

    const msgEl = el('div', { className: `message ${msg.type}` }, [
        el('div', { className: 'message-avatar' }, [msg.type === 'user' ? 'U' : 'W']),
        el('div', { className: 'message-content' }, [
            el('div', {
                className: 'message-text',
                textContent: msg.text,
                style: msg.isError ? 'color: #e74c3c' : '',
            }),
            msg.meta ? el('div', { className: 'message-meta', textContent: msg.meta }) : null,
        ].filter(Boolean)),
    ]);

    container.appendChild(msgEl);
    container.scrollTop = container.scrollHeight;
}

function showProcessing() {
    const container = $('#chat-messages');
    if (!container) return;

    let proc = $('#processing-msg');
    if (!proc) {
        proc = el('div', { className: 'processing-indicator', id: 'processing-msg' }, [
            el('div', { className: 'processing-dots' }, [
                el('span'), el('span'), el('span'),
            ]),
            document.createTextNode(' Agents are thinking...'),
        ]);
        container.appendChild(proc);
    }
    container.scrollTop = container.scrollHeight;
}

function hideProcessing() {
    const proc = $('#processing-msg');
    if (proc) proc.remove();
}

// ──────────────────────────────────────────────
// Panel Rendering
// ──────────────────────────────────────────────
function renderAgentPanel(result) {
    if (state.activeTab !== 'agents') return;

    const panel = $('#panel-content');
    if (!panel) return;
    panel.innerHTML = '';

    if (!result || !result.responses) {
        renderAgentStatusCards();
        return;
    }

    // Consensus summary
    const summary = el('div', { className: 'consensus-summary' }, [
        el('div', { className: 'consensus-title' }, ['Consensus Result']),
        el('div', { className: 'consensus-answer', textContent: result.selected_answer }),
        el('div', { className: 'consensus-meta' }, [
            el('span', {}, [`Selected: ${result.selected_agent}`]),
            el('span', {}, [`Confidence: ${(result.confidence * 100).toFixed(0)}%`]),
            el('span', {}, [`Agreement: ${(result.agreement_score * 100).toFixed(0)}%`]),
        ]),
    ]);
    panel.appendChild(summary);

    // Agent cards
    const cards = el('div', { className: 'agent-cards' });
    for (const resp of result.responses) {
        const isWinner = resp.agent_name === result.selected_agent;
        const hasError = !!resp.error;

        const confColor = resp.confidence > 0.7 ? 'var(--success)' :
                          resp.confidence > 0.4 ? 'var(--warning)' : 'var(--danger)';

        const card = el('div', { className: `agent-card ${isWinner ? 'selected' : ''}` }, [
            el('div', { className: 'agent-header' }, [
                el('span', { className: 'agent-name' }, [resp.agent_name]),
                el('span', {
                    className: `agent-badge ${isWinner ? 'winner' : hasError ? 'disabled' : 'enabled'}`,
                }, [isWinner ? 'SELECTED' : hasError ? 'ERROR' : 'OK']),
            ]),
            hasError
                ? el('div', { className: 'agent-answer', style: 'color: var(--danger)' }, [resp.error])
                : el('div', { className: 'agent-answer' }, [resp.answer || 'No answer']),
            !hasError ? el('div', { className: 'agent-reasoning' }, [resp.reasoning || '']) : null,
            el('div', { className: 'agent-metrics' }, [
                el('span', { className: 'metric' }, [
                    'Confidence: ',
                    el('span', { className: 'metric-value' }, [`${(resp.confidence * 100).toFixed(0)}%`]),
                ]),
                el('span', { className: 'metric' }, [
                    'Time: ',
                    el('span', { className: 'metric-value' }, [`${resp.processing_time?.toFixed(1) || '?'}s`]),
                ]),
            ]),
            !hasError ? el('div', { className: 'confidence-bar' }, [
                el('div', {
                    className: 'confidence-fill',
                    style: `width: ${resp.confidence * 100}%; background: ${confColor}`,
                }),
            ]) : null,
        ].filter(Boolean));

        cards.appendChild(card);
    }
    panel.appendChild(cards);

    // Vote details
    if (result.vote_details && Object.keys(result.vote_details).length > 0) {
        const detailSection = el('div', { className: 'mt-16' }, [
            el('div', { className: 'settings-title' }, ['Vote Breakdown']),
        ]);

        for (const [name, detail] of Object.entries(result.vote_details)) {
            const row = el('div', { className: 'memory-entry' }, [
                el('div', { className: 'memory-instruction' }, [name]),
                el('div', { className: 'memory-answer' }, [
                    `Score: ${detail.total_score} | Agreement: ${(detail.agreement_with_others * 100).toFixed(0)}% | Quality: ${(detail.reasoning_quality * 100).toFixed(0)}%`,
                ]),
            ]);
            detailSection.appendChild(row);
        }
        panel.appendChild(detailSection);
    }
}

function renderAgentStatusCards() {
    if (state.activeTab !== 'agents') return;

    const panel = $('#panel-content');
    if (!panel) return;

    // If we have a last result, show that instead
    if (state.lastResult) {
        renderAgentPanel(state.lastResult);
        return;
    }

    panel.innerHTML = '';

    if (Object.keys(state.agents).length === 0) {
        panel.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">&#129302;</div>
                <div class="empty-state-text">No agents configured yet. Add API keys in Settings to enable AI agents.</div>
            </div>`;
        return;
    }

    const cards = el('div', { className: 'agent-cards' });
    for (const [key, agent] of Object.entries(state.agents)) {
        const card = el('div', { className: 'agent-card' }, [
            el('div', { className: 'agent-header' }, [
                el('span', { className: 'agent-name' }, [agent.name]),
                el('span', {
                    className: `agent-badge ${agent.enabled ? 'enabled' : 'disabled'}`,
                }, [agent.enabled ? 'READY' : 'NO KEY']),
            ]),
            el('div', { className: 'agent-metrics' }, [
                el('span', { className: 'metric' }, [
                    'Model: ',
                    el('span', { className: 'metric-value' }, [agent.model]),
                ]),
                el('span', { className: 'metric' }, [
                    'Status: ',
                    el('span', { className: 'metric-value' }, [agent.status]),
                ]),
            ]),
        ]);
        cards.appendChild(card);
    }
    panel.appendChild(cards);
}

function renderMemoryPanel() {
    if (state.activeTab !== 'memory') return;

    const panel = $('#panel-content');
    if (!panel) return;
    panel.innerHTML = '';

    // Stats
    const stats = state.memoryStats;
    const statsEl = el('div', { className: 'memory-stats' }, [
        el('div', { className: 'stat-card' }, [
            el('div', { className: 'stat-value' }, [String(stats.total_entries || 0)]),
            el('div', { className: 'stat-label' }, ['Total']),
        ]),
        el('div', { className: 'stat-card' }, [
            el('div', { className: 'stat-value' }, [
                String((stats.by_outcome || {}).correct || 0),
            ]),
            el('div', { className: 'stat-label' }, ['Correct']),
        ]),
        el('div', { className: 'stat-card' }, [
            el('div', { className: 'stat-value' }, [
                `${((stats.avg_confidence_when_correct || 0) * 100).toFixed(0)}%`,
            ]),
            el('div', { className: 'stat-label' }, ['Avg Conf.']),
        ]),
    ]);
    panel.appendChild(statsEl);

    // Clear button
    const clearBtn = el('button', {
        className: 'btn btn-outline btn-sm mb-8',
        onClick: clearMemory,
    }, ['Clear Memory']);
    panel.appendChild(clearBtn);

    // Entries
    if (state.memory.length === 0) {
        panel.appendChild(el('div', { className: 'empty-state' }, [
            el('div', { className: 'empty-state-text' }, ['No memory entries yet.']),
        ]));
        return;
    }

    const list = el('div', { className: 'memory-list' });
    for (const entry of state.memory) {
        const entryEl = el('div', { className: 'memory-entry' }, [
            el('div', { className: 'memory-instruction' }, [
                entry.instruction?.substring(0, 100) || 'N/A',
            ]),
            el('div', { className: 'memory-answer' }, [
                `${entry.selected_agent}: ${(entry.selected_answer || '').substring(0, 80)}`,
            ]),
            el('span', {
                className: `memory-outcome ${entry.outcome || 'unknown'}`,
            }, [entry.outcome || 'unknown']),
        ]);
        list.appendChild(entryEl);
    }
    panel.appendChild(list);
}

function renderSettingsPanel() {
    if (state.activeTab !== 'settings') return;

    const panel = $('#panel-content');
    if (!panel) return;
    panel.innerHTML = '';

    panel.innerHTML = `
        <div class="settings-section">
            <div class="settings-title">API Keys</div>
            <div class="settings-field">
                <label>OpenAI API Key</label>
                <input type="password" id="setting-openai-key" placeholder="sk-...">
            </div>
            <div class="settings-field">
                <label>Anthropic API Key</label>
                <input type="password" id="setting-anthropic-key" placeholder="sk-ant-...">
            </div>
            <div class="settings-field">
                <label>Google API Key</label>
                <input type="password" id="setting-google-key" placeholder="AI...">
            </div>
            <div class="settings-field">
                <label>Microsoft / Azure API Key</label>
                <input type="password" id="setting-microsoft-key" placeholder="...">
            </div>
            <button class="btn btn-primary mt-8" onclick="saveSettings()">Save API Keys</button>
        </div>

        <div class="settings-section">
            <div class="settings-title">Models</div>
            <div class="settings-field">
                <label>OpenAI Model</label>
                <input type="text" id="setting-openai-model" value="gpt-4o">
            </div>
            <div class="settings-field">
                <label>Anthropic Model</label>
                <input type="text" id="setting-anthropic-model" value="claude-sonnet-4-20250514">
            </div>
            <div class="settings-field">
                <label>Gemini Model</label>
                <input type="text" id="setting-gemini-model" value="gemini-1.5-pro">
            </div>
        </div>
    `;
}

function renderControlsPanel() {
    if (state.activeTab !== 'controls') return;

    const panel = $('#panel-content');
    if (!panel) return;
    panel.innerHTML = '';

    panel.innerHTML = `
        <div class="controls-section">
            <div class="controls-title">Screen Capture</div>
            <div class="controls-grid">
                <button class="btn btn-success" onclick="grantScreenPermission()">Grant Permission</button>
                <button class="btn btn-outline" onclick="apiCall('POST', '/api/screen/permission?grant=false').then(() => addInfoMessage('Screen permission revoked.'))">Revoke</button>
            </div>
            <div class="settings-field mt-8">
                <label>Select Monitor / Screen</label>
                <select id="monitor-select-ctrl" onchange="state.selectedMonitor = parseInt(this.value); updateMonitorSelect();">
                    <option value="0">Grant permission to load monitors</option>
                </select>
            </div>
            <button class="btn btn-outline btn-sm mt-8" onclick="loadMonitors().then(() => { const s = document.getElementById('monitor-select-ctrl'); if(s) { s.innerHTML = document.getElementById('monitor-select')?.innerHTML || s.innerHTML; } })">Refresh Monitors</button>
        </div>

        <div class="controls-section">
            <div class="controls-title">Desktop Automation</div>
            <div class="controls-grid">
                <button class="btn btn-success" onclick="grantActionPermission()">Enable</button>
                <button class="btn btn-outline" onclick="apiCall('POST', '/api/action/permission?grant=false').then(() => { state.automationState = 'inactive'; updateAutomationStatus(); addInfoMessage('Automation disabled.'); })">Disable</button>
                <button class="btn btn-warning" onclick="pauseAutomation()">Pause</button>
                <button class="btn btn-primary" onclick="resumeAutomation()">Resume</button>
            </div>
            <button class="btn btn-danger emergency-btn" onclick="emergencyStop()">
                EMERGENCY STOP
            </button>
        </div>

        <div class="controls-section">
            <div class="controls-title">Execution Mode</div>
            <div class="controls-grid">
                <button class="btn btn-outline active" id="mode-auto">Automatic</button>
                <button class="btn btn-outline" id="mode-step">Step-by-Step</button>
            </div>
        </div>
    `;

    // Populate monitor select in controls panel
    const ctrlSelect = document.getElementById('monitor-select-ctrl');
    if (ctrlSelect && state.monitors.length > 0) {
        ctrlSelect.innerHTML = '';
        for (const mon of state.monitors) {
            const opt = document.createElement('option');
            opt.value = mon.index;
            opt.textContent = `${mon.label} (${mon.width}x${mon.height})`;
            if (mon.index === state.selectedMonitor) opt.selected = true;
            ctrlSelect.appendChild(opt);
        }
    }
}

function updateAutomationStatus() {
    const badge = $('#automation-badge');
    if (!badge) return;

    badge.className = 'status-badge ' + (
        state.automationState === 'active' ? 'active' :
        state.automationState === 'paused' ? 'paused' :
        state.automationState === 'emergency_stopped' ? 'emergency' :
        'inactive'
    );

    const labels = {
        inactive: 'Inactive',
        active: 'Active',
        paused: 'Paused',
        emergency_stopped: 'STOPPED',
    };

    badge.innerHTML = `<span class="status-dot"></span> ${labels[state.automationState] || 'Inactive'}`;
}

// ──────────────────────────────────────────────
// Tab switching
// ──────────────────────────────────────────────
function switchTab(tab) {
    state.activeTab = tab;
    $$('.panel-tab').forEach((t) => t.classList.remove('active'));
    $(`.panel-tab[data-tab="${tab}"]`)?.classList.add('active');

    switch (tab) {
        case 'agents':
            if (state.lastResult) renderAgentPanel(state.lastResult);
            else renderAgentStatusCards();
            break;
        case 'memory':
            loadMemory();
            break;
        case 'settings':
            renderSettingsPanel();
            break;
        case 'controls':
            renderControlsPanel();
            break;
    }
}

// ──────────────────────────────────────────────
// Chat input handling
// ──────────────────────────────────────────────
function setupChatInput() {
    const input = $('#chat-input');
    const sendBtn = $('#send-btn');
    const screenCheck = $('#include-screen');

    if (!input || !sendBtn) return;

    function doSend() {
        const text = input.value.trim();
        if (!text || state.processing) return;
        const includeScreen = screenCheck?.checked || false;
        sendQuery(text, includeScreen);
        input.value = '';
        input.style.height = 'auto';
    }

    sendBtn.addEventListener('click', doSend);

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            doSend();
        }
    });

    // Auto-resize textarea
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });
}

// ──────────────────────────────────────────────
// Keyboard shortcuts
// ──────────────────────────────────────────────
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+Shift+Escape = Emergency Stop
        if (e.ctrlKey && e.shiftKey && e.key === 'Escape') {
            e.preventDefault();
            emergencyStop();
        }
    });
}

// ──────────────────────────────────────────────
// Initialize
// ──────────────────────────────────────────────
function init() {
    setupChatInput();
    setupKeyboardShortcuts();
    connectWebSocket();
    loadAgents();

    // Tab click handlers
    $$('.panel-tab').forEach((tab) => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Show welcome message
    addInfoMessage(
        'Welcome to WA/D (Wisdom Assistor/Distributor)!\n\n' +
        'Configure your API keys in the Settings tab to get started. ' +
        'Then type a question or instruction below.\n\n' +
        'Keyboard shortcut: Ctrl+Shift+Escape for Emergency Stop'
    );

    // Default tab
    switchTab('agents');
}

document.addEventListener('DOMContentLoaded', init);
