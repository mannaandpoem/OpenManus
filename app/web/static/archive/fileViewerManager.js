export async function fetchGeneratedFiles() {
    try {
        const response = await fetch('/api/files');
        if (!response.ok) {
            throw new Error('获取文件列表失败');
        }
        
        const data = await response.json();
        
        if (data.workspaces) {
            updateWorkspaceList(data.workspaces);
        } else if (data.files) {
            updateFilesList(data.files);
        }
    } catch (error) {
        console.error('获取文件列表错误:', error);
    }
}

function updateWorkspaceList(workspaces) {
    const filesList = document.getElementById('files-list');
    if (!filesList) return;
    
    filesList.innerHTML = '';
    
    if (!workspaces || workspaces.length === 0) {
        filesList.innerHTML = '<div class="no-files">暂无工作区文件</div>';
        return;
    }
    
    const workspaceList = document.createElement('div');
    workspaceList.className = 'workspace-list';
    
    workspaces.forEach(workspace => {
        const workspaceItem = document.createElement('div');
        workspaceItem.className = 'workspace-item';
        
        const workspaceHeader = document.createElement('div');
        workspaceHeader.className = 'workspace-header';
        
        const timestamp = new Date(workspace.modified * 1000);
        const formattedDate = timestamp.toLocaleDateString() + ' ' + timestamp.toLocaleTimeString();
        
        workspaceHeader.innerHTML = `
            <div>${workspace.name}</div>
            <div class="workspace-date">${formattedDate}</div>
        `;
        
        const workspaceContent = document.createElement('div');
        workspaceContent.className = 'workspace-content';
        
        if (workspace.files && workspace.files.length > 0) {
            workspace.files.forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                
                let fileIcon = '📄';
                if (file.type === 'md') fileIcon = '📝';
                else if (file.type === 'html') fileIcon = '🌐';
                else if (file.type === 'css') fileIcon = '🎨';
                else if (file.type === 'js') fileIcon = '⚙️';
                else if (file.type === 'py') fileIcon = '🐍';
                else if (file.type === 'json') fileIcon = '📋';
                
                const modifiedDate = new Date(file.modified * 1000).toLocaleString();
                
                fileItem.innerHTML = `
                    <div class="file-icon">${fileIcon}</div>
                    <div class="file-details">
                        <div class="file-name">${file.name}</div>
                        <div class="file-meta">${getReadableFileSize(file.size)} · ${modifiedDate}</div>
                    </div>
                `;
                
                fileItem.addEventListener('click', () => viewFile(file.path));
                
                workspaceContent.appendChild(fileItem);
            });
        } else {
            workspaceContent.innerHTML = '<div class="no-files">工作区内无文件</div>';
        }
        
        workspaceHeader.addEventListener('click', () => {
            workspaceContent.classList.toggle('expanded');
        });
        
        workspaceItem.appendChild(workspaceHeader);
        workspaceItem.appendChild(workspaceContent);
        workspaceList.appendChild(workspaceItem);
    });
    
    filesList.appendChild(workspaceList);
    
    const firstWorkspace = workspaceList.querySelector('.workspace-content');
    if (firstWorkspace) {
        firstWorkspace.classList.add('expanded');
    }
}

function updateFilesList(files) {
    const filesList = document.getElementById('files-list');
    if (!filesList) return;
    
    filesList.innerHTML = '';
    
    if (!files || files.length === 0) {
        filesList.innerHTML = '<div class="no-files">暂无生成的文件</div>';
        return;
    }
    
    files.forEach(file => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        
        let fileIcon = '📄';
        if (file.type === 'md') fileIcon = '📝';
        else if (file.type === 'html') fileIcon = '🌐';
        else if (file.type === 'css') fileIcon = '🎨';
        else if (file.type === 'js') fileIcon = '⚙️';
        
        const modifiedDate = new Date(file.modified * 1000).toLocaleString();
        
        fileItem.innerHTML = `
            <div class="file-icon">${fileIcon}</div>
            <div class="file-details">
                <div class="file-name">${file.name}</div>
                <div class="file-meta">${getReadableFileSize(file.size)} · ${modifiedDate}</div>
            </div>
        `;
        
        fileItem.addEventListener('click', () => viewFile(file.path));
        
        filesList.appendChild(fileItem);
    });
}

async function viewFile(filePath) {
    try {
        const response = await fetch(`/api/files/${filePath}`);
        if (!response.ok) {
            throw new Error('获取文件内容失败');
        }
        
        const data = await response.json();
        
        const fileViewer = document.getElementById('file-viewer');
        const fileViewerTitle = document.getElementById('file-viewer-title');
        const fileContent = document.getElementById('file-content');
        
        if (fileViewer && fileViewerTitle && fileContent) {
            fileViewerTitle.textContent = data.name;
            fileContent.textContent = data.content;
            fileViewer.style.display = 'block';
            
            fileContent.className = 'file-content';
            if (['js', 'html', 'css'].includes(data.type)) {
                fileContent.classList.add(`language-${data.type}`);
            }
        }
    } catch (error) {
        console.error('获取文件内容错误:', error);
        alert('获取文件内容失败: ' + error.message);
    }
}

function getReadableFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + sizes[i];
}
