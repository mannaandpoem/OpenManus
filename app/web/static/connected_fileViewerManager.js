// connected_fileViewerManager.js - 处理文件内容查看

export class FileViewerManager {
    constructor() {
        this.fileViewer = document.getElementById('file-viewer');
        this.fileName = document.getElementById('file-name');
        this.fileContent = document.getElementById('file-content');
        this.closeButton = document.getElementById('close-file-viewer');
    }
    
    // 初始化文件查看器
    init() {
        // 初始隐藏文件查看器
        this.hideFileViewer();
        
        // 绑定关闭按钮事件
        this.closeButton.addEventListener('click', () => {
            this.hideFileViewer();
        });
    }
    
    // 显示文件内容
    showFile(name, content) {
        // 设置文件名
        this.fileName.textContent = name;
        
        // 设置文件内容，根据文件类型进行格式化
        const formattedContent = this.formatCode(content, this.getFileType(name));
        this.fileContent.textContent = formattedContent;
        
        // 根据文件类型设置语法高亮
        this.applySyntaxHighlighting(name);
        
        // 显示文件查看器
        this.fileViewer.style.display = 'block';
    }
    
    // 隐藏文件查看器
    hideFileViewer() {
        this.fileViewer.style.display = 'none';
    }
    
    // 获取文件类型
    getFileType(fileName) {
        const extension = fileName.split('.').pop().toLowerCase();
        return extension;
    }
    
    // 应用语法高亮
    applySyntaxHighlighting(fileName) {
        // 获取文件扩展名
        const extension = this.getFileType(fileName);
        
        // 根据文件类型设置类名
        this.fileContent.className = 'file-content';
        
        // 添加语言特定的类名
        switch (extension) {
            case 'html':
                this.fileContent.classList.add('language-html');
                break;
            case 'css':
                this.fileContent.classList.add('language-css');
                break;
            case 'js':
                this.fileContent.classList.add('language-javascript');
                break;
            case 'py':
                this.fileContent.classList.add('language-python');
                break;
            case 'json':
                this.fileContent.classList.add('language-json');
                break;
            case 'md':
                this.fileContent.classList.add('language-markdown');
                break;
            default:
                this.fileContent.classList.add('language-plaintext');
                break;
        }
        
        // 如果有Prism.js，触发语法高亮
        if (window.Prism) {
            window.Prism.highlightElement(this.fileContent);
        }
    }
    
    // 格式化代码
    formatCode(code, language) {
        // 简单的代码格式化，可以根据需要扩展
        if (!code) return '';
        
        // 对HTML进行简单的格式化
        if (language === 'html') {
            return this.formatHTML(code);
        }
        
        // 对JSON进行格式化
        if (language === 'json') {
            try {
                const obj = JSON.parse(code);
                return JSON.stringify(obj, null, 2);
            } catch (e) {
                return code;
            }
        }
        
        return code;
    }
    
    // 格式化HTML
    formatHTML(html) {
        // 简单的HTML格式化
        let formatted = '';
        let indent = 0;
        
        // 将HTML标签分割成数组
        const tags = html.split(/(<\/?[^>]+>)/g);
        
        for (let i = 0; i < tags.length; i++) {
            const tag = tags[i];
            
            // 如果是关闭标签，减少缩进
            if (tag.match(/^<\//)) {
                indent--;
            }
            
            // 添加适当的缩进
            if (tag.match(/^</) && !tag.match(/^<\//) && !tag.match(/\/>/)) {
                formatted += '  '.repeat(indent) + tag + '\n';
                indent++;
            } else if (tag.match(/^</) && tag.match(/\/>/)) {
                // 自闭合标签
                formatted += '  '.repeat(indent) + tag + '\n';
            } else if (tag.match(/^<\//)) {
                // 关闭标签
                formatted += '  '.repeat(indent) + tag + '\n';
            } else if (tag.trim() !== '') {
                // 文本内容
                formatted += '  '.repeat(indent) + tag + '\n';
            }
        }
        
        return formatted;
    }
}
