let currentEventSource = null;
let historyVisible = false; // Track history panel status

function createTask() {
    const promptInput = document.getElementById('prompt-input');
    const prompt = promptInput.value.trim();

    if (!prompt) {
        alert("Please enter a valid task");
        promptInput.focus();
        return;
    }

    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }

    const taskContainer = document.getElementById('task-container');
    const stepsContainer = document.getElementById('steps-container');
    const resultContainer = document.getElementById('result-container');
    const container = document.querySelector('.container');
    const resultPanel = document.getElementById('result-panel');

    // Reset UI state
    resetUIState();

    // Hide welcome message, show step loading status
    const welcomeMessage = taskContainer.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.style.display = 'none';
    }

    stepsContainer.innerHTML = '<div class="loading">Initializing task...</div>';
    resultContainer.innerHTML = '';

    // Close history panel on mobile devices
    closeHistoryOnMobile();

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
            promptInput.value = '';
        })
        .catch(error => {
            stepsContainer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
            updateResultPanel({ result: error.message }, 'error');
            showResultPanel();
            console.error('Failed to create task:', error);
        });
}

// Independent function to reset UI state, avoid duplicate code
function resetUIState() {
    const container = document.querySelector('.container');
    const resultPanel = document.getElementById('result-panel');

    // Reset container layout
    container.classList.remove('with-result');
    container.style.width = '98%';

    // Ensure result panel is completely hidden
    if (resultPanel) {
        resultPanel.classList.add('hidden');
        resultPanel.style.display = 'none';
    }

    // Trigger layout adjustment
    handleResponsiveLayout();
}

function setupSSE(taskId) {
    let retryCount = 0;
    const maxRetries = 3;
    const retryDelay = 2000;
    let lastResultContent = '';
    let stepsData = [];

    const stepsContainer = document.getElementById('steps-container');
    const resultContainer = document.getElementById('result-container');

    // Hide result panel by default
    hideResultPanel();

    function connect() {
        const eventSource = new EventSource(`/tasks/${taskId}/events`);
        currentEventSource = eventSource;

        let heartbeatTimer = setInterval(() => {
            const pingDiv = document.createElement('div');
            pingDiv.className = 'ping';
            pingDiv.innerHTML = '·';
            stepsContainer.appendChild(pingDiv);
        }, 5000);

        // Initial polling
        fetch(`/tasks/${taskId}`)
            .then(response => response.json())
            .then(task => {
                updateTaskStatus(task);
            })
            .catch(error => {
                console.error('Initial status retrieval failed:', error);
            });

        const handleEvent = (event, type) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                const loadingDiv = stepsContainer.querySelector('.loading');
                if (loadingDiv) loadingDiv.remove();

                const { formattedContent, timestamp, isoTimestamp } = formatStepContent(data, type);

                stepsData.push({
                    type: type,
                    content: formattedContent,
                    timestamp: timestamp,
                    isoTimestamp: isoTimestamp,
                    element: createStepElement(type, formattedContent, timestamp)
                });

                stepsData.sort((a, b) => {
                    return new Date(a.isoTimestamp) - new Date(b.isoTimestamp);
                });

                stepsContainer.innerHTML = '';
                stepsData.forEach(step => {
                    stepsContainer.appendChild(step.element);
                });

                document.querySelectorAll('.step-item').forEach(item => {
                    item.classList.remove('active');
                });

                const latestStep = stepsData[stepsData.length - 1];
                if (latestStep && latestStep.element) {
                    latestStep.element.classList.add('active');
                }

                autoScroll(stepsContainer);

                if (type === 'tool' || type === 'act' || type === 'result') {
                    updateResultPanel(data, type);
                    showResultPanel();
                }

                fetch(`/tasks/${taskId}`)
                    .then(response => response.json())
                    .then(task => {
                        updateTaskStatus(task);
                    })
                    .catch(error => {
                        console.error('Failed to update status:', error);
                    });
            } catch (e) {
                console.error(`Error processing ${type} event:`, e);
            }
        };

        const eventTypes = ['think', 'tool', 'act', 'log', 'run', 'message'];
        eventTypes.forEach(type => {
            eventSource.addEventListener(type, (event) => handleEvent(event, type));
        });

        eventSource.addEventListener('complete', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                lastResultContent = data.result || '';

                const completeDiv = document.createElement('div');
                completeDiv.className = 'complete';
                completeDiv.innerHTML = '<div>✅ Task completed</div>';
                stepsContainer.appendChild(completeDiv);

                updateResultPanel({ result: lastResultContent }, 'complete');
                showResultPanel();

                fetch(`/tasks/${taskId}`)
                    .then(response => response.json())
                    .then(task => {
                        updateTaskStatus(task);
                    })
                    .catch(error => {
                        console.error('Failed to update final status:', error);
                    });

                eventSource.close();
                currentEventSource = null;
            } catch (e) {
                console.error('Error processing completion event:', e);
            }
        });

        eventSource.addEventListener('error', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error';
                errorDiv.innerHTML = `<div>❌ Error: ${data.message}</div>`;
                stepsContainer.appendChild(errorDiv);

                updateResultPanel({ result: data.message }, 'error');
                showResultPanel();

                eventSource.close();
                currentEventSource = null;
            } catch (e) {
                console.error('Error processing error:', e);
            }
        });

        eventSource.onerror = (err) => {
            if (eventSource.readyState === EventSource.CLOSED) return;

            console.error('SSE connection error:', err);
            clearInterval(heartbeatTimer);
            eventSource.close();

            fetch(`/tasks/${taskId}`)
                .then(response => response.json())
                .then(task => {
                    if (task.status === 'completed' || task.status === 'failed') {
                        updateTaskStatus(task);
                        if (task.status === 'completed') {
                            const completeDiv = document.createElement('div');
                            completeDiv.className = 'complete';
                            completeDiv.innerHTML = '<div>✅ Task completed</div>';
                            stepsContainer.appendChild(completeDiv);

                            if (task.steps && task.steps.length > 0) {
                                const lastStep = task.steps[task.steps.length - 1];
                                updateResultPanel({ result: lastStep.result }, 'complete');
                                showResultPanel();
                            }
                        } else {
                            const errorDiv = document.createElement('div');
                            errorDiv.className = 'error';
                            errorDiv.innerHTML = `<div>❌ Error: ${task.error || 'Task failed'}</div>`;
                            stepsContainer.appendChild(errorDiv);

                            updateResultPanel({ result: task.error || 'Task failed' }, 'error');
                            showResultPanel();
                        }
                    } else if (retryCount < maxRetries) {
                        retryCount++;
                        const warningDiv = document.createElement('div');
                        warningDiv.className = 'warning';
                        warningDiv.innerHTML = `<div>⚠ Connection lost, retrying in ${retryDelay / 1000} seconds (${retryCount}/${maxRetries})...</div>`;
                        stepsContainer.appendChild(warningDiv);
                        setTimeout(connect, retryDelay);
                    } else {
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'error';
                        errorDiv.innerHTML = '<div>⚠ Connection lost, please refresh the page</div>';
                        stepsContainer.appendChild(errorDiv);

                        updateResultPanel({ result: 'Connection lost, please refresh the page' }, 'error');
                        showResultPanel();
                    }
                })
                .catch(error => {
                    console.error('Failed to check task status:', error);
                    if (retryCount < maxRetries) {
                        retryCount++;
                        setTimeout(connect, retryDelay);
                    }
                });
        };
    }

    connect();
}

function updateResultPanel(data, type) {
    const resultContainer = document.getElementById('result-container');
    const currentStep = document.getElementById('current-step');

    if (!resultContainer || !currentStep) return;

    // Update top step information
    const typeLabel = getEventLabel(type);
    const icon = getEventIcon(type);

    // Clear and build new UI
    currentStep.innerHTML = '';
    currentStep.setAttribute('data-type', type); // Add type attribute

    // Add icon
    const iconSpan = document.createElement('span');
    iconSpan.className = 'emoji-icon';
    iconSpan.innerHTML = icon; // Use innerHTML instead of textContent to support HTML tags
    currentStep.appendChild(iconSpan);

    // Create status text element, add typewriter effect
    const statusText = document.createElement('span');
    statusText.className = 'status-text';
    currentStep.appendChild(statusText);

    // Typewriter effect displaying status text
    let i = 0;
    let typingEffect = setInterval(() => {
        if (i < typeLabel.length) {
            statusText.textContent += typeLabel.charAt(i);
            i++;
        } else {
            clearInterval(typingEffect);
        }
    }, 50);

    // Update content area
    let content = '';

    if (data.result) {
        content = data.result;
    } else if (data.message) {
        content = data.message;
    } else {
        content = JSON.stringify(data, null, 2);
    }

    // Clear previous content, add new content
    resultContainer.innerHTML = '';

    // Create content area with proper styling for overflow control
    const contentDiv = document.createElement('div');
    contentDiv.classList.add('content-box');
    contentDiv.style.width = '100%';
    contentDiv.style.maxWidth = '100%';
    contentDiv.style.boxSizing = 'border-box';
    contentDiv.style.overflowWrap = 'break-word';
    contentDiv.style.wordWrap = 'break-word';
    contentDiv.style.wordBreak = 'break-word';

    const preElement = document.createElement('pre');
    preElement.style.whiteSpace = 'pre-wrap';
    preElement.style.wordWrap = 'break-word';
    preElement.style.wordBreak = 'break-word';
    preElement.style.maxWidth = '100%';
    preElement.style.boxSizing = 'border-box';
    preElement.textContent = content;

    contentDiv.appendChild(preElement);
    resultContainer.appendChild(contentDiv);

    // Ensure proper scrolling
    setTimeout(() => {
        resultContainer.scrollTop = 0;
    }, 100);
}

function loadHistory() {
    fetch('/tasks')
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    throw new Error(`Request failed: ${response.status} - ${text.substring(0, 100)}`);
                });
            }
            return response.json();
        })
        .then(tasks => {
            const listContainer = document.getElementById('task-list');
            if (tasks.length === 0) {
                listContainer.innerHTML = '<div class="info">No history tasks</div>';
                return;
            }

            // Update history count
            const historyCount = document.querySelector('.history-count');
            if (historyCount) {
                historyCount.textContent = tasks.length;
            }

            listContainer.innerHTML = tasks.map(task => `
            <div class="task-card" data-task-id="${task.id}" onclick="loadTask('${task.id}')">
                <div class="task-title">${task.prompt}</div>
                <div class="task-meta">
                    <span>${new Date(task.created_at).toLocaleString()}</span>
                    <span class="status status-${task.status ? task.status.toLowerCase() : 'unknown'}">
                        ${getStatusText(task.status)}
                    </span>
                </div>
            </div>
        `).join('');
        })
        .catch(error => {
            console.error('Failed to load history:', error);
            const listContainer = document.getElementById('task-list');
            listContainer.innerHTML = `<div class="error">Loading failed: ${error.message}</div>`;
        });
}

function loadTask(taskId) {
    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }

    const taskContainer = document.getElementById('task-container');
    const stepsContainer = document.getElementById('steps-container');
    const resultContainer = document.getElementById('result-container');

    // Reset UI state
    resetUIState();

    // Hide welcome message
    const welcomeMessage = taskContainer.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.style.display = 'none';
    }

    stepsContainer.innerHTML = '<div class="loading">Loading task...</div>';
    resultContainer.innerHTML = '';

    // Close history panel on mobile devices
    closeHistoryOnMobile();

    fetch(`/tasks/${taskId}`)
        .then(response => response.json())
        .then(task => {
            // Highlight currently selected task card
            highlightTaskCard(taskId);

            stepsContainer.innerHTML = '';
            if (task.steps && task.steps.length > 0) {
                // Sort and render steps by timestamp
                renderSortedSteps(task.steps, task.created_at);
            } else {
                stepsContainer.innerHTML = '<div class="info">No steps recorded for this task</div>';
            }

            updateTaskStatus(task);
        })
        .catch(error => {
            console.error('Failed to load task:', error);
            stepsContainer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
        });
}

// Highlight currently selected task card
function highlightTaskCard(taskId) {
    const taskCards = document.querySelectorAll('.task-card');
    taskCards.forEach(card => {
        card.classList.remove('active');
        if (card.getAttribute('data-task-id') === taskId) {
            card.classList.add('active');
        }
    });
}

// Sort and render steps by timestamp
function renderSortedSteps(steps, taskCreatedAt) {
    const stepsContainer = document.getElementById('steps-container');

    // Store steps collection
    let taskSteps = [];

    steps.forEach((step, index) => {
        const stepTimestamp = new Date(step.created_at || taskCreatedAt).toLocaleTimeString();
        const stepElement = createStepElement(
            step.type,
            step.result,
            stepTimestamp
        );

        // Add steps to collection
        taskSteps.push({
            index: index,
            timestamp: stepTimestamp,
            isoTimestamp: step.created_at || taskCreatedAt, // Save ISO timestamp
            element: stepElement,
            step: step
        });
    });

    // Sort steps by timestamp
    taskSteps.sort((a, b) => {
        // Try using ISO timestamp for comparison
        if (a.isoTimestamp && b.isoTimestamp) {
            return new Date(a.isoTimestamp) - new Date(b.isoTimestamp);
        }

        // First sort by timestamp, if time is the same, sort by index
        const timeCompare = new Date(a.timestamp) - new Date(b.timestamp);
        return timeCompare !== 0 ? timeCompare : a.index - b.index;
    });

    // Add sorted steps to container
    taskSteps.forEach((stepData, index) => {
        // Only set last step to expanded state
        if (index === taskSteps.length - 1) {
            stepData.element.classList.add('expanded');
            stepData.element.classList.add('active');

            // Show last step result
            updateResultPanel({ result: stepData.step.result }, stepData.step.type);
            showResultPanel();
        }

        stepsContainer.appendChild(stepData.element);
    });
}

function formatStepContent(data, eventType) {
    // Create ISO formatted timestamp, ensure consistent sorting
    const now = new Date();
    const isoTimestamp = now.toISOString();
    const localTime = now.toLocaleTimeString();

    return {
        formattedContent: data.result || (data.message || JSON.stringify(data)),
        timestamp: localTime,
        isoTimestamp: isoTimestamp // Add ISO formatted timestamp for sorting
    };
}

function createStepElement(type, content, timestamp) {
    const step = document.createElement('div');

    // Executing step
    const stepRegex = /Executing step (\d+)\/(\d+)/;
    if (type === 'log' && stepRegex.test(content)) {
        const match = content.match(stepRegex);
        const currentStep = parseInt(match[1]);
        const totalSteps = parseInt(match[2]);

        step.className = 'step-divider';
        step.innerHTML = `
            <div class="step-circle">${currentStep}</div>
            <div class="step-line"></div>
            <div class="step-info">${currentStep}/${totalSteps}</div>
        `;
    } else if (type === 'act') {
        // Check if it contains information about file saving
        const saveRegex = /Content successfully saved to (.+)/;
        const match = content.match(saveRegex);

        step.className = `step-item ${type}`;
        step.dataset.type = type;
        step.dataset.timestamp = timestamp; // Store timestamp as data attribute

        // Get icon HTML
        const iconHtml = getEventIcon(type);

        if (match && match[1]) {
            const filePath = match[1].trim();
            const fileName = filePath.split('/').pop();
            const fileExtension = fileName.split('.').pop().toLowerCase();

            // Handling different types of files
            let fileInteractionHtml = '';

            if (['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp'].includes(fileExtension)) {
                fileInteractionHtml = `
                    <div class="file-interaction image-preview">
                        <img src="${filePath}" alt="${fileName}" class="preview-image" onclick="showFullImage('${filePath}')">
                        <a href="/download?file_path=${filePath}" download="${fileName}" class="download-link">⬇️ Download image</a>
                    </div>
                `;
            } else if (['mp3', 'wav', 'ogg'].includes(fileExtension)) {
                fileInteractionHtml = `
                    <div class="file-interaction audio-player">
                        <audio controls src="${filePath}"></audio>
                        <a href="/download?file_path=${filePath}" download="${fileName}" class="download-link">⬇️ Download audio</a>
                    </div>
                `;
            } else if (['html', 'js', 'py'].includes(fileExtension)) {
                fileInteractionHtml = `
                    <div class="file-interaction code-file">
                        <button onclick="simulateRunPython('${filePath}')" class="run-button">▶️ Simulate run</button>
                        <a href="/download?file_path=${filePath}" download="${fileName}" class="download-link">⬇️ Download file</a>
                    </div>
                `;
            } else {
                fileInteractionHtml = `
                    <div class="file-interaction">
                        <a href="/download?file_path=${filePath}" download="${fileName}" class="download-link">⬇️ Download file: ${fileName}</a>
                    </div>
                `;
            }

            step.innerHTML = `
                <div class="log-header" onclick="toggleStepContent(this)">
                    <div class="log-prefix">
                        <span class="log-prefix-icon">${iconHtml}</span>
                        <span>${getEventLabel(type)}</span>
                        <time>${timestamp}</time>
                    </div>
                    <div class="content-preview">${content.substring(0, 20) + (content.length > 20 ? "..." : "")}</div>
                    <div class="step-controls">
                        <span class="minimize-btn" onclick="minimizeStep(event, this)"></span>
                    </div>
                </div>
                <div class="log-body">
                    <div class="log-content">
                        <pre>${content}</pre>
                        ${fileInteractionHtml}
                    </div>
                </div>
            `;
        } else {
            step.innerHTML = `
                <div class="log-header" onclick="toggleStepContent(this)">
                    <div class="log-prefix">
                        <span class="log-prefix-icon">${iconHtml}</span>
                        <span>${getEventLabel(type)}</span>
                        <time>${timestamp}</time>
                    </div>
                    <div class="content-preview">${content.substring(0, 20) + (content.length > 20 ? "..." : "")}</div>
                    <div class="step-controls">
                        <span class="minimize-btn" onclick="minimizeStep(event, this)"></span>
                    </div>
                </div>
                <div class="log-body">
                    <div class="log-content">
                        <pre>${content}</pre>
                    </div>
                </div>
            `;
        }
    } else {
        // Get content preview
        let contentPreview = "";
        if (type === 'think' && content.length > 0) {
            // Extract the first 30 characters of the thinking content as preview
            contentPreview = content.substring(0, 30) + (content.length > 30 ? "..." : "");
        } else if (type === 'tool' && content.includes('selected')) {
            // Tool selection content remains as is
            contentPreview = content;
        } else if (type === 'log') {
            // Log content remains as is, usually short
            contentPreview = content;
        } else {
            // Other types take the first 20 characters
            contentPreview = content.substring(0, 20) + (content.length > 20 ? "..." : "");
        }

        step.className = `step-item ${type}`;
        step.dataset.type = type;
        step.dataset.timestamp = timestamp; // Store timestamp as data attribute

        // Get icon HTML
        const iconHtml = getEventIcon(type);

        // Ensure timestamp is displayed in log-prefix, and wrap step type label in span tag
        step.innerHTML = `
            <div class="log-header" onclick="toggleStepContent(this)">
                <div class="log-prefix">
                    <span class="log-prefix-icon">${iconHtml}</span>
                    <span>${getEventLabel(type)}</span>
                    <time>${timestamp}</time>
                </div>
                <div class="content-preview">${contentPreview}</div>
                <div class="step-controls">
                    <span class="minimize-btn" onclick="minimizeStep(event, this)"></span>
                </div>
            </div>
            <div class="log-body">
                <div class="log-content">
                    <pre>${content}</pre>
                </div>
            </div>
        `;
    }

    return step;
}

// Toggle display/hide of step content
function toggleStepContent(header) {
    const stepItem = header.closest('.step-item');
    if (!stepItem) return;

    const logBody = stepItem.querySelector('.log-body');
    if (!logBody) return;

    // Close other expanded steps
    document.querySelectorAll('.step-item.expanded').forEach(item => {
        if (item !== stepItem) {
            item.classList.remove('expanded');
        }
    });

    // Toggle current step expanded state
    stepItem.classList.toggle('expanded');

    // Highlight current step
    highlightStep(stepItem);

    // If step expanded, update result panel and show
    if (stepItem.classList.contains('expanded')) {
        const type = stepItem.dataset.type;
        const content = stepItem.querySelector('pre')?.textContent || '';

        updateResultPanel({ result: content }, type);
        showResultPanel();
    }

    // Trigger layout adjustment
    handleResponsiveLayout();
}

// Minimize step without toggling expansion
function minimizeStep(event, btn) {
    event.stopPropagation(); // Prevent event bubbling

    const stepItem = btn.closest('.step-item');
    if (!stepItem) return;

    stepItem.classList.remove('expanded');

    // Trigger layout adjustment
    handleResponsiveLayout();
}

// Toggle result panel display state
function toggleResultPanel() {
    const resultPanel = document.getElementById('result-panel');

    if (!resultPanel) return;

    if (resultPanel.classList.contains('hidden')) {
        showResultPanel();
    } else {
        hideResultPanel();
    }
}

function hideResultPanel() {
    const resultPanel = document.getElementById('result-panel');
    const container = document.querySelector('.container');

    if (!resultPanel) return;

    // First add hidden class, trigger CSS animation
    resultPanel.classList.add('hidden');
    container.classList.remove('with-result');

    // Delay handling style changes, ensure transition effect
    setTimeout(function () {
        resultPanel.style.display = 'none';
        container.style.width = '98%';
        handleResponsiveLayout();
    }, 300);
}

function showResultPanel() {
    const resultPanel = document.getElementById('result-panel');
    const container = document.querySelector('.container');
    const resultContainer = document.getElementById('result-container');

    if (!resultPanel) return;

    // Set to visible
    resultPanel.style.display = 'flex';
    resultPanel.style.flexDirection = 'column';

    // Ensure result container is scrollable and content doesn't overflow
    if (resultContainer) {
        resultContainer.style.overflowY = 'auto';
        resultContainer.style.overflowX = 'hidden';
        resultContainer.style.maxHeight = 'calc(100vh - 200px)';
        resultContainer.style.width = '100%';
        resultContainer.style.wordWrap = 'break-word';
        resultContainer.style.wordBreak = 'break-word';
        resultContainer.style.boxSizing = 'border-box';
        resultContainer.style.padding = '5px 10px 15px 5px';

        // Apply content overflow handling
        ensureContentFitsContainer(resultContainer);
    }

    // Use setTimeout to ensure DOM updates
    setTimeout(() => {
        resultPanel.classList.remove('hidden');
        container.classList.add('with-result');

        // Adjust container width
        if (window.innerWidth > 1024) {
            container.style.width = 'calc(68% - 10px)';
            // Ensure result panel visual effects display correctly
            resultPanel.style.transform = 'translateX(0)';
        }

        // Trigger layout adjustment
        handleResponsiveLayout();

        // Apply content overflow handling again to ensure all content fits container
        if (resultContainer) {
            ensureContentFitsContainer(resultContainer);
        }
    }, 50);
}

function autoScroll(element) {
    if (element) {
        element.scrollTop = element.scrollHeight;
    }
}

// Comprehensive function to handle responsive layout
function handleResponsiveLayout() {
    const container = document.querySelector('.container');
    const resultPanel = document.getElementById('result-panel');
    const stepsContainer = document.getElementById('steps-container');
    const resultContainer = document.getElementById('result-container');
    const isMobile = window.innerWidth <= 768;
    const isTablet = window.innerWidth <= 1024 && window.innerWidth > 768;

    // Ensure scrollable container is always scrollable
    if (stepsContainer) {
        stepsContainer.style.overflowY = 'auto';
        stepsContainer.style.overflowX = 'hidden';
    }

    if (resultContainer) {
        resultContainer.style.overflowY = 'auto';
        resultContainer.style.overflowX = 'hidden';
        resultContainer.style.maxHeight = isMobile ? 'calc(50vh - 150px)' : 'calc(100vh - 200px)';
        resultContainer.style.width = '100%';
        resultContainer.style.boxSizing = 'border-box';

        // Ensure content doesn't overflow
        ensureContentFitsContainer(resultContainer);
    }

    // Adjust step item layout
    adjustStepItemsLayout();

    // Adjust container width based on screen size
    if (window.innerWidth <= 1024) {
        // Tablet and phone layout
        container.style.width = '98%';
    } else {
        // Desktop layout
        if (resultPanel && !resultPanel.classList.contains('hidden')) {
            container.style.width = 'calc(68% - 10px)';
            container.classList.add('with-result');
        } else {
            container.style.width = '98%';
            container.classList.remove('with-result');
        }
    }

    // Determine history panel display based on screen size
    if (historyVisible) {
        if (window.innerWidth > 768) {
            container.classList.add('with-history');
        } else {
            container.classList.remove('with-history');
        }
    }
}

// Ensure content fits container
function ensureContentFitsContainer(container) {
    if (!container) return;

    // Find all content elements in container
    const contentElements = container.querySelectorAll('p, div, pre, span, code, table');

    contentElements.forEach(element => {
        // Set necessary styles to prevent overflow
        element.style.maxWidth = '100%';
        element.style.wordWrap = 'break-word';
        element.style.wordBreak = 'break-word';
        element.style.overflowWrap = 'break-word';
        element.style.boxSizing = 'border-box';

        // Handle long strings or code
        if (element.scrollWidth > element.clientWidth) {
            element.style.whiteSpace = 'pre-wrap';
        }
    });
}

// Adjust step item layout
function adjustStepItemsLayout() {
    const stepItems = document.querySelectorAll('.step-item');
    const isMobile = window.innerWidth <= 768;

    stepItems.forEach(item => {
        const logHeader = item.querySelector('.log-header');
        const contentPreview = item.querySelector('.content-preview');
        const logPrefix = item.querySelector('.log-prefix');
        const timeElement = logPrefix ? logPrefix.querySelector('time') : null;

        if (isMobile) {
            // Phone layout
            if (contentPreview) {
                contentPreview.style.maxWidth = 'calc(100% - 40px)';
                contentPreview.style.marginLeft = '34px';
            }

            if (timeElement) {
                timeElement.style.fontSize = '0.7rem';
            }
        } else {
            // Desktop layout
            if (contentPreview) {
                contentPreview.style.maxWidth = '';
                contentPreview.style.marginLeft = '';
            }

            if (timeElement) {
                timeElement.style.fontSize = '';
            }
        }
    });
}

function getEventIcon(type) {
    switch (type) {
        case 'think': return '<i class="fas fa-brain"></i>';
        case 'tool': return '<i class="fas fa-cog"></i>';
        case 'act': return '<i class="fas fa-wave-square"></i>';
        case 'log': return '<i class="fas fa-file-alt"></i>';
        case 'run': return '<i class="fas fa-play"></i>';
        case 'message': return '<i class="fas fa-comment"></i>';
        case 'complete': return '<i class="fas fa-check"></i>';
        case 'error': return '<i class="fas fa-times"></i>';
        default: return '<i class="fas fa-thumbtack"></i>';
    }
}

function getEventLabel(type) {
    switch (type) {
        case 'think': return 'Thinking';
        case 'tool': return 'Using Tool';
        case 'act': return 'Taking Action';
        case 'log': return 'Log';
        case 'run': return 'Running';
        case 'message': return 'Message';
        case 'complete': return 'Completed';
        case 'error': return 'Error';
        default: return 'Step';
    }
}

function updateTaskStatus(task) {
    const statusBar = document.getElementById('status-bar');
    if (!statusBar) return;

    if (task.status === 'completed') {
        statusBar.innerHTML = `<span class="status-complete">✅ Task completed</span>`;

        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
    } else if (task.status === 'failed') {
        statusBar.innerHTML = `<span class="status-error">❌ Task failed: ${task.error || 'Unknown error'}</span>`;

        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
    } else {
        statusBar.innerHTML = `<span class="status-running">⚙️ Task running: ${task.status}</span>`;
    }
}

function showFullImage(imageSrc) {
    let modal = document.getElementById('image-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'image-modal';
        modal.className = 'image-modal';
        modal.innerHTML = `
            <span class="close-modal">&times;</span>
            <img src="${imageSrc}" class="modal-content" id="full-image">
        `;
        document.body.appendChild(modal);

        const closeBtn = modal.querySelector('.close-modal');
        closeBtn.addEventListener('click', () => {
            modal.classList.remove('active');
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    } else {
        document.getElementById('full-image').src = imageSrc;
    }

    modal.classList.add('active');
}

function simulateRunPython(filePath) {
    let modal = document.getElementById('python-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'python-modal';
        modal.className = 'python-modal';
        modal.innerHTML = `
            <div class="python-console">
                <div class="close-modal">&times;</div>
                <div class="python-output">Loading Python file content...</div>
            </div>
        `;
        document.body.appendChild(modal);

        const closeBtn = modal.querySelector('.close-modal');
        closeBtn.addEventListener('click', () => {
            modal.classList.remove('active');
        });
    }

    modal.classList.add('active');

    // Load Python file content
    fetch(filePath)
        .then(response => response.text())
        .then(code => {
            const outputDiv = modal.querySelector('.python-output');
            outputDiv.innerHTML = '';

            const codeElement = document.createElement('pre');
            codeElement.textContent = code;
            codeElement.style.marginBottom = '20px';
            codeElement.style.padding = '10px';
            codeElement.style.borderBottom = '1px solid #444';
            outputDiv.appendChild(codeElement);

            // Add simulation run results
            const resultElement = document.createElement('div');
            resultElement.innerHTML = `
                <div style="color: #4CAF50; margin-top: 10px; margin-bottom: 10px;">
                    > Simulation run output results:</div>
                <pre style="color: #f8f8f8;">
# This is the simulation run output results
# Actual run results may vary

# Running ${filePath.split('/').pop()}...
print("Hello from Python Simulated environment!")

# Code execution completed
</pre>
            `;
            outputDiv.appendChild(resultElement);
        })
        .catch(error => {
            console.error('Failed to load Python file:', error);
            const outputDiv = modal.querySelector('.python-output');
            outputDiv.innerHTML = `File loading error: ${error.message}`;
        });
}

// Highlight current selected step
function highlightStep(stepElement) {
    // Remove other steps highlight
    document.querySelectorAll('.step-item').forEach(item => {
        item.classList.remove('active');
    });

    // Add current step highlight
    stepElement.classList.add('active');

    // Update current step information to result panel
    const currentStep = document.getElementById('current-step');
    if (currentStep) {
        const type = stepElement.dataset.type;
        currentStep.setAttribute('data-type', type);
    }
}

// Toggle history panel display state
function toggleHistory() {
    const historyPanel = document.querySelector('.history-panel');
    const overlay = document.querySelector('.overlay');
    const historyToggle = document.querySelector('.history-toggle');
    const container = document.querySelector('.container');

    if (historyVisible) {
        // Hide history
        historyPanel.classList.remove('show');
        overlay.classList.remove('show');
        historyToggle.classList.remove('active');
        container.classList.remove('with-history');
    } else {
        // Show history
        historyPanel.classList.add('show');
        overlay.classList.add('show');
        historyToggle.classList.add('active');
        // Add spacing on large screens
        if (window.innerWidth > 768) {
            container.classList.add('with-history');
        }
    }

    historyVisible = !historyVisible;
}

// Close history panel on small screens
function closeHistoryOnMobile() {
    if (window.innerWidth <= 768 && historyVisible) {
        toggleHistory();
    }
}

// Get status text
function getStatusText(status) {
    switch (status) {
        case 'pending': return 'Pending';
        case 'running': return 'Running';
        case 'completed': return 'Completed';
        case 'failed': return 'Failed';
        default: return 'Unknown';
    }
}

// Initialize interface
function initializeInterface() {
    // Add history toggle logic
    const historyToggle = document.querySelector('.history-toggle');
    if (historyToggle) {
        historyToggle.addEventListener('click', toggleHistory);
    }

    // Add overlay click to close history
    const overlay = document.querySelector('.overlay');
    if (overlay) {
        overlay.addEventListener('click', toggleHistory);
    }

    // Bind input box events
    const promptInput = document.getElementById('prompt-input');
    if (promptInput) {
        promptInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                createTask();
            }
        });
    }

    // Add window resize event listener
    window.addEventListener('resize', handleWindowResize);

    // Add keyboard event listener for closing modal
    document.addEventListener('keydown', handleKeyboardEvents);

    // Add screen orientation change listener
    window.addEventListener('orientationchange', () => {
        // Delay execution to ensure orientation change is complete
        setTimeout(handleResponsiveLayout, 300);
    });

    // Prevent page scrolling
    preventPageScroll();

    // Set initial layout
    setupInitialLayout();

    // Load history tasks
    loadHistory();
}

// Prevent page scrolling
function preventPageScroll() {
    // Prevent document scroll wheel event, keep container scroll
    document.addEventListener('wheel', function (event) {
        // Check if in scrollable container
        const isInScrollable =
            event.target.closest('.steps-container') ||
            event.target.closest('.result-container') ||
            event.target.closest('.history-panel') ||
            event.target.closest('.log-body');

        if (!isInScrollable) {
            event.preventDefault();
        }
    }, { passive: false });
}

// Handle window resize
function handleWindowResize() {
    const container = document.querySelector('.container');

    // Large screen keep history sidebar effect, small screen remove
    if (window.innerWidth > 768 && historyVisible) {
        container.classList.add('with-history');
    } else {
        container.classList.remove('with-history');
    }

    // Call comprehensive handling function
    handleResponsiveLayout();
}

// Handle keyboard events
function handleKeyboardEvents(e) {
    // ESC key close history panel and modal
    if (e.key === 'Escape') {
        if (historyVisible) {
            toggleHistory();
        }

        const imageModal = document.getElementById('image-modal');
        if (imageModal && imageModal.classList.contains('active')) {
            imageModal.classList.remove('active');
        }

        const pythonModal = document.getElementById('python-modal');
        if (pythonModal && pythonModal.classList.contains('active')) {
            pythonModal.classList.remove('active');
        }
    }
}

// Set initial layout
function setupInitialLayout() {
    // Adjust step item layout
    adjustStepItemsLayout();

    // Initialize history panel state
    const historyPanel = document.querySelector('.history-panel');
    if (historyPanel) {
        historyPanel.classList.remove('show');
    }

    // Ensure result panel initial hidden
    const resultPanel = document.getElementById('result-panel');
    if (resultPanel) {
        hideResultPanel();
    }

    // Manual trigger once responsive layout
    handleResponsiveLayout();
}

// When document load complete initialize interface
document.addEventListener('DOMContentLoaded', initializeInterface);
