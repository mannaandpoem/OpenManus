export function addMessage(content, sender) {
    const chatMessages = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    const headerDiv = document.createElement('div');
    headerDiv.className = 'message-header';
    headerDiv.textContent = sender === 'user' ? '您' : 'OpenManus';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // 检测和格式化代码块
    if (sender === 'ai') {
        content = formatCodeBlocks(content);
        contentDiv.innerHTML = content;
    } else {
        contentDiv.textContent = content;
    }
    
    messageDiv.appendChild(headerDiv);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // 滚动到底部
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

export function clearChat() {
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = '';
}

function formatCodeBlocks(text) {
    let formattedText = text;
    formattedText = formattedText.replace(/```([a-zA-Z]*)\n([\s\S]*?)\n```/g, 
        '<pre><code class="language-$1">$2</code></pre>');
    formattedText = formattedText.replace(/\n/g, '<br>');
    return formattedText;
}
