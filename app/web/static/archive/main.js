import { addMessage, clearChat } from './chatManager.js';
import { connectWebSocket } from './websocketManager.js';
import { sendRequest, pollResults } from './apiManager.js';
import { updateLog, addLog, updateSystemLogs, addSystemLogsToChat } from './logManager.js';
import { fetchGeneratedFiles } from './fileViewerManager.js';
import { initializeTerminal, updateTerminalOutput } from './terminalManager.js';

document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chat-messages');
    const logMessages = document.getElementById('log-messages');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-btn');
    const clearButton = document.getElementById('clear-btn');
    const stopButton = document.getElementById('stop-btn');
    const statusIndicator = document.getElementById('status-indicator');
    
    let currentWebSocket = null;
    let currentSessionId = null;
    let processingRequest = false;
    
    stopButton.disabled = true;
    
    let thinkingStepsContainer = document.getElementById('thinking-steps');
    if (!thinkingStepsContainer) {
        thinkingStepsContainer = document.createElement('div');
        thinkingStepsContainer.id = 'thinking-steps';
        thinkingStepsContainer.className = 'thinking-steps';
        logMessages.appendChild(thinkingStepsContainer);
    }
    
    const fileViewer = document.getElementById('file-viewer');
    const fileViewerTitle = document.getElementById('file-viewer-title');
    const fileContent = document.getElementById('file-content');
    const closeFileViewer = document.getElementById('close-file-viewer');
    const filesList = document.getElementById('files-list');
    
    if (fileViewer) {
        fileViewer.style.display = 'none';
    }
    
    if (closeFileViewer) {
        closeFileViewer.addEventListener('click', function() {
            fileViewer.style.display = 'none';
        });
    }
    
    sendButton.addEventListener('click', sendMessage);
    
    userInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    clearButton.addEventListener('click', function() {
        clearChat();
        logMessages.innerHTML = '';
        
        thinkingStepsContainer = document.createElement('div');
        thinkingStepsContainer.id = 'thinking-steps';
        thinkingStepsContainer.className = 'thinking-steps';
        logMessages.appendChild(thinkingStepsContainer);
        
        statusIndicator.textContent = '';
        statusIndicator.className = 'status-indicator';
        
        if (filesList) {
            filesList.innerHTML = '';
        }
        
        if (fileViewer) {
            fileViewer.style.display = 'none';
        }

        const terminalContent = document.getElementById('terminal-content');
        if (terminalContent) {
            terminalContent.innerHTML = '';
        }
    });
    
    stopButton.addEventListener('click', async function() {
        if (currentSessionId) {
            try {
                const response = await fetch(`/api/chat/${currentSessionId}/stop`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    addLog('处理已停止', 'warning');
                }
            } catch (error) {
                console.error('停止请求错误:', error);
            }
            
            if (currentWebSocket) {
                currentWebSocket.close();
                currentWebSocket = null;
            }
            
            statusIndicator.textContent = '请求已停止';
            statusIndicator.className = 'status-indicator warning';
            sendButton.disabled = false;
            stopButton.disabled = true;
            processingRequest = false;
        }
    });
    
    async function sendMessage() {
        const prompt = userInput.value.trim();
        
        if (!prompt || processingRequest) return;
        
        processingRequest = true;
        addMessage(prompt, 'user');
        userInput.value = '';
        sendButton.disabled = true;
        stopButton.disabled = false;
        statusIndicator.textContent = '正在处理您的请求...';
        statusIndicator.className = 'status-indicator processing';
        
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
            currentSessionId = data.session_id;
            connectWebSocket(currentSessionId);
            pollResults(currentSessionId);
            
        } catch (error) {
            console.error('Error:', error);
            statusIndicator.textContent = '发生错误: ' + error.message;
            statusIndicator.className = 'status-indicator error';
            sendButton.disabled = false;
            stopButton.disabled = true;
            processingRequest = false;
        }
    }
    
    fetchGeneratedFiles();
    initializeTerminal();
});
