import { addMessage } from './chatManager.js';
import { connectWebSocket } from './websocketManager.js';
import { updateLog } from './logManager.js';

let processingRequest = false;

export async function sendRequest(prompt) {
    if (!prompt || processingRequest) return;
    
    processingRequest = true;
    addMessage(prompt, 'user');
    document.getElementById('user-input').value = '';
    document.getElementById('send-btn').disabled = true;
    document.getElementById('stop-btn').disabled = false;
    document.getElementById('status-indicator').textContent = '正在处理您的请求...';
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ prompt })
        });
        
        if (!response.ok) {
            throw new Error('网络请求失败');
        }
        
        const data = await response.json();
        connectWebSocket(data.session_id);
        pollResults(data.session_id);
        
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('status-indicator').textContent = '发生错误: ' + error.message;
        document.getElementById('send-btn').disabled = false;
        document.getElementById('stop-btn').disabled = true;
        processingRequest = false;
    }
}

export async function pollResults(sessionId) {
    let attempts = 0;
    const maxAttempts = 60;
    
    const poll = async () => {
        if (attempts >= maxAttempts || !processingRequest) {
            if (attempts >= maxAttempts) {
                document.getElementById('status-indicator').textContent = '请求超时';
            }
            document.getElementById('send-btn').disabled = false;
            document.getElementById('stop-btn').disabled = true;
            processingRequest = false;
            return;
        }
        
        try {
            const response = await fetch(`/api/chat/${sessionId}`);
            if (!response.ok) {
                throw new Error('获取结果失败');
            }
            
            const data = await response.json();
            
            if (data.status === 'completed') {
                if (data.result && !chatContainsResult(data.result)) {
                    addMessage(data.result, 'ai');
                }
                document.getElementById('status-indicator').textContent = '';
                document.getElementById('send-btn').disabled = false;
                document.getElementById('stop-btn').disabled = true;
                processingRequest = false;
                return;
            } else if (data.status === 'error') {
                document.getElementById('status-indicator').textContent = '处理请求时发生错误';
                document.getElementById('send-btn').disabled = false;
                document.getElementById('stop-btn').disabled = true;
                processingRequest = false;
                return;
            } else if (data.status === 'stopped') {
                document.getElementById('status-indicator').textContent = '处理已停止';
                document.getElementById('send-btn').disabled = false;
                document.getElementById('stop-btn').disabled = true;
                processingRequest = false;
                return;
            }
            
            if (data.log && data.log.length > 0) {
                updateLog(data.log);
            }
            
            attempts++;
            setTimeout(poll, 3000);
            
            try {
                const terminalResponse = await fetch(`/api/terminal/${sessionId}`);
                if (terminalResponse.ok) {
                    const terminalData = await terminalResponse.json();
                    if (terminalData.terminal_output && terminalData.terminal_output.length > 0) {
                        updateTerminalOutput(terminalData.terminal_output);
                    }
                }
            } catch (terminalError) {
                console.error('获取终端输出错误:', terminalError);
            }
            
        } catch (error) {
            console.error('轮询错误:', error);
            attempts++;
            setTimeout(poll, 3000);
        }
    };
    
    setTimeout(poll, 3000);
}

export function updateThinkingSteps(steps) {
    if (!Array.isArray(steps) || steps.length === 0) return;
    
    const thinkingStepsContainer = document.getElementById('thinking-steps');
    steps.forEach(step => {
        const existingStep = document.querySelector(`.thinking-step[data-timestamp="${step.timestamp}"]`);
        if (existingStep) return;
        
        const stepElement = document.createElement('div');
        stepElement.className = `thinking-step ${step.type}`;
        stepElement.dataset.timestamp = step.timestamp;
        
        const stepContent = document.createElement('div');
        stepContent.className = 'thinking-step-content';
        
        if (step.type === 'communication') {
            const headerDiv = document.createElement('div');
            headerDiv.className = 'communication-header';
            headerDiv.innerHTML = `<span class="communication-direction">${step.message}</span> <span class="toggle-icon">▶</span>`;
            headerDiv.onclick = function() {
                const detailsElement = this.nextElementSibling;
                const toggleIcon = this.querySelector('.toggle-icon');
                
                if (detailsElement.style.display === 'none' || !detailsElement.style.display) {
                    detailsElement.style.display = 'block';
                    toggleIcon.textContent = '▼';
                } else {
                    detailsElement.style.display = 'none';
                    toggleIcon.textContent = '▶';
                }
            };
            
            const detailsElement = document.createElement('div');
            detailsElement.className = 'communication-details';
            detailsElement.style.display = 'none';
            
            if (step.message.includes("发送到LLM")) {
                detailsElement.innerHTML = `<div class="prompt-wrapper">${formatCommunicationContent(step.details)}</div>`;
            } else {
                detailsElement.innerHTML = `<div class="response-wrapper">${formatCommunicationContent(step.details)}</div>`;
            }
            
            stepContent.appendChild(headerDiv);
            stepContent.appendChild(detailsElement);
            
        } else {
            stepContent.textContent = step.message;
            
            if (step.details) {
                const detailsToggle = document.createElement('div');
                detailsToggle.className = 'details-toggle';
                detailsToggle.textContent = '显示详情 ▼';
                detailsToggle.onclick = function() {
                    const detailsElement = this.nextElementSibling;
                    if (detailsElement.style.display === 'none') {
                        detailsElement.style.display = 'block';
                        this.textContent = '隐藏详情 ▲';
                    } else {
                        detailsElement.style.display = 'none';
                        this.textContent = '显示详情 ▼';
                    }
                };
                
                const detailsElement = document.createElement('div');
                detailsElement.className = 'step-details';
                detailsElement.textContent = step.details;
                detailsElement.style.display = 'none';
                
                stepContent.appendChild(detailsToggle);
                stepContent.appendChild(detailsElement);
            }
        }
        
        stepElement.appendChild(stepContent);
        thinkingStepsContainer.appendChild(stepElement);
        
        setTimeout(() => {
            stepElement.style.opacity = 1;
        }, 10);
    });
    
    thinkingStepsContainer.scrollTop = thinkingStepsContainer.scrollHeight;
}

function formatCommunicationContent(content) {
    if (!content) return '(无内容)';
    
    try {
        if (content.startsWith('{') && content.endsWith('}')) {
            const jsonObj = JSON.parse(content);
            return `<pre class="json-content">${JSON.stringify(jsonObj, null, 2)}</pre>`;
        }
    } catch (e) {}
    
    const htmlEscaped = content
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    
    return htmlEscaped.replace(/\n/g, '<br>');
}

export function updateTerminalOutput(outputs) {
    const terminalContent = document.getElementById('terminal-content');
    if (!Array.isArray(outputs) || outputs.length === 0 || !terminalContent) return;
    
    outputs.forEach(output => {
        const lineElement = document.createElement('div');
        lineElement.className = `terminal-line ${output.type}`;
        lineElement.textContent = output.content;
        
        terminalContent.appendChild(lineElement);
    });
    
    terminalContent.scrollTop = terminalContent.scrollHeight;
}
