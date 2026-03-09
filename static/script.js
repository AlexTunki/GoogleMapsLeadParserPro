let allCities = [];
let allNiches = [];
let selectedCities = [];
let selectedNiches = [];
let tasks = [];
let defaultSettings = {};
let sseSource = null;
let editingTaskId = null;

// Initialize
window.onload = async () => {
    // Load data lists
    try {
        const res = await fetch('/api/data');
        const data = await res.json();
        allCities = data.cities;
        allNiches = data.niches;
    } catch (e) { }

    setupCombobox('city-input', 'city-list', allCities, (val) => {
        if (val && !selectedCities.includes(val)) {
            selectedCities.push(val);
            renderCityTags();
            document.getElementById('city-input').value = '';
        }
    });

    setupCombobox('niche-input', 'niche-list', allNiches, (val) => {
        if (val && !selectedNiches.includes(val)) {
            selectedNiches.push(val);
            renderNicheTags();
            document.getElementById('niche-input').value = '';
        }
    });

    await loadSettings();
    await loadProjects();
    connectSSE();
};

async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        defaultSettings = await res.json();
    } catch (e) {
        defaultSettings = {
            quota: 100, radius: 20.0, step: 6.0,
            filters_enabled: false, min_rev: 0, max_rev: 50, freshness: 'Any'
        };
    }
}

async function saveSettings() {
    const s = {
        quota: parseInt(document.getElementById('def-quota').value) || 100,
        radius: parseFloat(document.getElementById('def-radius').value) || 20.0,
        step: parseFloat(document.getElementById('def-step').value) || 6.0,
        filters_enabled: document.getElementById('def-filter-toggle').checked,
        min_rev: parseInt(document.getElementById('def-min').value) || 0,
        max_rev: parseInt(document.getElementById('def-max').value) || 50,
        freshness: document.getElementById('def-freshness').value || 'Any',
        mode: document.getElementById('def-mode').value || 'Medium'
    };

    await fetch('/api/settings', {
        method: 'POST', body: JSON.stringify(s),
        headers: { 'Content-Type': 'application/json' }
    });

    defaultSettings = s;
    alert('Default settings successfully saved!');
    showPanel('welcome-panel');
}

function openSettingsPanel() {
    document.getElementById('def-quota').value = defaultSettings.quota;
    document.getElementById('def-radius').value = defaultSettings.radius;
    document.getElementById('def-step').value = defaultSettings.step;
    document.getElementById('def-filter-toggle').checked = defaultSettings.filters_enabled;
    document.getElementById('def-min').value = defaultSettings.min_rev;
    document.getElementById('def-max').value = defaultSettings.max_rev;
    document.getElementById('def-freshness').value = defaultSettings.freshness;
    document.getElementById('def-mode').value = defaultSettings.mode || 'Medium';
    showPanel('settings-panel');
}

function setupCombobox(inputId, listId, sourceArray, onSelect) {
    const input = document.getElementById(inputId);
    const list = document.getElementById(listId);

    function renderList(matches) {
        list.innerHTML = '';
        if (matches.length === 0) {
            list.classList.remove('open');
            return;
        }
        matches.forEach(m => {
            const div = document.createElement('div');
            div.className = 'combo-item';
            div.textContent = m;
            div.onclick = () => {
                input.value = m;
                list.classList.remove('open');
                onSelect(m);
            };
            list.appendChild(div);
        });
        list.classList.add('open');
    }

    input.addEventListener('input', () => {
        const val = input.value.toLowerCase();
        const matches = sourceArray.filter(i => i.toLowerCase().includes(val)).slice(0, 50); // limit 50 max
        renderList(matches);
    });

    input.addEventListener('focus', () => {
        const val = input.value.toLowerCase();
        let matches = sourceArray;
        if (val) matches = sourceArray.filter(i => i.toLowerCase().includes(val));
        renderList(matches.slice(0, 50));
    });

    document.addEventListener('click', (e) => {
        if (!input.contains(e.target) && !list.contains(e.target)) {
            list.classList.remove('open');
        }
    });
}

function renderTags(containerId, dataArray, onRemoveCb) {
    const cont = document.getElementById(containerId);
    cont.innerHTML = '';
    dataArray.forEach(item => {
        const tag = document.createElement('div');
        tag.className = 'tag';
        tag.innerHTML = `<span>${item}</span>`;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.innerHTML = '✖';
        btn.onclick = (e) => {
            e.preventDefault();
            onRemoveCb(item);
        };
        tag.appendChild(btn);
        cont.appendChild(tag);
    });
}

function renderCityTags() {
    renderTags('city-tags', selectedCities, (v) => {
        selectedCities = selectedCities.filter(c => c !== v);
        renderCityTags();
    });
}

function renderNicheTags() {
    renderTags('niche-tags', selectedNiches, (v) => {
        selectedNiches = selectedNiches.filter(c => c !== v);
        renderNicheTags();
    });
}

function addCity() {
    const input = document.getElementById('city-input');
    const val = input.value.trim();
    if (val && !selectedCities.includes(val)) {
        selectedCities.push(val);
        renderCityTags();
        input.value = '';
    }
}

function addNiche() {
    const input = document.getElementById('niche-input');
    const val = input.value.trim();
    if (val && !selectedNiches.includes(val)) {
        selectedNiches.push(val);
        renderNicheTags();
        input.value = '';
    }
}

async function loadProjects() {
    const res = await fetch('/api/projects');
    tasks = await res.json();
    renderSidebarTasks();
}

function renderSidebarTasks() {
    const list = document.getElementById('task-list');
    list.innerHTML = '';
    tasks.forEach((t, index) => {
        const item = document.createElement('div');
        item.className = 'task-item';
        // HTML safe
        const nameEscaped = t.name.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        item.innerHTML = `
            <div style="flex:1" onclick="viewTask(${index})">${nameEscaped}</div>
            <button class="task-del" onclick="deleteTask(event, ${index})">✖</button>
        `;
        list.appendChild(item);
    });
}

function openAddTaskPanel() {
    editingTaskId = null;
    document.getElementById('task-name').value = `Task ${tasks.length + 1}`;
    document.getElementById('task-quota').value = defaultSettings.quota || 100;
    document.getElementById('task-radius').value = defaultSettings.radius || 20.0;
    document.getElementById('task-step').value = defaultSettings.step || 6.0;
    document.getElementById('task-mode').value = defaultSettings.mode || 'Medium';

    const filterToggle = document.getElementById('filter-toggle');
    const filterBox = document.getElementById('filters-box');
    filterToggle.checked = defaultSettings.filters_enabled || false;
    if (defaultSettings.filters_enabled) {
        filterBox.classList.add('open');
    } else {
        filterBox.classList.remove('open');
    }

    document.getElementById('filter-min').value = defaultSettings.min_rev !== undefined ? defaultSettings.min_rev : 0;
    document.getElementById('filter-max').value = defaultSettings.max_rev !== undefined ? defaultSettings.max_rev : 50;
    document.getElementById('filter-freshness').value = defaultSettings.freshness || 'Any';

    selectedCities = [];
    selectedNiches = [];
    renderCityTags();
    renderNicheTags();
    showPanel('add-task-panel');
}

async function saveTask() {
    const tName = document.getElementById('task-name').value || `Task ${tasks.length + 1}`;

    // Check for duplicate names
    for (let i = 0; i < tasks.length; i++) {
        if (tasks[i].name.toLowerCase() === tName.toLowerCase() && i !== editingTaskId) {
            alert('A Task with this name already exists! Please choose another name.');
            return;
        }
    }
    const quota = parseInt(document.getElementById('task-quota').value) || 0;
    const rad = parseFloat(document.getElementById('task-radius').value) || 20.0;
    const stp = parseFloat(document.getElementById('task-step').value) || 6.0;

    const useFilters = document.getElementById('filter-toggle').checked;
    const minR = parseInt(document.getElementById('filter-min').value) || 0;
    const maxR = parseInt(document.getElementById('filter-max').value) || 1000;
    const fresh = document.getElementById('filter-freshness').value;
    const pMode = document.getElementById('task-mode').value || 'Medium';

    const task = {
        name: tName, quota: quota,
        cities: [...selectedCities], niches: [...selectedNiches],
        radius: rad, step: stp, mode: pMode,
        filters: { enabled: useFilters, min_rev: minR, max_rev: maxR, freshness: fresh }
    };

    if (editingTaskId !== null) {
        tasks[editingTaskId] = task;
        editingTaskId = null;
    } else {
        tasks.push(task);
    }

    await fetch('/api/projects', {
        method: 'POST', body: JSON.stringify(tasks),
        headers: { 'Content-Type': 'application/json' }
    });

    renderSidebarTasks();
    showPanel('welcome-panel');

    // reset fields
    selectedCities = [];
    selectedNiches = [];
    renderCityTags();
    renderNicheTags();
}

async function deleteTask(e, idx) {
    if (e) e.stopPropagation();
    tasks.splice(idx, 1);
    await fetch('/api/projects', {
        method: 'POST', body: JSON.stringify(tasks),
        headers: { 'Content-Type': 'application/json' }
    });
    renderSidebarTasks();
    showPanel('welcome-panel');
}

function editTask(idx) {
    editingTaskId = idx;
    const t = tasks[idx];

    document.getElementById('task-name').value = t.name;
    document.getElementById('task-quota').value = t.quota;
    document.getElementById('task-radius').value = t.radius;
    document.getElementById('task-step').value = t.step;
    document.getElementById('task-mode').value = t.mode || 'Medium';

    const filterToggle = document.getElementById('filter-toggle');
    const filterBox = document.getElementById('filters-box');
    filterToggle.checked = t.filters.enabled;
    if (t.filters.enabled) {
        filterBox.classList.add('open');
    } else {
        filterBox.classList.remove('open');
    }

    document.getElementById('filter-min').value = t.filters.min_rev;
    document.getElementById('filter-max').value = t.filters.max_rev;
    document.getElementById('filter-freshness').value = t.filters.freshness || 'Any';

    selectedCities = [...t.cities];
    selectedNiches = [...t.niches];
    renderCityTags();
    renderNicheTags();

    showPanel('add-task-panel');
}

function viewTask(idx) {
    const t = tasks[idx];
    const c = document.getElementById('view-task-content');
    const fStatus = t.filters.enabled ?
        `<span style="color:var(--accent)">ENABLED (From ${t.filters.min_rev} to ${t.filters.max_rev}, Freshness: ${t.filters.freshness})</span>` :
        `<span style="color:var(--text-muted)">DISABLED</span>`;

    c.innerHTML = `
        <h2>💼 Task: ${t.name.replace(/</g, "&lt;")}</h2>
        <div style="font-size:16px; line-height:1.8;">
            <div>🎯 Leads total quota: <b>${t.quota} pcs.</b></div>
            <div>🏙 Cities: <b>${t.cities.length}</b></div>
            <div>🔧 Niches: <b>${t.niches.length}</b></div>
            <div>📍 Grid: <b>Radius ${t.radius} km, Step ${t.step} km</b></div>
            <div>🚀 Speed Mode: <b>${t.mode || 'Medium'}</b></div>
            <div>🛡 Filters: <b>${fStatus}</b></div>
        </div>
        <button class="btn btn-primary" style="margin-top: 20px;" onclick="editTask(${idx})">✏️ Edit Task</button>
    `;
    showPanel('view-task-panel');
}

function showPanel(id) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

async function startParsing() {
    if (tasks.length === 0) return alert("Please create a task first!");
    showPanel('dashboard-panel');
    document.getElementById('dash-status').innerText = 'Status: ⚙ RUNNING';
    await fetch('/api/start', { method: 'POST' });
}

async function stopEngine() {
    await fetch('/api/stop', { method: 'POST' });
    document.getElementById('dash-status').innerText = 'Status: 🛑 STOPPED';
}

async function togglePause() {
    const res = await fetch('/api/pause', { method: 'POST' });
    const data = await res.json();
    const btn = document.getElementById('btn-pause');
    if (data.paused) {
        document.getElementById('dash-status').innerText = 'Status: ⏸ PAUSED';
        btn.innerText = '▶ Resume';
    } else {
        document.getElementById('dash-status').innerText = 'Status: ⚙ RUNNING';
        btn.innerText = '⏸ Pause';
    }
}

async function skip(type) {
    await fetch(`/api/skip/${type}`, { method: 'POST' });
}

function connectSSE() {
    if (sseSource) sseSource.close();
    sseSource = new EventSource('/api/stream');

    sseSource.onmessage = function (event) {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'LOG') {
                const term = document.getElementById('terminal-log');
                const line = document.createElement('div');
                line.className = 'log-line';
                line.style.color = msg.color || 'white';
                line.innerText = msg.text;
                term.appendChild(line);
                term.scrollTop = term.scrollHeight; // auto-scroll
            } else if (msg.type === 'PROGRESS') {
                document.getElementById('dash-progress').innerText = msg.info;
            } else if (msg.type === 'BAR') {
                document.getElementById('dash-progress-fill').style.width = msg.progress + '%';
                document.getElementById('dash-progress').innerText = msg.text;
            }
        } catch (e) { }
    };
}