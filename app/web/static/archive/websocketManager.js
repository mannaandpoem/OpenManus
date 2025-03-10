import { addMessage } from './chatManager.js';
import { updateSystemLogs, addSystemLogsToChat } from './logManager.js';
import { updateThinkingSteps, updateTerminalOutput } from './apiManager.js';

let currentWebSocket = null;

export function connectWebSocket(sessionId) {
    try {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const wsUrl = `${wsProtocol}://${window.location.host}/ws/${sessionId}`;
        const ws = new WebSocket(wsUrl);
        currentWebSocket = ws;
        
        window.lastSystemLogMessage = null;
        window.lastSystemLogTimestamp = 0;
        
        ws.onopen = function() {
            console.log('WebSocket连接已建立');
            document.getElementById('status-indicator').textContent = '已连接到服务器...';
        };
        
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            if (data.chat_logs && data.chat_logs.length > 0) {
                addSystemLogsToChat(data.chat_logs);
            } else if (data.system_logs && data.system_logs.length > 0) {
                updateSystemLogs(data.system_logs);
                addSystemLogsToChat(data.system_logs);
            }
            
            if (data.thinking_steps && data.thinking_steps.length > 0) {
                updateThinkingSteps(data.thinking_steps);
            }
            
            if (data.terminal_output && data.terminal_output.length > 0) {
                updateTerminalOutput(data.terminal_output);
            }
            
            if (data.status && data.status !== 'processing') {
                document.getElementById('status-indicator').textContent = data.status === 'completed' ? '' : `状态: ${data.status}`;
                document.getElementById('send-btn').disabled = false;
                document.getElementById('stop-btn').disabled = true;
            }
            
            if (data.result && !chatContainsResult(data.result)) {
                addMessage(data.result, 'ai');
            }
        };
        
        ws.onerror = function(error) {
            console.error('WebSocket错误:', error);
            document.getElementById('status-indicator').textContent = '使用轮询模式获取结果...';
        };
        
        ws.onclose = function() {
            console.log('WebSocket连接已关闭');
            currentWebSocket = null;
        };
        
        return ws;
    } catch (error) {
        console.error('创建WebSocket连接失败:', error);
        throw error;
    }
}

function chatContainsResult(result) {
    const chatMessages = document.getElementById('chat-messages');
    return Array.from(chatMessages.querySelectorAll('.ai-message .message-content'))
        .some(el => el.textContent.includes(result));
}
