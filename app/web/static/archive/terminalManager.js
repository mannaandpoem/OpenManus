export function initializeTerminal() {
    const terminalOutput = document.getElementById('terminal-output');
    const terminalContent = document.getElementById('terminal-content');
    const toggleTerminal = document.getElementById('toggle-terminal');
    const clearTerminal = document.getElementById('clear-terminal');
    
    if (terminalContent) {
        terminalContent.style.display = 'none';
    }
    
    if (toggleTerminal) {
        toggleTerminal.addEventListener('click', function() {
            if (terminalContent.style.display === 'none') {
                terminalContent.style.display = 'block';
                toggleTerminal.textContent = '折叠';
            } else {
                terminalContent.style.display = 'none';
                toggleTerminal.textContent = '展开';
            }
        });
    }
    
    if (clearTerminal) {
        clearTerminal.addEventListener('click', function() {
            if (terminalContent) {
                terminalContent.innerHTML = '';
            }
        });
    }
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
