const API = '/api/v1'; // Using the new API path
let currentRequestId = null;
let currentMachineId = null;
let partnersList = [];

const STAGES = [
    { id: 'quotation', label: 'Quotation' },
    { id: 'supplier_interaction', label: 'Supplier' },
    { id: 'selection', label: 'Selection' },
    { id: 'contracting', label: 'Contracting' },
    { id: 'installation', label: 'Installation' },
    { id: 'technical_acceptance', label: 'Acceptance' },
    { id: 'completed', label: 'Done' }
];

async function fetchAPI(endpoint, options = {}) {
    const token = localStorage.getItem('token');
    if (!options.headers) options.headers = {};
    if (token) {
        options.headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(`${API}${endpoint}`, options);
    if (res.status === 401) {
        showLogin();
        return null;
    }
    if (!res.ok) {
        const err = await res.json();
        alert(`Error: ${err.detail || 'Request failed'}`);
        return null;
    }
    return res.json();
}

function showLogin() {
    document.getElementById('loginOverlay').style.setProperty('display', 'flex', 'important');
}

function hideLogin() {
    document.getElementById('loginOverlay').style.setProperty('display', 'none', 'important');
}

document.getElementById('loginForm').onsubmit = async (e) => {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;

    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const res = await fetch(`${API}/auth/login/access-token`, {
        method: 'POST',
        body: formData
    });

    if (res.ok) {
        const data = await res.json();
        localStorage.setItem('token', data.access_token);
        hideLogin();
        initApp();
    } else {
        alert('Login failed. Check credentials.');
    }
};

// Workflows
async function loadRequests() {
    const data = await fetchAPI('/requests/');
    const tbody = document.getElementById('requestTableBody');
    tbody.innerHTML = '';
    data.forEach(req => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="ps-3 fw-bold">#${req.id}</td>
            <td>${req.client_id}</td>
            <td><span class="badge bg-light text-dark border status-badge">${req.status.replace('_', ' ')}</span></td>
            <td class="small text-muted">${new Date(req.created_at).toLocaleDateString()}</td>
            <td class="text-end pe-3">
                <button class="btn btn-sm btn-primary" onclick="viewRequest(${req.id})">Manage</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function viewRequest(id) {
    currentRequestId = id;
    const req = await fetchAPI(`/requests/${id}`);
    if (!req) return;

    document.getElementById('listPanel').style.display = 'none';
    document.getElementById('detailsPanel').style.display = 'block';
    document.getElementById('detailTitle').innerText = `Flow Control: #${req.id} - ${req.client_id}`;

    // Render Stepper
    const stepper = document.getElementById('workflowStepper');
    stepper.innerHTML = '';
    let reachedActive = false;
    STAGES.forEach((stage, index) => {
        const item = document.createElement('div');
        item.className = 'step-item';
        if (stage.id === req.status) {
            item.classList.add('active');
            reachedActive = true;
        } else if (!reachedActive) {
            item.classList.add('completed');
        }
        item.innerHTML = `
            <div class="step-circle">${reachedActive && stage.id !== req.status ? index + 1 : (item.classList.contains('completed') ? '✓' : index + 1)}</div>
            <div>${stage.label}</div>
        `;
        stepper.appendChild(item);
    });

    // Quotes
    const quotesList = document.getElementById('quotesList');
    quotesList.innerHTML = '';
    if (req.quotes.length === 0) {
        quotesList.innerHTML = '<p class="text-muted small italic">Waiting for supplier proposals...</p>';
    } else {
        req.quotes.forEach(q => {
            const isSelected = req.selected_quote_id === q.id;
            const card = document.createElement('div');
            card.className = `card mb-2 ${isSelected ? 'border-success' : ''}`;
            card.innerHTML = `
                <div class="card-body p-2 d-flex justify-content-between align-items-center">
                    <div class="small">
                        <strong>Partner #${q.partner_id}</strong>: $${q.price}<br>
                        <span class="text-muted">${q.details}</span>
                    </div>
                    ${isSelected ? '<span class="badge bg-success">Selected</span>' :
                    (req.status === 'quotation' || req.status === 'supplier_interaction' ? `<button class="btn btn-xs btn-outline-success" onclick="selectQuote(${q.id})">Select</button>` : '')}
                </div>
            `;
            quotesList.appendChild(card);
        });
    }

    // Documents
    const docList = document.getElementById('documentList');
    docList.innerHTML = '';
    if (req.documents.length === 0) {
        docList.innerHTML = '<p class="text-muted small">No documents uploaded.</p>';
    } else {
        req.documents.forEach(doc => {
            const div = document.createElement('div');
            div.className = 'd-flex justify-content-between align-items-center mb-1 small border-bottom pb-1';
            div.innerHTML = `
                <span><i class="bi bi-file-earmark-pdf me-2"></i>${doc.doc_type} (${doc.filename})</span>
                <a href="${API}/documents/download/${doc.id}" class="btn btn-xs btn-link p-0 text-primary">Download</a>
            `;
            docList.appendChild(div);
        });
    }

    // Contract Inputs
    document.getElementById('contractExp').value = req.contract_expiration || '';
    document.getElementById('adjMonth').value = req.adjustment_month || '';

    // Final Action
    const actionArea = document.getElementById('finalActionArea');
    actionArea.innerHTML = '';
    if (req.status === 'technical_acceptance') {
        actionArea.innerHTML = '<button class="btn btn-primary" onclick="completeAcceptance()">Grant Technical Acceptance</button>';
    } else if (req.status === 'completed') {
        actionArea.innerHTML = '<div class="alert alert-success py-2 mb-0 d-inline-block">Project Successfully Completed</div>';
    }

    loadTimeline(id);
}

async function loadTimeline(id) {
    const data = await fetchAPI(`/requests/${id}/timeline`);
    const container = document.getElementById('requestTimeline');
    container.innerHTML = '';
    data.forEach(log => {
        const li = document.createElement('li');
        li.className = 'list-group-item px-0 py-2 border-0 d-flex';
        li.innerHTML = `
            <div class="me-3 text-muted" style="min-width: 80px;">${new Date(log.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
            <div>
                <div class="fw-bold">${log.action.replace('_', ' ')}</div>
                <div class="text-muted small">${log.details ? JSON.stringify(log.details) : ''}</div>
            </div>
        `;
        container.appendChild(li);
    });
}

function hideDetails() {
    document.getElementById('listPanel').style.display = 'block';
    document.getElementById('detailsPanel').style.display = 'none';
    loadRequests();
}

// Machines
async function loadMachines() {
    const data = await fetchAPI('/machines/');
    const tbody = document.getElementById('machineTableBody');
    tbody.innerHTML = '';
    data.forEach(m => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="ps-3">${m.serial_number}</td>
            <td>${m.brand} ${m.model}</td>
            <td><span class="badge bg-info">${m.status}</span></td>
            <td>${m.location || 'N/A'}</td>
            <td class="text-end pe-3">
                <button class="btn btn-sm btn-outline-secondary" onclick="viewMachineHistory(${m.id})">History</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function viewMachineHistory(id) {
    currentMachineId = id;
    const maintenance = await fetchAPI(`/machines/${id}/maintenance`);
    const historyList = document.getElementById('machineHistoryList');
    historyList.innerHTML = '';
    if (maintenance.length === 0) {
        historyList.innerHTML = '<p class="text-muted small">No maintenance records found.</p>';
    } else {
        maintenance.forEach(log => {
            const div = document.createElement('div');
            div.className = 'border-bottom mb-2 pb-2 small';
            div.innerHTML = `
                <div class="d-flex justify-content-between">
                    <strong>${log.date}</strong>
                    <span>${log.technician}</span>
                </div>
                <div>${log.description}</div>
                ${log.next_maintenance_date ? `<div class="text-primary">Next due: ${log.next_maintenance_date}</div>` : ''}
            `;
            historyList.appendChild(div);
        });
    }
    new bootstrap.Modal(document.getElementById('machineHistoryModal')).show();
}

// Partners & Notifications
async function loadPartners() {
    partnersList = await fetchAPI('/partners/');
    const tbody = document.getElementById('partnerTableBody');
    tbody.innerHTML = '';
    partnersList.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${p.name}</td><td>${p.contact_info}</td><td>${p.id}</td>`;
        tbody.appendChild(tr);
    });
}

async function loadNotifications() {
    const data = await fetchAPI('/requests/notifications/upcoming');
    const container = document.getElementById('notificationContainer');
    container.innerHTML = '';
    if (!data || data.length === 0) {
        container.innerHTML = '<div class="text-center py-4 text-muted small">No pending alerts.</div>';
        return;
    }
    data.forEach(n => {
        const div = document.createElement('div');
        div.className = 'p-3 border-bottom';
        div.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="badge bg-warning text-dark">Action Required</span>
                <span class="small text-muted">ID #${n.id}</span>
            </div>
            <div class="small fw-bold">${n.client_id}</div>
            <div class="small text-muted">${n.contract_expiration ? 'Expiring: ' + n.contract_expiration : 'Adjustment Due'}</div>
        `;
        container.appendChild(div);
    });
}

// Actions
async function selectQuote(qId) {
    await fetchAPI(`/requests/${currentRequestId}/select-quote?quote_id=${qId}`, { method: 'POST' });
    viewRequest(currentRequestId);
}

async function uploadDoc() {
    const type = document.getElementById('docTypeSelect').value;
    const fileInput = document.getElementById('docFileInput');
    if (!fileInput.files[0]) return alert('Select a file');

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    const token = localStorage.getItem('token');
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API}/documents/${currentRequestId}/upload?doc_type=${type}`, {
        method: 'POST',
        headers: headers,
        body: formData
    });
    if (res.ok) {
        fileInput.value = '';
        viewRequest(currentRequestId);
    } else {
        alert('Upload failed');
    }
}

async function updateContract() {
    const expiration = document.getElementById('contractExp').value;
    const month = document.getElementById('adjMonth').value;
    await fetchAPI(`/requests/${currentRequestId}/contract-details`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            contract_expiration: expiration || null,
            adjustment_month: month ? parseInt(month) : null
        })
    });
    alert('Details updated');
    viewRequest(currentRequestId);
    loadNotifications();
}

async function completeAcceptance() {
    await fetchAPI(`/requests/${currentRequestId}/complete-technical-acceptance`, { method: 'POST' });
    viewRequest(currentRequestId);
}

// Event Listeners
document.getElementById('newRequestForm').onsubmit = async (e) => {
    e.preventDefault();
    const client_id = document.getElementById('reqClientId').value;
    const description = document.getElementById('reqDescription').value;
    const res = await fetchAPI('/requests/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id, description })
    });
    if (res) {
        bootstrap.Modal.getInstance(document.getElementById('newRequestModal')).hide();
        loadRequests();
    }
};

document.getElementById('newMachineForm').onsubmit = async (e) => {
    e.preventDefault();
    const data = {
        serial_number: document.getElementById('macSerial').value,
        model: document.getElementById('macModel').value,
        brand: document.getElementById('macBrand').value,
        location: document.getElementById('macLocation').value
    };
    await fetchAPI('/machines/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    bootstrap.Modal.getInstance(document.getElementById('newMachineModal')).hide();
    loadMachines();
};

document.getElementById('maintenanceLogForm').onsubmit = async (e) => {
    e.preventDefault();
    const data = {
        machine_id: currentMachineId,
        date: document.getElementById('maintDate').value,
        description: document.getElementById('maintDesc').value,
        technician: document.getElementById('maintTech').value,
        next_maintenance_date: document.getElementById('maintNext').value || null
    };
    await fetchAPI(`/machines/${currentMachineId}/maintenance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    viewMachineHistory(currentMachineId);
    document.getElementById('maintenanceLogForm').reset();
};

// Kanban
async function loadKanban() {
    const data = await fetchAPI('/requests/');
    const board = document.getElementById('kanbanBoard');
    board.innerHTML = '';

    STAGES.forEach(stage => {
        const col = document.createElement('div');
        col.className = 'kanban-col';
        col.innerHTML = `<div class="kanban-header text-uppercase small">${stage.label}</div>`;

        const stageRequests = data.filter(r => r.status === stage.id);
        stageRequests.forEach(req => {
            const card = document.createElement('div');
            card.className = 'kanban-card';
            card.innerHTML = `
                <div class="fw-bold small">#${req.id} - ${req.client_id}</div>
                <div class="text-muted extra-small" style="font-size: 0.7rem;">${new Date(req.created_at).toLocaleDateString()}</div>
            `;
            card.onclick = () => viewRequest(req.id);
            col.appendChild(card);
        });
        board.appendChild(col);
    });
}

// Tab Navigation
function showTab(tabId) {
    document.querySelectorAll('.tab-content-panel').forEach(p => p.style.display = 'none');
    document.getElementById(tabId + 'Panel').style.display = 'block';
    document.getElementById('detailsPanel').style.display = 'none';

    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    if (event) event.target.classList.add('active');

    if (tabId === 'list') loadRequests();
    if (tabId === 'kanban') loadKanban();
    if (tabId === 'machine') loadMachines();
}

// Initial Load
function initApp() {
    loadRequests();
    loadPartners();
    loadNotifications();
}

if (!localStorage.getItem('token')) {
    showLogin();
} else {
    initApp();
}

setInterval(() => {
    if (localStorage.getItem('token')) loadNotifications();
}, 60000);
