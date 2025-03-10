let currentEventSource = null;

function createTask() {
    const promptInput = document.getElementById('prompt-input');
    const prompt = promptInput.value.trim();

    if (!prompt) {
        alert("Please enter a valid prompt");
        promptInput.focus();
        return;
    }

    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }

    const container = document.getElementById('task-container');
    container.innerHTML = '<div class="loading">Initializing task...</div>';
    document.getElementById('input-container').classList.add('bottom');

    fetch('/tasks', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.detail || 'Request failed') });
        }
        return response.json();
    })
    .then(data => {
        if (!data.task_id) {
            throw new Error('Invalid task ID');
        }
        setupSSE(data.task_id);
        loadHistory();
    })
    .catch(error => {
        container.innerHTML = `<div class="error">Error: ${error.message}</div>`;
        console.error('Failed to create task:', error);
    });
}

function setupSSE(taskId) {
    let retryCount = 0;
    const maxRetries = 3;
    const retryDelay = 2000;

    const container = document.getElementById('task-container');

    function connect() {
        const eventSource = new EventSource(`/tasks/${taskId}/events`);
        currentEventSource = eventSource;

        let heartbeatTimer = setInterval(() => {
            container.innerHTML += '<div class="ping">·</div>';
        }, 5000);

        const pollInterval = setInterval(() => {
            fetch(`/tasks/${taskId}`)
                .then(response => response.json())
                .then(task => {
                    updateTaskStatus(task);
                })
                .catch(error => {
                    console.error('Polling failed:', error);
                });
        }, 10000);

        const handleEvent = (event, type) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                container.querySelector('.loading')?.remove();
                container.classList.add('active');

                const stepContainer = ensureStepContainer(container);
                const { formattedContent, timestamp } = formatStepContent(data, type);
                const step = createStepElement(type, formattedContent, timestamp);

                stepContainer.appendChild(step);
                autoScroll(stepContainer);

                fetch(`/tasks/${taskId}`)
                    .then(response => response.json())
                    .then(task => {
                        updateTaskStatus(task);
                    })
                    .catch(error => {
                        console.error('Status update failed:', error);
                    });
            } catch (e) {
                console.error(`Error handling ${type} event:`, e);
            }
        };

        const eventTypes = ['think', 'tool', 'act', 'log', 'run', 'message'];
        eventTypes.forEach(type => {
            eventSource.addEventListener(type, (event) => handleEvent(event, type));
        });

        eventSource.addEventListener('complete', (event) => {
            clearInterval(heartbeatTimer);
            clearInterval(pollInterval);
            container.innerHTML += `
                <div class="complete">
                    <div>✅ Task completed</div>
                    <pre>${lastResultContent}</pre>
                </div>
            `;
            eventSource.close();
            currentEventSource = null;
        });

        eventSource.addEventListener('error', (event) => {
            clearInterval(heartbeatTimer);
            clearInterval(pollInterval);
            try {
                const data = JSON.parse(event.data);
                container.innerHTML += `
                    <div class="error">
                        ❌ Error: ${data.message}
                    </div>
                `;
                eventSource.close();
                currentEventSource = null;
            } catch (e) {
                console.error('Error handling failed:', e);
            }
        });

        eventSource.onerror = (err) => {
            if (eventSource.readyState === EventSource.CLOSED) return;

            console.error('SSE connection error:', err);
            clearInterval(heartbeatTimer);
            clearInterval(pollInterval);
            eventSource.close();

            if (retryCount < maxRetries) {
                retryCount++;
                container.innerHTML += `
                    <div class="warning">
                        ⚠ Connection lost, retrying in ${retryDelay/1000} seconds (${retryCount}/${maxRetries})...
                    </div>
                `;
                setTimeout(connect, retryDelay);
            } else {
                container.innerHTML += `
                    <div class="error">
                        ⚠ Connection lost, please try refreshing the page
                    </div>
                `;
            }
        };
    }

    connect();
}

function loadHistory() {
    fetch('/tasks')
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(`请求失败: ${response.status} - ${text.substring(0, 100)}`);
            });
        }
        return response.json();
    })
    .then(tasks => {
        const listContainer = document.getElementById('task-list');
        listContainer.innerHTML = tasks.map(task => `
            <div class="task-card" data-task-id="${task.id}">
                <div>${task.prompt}</div>
                <div class="task-meta">
                    ${new Date(task.created_at).toLocaleString()} -
                    <span class="status status-${task.status ? task.status.toLowerCase() : 'unknown'}">
                        ${task.status || '未知状态'}
                    </span>
                </div>
            </div>
        `).join('');
    })
    .catch(error => {
        console.error('加载历史记录失败:', error);
        const listContainer = document.getElementById('task-list');
        listContainer.innerHTML = `<div class="error">加载失败: ${error.message}</div>`;
    });
}


function ensureStepContainer(container) {
    let stepContainer = container.querySelector('.step-container');
    if (!stepContainer) {
        container.innerHTML = '<div class="step-container"></div>';
        stepContainer = container.querySelector('.step-container');
    }
    return stepContainer;
}

function formatStepContent(data, eventType) {
    return {
        formattedContent: data.result,
        timestamp: new Date().toLocaleTimeString()
    };
}

function createStepElement(type, content, timestamp) {
    const step = document.createElement('div');
    step.className = `step-item ${type}`;
    step.innerHTML = `
        <div class="log-line">
            <span class="log-prefix">${getEventIcon(type)} [${timestamp}] ${getEventLabel(type)}:</span>
            <pre>${content}</pre>
        </div>
    `;
    return step;
}

function autoScroll(element) {
    requestAnimationFrame(() => {
        element.scrollTo({
            top: element.scrollHeight,
            behavior: 'smooth'
        });
    });
    setTimeout(() => {
        element.scrollTop = element.scrollHeight;
    }, 100);
}


function getEventIcon(eventType) {
    const icons = {
        'think': '🤔',
        'tool': '🛠️',
        'act': '🚀',
        'result': '🏁',
        'error': '❌',
        'complete': '✅',
        'log': '📝',
        'run': '⚙️'
    };
    return icons[eventType] || 'ℹ️';
}

function getEventLabel(eventType) {
    const labels = {
        'think': 'Thinking',
        'tool': 'Using Tool',
        'act': 'Action',
        'result': 'Result',
        'error': 'Error',
        'complete': 'Complete',
        'log': 'Log',
        'run': 'Running'
    };
    return labels[eventType] || 'Info';
}

function updateTaskStatus(task) {
    const statusBar = document.getElementById('status-bar');
    if (!statusBar) return;

    if (task.status === 'completed') {
        statusBar.innerHTML = `<span class="status-complete">✅ Task completed</span>`;
    } else if (task.status === 'failed') {
        statusBar.innerHTML = `<span class="status-error">❌ Task failed: ${task.error || 'Unknown error'}</span>`;
    } else {
        statusBar.innerHTML = `<span class="status-running">⚙️ Task running: ${task.status}</span>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadHistory();

    document.getElementById('prompt-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            createTask();
        }
    });

    const historyToggle = document.getElementById('history-toggle');
    if (historyToggle) {
        historyToggle.addEventListener('click', () => {
            const historyPanel = document.getElementById('history-panel');
            if (historyPanel) {
                historyPanel.classList.toggle('open');
                historyToggle.classList.toggle('active');
            }
        });
    }

    const clearButton = document.getElementById('clear-btn');
    if (clearButton) {
        clearButton.addEventListener('click', () => {
            document.getElementById('prompt-input').value = '';
            document.getElementById('prompt-input').focus();
        });
    }
});
