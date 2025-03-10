let currentEventSource = null;

function createTask() {
    const promptInput = document.getElementById('prompt-input');
    const prompt = promptInput.value.trim();
    
    if (!prompt) {
        alert("请输入有效的提示内容");
        promptInput.focus();
        return;
    }

    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }

    const container = document.getElementById('task-container');
    container.innerHTML = '<div class="loading">任务初始化中...</div>';
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
            return response.json().then(err => { throw new Error(err.detail || '请求失败') });
        }
        return response.json();
    })
    .then(data => {
        if (!data.task_id) {
            throw new Error('无效的任务ID');
        }
        setupSSE(data.task_id);
        loadHistory();
    })
    .catch(error => {
        container.innerHTML = `<div class="error">错误: ${error.message}</div>`;
        console.error('创建任务失败:', error);
    });
}

function setupSSE(taskId) {
    let retryCount = 0;
    const maxRetries = 3;
    const retryDelay = 2000;
    
    function connect() {
        const eventSource = new EventSource(`/tasks/${taskId}/events`);
        currentEventSource = eventSource;

        const container = document.getElementById('task-container');
        
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
                    console.error('轮询失败:', error);
                });
        }, 10000);

    if (!eventSource._listenersAdded) {
        eventSource._listenersAdded = true;
        
        let lastResultContent = '';
        eventSource.addEventListener('status', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                container.querySelector('.loading')?.remove();
                container.classList.add('active');
                const welcomeMessage = document.querySelector('.welcome-message');
                if (welcomeMessage) {
                    welcomeMessage.style.display = 'none';
                }

                let stepContainer = container.querySelector('.step-container');
                if (!stepContainer) {
                    container.innerHTML = '<div class="step-container"></div>';
                    stepContainer = container.querySelector('.step-container');
                }

                // 保存result内容
                if (data.steps && data.steps.length > 0) {
                    // 遍历所有步骤，找到最后一个result类型
                    for (let i = data.steps.length - 1; i >= 0; i--) {
                        if (data.steps[i].type === 'result') {
                            lastResultContent = data.steps[i].result;
                            break;
                        }
                    }
                }

                // Parse and display each step with proper formatting
                stepContainer.innerHTML = data.steps.map(step => {
                    const content = step.result;
                    const timestamp = new Date().toLocaleTimeString();
                    return `
                        <div class="step-item ${step.type || 'step'}">
                            <div class="log-line">
                                <span class="log-prefix">${getEventIcon(step.type)} [${timestamp}] ${getEventLabel(step.type)}:</span>
                                <pre>${content}</pre>
                            </div>
                        </div>
                    `;
                }).join('');
                
                // Auto-scroll to bottom
                container.scrollTo({
                    top: container.scrollHeight,
                    behavior: 'smooth'
                });
            } catch (e) {
                console.error('状态更新失败:', e);
            }
        });

        // 添加对think事件的处理
        eventSource.addEventListener('think', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                container.querySelector('.loading')?.remove();
                
                let stepContainer = container.querySelector('.step-container');
                if (!stepContainer) {
                    container.innerHTML = '<div class="step-container"></div>';
                    stepContainer = container.querySelector('.step-container');
                }

                const content = data.result;
                const timestamp = new Date().toLocaleTimeString();
                
                const step = document.createElement('div');
                step.className = 'step-item think';
                step.innerHTML = `
                    <div class="log-line">
                        <span class="log-prefix">${getEventIcon('think')} [${timestamp}] ${getEventLabel('think')}:</span>
                        <pre>${content}</pre>
                    </div>
                `;
                
                stepContainer.appendChild(step);
                container.scrollTo({
                    top: container.scrollHeight,
                    behavior: 'smooth'
                });

                // 更新任务状态
                fetch(`/tasks/${taskId}`)
                    .then(response => response.json())
                    .then(task => {
                        updateTaskStatus(task);
                    })
                    .catch(error => {
                        console.error('状态更新失败:', error);
                    });
            } catch (e) {
                console.error('思考事件处理失败:', e);
            }
        });

        // 添加对tool事件的处理
        eventSource.addEventListener('tool', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                container.querySelector('.loading')?.remove();
                
                let stepContainer = container.querySelector('.step-container');
                if (!stepContainer) {
                    container.innerHTML = '<div class="step-container"></div>';
                    stepContainer = container.querySelector('.step-container');
                }

                const content = data.result;
                const timestamp = new Date().toLocaleTimeString();
                
                const step = document.createElement('div');
                step.className = 'step-item tool';
                step.innerHTML = `
                    <div class="log-line">
                        <span class="log-prefix">${getEventIcon('tool')} [${timestamp}] ${getEventLabel('tool')}:</span>
                        <pre>${content}</pre>
                    </div>
                `;
                
                stepContainer.appendChild(step);
                container.scrollTo({
                    top: container.scrollHeight,
                    behavior: 'smooth'
                });

                // 更新任务状态
                fetch(`/tasks/${taskId}`)
                    .then(response => response.json())
                    .then(task => {
                        updateTaskStatus(task);
                    })
                    .catch(error => {
                        console.error('状态更新失败:', error);
                    });
            } catch (e) {
                console.error('工具事件处理失败:', e);
            }
        });

        // 添加对act事件的处理
        eventSource.addEventListener('act', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                container.querySelector('.loading')?.remove();
                
                let stepContainer = container.querySelector('.step-container');
                if (!stepContainer) {
                    container.innerHTML = '<div class="step-container"></div>';
                    stepContainer = container.querySelector('.step-container');
                }

                const content = data.result;
                const timestamp = new Date().toLocaleTimeString();
                
                const step = document.createElement('div');
                step.className = 'step-item act';
                step.innerHTML = `
                    <div class="log-line">
                        <span class="log-prefix">${getEventIcon('act')} [${timestamp}] ${getEventLabel('act')}:</span>
                        <pre>${content}</pre>
                    </div>
                `;
                
                stepContainer.appendChild(step);
                container.scrollTo({
                    top: container.scrollHeight,
                    behavior: 'smooth'
                });

                // 更新任务状态
                fetch(`/tasks/${taskId}`)
                    .then(response => response.json())
                    .then(task => {
                        updateTaskStatus(task);
                    })
                    .catch(error => {
                        console.error('状态更新失败:', error);
                    });
            } catch (e) {
                console.error('执行事件处理失败:', e);
            }
        });

        // 添加对run事件的处理
        // 添加对log事件的处理
        eventSource.addEventListener('log', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                container.querySelector('.loading')?.remove();
                
                let stepContainer = container.querySelector('.step-container');
                if (!stepContainer) {
                    container.innerHTML = '<div class="step-container"></div>';
                    stepContainer = container.querySelector('.step-container');
                }

                const content = data.result;
                const timestamp = new Date().toLocaleTimeString();
                
                const step = document.createElement('div');
                step.className = 'step-item log';
                step.innerHTML = `
                    <div class="log-line">
                        <span class="log-prefix">${getEventIcon('log')} [${timestamp}] ${getEventLabel('log')}:</span>
                        <pre>${content}</pre>
                    </div>
                `;
                
                stepContainer.appendChild(step);
                container.scrollTo({
                    top: container.scrollHeight,
                    behavior: 'smooth'
                });

                // 更新任务状态
                fetch(`/tasks/${taskId}`)
                    .then(response => response.json())
                    .then(task => {
                        updateTaskStatus(task);
                    })
                    .catch(error => {
                        console.error('状态更新失败:', error);
                    });
            } catch (e) {
                console.error('日志事件处理失败:', e);
            }
        });

        eventSource.addEventListener('run', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                container.querySelector('.loading')?.remove();
                
                let stepContainer = container.querySelector('.step-container');
                if (!stepContainer) {
                    container.innerHTML = '<div class="step-container"></div>';
                    stepContainer = container.querySelector('.step-container');
                }

                const content = data.result;
                const timestamp = new Date().toLocaleTimeString();
                
                const step = document.createElement('div');
                step.className = 'step-item run';
                step.innerHTML = `
                    <div class="log-line">
                        <span class="log-prefix">${getEventIcon('run')} [${timestamp}] ${getEventLabel('run')}:</span>
                        <pre>${content}</pre>
                    </div>
                `;
                
                stepContainer.appendChild(step);
                container.scrollTo({
                    top: container.scrollHeight,
                    behavior: 'smooth'
                });

                // 更新任务状态
                fetch(`/tasks/${taskId}`)
                    .then(response => response.json())
                    .then(task => {
                        updateTaskStatus(task);
                    })
                    .catch(error => {
                        console.error('状态更新失败:', error);
                    });
            } catch (e) {
                console.error('运行事件处理失败:', e);
            }
        });

        eventSource.addEventListener('message', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                container.querySelector('.loading')?.remove();

                let stepContainer = container.querySelector('.step-container');
                if (!stepContainer) {
                    container.innerHTML = '<div class="step-container"></div>';
                    stepContainer = container.querySelector('.step-container');
                }
                
                // Create new step element
                const step = document.createElement('div');
                step.className = `step-item ${data.type || 'step'}`;
                
                // Format content and timestamp
                const content = data.result;
                const timestamp = new Date().toLocaleTimeString();
                
                step.innerHTML = `
                    <div class="log-line ${data.type || 'info'}">
                        <span class="log-prefix">${getEventIcon(data.type)} [${timestamp}] ${getEventLabel(data.type)}:</span>
                        <pre>${content}</pre>
                    </div>
                `;
            
                // Add step to container with animation
                stepContainer.prepend(step);
                setTimeout(() => {
                    step.classList.add('show');
                }, 10);
                
                // Auto-scroll to bottom
                container.scrollTo({
                    top: container.scrollHeight,
                    behavior: 'smooth'
                });
            } catch (e) {
                console.error('消息处理失败:', e);
            }
        });

        let isTaskComplete = false;

        eventSource.addEventListener('complete', (event) => {
            isTaskComplete = true;
            clearInterval(heartbeatTimer);
            clearInterval(pollInterval);
            container.innerHTML += `
                <div class="complete">
                    <div>✅ 任务完成</div>
                    <pre>${lastResultContent}</pre>
                </div>
            `;
            eventSource.close();
            currentEventSource = null;
            lastResultContent = ''; // 清空结果内容
        });

        eventSource.addEventListener('error', (event) => {
            clearInterval(heartbeatTimer);
            clearInterval(pollInterval);
            try {
                const data = JSON.parse(event.data);
                container.innerHTML += `
                    <div class="error">
                        ❌ 错误: ${data.message}
                    </div>
                `;
                eventSource.close();
                currentEventSource = null;
            } catch (e) {
                console.error('错误处理失败:', e);
            }
        });
    }
            
    container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
    });

        eventSource.onerror = (err) => {
            if (isTaskComplete) {
                return;
            }
            
            console.error('SSE连接错误:', err);
            clearInterval(heartbeatTimer);
            clearInterval(pollInterval);
            eventSource.close();
            
            if (retryCount < maxRetries) {
                retryCount++;
                container.innerHTML += `
                    <div class="warning">
                        ⚠ 连接中断，${retryDelay/1000}秒后重试 (${retryCount}/${maxRetries})...
                    </div>
                `;
                setTimeout(connect, retryDelay);
            } else {
                container.innerHTML += `
                    <div class="error">
                        ⚠ 连接中断，请尝试刷新页面
                    </div>
                `;
            }
        };
    }
    
    connect();
}

function getEventIcon(eventType) {
    switch(eventType) {
        case 'think': return '🤔';
        case 'tool': return '🛠️';
        case 'act': return '🚀';
        case 'result': return '🏁';
        case 'error': return '❌';
        case 'complete': return '✅';
        case 'warning': return '⚠️';
        case 'log': return '📝';
        default: return '⚡';
    }
}

function getEventLabel(eventType) {
    switch(eventType) {
        case 'think': return '思考';
        case 'tool': return '工具执行';
        case 'act': return '执行';
        case 'result': return '结果';
        case 'error': return '错误';
        case 'complete': return '完成';
        case 'warning': return '警告';
        case 'log': return '日志';
        default: return '步骤';
    }
}

function formatContent(content) {
    // Remove timestamp and log level prefixes
    content = content.replace(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} \| [A-Z]+\s*\| /gm, '');
    // Format the remaining content
    return content
        .replace(/\n/g, '<br>')
        .replace(/  /g, '&nbsp;&nbsp;')
        .replace(/✨ Manus's thoughts:/g, '')
        .replace(/🛠️ Manus selected/g, '')
        .replace(/🧰 Tools being prepared:/g, '')
        .replace(/🔧 Activating tool:/g, '')
        .replace(/🎯 Tool/g, '')
        .replace(/📝 Oops!/g, '')
        .replace(/🏁 Special tool/g, '');
}

function updateTaskStatus(task) {
    const taskCard = document.querySelector(`.task-card[data-task-id="${task.id}"]`);
    if (taskCard) {
        const statusEl = taskCard.querySelector('.task-meta .status');
        if (statusEl) {
            statusEl.className = `status-${task.status ? task.status.toLowerCase() : 'unknown'}`;
            statusEl.textContent = task.status || '未知状态';
        }
    }
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

document.addEventListener('DOMContentLoaded', function() {
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.style.display = 'flex';
    }
    
    // 监听任务容器显示状态
    const taskContainer = document.getElementById('task-container');
    if (taskContainer) {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach(mutation => {
                if (mutation.attributeName === 'class') {
                    const welcomeMessage = document.querySelector('.welcome-message');
                    if (taskContainer.classList.contains('active')) {
                        if (welcomeMessage) {
                            welcomeMessage.style.display = 'none';
                        }
                    } else {
                        if (welcomeMessage) {
                            welcomeMessage.style.display = 'block';
                        }
                    }
                }
            });
        });
        
        observer.observe(taskContainer, {
            attributes: true
        });
    }
});
